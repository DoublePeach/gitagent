"""飞书事件回调相关的 Pydantic 模型。"""
from pydantic import BaseModel


class LarkEventHeader(BaseModel):
    event_id: str
    event_type: str
    app_id: str
    tenant_key: str


class LarkMessageEvent(BaseModel):
    header: LarkEventHeader
    event: dict
