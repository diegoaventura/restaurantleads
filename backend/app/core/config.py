"""Application settings, loaded from environment variables (see .env.example).

Defaults match the development `docker-compose.yml`, so the backend runs
out of the box in development. Never hardcode secrets: set them in `.env`.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Application ---
    app_name: str = "Restaurant Leads"
    env: str = "development"  # development | production
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"

    # --- Security (used from Milestone 2) ---
    secret_key: str = "change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # --- CORS ---
    frontend_url: str = "http://localhost:5173"

    # --- Database ---
    database_url: str = (
        "postgresql+psycopg://restaurant_leads:change_me_in_dev"
        "@localhost:5432/restaurant_leads"
    )

    model_config = SettingsConfigDict(
        # Repo root .env when running from backend/, local .env otherwise.
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
