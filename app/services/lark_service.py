"""飞书服务：解析事件消息、回复消息、发送通知卡片。"""


class LarkService:
    async def handle_event(self, event: dict) -> None:
        raise NotImplementedError

    async def send_message(self, chat_id: str, text: str) -> None:
        raise NotImplementedError
