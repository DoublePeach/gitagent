"""发布计划（ReleasePlan）与发布项（ReleaseItem）ORM 模型。"""
import enum
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PlanStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Environment(str, enum.Enum):
    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"


class ItemStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class ReleasePlan(Base):
    __tablename__ = "release_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="发布计划名称")
    system_name: Mapped[str] = mapped_column(String(64), nullable=False, comment="系统名称")
    environment: Mapped[Environment] = mapped_column(
        Enum(Environment, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        comment="目标环境",
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="计划执行时间"
    )
    status: Mapped[PlanStatus] = mapped_column(
        Enum(PlanStatus, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=PlanStatus.DRAFT,
        server_default=PlanStatus.DRAFT.value,
        comment="计划状态",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    items: Mapped[list["ReleaseItem"]] = relationship(
        "ReleaseItem",
        back_populates="plan",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<ReleasePlan id={self.id} name={self.name!r} status={self.status}>"


class ReleaseItem(Base):
    __tablename__ = "release_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("release_plans.id", ondelete="CASCADE"), nullable=False, comment="所属计划ID"
    )
    repo_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="仓库名称")
    branch_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="分支名称")
    commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True, comment="提交SHA")
    status: Mapped[ItemStatus] = mapped_column(
        Enum(ItemStatus, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=ItemStatus.PENDING,
        server_default=ItemStatus.PENDING.value,
        comment="发布项状态",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    plan: Mapped["ReleasePlan"] = relationship("ReleasePlan", back_populates="items")

    def __repr__(self) -> str:
        return f"<ReleaseItem id={self.id} repo={self.repo_name!r} status={self.status}>"
