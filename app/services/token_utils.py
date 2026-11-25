"""Helpers shared by the password-reset and refresh-token services."""
import hashlib
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes; they are stored as UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def hash_token(raw: str) -> str:
    """Only this SHA-256 is stored; the raw token stays with the client."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
