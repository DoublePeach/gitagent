"""LLM 服务：调用阿里云百炼（OpenAI 兼容接口），将自然语言指令解析为结构化意图。

百炼兼容 OpenAI SDK，只需修改 base_url 和 api_key 即可，无需更换 SDK。
推荐模型：qwen-plus（性价比）/ qwen-max（最强）/ qwen-turbo（最快）
"""
import json
import logging

from openai import AsyncOpenAI
from pydantic import ValidationError

from app.config import settings
from app.llm.prompts import SYSTEM_PROMPT, build_user_message
from app.schemas.llm import IntentResult

logger = logging.getLogger(__name__)

# 延迟初始化：首次调用时创建，避免模块导入时读取到被系统环境变量覆盖的错误密钥
_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    """获取（或创建）OpenAI 兼容客户端单例。"""
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )
        logger.info(
            "LLM 客户端已初始化 | base_url=%s | model=%s",
            settings.OPENAI_BASE_URL,
            settings.OPENAI_MODEL,
        )
    return _client


async def parse_intent(
    text: str,
    context: dict | None = None,
) -> IntentResult:
    """将用户自然语言指令解析为 IntentResult。

    Args:
        text:    用户原始输入（来自飞书消息等）。
        context: 可选的上下文字典，例如 {"当前操作人": "张三", "上次计划ID": 42}。

    Returns:
        IntentResult: 经 Pydantic 验证的结构化意图对象。

    Raises:
        ValueError: 当 LLM 返回内容无法解析或验证失败时。
    """
    client = _get_client()
    user_message = build_user_message(text, context)

    logger.debug("LLM 请求 | model=%s | input=%r", settings.OPENAI_MODEL, text)

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=512,
    )

    raw_content = response.choices[0].message.content or ""
    logger.debug("LLM 原始响应: %s", raw_content)

    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        logger.error("LLM 返回内容不是合法 JSON: %s", raw_content)
        raise ValueError(f"LLM 返回内容解析失败: {exc}") from exc

    try:
        result = IntentResult.model_validate(data)
    except ValidationError as exc:
        logger.error("IntentResult 验证失败: %s\n原始数据: %s", exc, data)
        raise ValueError(f"意图结构验证失败: {exc}") from exc

    logger.info(
        "意图解析完成 | intent=%s | needs_clarification=%s",
        result.intent,
        result.needs_clarification,
    )
    return result
