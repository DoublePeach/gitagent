"""管理员发布计划 API。

端点：
  POST   /admin/releases                创建计划
  GET    /admin/releases                列出计划（支持过滤 + 分页）
  GET    /admin/releases/{plan_id}      获取详情
  DELETE /admin/releases/{plan_id}      取消计划
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.release_plan import Environment, PlanStatus
from app.db.session import get_db
from app.schemas.release_plan import (
    ReleasePlanCreate,
    ReleasePlanListItem,
    ReleasePlanRead,
)
from app.services import release_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/releases",
    response_model=ReleasePlanRead,
    status_code=201,
    summary="创建发布计划",
)
async def create_release_plan(
    data: ReleasePlanCreate,
    db: AsyncSession = Depends(get_db),
) -> ReleasePlanRead:
    plan = await release_service.create_release_plan(db, data)
    return ReleasePlanRead.model_validate(plan)


@router.get(
    "/releases",
    response_model=list[ReleasePlanListItem],
    summary="获取发布计划列表",
)
async def list_release_plans(
    system_name: str | None = Query(None, description="按系统名称过滤"),
    environment: Environment | None = Query(None, description="按环境过滤"),
    status: PlanStatus | None = Query(None, description="按状态过滤"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="跳过条数"),
    db: AsyncSession = Depends(get_db),
) -> list[ReleasePlanListItem]:
    plans = await release_service.list_release_plans(
        db,
        system_name=system_name,
        environment=environment,
        status=status,
        limit=limit,
        offset=offset,
    )
    return [ReleasePlanListItem.model_validate(p) for p in plans]


@router.get(
    "/releases/{plan_id}",
    response_model=ReleasePlanRead,
    summary="获取发布计划详情",
)
async def get_release_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
) -> ReleasePlanRead:
    plan = await release_service.get_release_plan(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"发布计划 {plan_id} 不存在")
    return ReleasePlanRead.model_validate(plan)


@router.delete(
    "/releases/{plan_id}",
    response_model=ReleasePlanRead,
    summary="取消发布计划",
)
async def cancel_release_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
) -> ReleasePlanRead:
    plan = await release_service.cancel_release_plan(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"发布计划 {plan_id} 不存在")
    if plan.status not in ("cancelled",):
        raise HTTPException(
            status_code=409,
            detail=f"计划当前状态为 {plan.status}，无法取消（只允许取消 draft/scheduled 状态的计划）",
        )
    return ReleasePlanRead.model_validate(plan)
