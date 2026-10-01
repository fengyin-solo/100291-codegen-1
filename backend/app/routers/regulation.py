"""法规标准台账接口。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas import ActionResult, PageResult, RegulationActionPayload, RegulationPayload
from app.services.regulation import (
    ACTION_PERMISSIONS,
    RegulationError,
    regulation_service,
)

router = APIRouter(prefix="/api/regulations", tags=["法规标准台账"])


@router.get("/categories", response_model=dict[str, object])
def list_categories() -> dict[str, object]:
    """返回已出现的设备类别，供条款登记和匹配筛选使用。"""
    regulation_service.ensure_initialized()
    return {"items": regulation_service.categories()}


@router.get("/matches", response_model=PageResult[dict])
def list_matches(
    device_keyword: str | None = Query(default=None, description="按设备编号或名称检索"),
    device_category: str | None = Query(default=None, description="按设备类别过滤"),
    conflict_only: bool = Query(default=False, description="是否只看冲突设备"),
    as_of: str | None = Query(default=None, description="按指定日期复盘，默认今天"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """设备台账按类别带出当前适用法规，并列出两版条款冲突。"""
    try:
        items, total = regulation_service.list_device_matches(
            device_keyword=device_keyword,
            device_category=device_category,
            conflict_only=conflict_only,
            as_of=as_of,
            page=page,
            size=size,
        )
    except RegulationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/history", response_model=PageResult[dict])
def list_history(
    device_id: int | None = Query(default=None, description="限定单台设备"),
    device_keyword: str | None = Query(default=None, description="按设备编号或名称检索"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """读取每次重算时固化的匹配快照，历史结果不随新版本变化。"""
    regulation_service.ensure_initialized()
    items, total = regulation_service.list_history(
        device_id=device_id,
        device_keyword=device_keyword,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("", response_model=PageResult[dict])
def list_regulations(
    keyword: str | None = Query(default=None, description="法规编号、名称、版本或公告号"),
    status: str | None = Query(default=None, description="征求意见、已生效、已废止"),
    device_category: str | None = Query(default=None, description="适用设备类别"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """分页查看法规条款台账。"""
    regulation_service.ensure_initialized()
    items, total = regulation_service.list_regulations(
        keyword=keyword,
        status=status,
        device_category=device_category,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("", response_model=ActionResult)
def create_regulation(payload: RegulationPayload) -> ActionResult:
    """登记征求意见稿；同一法规编号、版本、设备类别重复登记时只认第一次。"""
    try:
        entry = regulation_service.create_regulation(payload.model_dump())
    except RegulationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return ActionResult(ok=True, message="法规条款已登记，当前状态为征求意见", entry=entry)


@router.post("/{regulation_id}/actions", response_model=ActionResult)
def run_action(
    regulation_id: int,
    payload: RegulationActionPayload,
    request: Request,
) -> ActionResult:
    """仅归口管理员可启用或废止条款；越权请求返回 403 和缺少的权限点。"""
    permission, permission_label = ACTION_PERMISSIONS.get(
        payload.action, ("", payload.action)
    )
    roles = {
        item.strip()
        for item in request.headers.get("x-roles", "").split(",")
        if item.strip()
    }
    # 内存示例没有登录中心，服务端只按角色派生权限，避免调用方自行夹带权限点头绕过。
    permissions = {"regulation:activate", "regulation:repeal"} if "regulation_admin" in roles else set()
    operator = request.headers.get("x-operator-id", "anonymous")
    if permission and permission not in permissions:
        raise HTTPException(
            status_code=403,
            detail=(
                f"越权驳回：当前操作员「{operator}」无权{permission_label}，"
                f"缺少权限点 {permission}（仅归口管理员可执行；当前角色："
                f"{'、'.join(sorted(roles)) or '无'}）"
            ),
        )

    try:
        entry = regulation_service.run_action(
            regulation_id,
            payload.action,
            operator=operator,
            remark=payload.remark,
        )
    except RegulationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return ActionResult(ok=True, message=f"法规条款已{permission_label}，设备适用清单已重算", entry=entry)
