from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SUBLYNT_", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite:///./data/sublynt.db"
    data_dir: Path = Path("./data/files")
    max_upload_bytes: int = Field(default=5 * 1024 * 1024, ge=1024)
    retention_hours: int = Field(default=24, ge=1)
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    storage_bucket: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
