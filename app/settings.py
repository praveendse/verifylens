
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from security.secrets import secrets_dir


class Settings(BaseSettings):

    app_name: str = "Wikipedia Verification API"
    gemini_api_key: str | None = None
    # gemini-2.5-flash shuts down on 2026-12-01; 3.5 Flash-Lite is Google's
    # named replacement at the same price. Override with GEMINI_MODEL.
    gemini_model: str = "gemini-3.5-flash-lite"
    # Gemini 3+ thinking depth (GEMINI_THINKING_LEVEL). "minimal" is only
    # accepted by Flash-Lite models; gemini-3.8-flash starts at "low".
    # Ignored for gemini-2.x models, which use a fixed thinking budget.
    gemini_thinking_level: Literal["minimal", "low", "medium", "high"] = "low"
    # Per-request Gemini timeout (GEMINI_TIMEOUT_SECONDS). Retries of transient
    # errors share an overall budget of twice this; see gemini_service.
    gemini_timeout_seconds: int = Field(default=75, ge=10, le=300)
    headless: bool = True

    # SQLite file (DATABASE_PATH). On a server, point this at a persistent
    # disk/volume that is backed up; see scripts/backup_db.py.
    database_path: Path = Path(__file__).resolve().parents[1] / "data" / "search_history.db"

    # Built React app (npm run build). Served by FastAPI at "/" when the
    # folder exists, so site and API share one origin and need no CORS.
    frontend_dist: Path = Path(__file__).resolve().parents[1] / "frontend-react" / "dist"

    # Rate limits (per server process, sliding one-minute window).
    login_attempts_per_ip_per_minute: int = Field(default=10, ge=1)
    login_attempts_per_username_per_minute: int = Field(default=5, ge=1)
    searches_per_user_per_minute: int = Field(default=5, ge=1)

    # Self-service password recovery by email (docs/specs/password-recovery.md).
    # Off unless enabled AND SMTP_HOST, SMTP_FROM and APP_BASE_URL are set.
    password_reset_enabled: bool = False
    password_reset_token_minutes: int = Field(default=15, ge=5, le=60)
    # Public address of the app, used to build reset links. Never derived
    # from the request's Host header, which a client controls.
    app_base_url: str | None = None
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None  # secret: env, .env or SECRETS_DIR
    smtp_from: str | None = None
    smtp_starttls: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        secrets_dir=secrets_dir(),
    )

