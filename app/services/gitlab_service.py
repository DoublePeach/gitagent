"""GitLab 服务：封装最小可用的 GitLab 真实操作。"""
from __future__ import annotations

from app.integrations.gitlab_client import GitLabClient


class GitLabService:
    def __init__(self, client: GitLabClient | None = None) -> None:
        self.client = client or GitLabClient()

    async def resolve_project_ref(self, repo_name: str) -> str:
        """将 repo_name 解析为 GitLab 项目标识。

        优先策略：
        1. 若 repo_name 已是 `group/project`，直接尝试获取。
        2. 否则搜索项目名，并要求结果唯一或精确匹配。
        """
        if "/" in repo_name:
            project = await self.client.get_project(repo_name)
            return project["path_with_namespace"]

        candidates = await self.client.search_projects(repo_name)
        exact = [
            item for item in candidates
            if item.get("path") == repo_name or item.get("name") == repo_name
        ]
        if len(exact) == 1:
            return exact[0]["path_with_namespace"]
        if len(candidates) == 1:
            return candidates[0]["path_with_namespace"]
        if not candidates:
            raise ValueError(f"GitLab 中未找到仓库：{repo_name}")
        raise ValueError(
            f"仓库名 {repo_name} 匹配到多个 GitLab 项目，请改用 group/project 形式。"
        )

    async def get_latest_commit(self, repo_name: str, branch_name: str) -> dict:
        project_ref = await self.resolve_project_ref(repo_name)
        branch = await self.client.get_branch(project_ref, branch_name)
        commit = branch["commit"]
        return {
            "project_ref": project_ref,
            "branch_name": branch["name"],
            "commit_sha": commit["id"],
            "short_sha": commit.get("short_id"),
            "commit_title": commit.get("title"),
            "web_url": commit.get("web_url"),
        }

    async def trigger_pipeline(self, repo_name: str, ref: str) -> dict:
        project_ref = await self.resolve_project_ref(repo_name)
        pipeline = await self.client.trigger_pipeline(project_ref, ref)
        return {
            "project_ref": project_ref,
            "pipeline_id": pipeline.get("id"),
            "status": pipeline.get("status"),
            "web_url": pipeline.get("web_url"),
        }

    async def aclose(self) -> None:
        await self.client.aclose()
