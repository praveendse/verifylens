"""Access-token settings. Encoding and checking tokens stays in security/tokens.py."""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config.settings import ENV_FILE
from security.secrets import secrets_dir


class JWTSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        secrets_dir=secrets_dir(),
    )

    jwt_secret_key: str = Field(min_length=32)
    jwt_access_token_minutes: int = Field(default=30, gt=0, le=1440)
    jwt_issuer: str = "verifylens"
    jwt_audience: str = "verifylens-api"
