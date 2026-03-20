"""Zadig 服务：封装工作流执行、环境查询等操作。"""


class ZadigService:
    async def run_workflow(self, workflow_name: str, env: str) -> dict:
        raise NotImplementedError
