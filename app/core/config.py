"""应用配置：一律从环境变量 / .env 读取，代码里不出现魔法值。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "FastAPI Starter"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    database_url: str = "sqlite+aiosqlite:///./app.db"
    auto_create_tables: bool = True
    db_echo: bool = False

    secret_key: str = "dev-only-insecure-secret-key-please-change"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    """缓存实例：整个进程只解析一次配置。"""
    return Settings()


settings = get_settings()
