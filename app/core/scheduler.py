"""应用内调度器：扫描到期计划并自动执行。"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db.session import AsyncSessionLocal
from app.services import release_service

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")


async def scan_and_execute_due_plans() -> None:
    async with AsyncSessionLocal() as db:
        plans = await release_service.execute_due_plans(db)
        if plans:
            logger.info("调度器已执行 %d 个到期计划", len(plans))


def setup_scheduler() -> None:
    if scheduler.get_job("scan_due_release_plans"):
        return
    scheduler.add_job(
        scan_and_execute_due_plans,
        trigger="interval",
        minutes=1,
        id="scan_due_release_plans",
        replace_existing=True,
    )
