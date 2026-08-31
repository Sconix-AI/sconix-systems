"""Typed settings, 12-factor. Every app subclasses ``Settings`` and adds its own.

    # app-specific settings.py
    from sconixapp import Settings

    class AppSettings(Settings):
        feature_x_enabled: bool = False

    settings = AppSettings()  # reads env + .env

Values come from the process environment, then a ``.env`` file if present.
Secrets (JWT signing key, Stripe keys, ...) are injected by the deploy, never
committed — see SOPS in STACK.md.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["dev", "staging", "prod", "test"]


class Settings(BaseSettings):
    """Base settings shared by every Sconix app. Subclass per app."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- identity / runtime -------------------------------------------------
    app_name: str = "sconix-app"
    environment: Environment = "dev"
    debug: bool = False
    base_url: str = "http://localhost:8000"

    # --- data ---------------------------------------------------------
    # str, not PostgresDsn: prod is postgresql+asyncpg://, but zero-Docker
    # local dev uses sqlite+aiosqlite:///./dev.db
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/app"
    redis_url: str = "redis://localhost:6379/0"

    # --- auth ----------------------------------------------------------
    jwt_secret: str = "dev-insecure-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_s: int = 60 * 15  # 15 min
    refresh_token_ttl_s: int = 60 * 60 * 24 * 30  # 30 days

    # --- integrations (optional until a feature needs them) ---------------
    sentry_dsn: str | None = None
    posthog_key: str | None = None
    resend_api_key: str | None = None
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_price_id: str | None = None

    # --- agent (sconixapp.agent) --------------------------------------
    anthropic_api_key: str | None = None
    # per-user input+output tokens/month before run_agent soft-degrades to the
    # cheap model; 0 disables the ceiling.
    agent_token_ceiling: int = 0

    # --- CORS: origins allowed to call the API (web + mobile dev) --------
    cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def is_prod(self) -> bool:
        return self.environment == "prod"


@lru_cache
def get_settings() -> Settings:
    """Cached accessor. Override the class in the app; this still returns it
    if the app rebinds ``get_settings`` — otherwise use the app's own instance."""
    return Settings()
