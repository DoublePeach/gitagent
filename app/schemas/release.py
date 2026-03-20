"""发布计划相关的 Pydantic 模型（请求体 / 响应体）。"""
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ReleaseStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReleasePlanCreate(BaseModel):
    title: str = Field(..., description="发布标题")
    project: str = Field(..., description="GitLab 项目路径，如 group/repo")
    branch: str = Field(default="main", description="发布分支")
    env: str = Field(..., description="目标环境，如 staging / production")
    scheduled_at: datetime | None = None


class ReleasePlanResponse(ReleasePlanCreate):
    id: int
    status: ReleaseStatus
    created_at: datetime

    model_config = {"from_attributes": True}
