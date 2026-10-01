"""法规标准台账接口：法规条款登记、状态流转、设备适用匹配与历史留痕。

业务规则全部在 app.services.regulation 里；路由层只负责把领域异常翻译成
可读的 HTTP 回执，越权 / 跳级等动作不静默成功。
"""
from __future__ import annotations

from datetime import date
from typing import Any, NoReturn

from fastapi import APIRouter, HTTPException, Query

from app.schemas import (
    ActionResult,
    ClauseAction,
    ClauseVersionCreate,
    EquipmentCreate,
    RegulationCreate,
)
from app.services.regulation import (
    IllegalTransition,
    LedgerValidationError,
    NotFound,
    PermissionDenied,
    ledgers as ledger,
)

router = APIRouter(prefix="/api/regulation", tags=["法规标准台账"])


def _raise_domain(exc: Exception) -> NoReturn:
    if isinstance(exc, PermissionDenied):
        # 越权启用/废止：当场驳回（403），回执里点名缺的权限。
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, IllegalTransition):
        # 跳级流转：状态机不允许，返回 409 冲突。
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, NotFound):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, LedgerValidationError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc


@router.get("/meta")
def meta() -> dict[str, Any]:
    """返回设备类别目录、状态序列、权限项与可操作账号。"""
    return ledger.meta()


# ----- 法规与条款 ----------------------------------------------------------


@router.get("/regulations")
def list_regulations(
    status: str | None = Query(default=None, description="按条款状态过滤：征求意见/已生效/已废止"),
) -> dict[str, Any]:
    items = ledger.list_regulations(status=status)
    return {"items": items, "total": len(items)}


@router.post("/regulations", response_model=ActionResult, status_code=201)
def create_regulation(payload: RegulationCreate) -> ActionResult:
    """登记法规；同文号重复登记只认第一次，回执里标明“重复登记”。"""
    try:
        regulation, duplicated = ledger.register_regulation(
            payload.code, payload.name, payload.owner_dept
        )
    except (LedgerValidationError, NotFound) as exc:
        _raise_domain(exc)
    if duplicated:
        return ActionResult(
            ok=True, message=f"法规「{regulation.code}」已登记过，重复登记只认第一次，沿用原记录",
            entry=regulation.to_dict(),
        )
    return ActionResult(ok=True, message="法规标准已登记", entry=regulation.to_dict())


@router.get("/regulations/{regulation_id}")
def get_regulation(regulation_id: int) -> dict[str, Any]:
    try:
        return ledger.get_regulation(regulation_id)
    except NotFound as exc:
        _raise_domain(exc)


@router.post("/regulations/{regulation_id}/versions", response_model=ActionResult, status_code=201)
def add_version(regulation_id: int, payload: ClauseVersionCreate) -> ActionResult:
    """登记一版条款，初始一律“征求意见”；同版本重复登记只认第一次。"""
    try:
        clause, duplicated = ledger.add_version(
            regulation_id,
            payload.version,
            payload.title,
            payload.categories,
            payload.effective_date,
        )
    except (LedgerValidationError, NotFound) as exc:
        _raise_domain(exc)
    if duplicated:
        return ActionResult(
            ok=True, message=f"版本「{clause.version}」已登记过，重复登记只认第一次，沿用原记录",
            entry=clause.to_dict(),
        )
    return ActionResult(ok=True, message="条款版本已登记（征求意见）", entry=clause.to_dict())


@router.post("/versions/{version_id}/publish", response_model=ActionResult)
def publish_version(version_id: int, payload: ClauseAction) -> ActionResult:
    """征求意见 → 已生效（归口管理员 + 启用权限）；启用后全量重算设备适用清单。"""
    try:
        clause, event = ledger.publish_version(version_id, payload.operator, payload.date)
    except (PermissionDenied, IllegalTransition, LedgerValidationError, NotFound) as exc:
        _raise_domain(exc)
    return ActionResult(
        ok=True,
        message=f"条款已启用，生效日期 {clause.effective_date.isoformat()}，已按新版重算全部设备适用清单",
        entry=clause.to_dict(),
    )


@router.post("/versions/{version_id}/repeal", response_model=ActionResult)
def repeal_version(version_id: int, payload: ClauseAction) -> ActionResult:
    """已生效 → 已废止（归口管理员 + 废止权限）；废止后全量重算设备适用清单。"""
    try:
        clause, event = ledger.repeal_version(version_id, payload.operator, payload.date)
    except (PermissionDenied, IllegalTransition, LedgerValidationError, NotFound) as exc:
        _raise_domain(exc)
    return ActionResult(
        ok=True,
        message=f"条款已废止，废止日期 {clause.repeal_date.isoformat()}，已按最新口径重算全部设备适用清单",
        entry=clause.to_dict(),
    )


# ----- 设备与匹配 ----------------------------------------------------------


@router.get("/equipment")
def list_equipment(
    category: str | None = Query(default=None, description="按设备类别过滤"),
    as_of: str | None = Query(default=None, description="按指定日期重放，默认今天"),
) -> dict[str, Any]:
    """设备台账带出当前（或指定日期）适用法规；冲突一并返回。"""
    items = []
    for equipment in ledger.list_equipment(category=category):
        try:
            items.append(ledger.match_equipment(equipment["id"], as_of))
        except (LedgerValidationError, NotFound) as exc:
            _raise_domain(exc)
    return {"items": items, "total": len(items)}


@router.post("/equipment", response_model=ActionResult, status_code=201)
def create_equipment(payload: EquipmentCreate) -> ActionResult:
    """登记设备并当场带出适用清单；设备编号重复时沿用第一次记录。"""
    try:
        equipment, duplicated = ledger.register_equipment(
            payload.code, payload.name, payload.category
        )
        result = ledger.match_equipment(equipment.id, equipment.registered_at.isoformat())
    except (LedgerValidationError, NotFound) as exc:
        _raise_domain(exc)
    message = "设备已登记并匹配当前适用法规"
    if duplicated:
        message = "设备编号已存在，重复登记只认第一次，沿用原记录"
    return ActionResult(ok=True, message=message, entry=result)


@router.get("/equipment/{equipment_id}")
def get_equipment_match(
    equipment_id: int,
    as_of: str | None = Query(default=None, description="按指定日期重放历史口径"),
) -> dict[str, Any]:
    try:
        return ledger.match_equipment(equipment_id, as_of)
    except (LedgerValidationError, NotFound) as exc:
        _raise_domain(exc)


@router.get("/equipment/{equipment_id}/history")
def equipment_history(equipment_id: int) -> dict[str, Any]:
    """该设备的历史匹配快照：每次按当时那一版记录，只追加不改写。"""
    try:
        items = ledger.history(equipment_id=equipment_id)
    except NotFound as exc:
        _raise_domain(exc)
    return {"items": items, "total": len(items)}


@router.get("/conflicts")
def conflicts(
    as_of: str | None = Query(default=None, description="按指定日期查看冲突，默认今天"),
) -> dict[str, Any]:
    """汇总两版条款打架的设备与版本：谁生效日晚、谁说了算。"""
    try:
        day = date.fromisoformat(as_of) if as_of else None
        items = ledger.current_conflicts(today=day)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="as_of 应为 YYYY-MM-DD 格式") from exc
    return {"items": items, "total": len(items)}


@router.get("/history")
def all_history() -> dict[str, Any]:
    """全量历史事件（条款启用/废止触发的重算快照）。"""
    items = ledger.history()
    return {"items": items, "total": len(items)}
