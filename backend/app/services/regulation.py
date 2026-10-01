"""法规标准台账业务规则。

领域规则全部收在本模块，路由层不做业务判断：

- 条款版本状态只能沿 ``征求意见 → 已生效 → 已废止`` 逐级流转，任何跳级当场驳回；
- 同一份法规（按文号去重）、同一文号下的同一版本重复登记，只认第一次；
- 设备台账按设备类别匹配当前适用条款；一台设备同时命中同一法规的两版条款时，
  生效日期较晚的一版说了算，冲突结果里保留“哪两版在打架”；
- 条款口径调整（启用新版 / 废止旧版）后，全部已登记设备按新版重算适用清单，
  存量匹配记录就地回填，历史匹配按当时生效的那一版保留（只追加、不改写）；
- 只有该法规的归口管理员、且持有对应权限（``法规条款:启用`` / ``法规条款:废止``）
  才能启用或废止条款，越权操作当场驳回，并在回执里点名缺的是哪项权限。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

EQUIPMENT_CATEGORIES = [
    "锅炉",
    "压力容器",
    "压力管道",
    "电梯",
    "起重机械",
    "场（厂）内专用机动车辆",
]

STATUS_DRAFT = "征求意见"
STATUS_EFFECTIVE = "已生效"
STATUS_REPEALED = "已废止"
STATUS_FLOW = [STATUS_DRAFT, STATUS_EFFECTIVE, STATUS_REPEALED]

# 允许的逐级流转表：目标状态 -> 所需权限 / 动作名。
NEXT_STATUS = {
    STATUS_DRAFT: (STATUS_EFFECTIVE, "法规条款:启用", "启用"),
    STATUS_EFFECTIVE: (STATUS_REPEALED, "法规条款:废止", "废止"),
}

PERM_PUBLISH = "法规条款:启用"
PERM_REPEAL = "法规条款:废止"
ALL_PERMISSIONS = [PERM_PUBLISH, PERM_REPEAL]


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class RegulationError(Exception):
    """法规台账业务异常基类。"""


class LedgerValidationError(RegulationError):
    """登记内容不合法（缺字段、类别不在目录、日期格式错误等）。"""


class NotFound(RegulationError):
    """法规、版本或设备不存在。"""


class IllegalTransition(RegulationError):
    """条款版本试图跳过状态序列（如征求意见直接废止）。"""


class PermissionDenied(RegulationError):
    """非归口管理员或缺权限，操作被当场驳回。"""


def _parse_date(value: Any, field_name: str = "日期") -> Optional[date]:
    """把 'YYYY-MM-DD' 解析成 date；空值放行，非法格式说明清楚。"""
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise LedgerValidationError(f"{field_name}应为 YYYY-MM-DD 格式，收到的是「{value}」") from exc


def _iso(value: Optional[date]) -> Optional[str]:
    return value.isoformat() if value else None


# ---------------------------------------------------------------------------
# 领域对象
# ---------------------------------------------------------------------------


@dataclass
class Operator:
    """操作账号：归属部门 + 持有权限。归口与权限两项都要过。"""

    name: str
    dept: str
    permissions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "dept": self.dept, "permissions": list(self.permissions)}


@dataclass
class ClauseVersion:
    """同一法规下的一版条款（口径）。"""

    id: int
    regulation_id: int
    version: str
    title: str
    applicable_categories: list[str]
    registered_at: date
    status: str = STATUS_DRAFT
    effective_date: Optional[date] = None
    repeal_date: Optional[date] = None
    published_at: Optional[date] = None
    repealed_at: Optional[date] = None

    def is_active_on(self, day: date) -> bool:
        """该版本在指定日期是否处于生效区间 [生效日, 废止日)。征求意见稿永不生效。"""
        if self.status == STATUS_DRAFT:
            return False
        if self.effective_date is None or self.effective_date > day:
            return False
        if self.repeal_date is not None and day >= self.repeal_date:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "regulation_id": self.regulation_id,
            "version": self.version,
            "title": self.title,
            "applicable_categories": list(self.applicable_categories),
            "status": self.status,
            "effective_date": _iso(self.effective_date),
            "repeal_date": _iso(self.repeal_date),
            "registered_at": _iso(self.registered_at),
            "published_at": _iso(self.published_at),
            "repealed_at": _iso(self.repealed_at),
        }


@dataclass
class Regulation:
    """法规标准（按文号唯一）。"""

    id: int
    code: str
    name: str
    owner_dept: str
    registered_at: date
    versions: list[ClauseVersion] = field(default_factory=list)

    def to_dict(self, *, with_versions: bool = True) -> dict[str, Any]:
        data = {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "owner_dept": self.owner_dept,
            "registered_at": _iso(self.registered_at),
            "version_count": len(self.versions),
        }
        if with_versions:
            data["versions"] = [version.to_dict() for version in self.versions]
        return data


@dataclass
class Equipment:
    """纳入法规适用范围的设备台账记录。"""

    id: int
    code: str
    name: str
    category: str
    registered_at: date

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "category": self.category,
            "registered_at": _iso(self.registered_at),
        }


# ---------------------------------------------------------------------------
# 台账
# ---------------------------------------------------------------------------


class RegulationLedger:
    """法规标准台账：登记、流转、匹配、重算、历史留痕。

    内存实现，只依赖标准库；方法即业务用例，路由层薄薄包一层即可。
    """

    def __init__(self) -> None:
        self._regulations: dict[int, Regulation] = {}
        self._equipment: dict[int, Equipment] = {}
        self._code_index: dict[str, int] = {}
        self._equipment_code_index: dict[str, int] = {}
        self._operators: dict[str, Operator] = {}
        self._matches: dict[int, dict[str, Any]] = {}
        self._events: list[dict[str, Any]] = []
        self._seq_regulation = 0
        self._seq_version = 0
        self._seq_equipment = 0
        self._seq_event = 0

    # ----- 账号 -----------------------------------------------------------

    def register_operator(self, name: str, dept: str, permissions: list[str]) -> Operator:
        operator = Operator(name=name.strip(), dept=dept.strip(), permissions=list(permissions))
        self._operators[operator.name] = operator
        return operator

    def list_operators(self) -> list[dict[str, Any]]:
        return [op.to_dict() for op in self._operators.values()]

    # ----- 法规与条款登记 --------------------------------------------------

    def register_regulation(
        self, code: str, name: str, owner_dept: str, *, today: Optional[date] = None
    ) -> tuple[Regulation, bool]:
        """登记法规。同文号重复登记只认第一次，返回 (法规, 是否重复登记)。"""
        code = (code or "").strip()
        name = (name or "").strip()
        owner_dept = (owner_dept or "").strip()
        missing = [
            label
            for label, value in (("文号", code), ("法规名称", name), ("归口部门", owner_dept))
            if not value
        ]
        if missing:
            raise LedgerValidationError(f"缺少必填字段：{'、'.join(missing)}")

        existing_id = self._code_index.get(code)
        if existing_id is not None:
            # 同一份法规重复登记：原样退回第一次登记，不新增、不改写。
            return self._regulations[existing_id], True

        self._seq_regulation += 1
        regulation = Regulation(
            id=self._seq_regulation,
            code=code,
            name=name,
            owner_dept=owner_dept,
            registered_at=today or date.today(),
        )
        self._regulations[regulation.id] = regulation
        self._code_index[code] = regulation.id
        return regulation, False

    def add_version(
        self,
        regulation_id: int,
        version: str,
        title: str,
        categories: list[str],
        effective_date: Any = None,
        *,
        today: Optional[date] = None,
    ) -> tuple[ClauseVersion, bool]:
        """为法规登记一版条款，初始一律为“征求意见”，不允许带状态登记。"""
        regulation = self._get_regulation(regulation_id)
        version = (version or "").strip()
        if not version:
            raise LedgerValidationError("缺少必填字段：条款版本")
        categories = [str(item).strip() for item in (categories or []) if str(item).strip()]
        if not categories:
            raise LedgerValidationError("至少登记一个适用设备类别")
        unknown = [item for item in categories if item not in EQUIPMENT_CATEGORIES]
        if unknown:
            raise LedgerValidationError(
                f"适用设备类别不在目录内：{'、'.join(unknown)}；可选：{'、'.join(EQUIPMENT_CATEGORIES)}"
            )
        eff = _parse_date(effective_date, "拟生效日期")

        for existing in regulation.versions:
            if existing.version == version:
                # 同一版本重复登记同样只认第一次。
                return existing, True

        self._seq_version += 1
        clause = ClauseVersion(
            id=self._seq_version,
            regulation_id=regulation.id,
            version=version,
            title=(title or "").strip(),
            applicable_categories=categories,
            registered_at=today or date.today(),
            effective_date=eff,
        )
        regulation.versions.append(clause)
        return clause, False

    # ----- 状态流转（含权限） ----------------------------------------------

    def publish_version(
        self,
        version_id: int,
        operator_name: str,
        effective_date: Any = None,
        *,
        today: Optional[date] = None,
    ) -> tuple[ClauseVersion, dict[str, Any]]:
        """征求意见 → 已生效。启用后全量重算设备适用清单。"""
        clause, regulation = self._resolve_version(version_id)
        self._authorize(regulation, operator_name, PERM_PUBLISH, "启用")
        self._assert_flow(clause, STATUS_EFFECTIVE, "启用")

        day = today or date.today()
        eff = _parse_date(effective_date, "生效日期") or clause.effective_date or day
        clause.status = STATUS_EFFECTIVE
        clause.effective_date = eff
        clause.published_at = day

        event = self._recompute_all(
            reason="条款启用", actor=operator_name, regulation=regulation, clause=clause, day=day
        )
        return clause, event

    def repeal_version(
        self,
        version_id: int,
        operator_name: str,
        repeal_date: Any = None,
        *,
        today: Optional[date] = None,
    ) -> tuple[ClauseVersion, dict[str, Any]]:
        """已生效 → 已废止。废止后全量重算设备适用清单。"""
        clause, regulation = self._resolve_version(version_id)
        self._authorize(regulation, operator_name, PERM_REPEAL, "废止")
        self._assert_flow(clause, STATUS_REPEALED, "废止")

        day = today or date.today()
        rep = _parse_date(repeal_date, "废止日期") or day
        if clause.effective_date is not None and rep < clause.effective_date:
            raise LedgerValidationError(
                f"废止日期（{_iso(rep)}）不能早于该版生效日期（{_iso(clause.effective_date)}）"
            )
        clause.status = STATUS_REPEALED
        clause.repeal_date = rep
        clause.repealed_at = day

        event = self._recompute_all(
            reason="条款废止", actor=operator_name, regulation=regulation, clause=clause, day=day
        )
        return clause, event

    def _assert_flow(self, clause: ClauseVersion, target: str, action: str) -> None:
        allowed = NEXT_STATUS.get(clause.status)
        if allowed is None or allowed[0] != target:
            raise IllegalTransition(
                f"条款状态只能按 {STATUS_FLOW[0]}→{STATUS_FLOW[1]}→{STATUS_FLOW[2]} 逐级流转，"
                f"「{clause.version}」当前为「{clause.status}」，不能{action}到「{target}」，"
                f"属于跳级，已驳回"
            )

    def _authorize(self, regulation: Regulation, operator_name: str, permission: str, action: str) -> None:
        operator = self._operators.get((operator_name or "").strip())
        if operator is None:
            raise PermissionDenied(
                f"当场驳回：未知操作账号「{operator_name}」，无法核验归口与权限"
            )
        problems: list[str] = []
        if operator.dept != regulation.owner_dept:
            problems.append(
                f"账号归属「{operator.dept}」，而该法规归口部门为「{regulation.owner_dept}」，非归口管理员"
            )
        if permission not in operator.permissions:
            problems.append(f"缺少权限「{permission}」")
        if problems:
            raise PermissionDenied(
                f"当场驳回：{action}条款「{regulation.code}」需由归口管理员持权限「{permission}」；"
                + "；".join(problems)
            )

    # ----- 设备登记 --------------------------------------------------------

    def register_equipment(
        self, code: str, name: str, category: str, *, today: Optional[date] = None
    ) -> tuple[Equipment, bool]:
        code = (code or "").strip()
        name = (name or "").strip()
        category = (category or "").strip()
        missing = [
            label
            for label, value in (("设备编号", code), ("设备名称", name), ("设备类别", category))
            if not value
        ]
        if missing:
            raise LedgerValidationError(f"缺少必填字段：{'、'.join(missing)}")
        if category not in EQUIPMENT_CATEGORIES:
            raise LedgerValidationError(
                f"设备类别「{category}」不在目录内；可选：{'、'.join(EQUIPMENT_CATEGORIES)}"
            )

        existing_id = self._equipment_code_index.get(code)
        if existing_id is not None:
            return self._equipment[existing_id], True

        self._seq_equipment += 1
        equipment = Equipment(
            id=self._seq_equipment,
            code=code,
            name=name,
            category=category,
            registered_at=today or date.today(),
        )
        self._equipment[equipment.id] = equipment
        self._equipment_code_index[code] = equipment.id

        # 新设备当场算出适用清单（按登记当时的生效口径），并留一条登记快照。
        result = self._match(equipment, equipment.registered_at)
        self._matches[equipment.id] = result
        self._append_event(
            reason="设备登记",
            actor="",
            regulation=None,
            clause=None,
            day=equipment.registered_at,
            snapshot=[self._snapshot_entry(result)],
        )
        return equipment, False

    # ----- 匹配 ------------------------------------------------------------

    def current_matches(self, *, today: Optional[date] = None) -> list[dict[str, Any]]:
        """全部设备的当前适用清单（条款变动后已就地回填）。"""
        day = today or date.today()
        return [self._match(equipment, day) for equipment in self._equipment.values()]

    def match_equipment(self, equipment_id: int, as_of: Any = None) -> dict[str, Any]:
        """按指定日期重放：历史匹配按当时那一版算，与今天的状态无关。"""
        equipment = self._get_equipment(equipment_id)
        day = _parse_date(as_of, "查询日期") or date.today()
        return self._match(equipment, day)

    def current_conflicts(self, *, today: Optional[date] = None) -> list[dict[str, Any]]:
        """汇总当前所有“两版打架”的冲突，标明赢家与输家。"""
        conflicts: list[dict[str, Any]] = []
        for result in self.current_matches(today=today):
            for conflict in result["conflicts"]:
                conflicts.append(
                    {
                        "equipment": result["equipment"],
                        "regulation": conflict["regulation"],
                        "winner": conflict["winner"],
                        "others": conflict["others"],
                    }
                )
        return conflicts

    def _match(self, equipment: Equipment, day: date) -> dict[str, Any]:
        applicable: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []
        for regulation in self._regulations.values():
            candidates = [
                version
                for version in regulation.versions
                if equipment.category in version.applicable_categories
                and version.is_active_on(day)
            ]
            if not candidates:
                continue
            # 生效日期较晚者说了算；同日按登记先后（版本 id）兜底，保证结果稳定。
            ordered = sorted(candidates, key=lambda item: (item.effective_date, item.id), reverse=True)
            winner = ordered[0]
            others = ordered[1:]
            entry = {
                "regulation": {
                    "id": regulation.id,
                    "code": regulation.code,
                    "name": regulation.name,
                    "owner_dept": regulation.owner_dept,
                },
                "winner": self._version_brief(winner),
                "has_conflict": bool(others),
            }
            applicable.append(entry)
            if others:
                conflicts.append(
                    {
                        "regulation": entry["regulation"],
                        "winner": self._version_brief(winner),
                        "others": [self._version_brief(item) for item in others],
                        "versions": [self._version_brief(item) for item in ordered],
                    }
                )
        applicable.sort(key=lambda item: item["regulation"]["code"])
        conflicts.sort(key=lambda item: item["regulation"]["code"])
        return {
            "equipment": equipment.to_dict(),
            "as_of": _iso(day),
            "applicable": applicable,
            "conflicts": conflicts,
            "has_conflict": bool(conflicts),
        }

    @staticmethod
    def _version_brief(version: ClauseVersion) -> dict[str, Any]:
        return {
            "version_id": version.id,
            "version": version.version,
            "title": version.title,
            "status": version.status,
            "effective_date": _iso(version.effective_date),
            "repeal_date": _iso(version.repeal_date),
        }

    # ----- 重算与历史 ------------------------------------------------------

    def _recompute_all(
        self,
        *,
        reason: str,
        actor: str,
        regulation: Regulation,
        clause: ClauseVersion,
        day: date,
    ) -> dict[str, Any]:
        """口径调整后：存量匹配就地回填（同一设备同一行），历史只追加不改写。"""
        snapshot: list[dict[str, Any]] = []
        for equipment in self._equipment.values():
            result = self._match(equipment, day)
            self._matches[equipment.id] = result  # 回填已有记录，不新增设备、不删历史
            snapshot.append(self._snapshot_entry(result))
        return self._append_event(
            reason=reason,
            actor=actor,
            regulation=regulation,
            clause=clause,
            day=day,
            snapshot=snapshot,
        )

    def _snapshot_entry(self, result: dict[str, Any]) -> dict[str, Any]:
        return {
            "equipment_id": result["equipment"]["id"],
            "equipment_code": result["equipment"]["code"],
            "category": result["equipment"]["category"],
            "winners": [
                {
                    "regulation_code": item["regulation"]["code"],
                    "regulation_name": item["regulation"]["name"],
                    "version": item["winner"]["version"],
                    "version_id": item["winner"]["version_id"],
                    "effective_date": item["winner"]["effective_date"],
                    "has_conflict": item["has_conflict"],
                }
                for item in result["applicable"]
            ],
        }

    def _append_event(
        self,
        *,
        reason: str,
        actor: str,
        regulation: Optional[Regulation],
        clause: Optional[ClauseVersion],
        day: date,
        snapshot: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self._seq_event += 1
        event = {
            "id": self._seq_event,
            "date": _iso(day),
            "reason": reason,
            "actor": actor,
            "target": {
                "regulation_code": regulation.code if regulation else None,
                "regulation_name": regulation.name if regulation else None,
                "version": clause.version if clause else None,
                "status": clause.status if clause else None,
            },
            "snapshot": snapshot,
        }
        self._events.append(event)
        return event

    def history(self, equipment_id: Optional[int] = None) -> list[dict[str, Any]]:
        """历史匹配快照（只追加）。可按设备过滤，看这台设备每次按哪版算的。"""
        if equipment_id is None:
            return [dict(event) for event in self._events]
        self._get_equipment(equipment_id)
        result: list[dict[str, Any]] = []
        for event in self._events:
            entries = [
                entry for entry in event["snapshot"] if entry["equipment_id"] == equipment_id
            ]
            if entries:
                viewed = dict(event)
                viewed["snapshot"] = entries
                result.append(viewed)
        return result

    def seed_baseline(self, *, actor: str = "", day: Optional[date] = None) -> dict[str, Any]:
        """期初建账：为全部已登记设备留一张基线快照，不绑定具体条款动作。"""
        return self._recompute_all(
            reason="期初建账",
            actor=actor,
            regulation=None,
            clause=None,
            day=day or date.today(),
        )

    # ----- 查询 ------------------------------------------------------------

    def list_regulations(self, status: Optional[str] = None) -> list[dict[str, Any]]:
        regulations = list(self._regulations.values())
        if status:
            regulations = [
                regulation
                for regulation in regulations
                if any(version.status == status for version in regulation.versions)
            ]
        return [regulation.to_dict() for regulation in regulations]

    def get_regulation(self, regulation_id: int) -> dict[str, Any]:
        return self._get_regulation(regulation_id).to_dict()

    def list_equipment(self, category: Optional[str] = None) -> list[dict[str, Any]]:
        items = list(self._equipment.values())
        if category:
            items = [item for item in items if item.category == category]
        return [item.to_dict() for item in items]

    def meta(self) -> dict[str, Any]:
        owner_depts = sorted({reg.owner_dept for reg in self._regulations.values()})
        return {
            "categories": list(EQUIPMENT_CATEGORIES),
            "status_flow": list(STATUS_FLOW),
            "permissions": list(ALL_PERMISSIONS),
            "operators": self.list_operators(),
            "owner_depts": owner_depts,
        }

    # ----- 内部 ------------------------------------------------------------

    def _get_regulation(self, regulation_id: int) -> Regulation:
        regulation = self._regulations.get(regulation_id)
        if regulation is None:
            raise NotFound(f"法规 {regulation_id} 不存在")
        return regulation

    def _get_equipment(self, equipment_id: int) -> Equipment:
        equipment = self._equipment.get(equipment_id)
        if equipment is None:
            raise NotFound(f"设备 {equipment_id} 不存在")
        return equipment

    def _resolve_version(self, version_id: int) -> tuple[ClauseVersion, Regulation]:
        for regulation in self._regulations.values():
            for clause in regulation.versions:
                if clause.id == version_id:
                    return clause, regulation
        raise NotFound(f"条款版本 {version_id} 不存在")


# ---------------------------------------------------------------------------
# 单例与示例数据
# ---------------------------------------------------------------------------

ledgers = RegulationLedger()


def seed_ledger(target: RegulationLedger) -> None:
    """填一套能直接演示全部规则的示例数据。重复执行幂等。"""
    # 账号：归口管理员（两权齐全）、归口只读（缺权限）、外部门（非归口）。
    target.register_operator("张监察", "特种设备安全监察局", [PERM_PUBLISH, PERM_REPEAL])
    target.register_operator("李复核", "特种设备安全监察局", [])
    target.register_operator("王综合", "综合管理部", [PERM_PUBLISH, PERM_REPEAL])

    boiler, _ = target.register_regulation(
        "TSG 11", "锅炉安全技术规程", "特种设备安全监察局", today=date(2020, 3, 1)
    )
    v2020, _ = target.add_version(
        boiler.id, "2020版", "锅炉安全技术监察口径（2020）", ["锅炉"],
        effective_date="2020-09-01", today=date(2020, 3, 1),
    )
    target.publish_version(v2020.id, "张监察", effective_date="2020-09-01", today=date(2020, 9, 1))
    # 新版已生效、旧版漏废止：制造一个“两版同时有效”的冲突现场，新版生效日更晚、说了算。
    v2025, _ = target.add_version(
        boiler.id, "2025版", "锅炉安全技术监察口径（2025修订）", ["锅炉"],
        effective_date="2026-01-01", today=date(2025, 6, 1),
    )
    target.publish_version(v2025.id, "张监察", effective_date="2026-01-01", today=date(2026, 1, 1))

    elevator, _ = target.register_regulation(
        "TSG T7001", "电梯监督检验和定期检验规则", "特种设备安全监察局", today=date(2009, 6, 1)
    )
    old_elev, _ = target.add_version(
        elevator.id, "2009版", "电梯定期检验口径（2009）", ["电梯"],
        effective_date="2009-12-01", today=date(2009, 6, 1),
    )
    target.publish_version(old_elev.id, "张监察", effective_date="2009-12-01", today=date(2009, 12, 1))
    target.repeal_version(old_elev.id, "张监察", repeal_date="2024-04-01", today=date(2024, 4, 1))
    new_elev, _ = target.add_version(
        elevator.id, "2023版", "电梯定期检验口径（2023修订）", ["电梯"],
        effective_date="2024-04-01", today=date(2023, 10, 1),
    )
    target.publish_version(new_elev.id, "张监察", effective_date="2024-04-01", today=date(2024, 4, 1))

    crane, _ = target.register_regulation(
        "TSG Q5001", "起重机械使用管理规则", "特种设备安全监察局", today=date(2009, 9, 1)
    )
    old_crane, _ = target.add_version(
        crane.id, "2009版", "起重机械使用管理口径（2009）", ["起重机械"],
        effective_date="2010-01-01", today=date(2009, 9, 1),
    )
    target.publish_version(old_crane.id, "张监察", effective_date="2010-01-01", today=date(2010, 1, 1))
    # 新版还在征求意见：当前设备不命中它，仍按 2009 版管。
    target.add_version(
        crane.id, "2026征求意见稿", "起重机械使用管理口径（2026拟修订）", ["起重机械"],
        effective_date="2027-03-01", today=date(2026, 8, 1),
    )

    vessel, _ = target.register_regulation(
        "TSG 21", "固定式压力容器安全技术监察规程", "特种设备安全监察局", today=date(2016, 6, 1)
    )
    v2016, _ = target.add_version(
        vessel.id, "2016版", "固定式压力容器监察口径（2016）", ["压力容器"],
        effective_date="2016-10-01", today=date(2016, 6, 1),
    )
    target.publish_version(v2016.id, "张监察", effective_date="2016-10-01", today=date(2016, 10, 1))

    target.register_equipment("EQ-B001", "1号主蒸汽锅炉", "锅炉", today=date(2023, 5, 10))
    target.register_equipment("EQ-B002", "2号热水锅炉", "锅炉", today=date(2024, 2, 18))
    target.register_equipment("EQ-E001", "厂区客梯1#", "电梯", today=date(2022, 11, 3))
    target.register_equipment("EQ-C001", "桥式起重机5t", "起重机械", today=date(2021, 7, 22))
    target.register_equipment("EQ-V001", "立式储气罐", "压力容器", today=date(2023, 9, 1))
    target.register_equipment("EQ-F001", "平衡重式叉车", "场（厂）内专用机动车辆", today=date(2025, 1, 6))

    # 期初建账：为已登记设备留一张全量基线快照。
    target.seed_baseline(actor="张监察", day=date(2026, 10, 1))


seed_ledger(ledgers)
