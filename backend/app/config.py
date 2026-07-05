"""
KrishiMitra Backend – Application Configuration
=================================================
Loads all settings from environment variables via pydantic-settings.
Single source of truth for the entire application.
"""
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    All secrets stay in .env and are never committed to source control.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_name: str = Field(default="KrishiMitra-Backend")
    app_env: str = Field(default="development")
    app_version: str = Field(default="1.0.0")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # ── Server ────────────────────────────────────────────────────────────────
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # ── Security ──────────────────────────────────────────────────────────────
    secret_key: str = Field(
        default="changeme_this_is_insecure_default_key_replace_in_production"
    )
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=60)
    refresh_token_expire_days: int = Field(default=30)

    # ── MongoDB ───────────────────────────────────────────────────────────────
    mongodb_uri: str = Field(default="mongodb://localhost:27017")
    mongodb_db_name: str = Field(default="krishimitra")

    # ── Claude AI (current default) ───────────────────────────────────────────
    claude_api_key: str = Field(default="")
    claude_model: str = Field(default="claude-haiku-4-5-20251001")

    # ── AI Provider Selection ─────────────────────────────────────────────────
    # Values: "claude" | "gemini" | "openai"
    # Switch this to migrate reasoning engine without touching any other module.
    ai_provider: str = Field(default="claude")

    # ── Gemini AI (optional future provider) ──────────────────────────────────
    gemini_api_key: str = Field(default="")

    # ── OpenAI-compatible (local Llama, Qwen, DeepSeek, etc.) ────────────────
    openai_api_key: str = Field(default="")
    openai_base_url: str = Field(default="")
    openai_model: str = Field(default="gpt-4o-mini")

    # ── Market / Agmarknet (data.gov.in) ─────────────────────────────────────
    # Get a free key from: https://data.gov.in/user/register
    data_gov_api_key: str = Field(default="")


    # ── Google Earth Engine ───────────────────────────────────────────────────
    gee_service_account: str = Field(default="")
    gee_key_file: str = Field(default="")

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    rate_limit_requests: int = Field(default=60)
    rate_limit_window_seconds: int = Field(default=60)

    # ── Cache TTL (seconds) ───────────────────────────────────────────────────
    weather_cache_ttl: int = Field(default=1800)
    geocode_cache_ttl: int = Field(default=86400)

    # ── Voice ─────────────────────────────────────────────────────────────────
    whisper_model_size: str = Field(default="base")
    piper_model_path: str = Field(default="./models/piper")
    audio_output_dir: str = Field(default="./audio_outputs")

    # ── CORS ──────────────────────────────────────────────────────────────────
    allowed_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000"
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v: str) -> str:
        """Keep as raw string; parsed into list via property."""
        return v

    @property
    def cors_origins(self) -> List[str]:
        """Parse comma-separated CORS origins into a list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Cached settings factory.
    Call this anywhere via Depends(get_settings) or get_settings().
    """
    return Settings()
