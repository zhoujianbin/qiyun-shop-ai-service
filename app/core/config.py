from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    app_name: str = "栖云智家企业电商基础平台"
    app_version: str = "1.0.0"
    tenant_id: int = 1
    database_url: str = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/qiyun_shop_dev"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 14
    cors_origins: str = "http://localhost:5173"
    payment_provider: str = "mock"
    demo_mode: bool = True
    storage_backend: str = "local"
    storage_local_dir: str = "./var/uploads"
    log_level: str = "INFO"
    max_upload_mb: int = 20

    # 二期：知识库向量化
    embedding_provider: str = "auto"          # auto | bge | fake；auto 在 APP_ENV=test 时用 fake
    embedding_model_name: str = "BAAI/bge-small-zh-v1.5"
    embedding_model_path: str | None = None   # 指定离线模型目录时不再联网下载
    embedding_dim: int = 512
    embedding_query_prefix: str = "为这个句子生成表示以用于检索相关文章："
    hf_home: str = "./var/models"

    # 二期：知识库审核
    knowledge_allow_self_review: bool = True   # 单人开发默认开；企业上线可视规模关闭

    # 三期：智能客服 / 大模型（OpenAI 兼容端点；APP_ENV=test 时自动 fake）
    llm_provider: str = "auto"                 # auto | openai | fake
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-flash"
    llm_api_key: str = ""
    llm_timeout_seconds: int = 60
    llm_max_tokens: int = 800
    llm_temperature: float = 0.2
    assistant_context_rounds: int = 6
    assistant_message_max_chars: int = 2000
    assistant_rate_limit_per_minute: int = 20
    assistant_retention_days: int = 90
    assistant_use_llm_planner: bool = False      # 三期无工具，默认关；四期有工具时再打开
    assistant_relevance_min_ratio: float = 0.2   # 问题与 top 命中关键词重合度下限

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    @property
    def is_prod(self) -> bool:
        return self.app_env.lower() in ("prod", "production")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
