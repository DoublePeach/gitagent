"""Zadig HTTP 客户端：基于 httpx 封装 REST API 调用。"""
import httpx

from app.config import settings


class ZadigClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.ZADIG_URL,
            headers={"Authorization": f"Bearer {settings.ZADIG_TOKEN}"},
            timeout=30,
        )

    async def get(self, path: str, **kwargs) -> dict:
        resp = await self._client.get(path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def post(self, path: str, **kwargs) -> dict:
        resp = await self._client.post(path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def aclose(self) -> None:
        await self._client.aclose()
