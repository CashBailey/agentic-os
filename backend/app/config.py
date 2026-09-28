"""Backend configuration (pydantic-settings)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    DATABASE_URL: str = (
        "postgresql+psycopg://agentos:agentos@127.0.0.1:5432/agentos"
    )
    APP_VERSION: str = "0.1.0"
    CORS_ORIGIN: str = "http://localhost:5173"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384

    APPROVAL_TTL_SECONDS: int = 300
    WORKER_HEARTBEAT_SECONDS: int = 30
    WORKER_STUCK_SECONDS: int = 90

    BIND_HOST: str = "127.0.0.1"
    BIND_PORT: int = 8000

    AGENT_OS_ROOT: str = "/home/raptor-lab-laptop2/AgenticOS/agentic-os/agent-os"


settings = Settings()


def sync_database_url() -> str:
    """Return a psycopg-sync URL for the worker (no +async driver)."""
    url = settings.DATABASE_URL
    if url.startswith("postgresql+psycopg://"):
        return url
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    return url
