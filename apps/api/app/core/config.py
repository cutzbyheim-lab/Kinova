"""Environment-based configuration. Every setting can be overridden by an env var."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "KINOVA"
    environment: str = "local"

    database_url: str = "postgresql+psycopg://kinova:kinova@localhost:5432/kinova"
    redis_url: str = "redis://localhost:6379/0"
    storage_dir: Path = Path("./data/storage")
    secret_key: str = "change-me-to-a-long-random-string"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Claude
    anthropic_api_key: str = ""
    model_fast: str = "claude-haiku-5-5"
    model_smart: str = "claude-sonnet-5-5"
    # USD per million tokens (input, output). Haiku is listed "from" $0.10/$0.50;
    # these defaults are deliberately conservative so cost caps err on the safe side.
    price_fast_in: float = 0.50
    price_fast_out: float = 2.50
    price_smart_in: float = 2.00
    price_smart_out: float = 10.00
    max_job_cost_usd: float = 0.50

    # YouTube trends
    youtube_api_key: str = ""
    youtube_region: str = "US"

    # Whisper
    whisper_enabled: bool = True
    whisper_model: str = "base"

    # Limits
    max_upload_mb: int = 1024
    max_video_seconds: int = 900
    signed_url_ttl_seconds: int = 3600

    # Run Celery tasks inline (tests / no-worker dev)
    celery_eager: bool = False

    @property
    def anthropic_configured(self) -> bool:
        return bool(self.anthropic_api_key.strip())

    @property
    def youtube_configured(self) -> bool:
        return bool(self.youtube_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
