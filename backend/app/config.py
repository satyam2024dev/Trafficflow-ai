"""Backend settings, read from environment variables / .env (never hard-coded)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", REPO_ROOT / "backend" / ".env"),
        extra="ignore",
    )

    postgres_user: str = "trafficflow"
    postgres_password: str = ""
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "trafficflow"
    database_url_override: str | None = Field(default=None, alias="DATABASE_URL")

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    video_dir: str = "videos"
    allowed_video_extensions: str = ".mp4,.avi,.mov,.mkv,.webm"
    app_timezone: str = "UTC"           # used for "today", hourly buckets, daily trends
    auto_create_tables: bool = True      # create tables from SQLAlchemy models if missing
    auto_seed: bool = True               # insert default areas/cameras/lines if DB is empty
    log_level: str = "INFO"

    @computed_field  # type: ignore[misc]
    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return (f"postgresql+psycopg2://{quote_plus(self.postgres_user)}:{quote_plus(self.postgres_password)}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def video_path(self) -> Path:
        p = Path(self.video_dir)
        return (p if p.is_absolute() else REPO_ROOT / p).resolve()

    @property
    def video_extensions(self) -> set[str]:
        return {e.strip().lower() for e in self.allowed_video_extensions.split(",") if e.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
