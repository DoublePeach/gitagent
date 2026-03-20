"""飞书 HTTP 客户端：封装消息发送、Token 获取等接口。"""
from __future__ import annotations

import json

import httpx

from app.config import settings

LARK_API_BASE = "https://open.feishu.cn/open-apis"


class LarkClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=LARK_API_BASE,
            timeout=15,
            trust_env=False,
        )
        self._tenant_token: str | None = None

    async def _get_tenant_token(self) -> str:
        resp = await self._client.post(
            "/auth/v3/tenant_access_token/internal",
            json={"app_id": settings.LARK_APP_ID, "app_secret": settings.LARK_APP_SECRET},
        )
        resp.raise_for_status()
        self._tenant_token = resp.json()["tenant_access_token"]
        return self._tenant_token

    async def send_text(
        self,
        receive_id: str,
        text: str,
        *,
        receive_id_type: str = "chat_id",
    ) -> dict:
        token = self._tenant_token or await self._get_tenant_token()
        resp = await self._client.post(
            "/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            headers={"Authorization": f"Bearer {token}"},
            json={
                "receive_id": receive_id,
                "msg_type": "text",
                "content": json.dumps({"text": text}, ensure_ascii=False),
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def aclose(self) -> None:
        await self._client.aclose()
