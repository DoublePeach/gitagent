"""意图解析器：对外暴露简洁入口，内部委托给 llm_service。"""
from app.schemas.llm import IntentResult
from app.services.llm_service import parse_intent


async def parse(text: str, context: dict | None = None) -> IntentResult:
    """快捷入口，供 router / bot handler 直接调用。"""
    return await parse_intent(text, context)
