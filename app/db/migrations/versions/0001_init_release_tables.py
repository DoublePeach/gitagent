"""init release tables

Revision ID: 0001
Revises: 
Create Date: 2026-03-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "release_plans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False, comment="发布计划名称"),
        sa.Column("system_name", sa.String(length=64), nullable=False, comment="系统名称"),
        sa.Column(
            "environment",
            sa.Enum("dev", "staging", "production", name="environment"),
            nullable=False,
            comment="目标环境",
        ),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True, comment="计划执行时间"),
        sa.Column(
            "status",
            sa.Enum("draft", "scheduled", "running", "success", "failed", "cancelled", name="planstatus"),
            nullable=False,
            server_default="draft",
            comment="计划状态",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()"), comment="创建时间"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW() ON UPDATE NOW()"),
            comment="更新时间",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "release_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False, comment="所属计划ID"),
        sa.Column("repo_name", sa.String(length=128), nullable=False, comment="仓库名称"),
        sa.Column("branch_name", sa.String(length=128), nullable=False, comment="分支名称"),
        sa.Column("commit_sha", sa.String(length=40), nullable=True, comment="提交SHA"),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "success", "failed", "skipped", name="itemstatus"),
            nullable=False,
            server_default="pending",
            comment="发布项状态",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()"), comment="创建时间"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW() ON UPDATE NOW()"),
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(["plan_id"], ["release_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_release_items_plan_id", "release_items", ["plan_id"])


def downgrade() -> None:
    op.drop_index("ix_release_items_plan_id", table_name="release_items")
    op.drop_table("release_items")
    op.drop_table("release_plans")
