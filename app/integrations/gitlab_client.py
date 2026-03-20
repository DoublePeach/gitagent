"""GitLab HTTP 客户端：基于 httpx 封装 REST API 调用。"""
from __future__ import annotations

from urllib.parse import quote

import httpx

from app.config import settings


def _build_gitlab_api_base() -> str:
    base = settings.GITLAB_URL.rstrip("/")
    if not base.endswith("/api/v4"):
        base = f"{base}/api/v4"
    return base


class GitLabClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=_build_gitlab_api_base(),
            headers={"PRIVATE-TOKEN": settings.GITLAB_TOKEN},
            timeout=30,
            trust_env=False,
        )

    async def get(self, path: str, **kwargs) -> dict | list:
        resp = await self._client.get(path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def post(self, path: str, **kwargs) -> dict | list:
        resp = await self._client.post(path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def search_projects(self, keyword: str) -> list[dict]:
        data = await self.get("/projects", params={"search": keyword, "simple": True, "per_page": 20})
        return list(data)

    async def get_project(self, project_ref: str) -> dict:
        encoded = quote(project_ref, safe="")
        data = await self.get(f"/projects/{encoded}")
        return dict(data)

    async def get_branch(self, project_ref: str, branch_name: str) -> dict:
        project_encoded = quote(project_ref, safe="")
        branch_encoded = quote(branch_name, safe="")
        data = await self.get(f"/projects/{project_encoded}/repository/branches/{branch_encoded}")
        return dict(data)

    async def trigger_pipeline(self, project_ref: str, ref: str) -> dict:
        project_encoded = quote(project_ref, safe="")
        data = await self.post(
            f"/projects/{project_encoded}/pipeline",
            data={"ref": ref},
        )
        return dict(data)

    async def aclose(self) -> None:
        await self._client.aclose()
