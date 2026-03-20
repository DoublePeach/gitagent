from typing import Tuple, Type

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    # 应用
    APP_ENV: str = "development"
    DEBUG: bool = False
    ENABLE_SCHEDULER: bool = False

    # 数据库（MySQL 异步驱动 aiomysql）
    # 必须在 .env 中配置（不要在代码里硬编码账号密码/内网地址）
    DATABASE_URL: str = ""

    # LLM（阿里云百炼，OpenAI 兼容接口）
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "qwen-plus"
    OPENAI_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # GitLab
    GITLAB_URL: str = ""
    GITLAB_TOKEN: str = ""

    # Zadig
    ZADIG_URL: str = ""
    ZADIG_TOKEN: str = ""

    # 飞书 (Lark)
    LARK_APP_ID: str = ""
    LARK_APP_SECRET: str = ""
    LARK_VERIFICATION_TOKEN: str = ""
    LARK_ENCRYPT_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        # .env 文件优先于系统环境变量（解决本机 OPENAI_API_KEY 等覆盖 .env 的问题）
        return init_settings, dotenv_settings, env_settings, file_secret_settings


settings = Settings()
