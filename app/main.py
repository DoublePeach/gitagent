import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.logging import setup_logging
from app.core.scheduler import scheduler, setup_scheduler
from app.routers import admin_release, bot_feishu, debug_llm, health

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    if settings.ENABLE_SCHEDULER:
        setup_scheduler()
        if not scheduler.running:
            scheduler.start()
    yield
    if settings.ENABLE_SCHEDULER and scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="发布管理中心",
    version="0.1.0",
    description="接收飞书指令，通过 LLM 解析意图，驱动 GitLab / Zadig 完成发布流程",
    lifespan=lifespan,
    debug=True,   # 生产环境部署前改为 False
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """捕获所有未处理异常，返回结构化 JSON 并记录堆栈，避免 500 空响应。"""
    logger.error(
        "未处理异常 %s %s\n%s",
        request.method,
        request.url,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"error": type(exc).__name__, "detail": str(exc)},
    )


app.include_router(health.router)
app.include_router(admin_release.router, prefix="/api/v1/admin", tags=["Admin Release"])
app.include_router(bot_feishu.router,    prefix="/api/v1/bot",   tags=["Feishu Bot"])
app.include_router(debug_llm.router,     prefix="/api/v1/debug", tags=["LLM Debug"])
