"""法规标准台账业务规则。

规则要点：
- 条款状态只能按「征求意见 → 已生效 → 已废止」顺向流转，不能跳级或回退；
- 同一法规编号、版本、适用设备类别只认第一次登记；
- 设备按当前日期匹配已生效且已到生效日的条款，同一编号多版命中时取生效日期较晚者；
- 每次重算只覆盖设备当前适用字段，历史匹配以快照形式追加，不覆盖旧记录。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.store import store

MODULE = "regulation"
HISTORY_MODULE = "regulation_match_history"
REGISTER_MODULE = "register"

DRAFT = "征求意见"
EFFECTIVE = "已生效"
REPEALED = "已废止"
STATUS_ORDER = [DRAFT, EFFECTIVE, REPEALED]
ACTION_TARGETS = {"启用条款": EFFECTIVE, "废止条款": REPEALED}
ACTION_PERMISSIONS = {
    "启用条款": ("regulation:activate", "启用条款"),
    "废止条款": ("regulation:repeal", "废止条款"),
}

REQUIRED_FIELDS = [
    "regulation_code",
    "regulation_name",
    "version",
    "device_category",
    "effective_date",
]
DISPLAY_FIELDS = ["当前适用法规", "冲突条款", "最近重算时间"]


class RegulationError(ValueError):
    """业务校验未通过。"""

    status_code = 400


class RegulationConflictError(RegulationError):
    """重复登记等与现有数据冲突。"""

    status_code = 409


class RegulationService:
    def __init__(self) -> None:
        self._initialized = False

    def ensure_initialized(self) -> None:
        """首次使用时把既有设备台账按当前条款做一次存量回填。"""
        if self._initialized:
            return
        if not store.rows(HISTORY_MODULE):
            for device in store.rows(REGISTER_MODULE):
                if device.get("_regulation_bootstrapped"):
                    continue
                self.recalculate_device(
                    device,
                    reason="存量初始回填",
                    operator="system",
                    remark="服务启动后按当前已生效条款回填",
                )
                device["_regulation_bootstrapped"] = True
        self._initialized = True

    def list_regulations(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        device_category: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        self.ensure_initialized()
        rows = store.rows(MODULE)
        if keyword:
            needle = keyword.strip().lower()
            rows = [
                row
                for row in rows
                if needle
                in " ".join(
                    str(row.get(key, ""))
                    for key in [
                        "regulation_code",
                        "regulation_name",
                        "version",
                        "announcement_no",
                    ]
                ).lower()
            ]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if device_category:
            rows = [row for row in rows if row.get("device_category") == device_category]

        ordered = sorted(
            rows,
            key=lambda row: (
                str(row.get("device_category", "")),
                str(row.get("regulation_code", "")),
                str(row.get("effective_date", "")),
                int(row.get("id", 0)),
            ),
        )
        total = len(ordered)
        start = max(page - 1, 0) * size
        return ordered[start:start + size], total

    def create_regulation(self, payload: dict[str, Any]) -> dict[str, Any]:
        values = {field: str(payload.get(field) or "").strip() for field in REQUIRED_FIELDS}
        missing = [self._field_label(field) for field in REQUIRED_FIELDS if not values[field]]
        if missing:
            raise RegulationError(f"缺少必填字段：{'、'.join(missing)}")
        self._parse_date(values["effective_date"], "生效日期")
        if payload.get("publish_date"):
            self._parse_date(str(payload["publish_date"]), "发布日期")

        rows = store.rows(MODULE)
        duplicate = self._find_duplicate(
            values["regulation_code"],
            values["version"],
            values["device_category"],
        )
        if duplicate is not None:
            raise RegulationConflictError(
                "同一法规编号、条款版本与适用设备类别已登记，只认第一次登记："
                f"{duplicate['regulation_code']} {duplicate['version']} / {duplicate['device_category']}"
            )

        entry = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
            **values,
            "publish_date": str(payload.get("publish_date") or "").strip(),
            "announcement_no": str(payload.get("announcement_no") or "").strip(),
            "status": DRAFT,
            "remark": str(payload.get("remark") or "").strip(),
            "created_at": self._now(),
        }
        rows.append(entry)
        # 征求意见稿不参与设备当前适用，不触发设备清单重算。
        return entry

    def run_action(
        self,
        regulation_id: int,
        action: str,
        *,
        operator: str = "unknown",
        remark: str | None = None,
    ) -> dict[str, Any]:
        self.ensure_initialized()
        entry = store.find(MODULE, regulation_id)
        if entry is None:
            raise RegulationError(f"法规条款 {regulation_id} 不存在")
        if action not in ACTION_TARGETS:
            raise RegulationError(f"动作「{action}」不属于法规条款可执行范围")

        target = ACTION_TARGETS[action]
        current = str(entry.get("status"))
        current_index = STATUS_ORDER.index(current) if current in STATUS_ORDER else -1
        target_index = STATUS_ORDER.index(target)
        if target_index != current_index + 1:
            allowed = STATUS_ORDER[current_index + 1] if 0 <= current_index < len(STATUS_ORDER) - 1 else "无"
            raise RegulationError(
                f"条款版本不能从「{current}」{action}为「{target}」；"
                f"状态只能按征求意见 → 已生效 → 已废止顺序流转，下一步仅允许：{allowed}"
            )

        entry["status"] = target
        entry["changed_at"] = self._now()
        entry["changed_by"] = operator
        if remark:
            entry["last_remark"] = remark

        reason = "启用条款后重算" if target == EFFECTIVE else "废止条款后重算"
        self.recalculate_all(reason=reason, operator=operator, remark=remark)
        return entry

    def categories(self) -> list[str]:
        self.ensure_initialized()
        categories = {str(row.get("device_category", "")).strip() for row in store.rows(MODULE)}
        categories.update(str(row.get("设备种类", "")).strip() for row in store.rows(REGISTER_MODULE))
        categories.discard("")
        return sorted(categories)

    def list_device_matches(
        self,
        *,
        device_keyword: str | None = None,
        device_category: str | None = None,
        conflict_only: bool = False,
        as_of: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        self.ensure_initialized()
        as_of_date = self._parse_date(as_of, "判定日期") if as_of else date.today()
        devices = store.rows(REGISTER_MODULE)
        if device_keyword:
            needle = device_keyword.strip().lower()
            devices = [
                row
                for row in devices
                if needle
                in " ".join(str(row.get(key, "")) for key in ["设备编号", "设备名称", "使用单位"]).lower()
            ]
        if device_category:
            devices = [row for row in devices if row.get("设备种类") == device_category]

        items = [self._build_device_match(row, as_of_date=as_of_date) for row in devices]
        if conflict_only:
            items = [item for item in items if item["has_conflict"]]
        total = len(items)
        start = max(page - 1, 0) * size
        return items[start:start + size], total

    def recalculate_all(
        self,
        *,
        reason: str,
        operator: str,
        remark: str | None = None,
        as_of: date | None = None,
    ) -> int:
        count = 0
        for device in store.rows(REGISTER_MODULE):
            self.recalculate_device(device, reason=reason, operator=operator, remark=remark, as_of=as_of)
            device["_regulation_bootstrapped"] = True
            count += 1
        return count

    def recalculate_device(
        self,
        device: dict[str, Any],
        *,
        reason: str,
        operator: str,
        remark: str | None = None,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        as_of_date = as_of or date.today()
        result = self._build_device_match(device, as_of_date=as_of_date)
        applied_text = "；".join(item["applied_text"] for item in result["matches"]) or "无适用法规"
        conflict_text = "；".join(result["conflicts"]) or "无"

        device["当前适用法规"] = applied_text
        device["冲突条款"] = conflict_text
        device["最近重算时间"] = self._now()
        device["_matches"] = result["matches"]
        device["_conflicts"] = result["conflicts"]
        device["_recalculated_at"] = device["最近重算时间"]

        history_rows = store.rows(HISTORY_MODULE)
        history_rows.append(
            {
                "id": max((int(row.get("id", 0)) for row in history_rows), default=0) + 1,
                "device_id": device.get("id"),
                "device_code": device.get("设备编号", ""),
                "device_name": device.get("设备名称", ""),
                "device_category": device.get("设备种类", ""),
                "as_of_date": as_of_date.isoformat(),
                "event_reason": reason,
                "operator": operator,
                "remark": remark or "",
                "calculated_at": device["最近重算时间"],
                "matches": result["matches"],
                "applied_count": len(result["matches"]),
                "has_conflict": result["has_conflict"],
                "conflict_summary": conflict_text,
            }
        )
        return result

    def list_history(
        self,
        *,
        device_id: int | None = None,
        device_keyword: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        self.ensure_initialized()
        rows = list(reversed(store.rows(HISTORY_MODULE)))
        if device_id is not None:
            rows = [row for row in rows if row.get("device_id") == device_id]
        if device_keyword:
            needle = device_keyword.strip().lower()
            rows = [
                row
                for row in rows
                if needle
                in " ".join(str(row.get(key, "")) for key in ["device_code", "device_name"]).lower()
            ]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def _build_device_match(self, device: dict[str, Any], *, as_of_date: date) -> dict[str, Any]:
        category = str(device.get("设备种类", "")).strip()
        candidates = [
            row
            for row in store.rows(MODULE)
            if row.get("device_category") == category
            and row.get("status") == EFFECTIVE
            and self._parse_date(str(row.get("effective_date")), "生效日期") <= as_of_date
        ]

        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in candidates:
            grouped.setdefault(str(row.get("regulation_code")), []).append(row)

        matches: list[dict[str, Any]] = []
        conflicts: list[str] = []
        for code, group in grouped.items():
            ordered = sorted(
                group,
                key=lambda item: (str(item.get("effective_date")), int(item.get("id", 0))),
            )
            winner = ordered[-1]
            losers = ordered[:-1]
            conflict_versions = [
                {
                    "regulation_id": loser.get("id"),
                    "version": loser.get("version"),
                    "effective_date": loser.get("effective_date"),
                }
                for loser in losers
            ]
            match = {
                "regulation_id": winner.get("id"),
                "regulation_code": winner.get("regulation_code"),
                "regulation_name": winner.get("regulation_name"),
                "version": winner.get("version"),
                "device_category": winner.get("device_category"),
                "effective_date": winner.get("effective_date"),
                "announcement_no": winner.get("announcement_no"),
                "applied_rule": "同一法规多版命中，采用生效日期较晚版本",
                "conflicts": conflict_versions,
                "applied_text": (
                    f"{winner.get('regulation_code')}《{winner.get('regulation_name')}》"
                    f"{winner.get('version')}（{winner.get('effective_date')}生效）"
                ),
            }
            matches.append(match)
            if losers:
                older = "、".join(
                    f"{loser.get('version')}({loser.get('effective_date')})" for loser in losers
                )
                conflicts.append(
                    f"{code}：{older} 与 {winner.get('version')}({winner.get('effective_date')}) "
                    f"同时命中，采用生效较晚的 {winner.get('version')}"
                )

        matches.sort(key=lambda item: str(item.get("regulation_code")))
        return {
            "device_id": device.get("id"),
            "设备编号": device.get("设备编号", ""),
            "设备名称": device.get("设备名称", ""),
            "设备种类": category,
            "使用单位": device.get("使用单位", ""),
            "matches": matches,
            "applied_count": len(matches),
            "has_conflict": bool(conflicts),
            "conflicts": conflicts,
            "applied_text": "；".join(item["applied_text"] for item in matches) or "无适用法规",
            "conflict_text": "；".join(conflicts) or "无",
            "as_of_date": as_of_date.isoformat(),
            "最近重算时间": device.get("最近重算时间", ""),
        }

    def _find_duplicate(
        self,
        regulation_code: str,
        version: str,
        device_category: str,
    ) -> dict[str, Any] | None:
        code = self._normalize(regulation_code)
        ver = self._normalize(version)
        category = self._normalize(device_category)
        for row in store.rows(MODULE):
            if (
                self._normalize(str(row.get("regulation_code", ""))) == code
                and self._normalize(str(row.get("version", ""))) == ver
                and self._normalize(str(row.get("device_category", ""))) == category
            ):
                return row
        return None

    @staticmethod
    def _normalize(value: str) -> str:
        return "".join(value.strip().lower().split())

    @staticmethod
    def _parse_date(value: str, label: str) -> date:
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise RegulationError(f"{label}必须是 YYYY-MM-DD 格式，收到：{value}") from exc

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    @staticmethod
    def _field_label(field: str) -> str:
        return {
            "regulation_code": "法规编号",
            "regulation_name": "法规名称",
            "version": "条款版本",
            "device_category": "适用设备类别",
            "effective_date": "生效日期",
        }.get(field, field)


regulation_service = RegulationService()
