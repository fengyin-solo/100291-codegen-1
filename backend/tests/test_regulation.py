"""法规标准台账规则测试。

覆盖：状态机逐级流转与跳级驳回、重复登记只认第一次、设备按类别匹配、
同法规两版冲突时生效日期晚者说了算、口径调整后全量重算回填、历史按当时版本保留、
越权启用/废止当场驳回并点名缺失权限。

运行：python3 -m unittest discover -s backend/tests -v
"""
from __future__ import annotations

import unittest
from datetime import date

from app.services.regulation import (
    PERM_PUBLISH,
    PERM_REPEAL,
    STATUS_DRAFT,
    STATUS_EFFECTIVE,
    STATUS_REPEALED,
    IllegalTransition,
    LedgerValidationError,
    NotFound,
    PermissionDenied,
    RegulationLedger,
)


class RegulationLedgerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        # 每个用例一份干净台账，避免示例数据串扰。
        self.ledger = RegulationLedger()
        self.ledger.register_operator("张监察", "特种设备安全监察局", [PERM_PUBLISH, PERM_REPEAL])
        self.ledger.register_operator("李复核", "特种设备安全监察局", [])
        self.ledger.register_operator("王综合", "综合管理部", [PERM_PUBLISH, PERM_REPEAL])
        self.reg, _ = self.ledger.register_regulation(
            "TSG-T-001", "测试安全技术规程", "特种设备安全监察局", today=date(2026, 1, 1)
        )
        self.v1, _ = self.ledger.add_version(
            self.reg.id, "2024版", "旧口径", ["锅炉"],
            effective_date="2024-01-01", today=date(2023, 10, 1),
        )
        self.v2, _ = self.ledger.add_version(
            self.reg.id, "2026版", "新口径", ["锅炉"],
            effective_date="2026-06-01", today=date(2026, 2, 1),
        )
        self.ledger.register_equipment("EQ-1", "一号锅炉", "锅炉", today=date(2025, 1, 1))
        self.ledger.register_equipment("EQ-2", "一号电梯", "电梯", today=date(2025, 1, 1))

    # ------------------------------------------------------------------
    # 状态机：只能逐级，不允许跳级
    # ------------------------------------------------------------------

    def test_version_starts_at_draft(self) -> None:
        self.assertEqual(self.v1.status, STATUS_DRAFT)
        self.assertEqual(self.v2.status, STATUS_DRAFT)

    def test_cannot_repeal_draft_directly(self) -> None:
        # 征求意见 -> 已废止：跳过“已生效”，当场驳回。
        with self.assertRaises(IllegalTransition) as ctx:
            self.ledger.repeal_version(self.v1.id, "张监察", today=date(2026, 1, 1))
        self.assertIn("逐级流转", str(ctx.exception))
        self.assertIn("跳级", str(ctx.exception))

    def test_can_publish_then_repeal_in_order(self) -> None:
        clause, _ = self.ledger.publish_version(
            self.v1.id, "张监察", effective_date="2024-01-01", today=date(2024, 1, 1)
        )
        self.assertEqual(clause.status, STATUS_EFFECTIVE)
        clause, _ = self.ledger.repeal_version(
            self.v1.id, "张监察", repeal_date="2026-06-01", today=date(2026, 6, 1)
        )
        self.assertEqual(clause.status, STATUS_REPEALED)
        self.assertEqual(clause.repeal_date.isoformat(), "2026-06-01")
        # 已废止没有下一步，再启用也算非法流转。
        with self.assertRaises(IllegalTransition):
            self.ledger.publish_version(self.v1.id, "张监察", today=date(2026, 6, 2))

    # ------------------------------------------------------------------
    # 重复登记只认第一次
    # ------------------------------------------------------------------

    def test_duplicate_regulation_keeps_first(self) -> None:
        again, duplicated = self.ledger.register_regulation(
            "TSG-T-001", "被人改了名的同文号法规", "别的部门", today=date(2026, 3, 1)
        )
        self.assertTrue(duplicated)
        self.assertEqual(again.id, self.reg.id)
        self.assertEqual(again.name, "测试安全技术规程")
        self.assertEqual(again.owner_dept, "特种设备安全监察局")
        self.assertEqual(len(self.ledger.list_regulations()), 1)

    def test_duplicate_version_keeps_first(self) -> None:
        again, duplicated = self.ledger.add_version(
            self.reg.id, "2024版", "重复提交的旧口径", ["锅炉"], today=date(2026, 3, 1)
        )
        self.assertTrue(duplicated)
        self.assertEqual(again.id, self.v1.id)
        self.assertEqual(again.title, "旧口径")
        self.assertEqual(len(self.ledger.get_regulation(self.reg.id)["versions"]), 2)

    def test_duplicate_equipment_keeps_first(self) -> None:
        again, duplicated = self.ledger.register_equipment(
            "EQ-1", "改名锅炉", "锅炉", today=date(2026, 5, 1)
        )
        self.assertTrue(duplicated)
        self.assertEqual(again.name, "一号锅炉")
        self.assertEqual(len(self.ledger.list_equipment()), 2)

    # ------------------------------------------------------------------
    # 设备按类别匹配
    # ------------------------------------------------------------------

    def test_equipment_only_matches_its_category(self) -> None:
        self.ledger.publish_version(
            self.v1.id, "张监察", effective_date="2024-01-01", today=date(2024, 1, 1)
        )
        boiler = self.ledger.match_equipment(1, as_of="2025-01-01")
        elevator = self.ledger.match_equipment(2, as_of="2025-01-01")
        self.assertEqual(len(boiler["applicable"]), 1)
        self.assertEqual(boiler["applicable"][0]["winner"]["version"], "2024版")
        self.assertEqual(elevator["applicable"], [])

    def test_draft_and_future_version_not_applied(self) -> None:
        self.ledger.publish_version(
            self.v1.id, "张监察", effective_date="2024-01-01", today=date(2024, 1, 1)
        )
        # v2 仍是征求意见稿，2026-03-01 时设备只认 v1。
        result = self.ledger.match_equipment(1, as_of="2026-03-01")
        self.assertEqual(result["applicable"][0]["winner"]["version"], "2024版")
        # 即便启用日期登记在未来，未到生效日也不适用。
        self.ledger.publish_version(
            self.v2.id, "张监察", effective_date="2026-06-01", today=date(2026, 3, 1)
        )
        result = self.ledger.match_equipment(1, as_of="2026-05-31")
        self.assertEqual(result["applicable"][0]["winner"]["version"], "2024版")

    # ------------------------------------------------------------------
    # 两版同时命中：生效日期晚者说了算，冲突可见是哪两版
    # ------------------------------------------------------------------

    def test_conflict_later_effective_date_wins(self) -> None:
        self.ledger.publish_version(
            self.v1.id, "张监察", effective_date="2024-01-01", today=date(2024, 1, 1)
        )
        self.ledger.publish_version(
            self.v2.id, "张监察", effective_date="2026-06-01", today=date(2026, 6, 1)
        )
        # 旧版未废止、新版已生效：两版同时命中，新版生效日更晚，说了算。
        result = self.ledger.match_equipment(1, as_of="2026-07-01")
        self.assertTrue(result["has_conflict"])
        entry = result["applicable"][0]
        self.assertEqual(entry["winner"]["version"], "2026版")
        self.assertTrue(entry["has_conflict"])
        conflict = result["conflicts"][0]
        self.assertEqual(conflict["winner"]["version"], "2026版")
        self.assertEqual([item["version"] for item in conflict["others"]], ["2024版"])
        self.assertEqual(
            sorted(item["version"] for item in conflict["versions"]), ["2024版", "2026版"]
        )

    def test_repeal_old_version_clears_conflict(self) -> None:
        self.ledger.publish_version(
            self.v1.id, "张监察", effective_date="2024-01-01", today=date(2024, 1, 1)
        )
        self.ledger.publish_version(
            self.v2.id, "张监察", effective_date="2026-06-01", today=date(2026, 6, 1)
        )
        self.ledger.repeal_version(
            self.v1.id, "张监察", repeal_date="2026-06-01", today=date(2026, 6, 1)
        )
        result = self.ledger.match_equipment(1, as_of="2026-07-01")
        self.assertFalse(result["has_conflict"])
        self.assertEqual(result["applicable"][0]["winner"]["version"], "2026版")
        self.assertEqual(self.ledger.current_conflicts(today=date(2026, 7, 1)), [])

    # ------------------------------------------------------------------
    # 口径调整后全量重算回填；历史按当时版本保留
    # ------------------------------------------------------------------

    def test_recalc_backfills_existing_equipment(self) -> None:
        self.ledger.publish_version(
            self.v1.id, "张监察", effective_date="2024-01-01", today=date(2024, 1, 1)
        )
        self.assertEqual(
            self.ledger.current_matches(today=date(2026, 5, 1))[0]["applicable"][0]["winner"][
                "version"
            ],
            "2024版",
        )
        # 启用新版：存量锅炉 EQ-1 当场回填为新版，无需重新登记设备。
        self.ledger.publish_version(
            self.v2.id, "张监察", effective_date="2026-06-01", today=date(2026, 6, 1)
        )
        current = {item["equipment"]["code"]: item for item in
                   self.ledger.current_matches(today=date(2026, 7, 1))}
        self.assertEqual(current["EQ-1"]["applicable"][0]["winner"]["version"], "2026版")
        # 电梯与该法规无关，适用清单保持为空。
        self.assertEqual(current["EQ-2"]["applicable"], [])
        # 设备仍是最初两台，回填不新增设备记录。
        self.assertEqual(len(self.ledger.list_equipment()), 2)

    def test_history_keeps_version_as_it_was_at_the_time(self) -> None:
        self.ledger.publish_version(
            self.v1.id, "张监察", effective_date="2024-01-01", today=date(2024, 1, 1)
        )
        self.ledger.publish_version(
            self.v2.id, "张监察", effective_date="2026-06-01", today=date(2026, 6, 1)
        )
        self.ledger.repeal_version(
            self.v1.id, "张监察", repeal_date="2026-06-01", today=date(2026, 6, 1)
        )
        # 历史时点重放：2025 年按 v1，2026-07 按 v2，互不覆盖。
        self.assertEqual(
            self.ledger.match_equipment(1, as_of="2025-06-01")["applicable"][0]["winner"][
                "version"
            ],
            "2024版",
        )
        self.assertEqual(
            self.ledger.match_equipment(1, as_of="2026-07-01")["applicable"][0]["winner"][
                "version"
            ],
            "2026版",
        )
        # 事件快照只追加：启用 v1、启用 v2、废止 v1 各一条，且包含设备快照。
        events = self.ledger.history(equipment_id=1)
        reasons = [event["reason"] for event in events]
        self.assertEqual(reasons.count("条款启用"), 2)
        self.assertEqual(reasons.count("条款废止"), 1)
        for event in events:
            self.assertEqual(len(event["snapshot"]), 1)
            self.assertEqual(event["snapshot"][0]["equipment_code"], "EQ-1")

    # ------------------------------------------------------------------
    # 权限：只有归口管理员可启用/废止，越权驳回并点名缺的权限
    # ------------------------------------------------------------------

    def test_non_owner_admin_denied(self) -> None:
        # 王综合持有权限但归属外部门：非归口，驳回并说明部门不符。
        with self.assertRaises(PermissionDenied) as ctx:
            self.ledger.publish_version(self.v1.id, "王综合", today=date(2024, 1, 1))
        message = str(ctx.exception)
        self.assertIn("当场驳回", message)
        self.assertIn("非归口管理员", message)
        self.assertIn(PERM_PUBLISH, message)

    def test_owner_without_permission_denied_names_missing_perm(self) -> None:
        # 李复核同属归口部门但没有任何权限：必须点名缺少的权限项。
        with self.assertRaises(PermissionDenied) as ctx:
            self.ledger.publish_version(self.v1.id, "李复核", today=date(2024, 1, 1))
        self.assertIn(f"缺少权限「{PERM_PUBLISH}」", str(ctx.exception))
        with self.assertRaises(PermissionDenied) as ctx:
            self.ledger.repeal_version(self.v1.id, "李复核", today=date(2026, 6, 1))
        self.assertIn(f"缺少权限「{PERM_REPEAL}」", str(ctx.exception))

    def test_unknown_operator_denied(self) -> None:
        with self.assertRaises(PermissionDenied):
            self.ledger.publish_version(self.v1.id, "陌生人", today=date(2024, 1, 1))

    def test_authorized_owner_admin_succeeds(self) -> None:
        clause, event = self.ledger.publish_version(
            self.v1.id, "张监察", effective_date="2024-01-01", today=date(2024, 1, 1)
        )
        self.assertEqual(clause.status, STATUS_EFFECTIVE)
        self.assertEqual(event["actor"], "张监察")
        self.assertEqual(event["reason"], "条款启用")

    # ------------------------------------------------------------------
    # 输入校验与异常
    # ------------------------------------------------------------------

    def test_invalid_category_and_date(self) -> None:
        with self.assertRaises(LedgerValidationError):
            self.ledger.register_equipment("EQ-9", "X", "不明设备", today=date(2026, 1, 1))
        with self.assertRaises(LedgerValidationError):
            self.ledger.add_version(
                self.reg.id, "2099版", "未来口径", ["锅炉"], effective_date="not-a-date"
            )

    def test_missing_not_found(self) -> None:
        with self.assertRaises(NotFound):
            self.ledger.match_equipment(999)


if __name__ == "__main__":
    unittest.main()
