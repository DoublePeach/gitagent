"""发布计划 API 的 Pydantic 请求/响应模型，与 ORM 模型字段严格对齐。"""
from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models.release_plan import Environment, ItemStatus, PlanStatus


# ---------------------------------------------------------------------------
# ReleaseItem 嵌套模型
# ---------------------------------------------------------------------------

class ReleaseItemCreate(BaseModel):
    repo_name: str = Field(..., description="代码仓库名称")
    branch_name: str = Field(..., description="分支名称")
    commit_sha: str | None = Field(None, description="可选的提交 SHA")


class ReleaseItemRead(BaseModel):
    id: int
    plan_id: int
    repo_name: str
    branch_name: str
    commit_sha: str | None
    status: ItemStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# ReleasePlan 请求模型
# ---------------------------------------------------------------------------

class ReleasePlanCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="发布计划名称")
    system_name: str = Field(..., min_length=1, max_length=64, description="系统名称，如 WMS、OMS")
    environment: Environment = Field(..., description="目标环境：dev / staging / production")
    scheduled_at: datetime | None = Field(None, description="计划执行时间，为空则为草稿")
    items: list[ReleaseItemCreate] = Field(default_factory=list, description="初始发布项列表（可为空）")


# ---------------------------------------------------------------------------
# ReleasePlan 响应模型
# ---------------------------------------------------------------------------

class ReleasePlanRead(BaseModel):
    """完整详情，包含 items 列表。"""
    id: int
    name: str
    system_name: str
    environment: Environment
    scheduled_at: datetime | None
    status: PlanStatus
    created_at: datetime
    updated_at: datetime
    items: list[ReleaseItemRead] = []

    model_config = {"from_attributes": True}


class ReleasePlanListItem(BaseModel):
    """列表视图：不含 items，减少数据传输量。"""
    id: int
    name: str
    system_name: str
    environment: Environment
    scheduled_at: datetime | None
    status: PlanStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
