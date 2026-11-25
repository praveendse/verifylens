"""Create and verify short-lived JWT access tokens for VerifyLens."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

from app.config import JWTSettings


@dataclass(frozen=True)
class TokenClaims:
    user_id: int
    token_version: int


def create_access_token(user_id: int, token_version: int = 0) -> str:
    settings = JWTSettings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        # Must equal User.token_version, so a password change revokes old tokens.
        "tv": token_version,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_minutes),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def decode_access_claims(token: str) -> TokenClaims:
    settings = JWTSettings()
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=["HS256"],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
        options={"require": ["sub", "exp", "iat", "iss", "aud"]},
    )
    subject = payload["sub"]
    if not isinstance(subject, str) or not subject.isdecimal():
        raise jwt.InvalidTokenError("Invalid token subject")
    user_id = int(subject)
    if user_id <= 0:
        raise jwt.InvalidTokenError("Invalid token subject")
    # Tokens issued before this claim existed count as version 0.
    version = payload.get("tv", 0)
    if not isinstance(version, int) or isinstance(version, bool) or version < 0:
        raise jwt.InvalidTokenError("Invalid token version")
    return TokenClaims(user_id=user_id, token_version=version)


def decode_access_token(token: str) -> int:
    """User id only (kept for existing callers)."""
    return decode_access_claims(token).user_id
