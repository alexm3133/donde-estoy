"""Application settings, read from environment variables (prefix ``DE_``)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DE_", env_file=".env", extra="ignore")

    #: SQLAlchemy async URL. SQLite for local dev, PostgreSQL in production.
    database_url: str = "sqlite+aiosqlite:///./donde_estoy.db"
    #: Create tables on startup instead of relying on Alembic (tests, quick demos).
    auto_create_tables: bool = False

    #: Public base URL of the *frontend*; share links are built from it.
    public_url: str = "http://localhost:5173"
    #: Comma-separated origins allowed to call the API from a browser.
    cors_origins: str = "http://localhost:5173"

    #: Session lifetime: default and the maximum a runner may ask for.
    default_session_hours: float = 8.0
    max_session_hours: float = 24.0
    #: After arrival the link keeps working this long, then everything is purged.
    finished_grace_minutes: int = 60
    #: How often the background task purges expired sessions.
    cleanup_interval_seconds: int = 60

    #: Upload limit for GPX files.
    max_gpx_bytes: int = 5_000_000
    #: Sessions one IP address may create per hour (0 disables the limit).
    create_rate_limit_per_hour: int = 30

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
