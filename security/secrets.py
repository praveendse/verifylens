"""Where secrets come from, and a startup check that they are present.

Lookup order (first wins), handled by pydantic-settings:
  1. Real environment variables  (set by the host: systemd, Docker, cloud)
  2. The .env file               (local development only)
  3. Secret files in SECRETS_DIR (default /run/secrets, used by Docker /
     Kubernetes secrets). File name = setting name, e.g.
     /run/secrets/jwt_secret_key containing just the value.
"""
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def secrets_dir() -> Path | None:
    """SECRETS_DIR if it exists (missing dirs would only produce warnings)."""
    path = Path(os.environ.get("SECRETS_DIR", "/run/secrets"))
    return path if path.is_dir() else None


def validate_secrets() -> None:
    """Fail at startup, not at first login, if secrets are missing or weak.

    Never logs secret values.
    """
    from pydantic import ValidationError

    from app.config import Settings
    from security.tokens import JWTSettings

    try:
        JWTSettings()
    except ValidationError as exc:
        fields = ", ".join(str(e["loc"][0]) for e in exc.errors())
        raise RuntimeError(
            f"Invalid or missing secret setting(s): {fields}. "
            "JWT_SECRET_KEY must be at least 32 characters; generate one with "
            "`python -c \"import secrets; print(secrets.token_urlsafe(48))\"`."
        ) from None

    if not Settings().gemini_api_key:
        # Login/history still work; only searches fail. Warn, don't block.
        logger.warning("GEMINI_API_KEY is not set: searches will fail until it is configured.")
