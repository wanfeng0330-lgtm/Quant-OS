"""Application settings using pydantic-settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", env_file_encoding="utf-8", extra="ignore")
    host: str = Field(default="localhost", alias="POSTGRES_HOST")
    port: int = Field(default=5432, alias="POSTGRES_PORT")
    user: str = Field(default="quant_os", alias="POSTGRES_USER")
    password: str = Field(default="quant_os_dev_2024", alias="POSTGRES_PASSWORD")
    db: str = Field(default="quant_os", alias="POSTGRES_DB")
    pool_size: int = 20
    max_overflow: int = 10
    # Override URL for SQLite or custom connection strings
    database_url: str = Field(default="", alias="DATABASE_URL")

    @property
    def async_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"

    @property
    def sync_url(self) -> str:
        if self.database_url:
            # Convert async SQLite URL to sync if needed
            url = self.database_url
            if url.startswith("sqlite+aiosqlite://"):
                return url.replace("sqlite+aiosqlite://", "sqlite://")
            return url
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite") if self.database_url else False


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REDIS_")
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    cache_ttl: int = 3600
    key_prefix: str = "quant_os"

    @property
    def url(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db}"


class QdrantSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QDRANT_")
    host: str = "localhost"
    port: int = 6333

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="")
    default_provider: str = Field(default="mimo", alias="LLM_DEFAULT_PROVIDER")
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")
    deepseek_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_MODEL")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="", alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")
    mimo_api_key: str = Field(default="", alias="MIMO_API_KEY")
    mimo_base_url: str = Field(default="https://token-plan-cn.xiaomimimo.com/v1", alias="MIMO_BASE_URL")
    mimo_model: str = Field(default="mimo-v2.5-pro", alias="MIMO_MODEL")
    claude_api_key: str = Field(default="", alias="CLAUDE_API_KEY")
    qwen_api_key: str = Field(default="", alias="QWEN_API_KEY")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout_seconds: int = 120


class DataSourceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="")
    tushare_token: str = Field(default="", alias="TUSHARE_TOKEN")
    akshare_enabled: bool = Field(default=True, alias="AKSHARE_ENABLED")
    primary_provider: str = "akshare"
    fallback_provider: str = "tushare"


class CelerySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CELERY_")
    broker_url: str = "redis://localhost:6379/1"
    result_backend: str = "redis://localhost:6379/2"
    worker_concurrency: int = 4


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", env_file_encoding="utf-8", extra="ignore")
    env: str = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "DEBUG"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]


class Settings:
    """Aggregated application settings."""

    def __init__(self, env_file: str | None = None) -> None:
        kwargs = {}
        if env_file:
            kwargs["_env_file"] = env_file
        self.app = AppSettings(**kwargs)
        self.database = DatabaseSettings(**kwargs)
        self.redis = RedisSettings(**kwargs)
        self.qdrant = QdrantSettings(**kwargs)
        self.llm = LLMSettings(**kwargs)
        self.data_source = DataSourceSettings(**kwargs)
        self.celery = CelerySettings(**kwargs)


def get_settings() -> Settings:
    return Settings()
