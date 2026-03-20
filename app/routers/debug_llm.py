"""LLM 调试接口：开发阶段快速测试 Prompt 和意图解析。"""
import logging
import traceback

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.schemas.llm import IntentResult
from app.services.llm_service import parse_intent

router = APIRouter()
logger = logging.getLogger(__name__)


class DebugRequest(BaseModel):
    text: str
    context: dict | None = None


@router.get("/config", summary="查看服务器加载的 LLM 配置（仅开发用）")
async def debug_config():
    from app.config import settings
    return {
        "OPENAI_API_KEY_PREFIX": settings.OPENAI_API_KEY[:12] + "...",
        "OPENAI_MODEL": settings.OPENAI_MODEL,
        "OPENAI_BASE_URL": settings.OPENAI_BASE_URL,
    }


@router.post("/llm/parse", response_model=IntentResult, summary="调试意图解析")
async def debug_parse(req: DebugRequest) -> IntentResult:
    """接收自然语言文本，返回 LLM 解析后的结构化意图（仅供开发调试）。"""
    logger.info("LLM 调试请求: text=%r", req.text)
    try:
        result = await parse_intent(req.text, req.context)
        logger.info("LLM 调试成功: intent=%s", result.intent)
        return result
    except Exception as exc:
        logger.error("LLM 调试失败:\n%s", traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail={"error": type(exc).__name__, "message": str(exc)},
        ) from exc
