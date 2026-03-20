"""LLM 意图解析相关的 Pydantic 模型。"""
from enum import StrEnum

from pydantic import BaseModel, Field


class IntentType(StrEnum):
    CREATE_RELEASE = "create_release"        # 创建一个新发布计划
    REGISTER_BRANCH = "register_branch"      # 将分支/仓库注册到已有计划
    TRIGGER_DEPLOY = "trigger_deploy"        # 立即触发某个计划的部署
    QUERY_STATUS = "query_status"            # 查询计划/部署状态
    CANCEL_RELEASE = "cancel_release"        # 取消发布计划
    UNKNOWN = "unknown"                      # 无法识别


class IntentParams(BaseModel):
    """从用户自然语言中提取的结构化参数，所有字段均可为空。"""

    # --- 发布计划相关 ---
    system_name: str | None = Field(None, description="系统/项目名称，如 WMS、OMS")
    environment: str | None = Field(None, description="目标环境：dev / staging / production")
    scheduled_at: str | None = Field(
        None,
        description="计划执行时间，ISO-8601 字符串或自然语言描述，如 '今晚6点'、'2026-03-20T18:00:00'",
    )
    plan_name: str | None = Field(None, description="发布计划名称")

    # --- 发布项相关 ---
    plan_id: int | None = Field(None, description="已存在的发布计划 ID")
    repo_name: str | None = Field(None, description="代码仓库名称")
    branch_name: str | None = Field(None, description="分支名称")
    commit_sha: str | None = Field(None, description="可选的提交 SHA")


class IntentResult(BaseModel):
    """LLM 解析后返回的完整意图结果。"""

    intent: IntentType = Field(..., description="识别出的意图类型")
    params: IntentParams = Field(default_factory=IntentParams, description="提取的结构化参数")
    needs_clarification: bool = Field(
        False, description="若信息不足以完成操作则为 True"
    )
    clarification_question: str | None = Field(
        None, description="需要向用户追问的具体问题"
    )
