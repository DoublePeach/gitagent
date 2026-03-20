"""飞书机器人事件回调路由。"""
from __future__ import annotations

import base64
import hashlib
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from Crypto.Cipher import AES

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.integrations.lark_client import LarkClient
from app.schemas.llm import IntentResult, IntentType
from app.services import release_service
from app.services.llm_service import parse_intent

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 飞书事件 Pydantic 模型（精简版，仅保留必要字段）
# ---------------------------------------------------------------------------

class _FeishuSenderId(BaseModel):
    open_id: str | None = None
    user_id: str | None = None
    union_id: str | None = None


class _FeishuSender(BaseModel):
    sender_id: _FeishuSenderId = Field(default_factory=_FeishuSenderId)
    sender_type: str = "user"


class _FeishuMessage(BaseModel):
    message_id: str | None = None
    chat_id: str | None = None
    chat_type: str | None = None       # "p2p" | "group"
    message_type: str | None = None    # "text" | "post" | ...
    content: str | None = None         # JSON 字符串，如 '{"text":"hello"}'


class _FeishuEventBody(BaseModel):
    sender: _FeishuSender = Field(default_factory=_FeishuSender)
    message: _FeishuMessage = Field(default_factory=_FeishuMessage)


class FeishuEventPayload(BaseModel):
    """飞书事件推送的顶层结构（Event API 2.0）。"""

    # URL 验证时飞书只发 challenge + token + type，其余字段缺省
    challenge: str | None = None
    encrypt: str | None = None
    token: str | None = None
    type: str | None = None            # "url_verification" | None

    schema_version: str | None = Field(None, alias="schema")
    event: _FeishuEventBody | None = None

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _extract_text(message: _FeishuMessage) -> str | None:
    """从飞书消息的 content JSON 字符串中提取纯文本。"""
    if not message.content:
        return None
    try:
        data = json.loads(message.content)
        return data.get("text", "").strip() or None
    except (json.JSONDecodeError, AttributeError):
        logger.warning("无法解析消息 content: %r", message.content)
        return None


def _pkcs7_unpad(data: bytes) -> bytes:
    if not data:
        return data
    pad_len = data[-1]
    if pad_len < 1 or pad_len > 16:
        return data
    return data[:-pad_len]


def _decrypt_feishu_encrypt(encrypt_text: str, encrypt_key: str) -> dict:
    """按飞书文档解密 `encrypt` 字段。

    算法：
    - key = sha256(encrypt_key)
    - raw = base64_decode(encrypt_text)
    - iv = raw[:16]
    - ciphertext = raw[16:]
    - AES-256-CBC 解密
    """
    raw = base64.b64decode(encrypt_text)
    iv = raw[:16]
    ciphertext = raw[16:]
    aes_key = hashlib.sha256(encrypt_key.encode("utf-8")).digest()
    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    decrypted = _pkcs7_unpad(cipher.decrypt(ciphertext)).decode("utf-8")
    return json.loads(decrypted)


def _format_plan(plan) -> str:
    scheduled = plan.scheduled_at.strftime("%Y-%m-%d %H:%M") if plan.scheduled_at else "未设置"
    environment = getattr(plan.environment, "value", plan.environment)
    status = getattr(plan.status, "value", plan.status)
    return (
        f"计划ID：{plan.id}\n"
        f"名称：{plan.name}\n"
        f"系统：{plan.system_name}\n"
        f"环境：{environment}\n"
        f"时间：{scheduled}\n"
        f"状态：{status}"
    )


def _format_plan_detail(plan) -> str:
    lines = [_format_plan(plan), f"发布项数量：{len(plan.items)}"]
    for idx, item in enumerate(plan.items[:10], start=1):
        sha = item.commit_sha[:8] if item.commit_sha else "未记录"
        item_status = getattr(item.status, "value", item.status)
        lines.append(
            f"{idx}. {item.repo_name}:{item.branch_name} | {item_status} | commit={sha}"
        )
    return "\n".join(lines)


async def _dispatch_intent(
    db,
    intent_result: IntentResult,
) -> str:
    params = intent_result.params

    if intent_result.needs_clarification:
        return intent_result.clarification_question or "请提供更多信息，我才能帮您完成操作。"

    match intent_result.intent:
        case IntentType.CREATE_RELEASE:
            plan = await release_service.create_plan_from_intent(db, params)
            return "已创建发布计划：\n" + _format_plan_detail(plan)

        case IntentType.REGISTER_BRANCH:
            plan, item = await release_service.register_branch_from_intent(db, params)
            sha = item.commit_sha[:8] if item.commit_sha else "未获取"
            return (
                f"已登记分支到计划 {plan.id}\n"
                f"仓库：{item.repo_name}\n"
                f"分支：{item.branch_name}\n"
                f"commit：{sha}"
            )

        case IntentType.QUERY_STATUS:
            plan = await release_service.query_latest_plan_summary(db, params)
            if plan is None:
                return "未查询到符合条件的发布计划。"
            return "当前计划状态如下：\n" + _format_plan_detail(plan)

        case IntentType.CANCEL_RELEASE:
            plan = await release_service.cancel_release_from_intent(db, params)
            if plan is None:
                return "未找到可取消的发布计划。"
            return f"已取消发布计划 {plan.id}，当前状态：{getattr(plan.status, 'value', plan.status)}"

        case IntentType.TRIGGER_DEPLOY:
            target_plan = None
            if params.plan_id:
                target_plan = await release_service.get_release_plan(db, params.plan_id)
            elif params.system_name:
                target_plan = await release_service.find_latest_plan(
                    db,
                    system_name=params.system_name,
                    environment=release_service._to_environment(params.environment),
                    active_only=True,
                )
            if target_plan is None:
                return "未找到可执行的发布计划，请提供 plan_id 或先创建计划。"
            executed = await release_service.execute_plan(db, target_plan.id)
            if executed is None:
                return "执行失败：目标计划不存在。"
            return f"计划 {executed.id} 已开始执行，当前状态：{getattr(executed.status, 'value', executed.status)}"

        case IntentType.UNKNOWN | _:
            return (
                "抱歉，我没能理解您的指令。你可以这样说：\n"
                "- 今晚 6 点将 WMS 发到生产环境\n"
                "- 把 wms-service 的 feature/xxx 加到 12 号计划里\n"
                "- 查一下 WMS 生产环境最新发布状态\n"
                "- 取消 WMS 最新的发布计划"
            )


# ---------------------------------------------------------------------------
# 路由处理器
# ---------------------------------------------------------------------------

@router.post("/feishu/events", summary="飞书事件回调")
async def feishu_events(request: Request) -> dict:
    """
    飞书事件推送入口。

    流程：
    1. URL 验证：直接返回 challenge（飞书要求）。
    2. 消息事件：提取文本 → LLM 解析意图 → 构造回复。

    TODO: 实现飞书签名验证（X-Lark-Signature header）。
    TODO: 实现消息去重（message_id 幂等检查）。
    TODO: 异步回复（先返回 200，再通过飞书 API 主动推送回复）。
    """
    # --- 1. 原始 body 解析 ---
    try:
        body_bytes = await request.body()
        body_text = body_bytes.decode("utf-8")
        raw_body = json.loads(body_text)
    except Exception:
        logger.error("飞书回调请求体解析失败")
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    logger.info("飞书原始回调体: %s", body_text)

    # 若配置了 Encrypt Key 且回调体包含 encrypt，则先解密
    if raw_body.get("encrypt") and settings.LARK_ENCRYPT_KEY:
        try:
            raw_body = _decrypt_feishu_encrypt(raw_body["encrypt"], settings.LARK_ENCRYPT_KEY)
            logger.info("飞书解密后的回调体: %s", json.dumps(raw_body, ensure_ascii=False))
        except Exception as exc:
            logger.error("飞书 encrypt 解密失败: %s", exc)
            raise HTTPException(status_code=400, detail="Invalid encrypted payload")

    payload = FeishuEventPayload.model_validate(raw_body)

    # --- 2. URL 验证握手 ---
    # 飞书官方要求：收到 challenge 后 1 秒内原样返回。
    # 实际上有些场景只带 challenge，不一定严格依赖 type 字段，因此这里放宽判断。
    if payload.challenge:
        logger.info(
            "飞书 URL 验证请求，type=%s challenge=%s",
            payload.type,
            payload.challenge,
        )
        return JSONResponse(content={"challenge": payload.challenge})

    if payload.token and settings.LARK_VERIFICATION_TOKEN:
        if payload.token != settings.LARK_VERIFICATION_TOKEN:
            logger.warning("飞书 verification token 不匹配")
            raise HTTPException(status_code=401, detail="Invalid verification token")

    # --- 3. 提取消息内容 ---
    event = payload.event
    if not event or not event.message:
        logger.debug("收到非消息类事件，忽略")
        return {"msg": "ignored"}

    message = event.message
    user_open_id = event.sender.sender_id.open_id
    chat_id = message.chat_id

    logger.info(
        "收到飞书消息 | message_id=%s | chat_id=%s | user=%s | type=%s",
        message.message_id,
        chat_id,
        user_open_id,
        message.message_type,
    )

    if event.sender.sender_type != "user":
        logger.debug("非用户消息，忽略")
        return {"msg": "ignored"}

    # 目前只处理文本消息
    if message.message_type != "text":
        logger.debug("非文本消息（type=%s），跳过", message.message_type)
        return {"msg": "non-text ignored"}

    text = _extract_text(message)
    if not text:
        logger.warning("文本内容为空，跳过")
        return {"msg": "empty text"}

    # --- 4. LLM 意图解析 ---
    context = {
        "user_open_id": user_open_id,
        "chat_id": chat_id,
        "chat_type": message.chat_type,
    }
    async with AsyncSessionLocal() as db:
        try:
            intent_result = await parse_intent(text, context)
            reply_text = await _dispatch_intent(db, intent_result)
        except ValueError as exc:
            logger.error("消息处理失败: %s", exc)
            intent_result = None
            reply_text = f"处理失败：{exc}"

    logger.info(
        "意图处理完成 | intent=%s | needs_clarification=%s | reply_preview=%.50r",
        intent_result.intent if intent_result else "error",
        intent_result.needs_clarification if intent_result else False,
        reply_text,
    )

    # --- 5. 通过飞书 Open API 真正回复消息 ---
    # TODO: 后续可改为异步后台发送，当前为了可测性直接同步发送
    send_result: dict | None = None
    if chat_id:
        lark_client = LarkClient()
        try:
            send_result = await lark_client.send_text(
                chat_id,
                reply_text,
                receive_id_type="chat_id",
            )
        except Exception as exc:
            logger.error("飞书发送回复失败 chat_id=%s error=%s", chat_id, exc)
        finally:
            await lark_client.aclose()

    return {
        "ok": True,
        "reply": reply_text,
        "intent": intent_result.intent if intent_result else "error",
        "params": intent_result.params.model_dump(exclude_none=True) if intent_result else {},
        "needs_clarification": intent_result.needs_clarification if intent_result else False,
        "sent": bool(send_result),
    }
