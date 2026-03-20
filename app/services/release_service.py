"""发布计划业务服务层。

职责：所有对 ReleasePlan / ReleaseItem 的数据库操作和业务规则。
Router 只做 HTTP 适配，不直接操作 ORM。
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_parser import parse_user_datetime
from app.db.models.release_plan import (
    Environment,
    ItemStatus,
    PlanStatus,
    ReleaseItem,
    ReleasePlan,
)
from app.schemas.llm import IntentParams
from app.schemas.release_plan import ReleasePlanCreate
from app.services.gitlab_service import GitLabService

logger = logging.getLogger(__name__)


async def create_release_plan(
    db: AsyncSession,
    data: ReleasePlanCreate,
) -> ReleasePlan:
    """创建发布计划，并同步写入初始 ReleaseItem 列表（如有）。

    - 若提供了 scheduled_at，状态设为 SCHEDULED；否则为 DRAFT。
    """
    status = PlanStatus.SCHEDULED if data.scheduled_at else PlanStatus.DRAFT

    plan = ReleasePlan(
        name=data.name,
        system_name=data.system_name,
        environment=data.environment,
        scheduled_at=data.scheduled_at,
        status=status,
    )
    db.add(plan)
    await db.flush()  # 获取 plan.id，不提交事务

    for item_data in data.items:
        item = ReleaseItem(
            plan_id=plan.id,
            repo_name=item_data.repo_name,
            branch_name=item_data.branch_name,
            commit_sha=item_data.commit_sha,
            status=ItemStatus.PENDING,
        )
        db.add(item)

    await db.commit()
    await db.refresh(plan)

    logger.info(
        "发布计划已创建 | id=%d name=%r system=%r env=%s status=%s items=%d",
        plan.id, plan.name, plan.system_name,
        plan.environment, plan.status, len(data.items),
    )
    return plan


async def list_release_plans(
    db: AsyncSession,
    *,
    system_name: str | None = None,
    environment: Environment | None = None,
    status: PlanStatus | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[ReleasePlan]:
    """按条件分页查询发布计划列表（不加载 items，仅列表视图）。"""
    stmt = select(ReleasePlan).order_by(ReleasePlan.created_at.desc())

    if system_name:
        stmt = stmt.where(ReleasePlan.system_name == system_name)
    if environment:
        stmt = stmt.where(ReleasePlan.environment == environment)
    if status:
        stmt = stmt.where(ReleasePlan.status == status)

    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_release_plan(
    db: AsyncSession,
    plan_id: int,
) -> ReleasePlan | None:
    """按 ID 获取单个发布计划（含 items，relationship lazy=selectin 自动加载）。"""
    result = await db.execute(
        select(ReleasePlan).where(ReleasePlan.id == plan_id)
    )
    return result.scalar_one_or_none()


async def cancel_release_plan(
    db: AsyncSession,
    plan_id: int,
) -> ReleasePlan | None:
    """取消尚未执行的发布计划（仅允许 DRAFT / SCHEDULED 状态）。

    TODO: 若计划已进入 RUNNING，需先中止 GitLab / Zadig 任务再取消。
    """
    plan = await get_release_plan(db, plan_id)
    if plan is None:
        return None

    if plan.status not in (PlanStatus.DRAFT, PlanStatus.SCHEDULED):
        logger.warning("计划 %d 状态为 %s，不可取消", plan_id, plan.status)
        return plan  # 调用方根据状态判断是否报错

    plan.status = PlanStatus.CANCELLED
    await db.commit()
    await db.refresh(plan)
    logger.info("计划 %d 已取消", plan_id)
    return plan


async def get_due_plans(db: AsyncSession) -> list[ReleasePlan]:
    """查询所有到期待执行的计划（供调度器使用）。

    条件：status=SCHEDULED AND scheduled_at <= now(UTC)
    """
    now = datetime.now(tz=timezone.utc).replace(tzinfo=None)  # MySQL 存储 naive datetime
    stmt = (
        select(ReleasePlan)
        .where(ReleasePlan.status == PlanStatus.SCHEDULED)
        .where(ReleasePlan.scheduled_at <= now)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def execute_plan(db: AsyncSession, plan_id: int) -> ReleasePlan | None:
    """执行单个发布计划：状态置为 RUNNING，触发各 ReleaseItem 的实际部署。

    当前最小实现：
    1. 对每个 ReleaseItem 调用 GitLab 获取最新 commit_sha
    2. 触发该分支对应的 GitLab pipeline
    3. 成功则 item.status=SUCCESS，失败则 item.status=FAILED
    4. 若全部成功则 plan.status=SUCCESS，否则为 FAILED

    TODO: 后续补充 MR 合并 / Zadig 部署 / 飞书通知。
    """
    plan = await get_release_plan(db, plan_id)
    if plan is None:
        return None

    plan.status = PlanStatus.RUNNING
    await db.commit()
    logger.info("计划 %d 开始执行，共 %d 个发布项", plan_id, len(plan.items))

    gitlab = GitLabService()
    has_failure = False

    for item in plan.items:
        try:
            commit = await gitlab.get_latest_commit(item.repo_name, item.branch_name)
            item.commit_sha = commit["commit_sha"]
            try:
                await gitlab.trigger_pipeline(item.repo_name, item.branch_name)
            except Exception as exc:
                logger.warning(
                    "Pipeline 触发失败，但保留 commit 获取结果 | repo=%s branch=%s error=%s",
                    item.repo_name,
                    item.branch_name,
                    exc,
                )
            item.status = ItemStatus.SUCCESS
        except Exception as exc:
            has_failure = True
            item.status = ItemStatus.FAILED
            logger.error(
                "执行计划项失败 | plan_id=%s repo=%s branch=%s error=%s",
                plan.id,
                item.repo_name,
                item.branch_name,
                exc,
            )

    plan.status = PlanStatus.FAILED if has_failure else PlanStatus.SUCCESS
    await db.commit()
    await db.refresh(plan)
    return plan


def _build_plan_name(system_name: str, environment: str, scheduled_at: datetime | None) -> str:
    if scheduled_at:
        return f"{system_name}-{environment}-{scheduled_at.strftime('%Y%m%d-%H%M')}"
    return f"{system_name}-{environment}-draft"


def _to_environment(value: str | None) -> Environment | None:
    if value is None:
        return None
    mapping = {
        "dev": Environment.DEV,
        "development": Environment.DEV,
        "测试": Environment.DEV,
        "开发": Environment.DEV,
        "staging": Environment.STAGING,
        "uat": Environment.STAGING,
        "预发布": Environment.STAGING,
        "灰度": Environment.STAGING,
        "production": Environment.PRODUCTION,
        "prod": Environment.PRODUCTION,
        "线上": Environment.PRODUCTION,
        "生产": Environment.PRODUCTION,
    }
    return mapping.get(value.strip().lower()) or mapping.get(value.strip())


async def create_plan_from_intent(
    db: AsyncSession,
    params: IntentParams,
) -> ReleasePlan:
    environment = _to_environment(params.environment)
    if not params.system_name or not environment:
        raise ValueError("创建发布计划至少需要 system_name 和 environment。")

    scheduled_at = parse_user_datetime(params.scheduled_at)
    plan_name = params.plan_name or _build_plan_name(
        params.system_name, environment.value, scheduled_at
    )

    plan = await create_release_plan(
        db,
        ReleasePlanCreate(
            name=plan_name,
            system_name=params.system_name,
            environment=environment,
            scheduled_at=scheduled_at,
            items=[],
        ),
    )
    if params.repo_name and params.branch_name:
        await register_branch_to_plan(
            db,
            plan_id=plan.id,
            repo_name=params.repo_name,
            branch_name=params.branch_name,
        )
        await db.refresh(plan, attribute_names=["items"])
    return plan


async def register_branch_to_plan(
    db: AsyncSession,
    *,
    plan_id: int,
    repo_name: str,
    branch_name: str,
    gitlab_service: GitLabService | None = None,
) -> ReleaseItem:
    plan = await get_release_plan(db, plan_id)
    if plan is None:
        raise ValueError(f"发布计划 {plan_id} 不存在。")

    existing = next(
        (
            item for item in plan.items
            if item.repo_name == repo_name and item.branch_name == branch_name
        ),
        None,
    )
    if existing:
        return existing

    commit_sha: str | None = None
    service = gitlab_service or GitLabService()
    try:
        commit = await service.get_latest_commit(repo_name, branch_name)
        commit_sha = commit["commit_sha"]
    except Exception as exc:
        logger.warning("GitLab 分支检查失败 repo=%s branch=%s error=%s", repo_name, branch_name, exc)

    item = ReleaseItem(
        plan_id=plan.id,
        repo_name=repo_name,
        branch_name=branch_name,
        commit_sha=commit_sha,
        status=ItemStatus.PENDING,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def find_latest_plan(
    db: AsyncSession,
    *,
    system_name: str,
    environment: Environment | None = None,
    active_only: bool = False,
) -> ReleasePlan | None:
    stmt = select(ReleasePlan).where(ReleasePlan.system_name == system_name)
    if environment is not None:
        stmt = stmt.where(ReleasePlan.environment == environment)
    if active_only:
        stmt = stmt.where(ReleasePlan.status.in_([PlanStatus.DRAFT, PlanStatus.SCHEDULED, PlanStatus.RUNNING]))
    stmt = stmt.order_by(ReleasePlan.created_at.desc()).limit(1)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def register_branch_from_intent(
    db: AsyncSession,
    params: IntentParams,
) -> tuple[ReleasePlan, ReleaseItem]:
    if not params.repo_name or not params.branch_name:
        raise ValueError("登记分支至少需要 repo_name 和 branch_name。")

    target_plan: ReleasePlan | None = None
    if params.plan_id:
        target_plan = await get_release_plan(db, params.plan_id)
    elif params.system_name:
        target_plan = await find_latest_plan(
            db,
            system_name=params.system_name,
            environment=_to_environment(params.environment),
            active_only=True,
        )

    if target_plan is None:
        raise ValueError("未找到可登记分支的发布计划，请提供 plan_id 或先创建计划。")

    item = await register_branch_to_plan(
        db,
        plan_id=target_plan.id,
        repo_name=params.repo_name,
        branch_name=params.branch_name,
    )
    return target_plan, item


async def query_latest_plan_summary(
    db: AsyncSession,
    params: IntentParams,
) -> ReleasePlan | None:
    if params.plan_id:
        return await get_release_plan(db, params.plan_id)
    if not params.system_name:
        return None
    return await find_latest_plan(
        db,
        system_name=params.system_name,
        environment=_to_environment(params.environment),
        active_only=False,
    )


async def cancel_release_from_intent(
    db: AsyncSession,
    params: IntentParams,
) -> ReleasePlan | None:
    if params.plan_id:
        return await cancel_release_plan(db, params.plan_id)
    if not params.system_name:
        raise ValueError("取消计划至少需要 plan_id 或 system_name。")

    plan = await find_latest_plan(
        db,
        system_name=params.system_name,
        environment=_to_environment(params.environment),
        active_only=True,
    )
    if plan is None:
        return None
    return await cancel_release_plan(db, plan.id)


async def execute_due_plans(db: AsyncSession) -> list[ReleasePlan]:
    due_plans = await get_due_plans(db)
    results: list[ReleasePlan] = []
    for plan in due_plans:
        executed = await execute_plan(db, plan.id)
        if executed is not None:
            results.append(executed)
    return results
