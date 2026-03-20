"""飞书机器人 Webhook：接收事件回调，转交 LarkService 处理。"""
from fastapi import APIRouter, Request

router = APIRouter()


@router.post("/lark/event", summary="飞书事件回调")
async def lark_event(request: Request):
    # TODO: 验签 -> LarkService.handle_event()
    body = await request.json()
    return {"challenge": body.get("challenge", "")}
