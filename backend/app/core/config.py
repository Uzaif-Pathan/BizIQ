"""Application settings, loaded from environment variables and the backend/.env file."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore variables we do not model yet (e.g. DATABASE_URL users)
    )

    app_name: str = "BizIQ"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Placeholder default so the app starts; set a real random value in .env.
    secret_key: str = "replace-with-a-random-secret"
    access_token_expire_minutes: int = 30

    # Used by the database layer (owned by the database/migrations task).
    database_url: str = ""

    # Owner of every business until real login exists (the seed script creates this demo user).
    default_owner_user_id: int = 1

    # Comma-separated list, e.g. "http://localhost:5173,http://127.0.0.1:5173"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
