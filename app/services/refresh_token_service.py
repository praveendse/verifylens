"""Refresh tokens: issue, rotate, revoke, purge (docs/specs/auth.md, AUTH-12..18).

The raw token lives only in the browser's HttpOnly cookie. The database keeps
its SHA-256, so a database leak doesn't hand out sessions.
"""
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import Engine, delete, or_, update
from sqlmodel import Session, select

from app.infra.db.models import RefreshToken, User
from app.services.password_reset_service import _as_utc, hash_token, utcnow
from app.config import Settings

logger = logging.getLogger(__name__)

# Two tabs can refresh with the same cookie at the same moment. The loser of
# that race presents a token that was just rotated; within this window it
# gets an access token (no new cookie) instead of tripping reuse detection.
ROTATION_GRACE = timedelta(seconds=30)
PURGE_AFTER_DAYS = 7


@dataclass(frozen=True)
class Refreshed:
    user: User
    raw: str | None          # new cookie value; None = keep the current cookie
    expires_at: datetime | None


def _new_row(session: Session, user: User, family_id: str, family_expires_at: datetime,
             now: datetime, idle: timedelta) -> tuple[str, RefreshToken]:
    raw = secrets.token_urlsafe(32)
    row = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw),
        family_id=family_id,
        token_version=user.token_version,
        created_at=now,
        expires_at=min(now + idle, family_expires_at),
        family_expires_at=family_expires_at,
    )
    session.add(row)
    return raw, row


def issue(session: Session, user: User, settings: Settings) -> tuple[str, datetime]:
    """Start a new sign-in. Returns (raw token, cookie expiry). Commits."""
    now = utcnow()
    raw, row = _new_row(
        session, user, secrets.token_urlsafe(16),
        now + timedelta(days=settings.refresh_token_max_days),
        now, timedelta(hours=settings.refresh_token_idle_hours),
    )
    session.commit()
    return raw, row.expires_at


def _usable_user(session: Session, row: RefreshToken) -> User | None:
    user = session.get(User, row.user_id)
    if user is None or not user.is_active or user.token_version != row.token_version:
        return None
    return user


def revoke_user(session: Session, user_id: int, now: datetime | None = None) -> None:
    """Revoke every live refresh token of the user. Caller commits."""
    session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now or utcnow())
    )


def rotate(session: Session, raw: str, settings: Settings) -> Refreshed | None:
    """Swap a valid refresh token for a new one. None if it can't be used."""
    now = utcnow()
    row = session.exec(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw))).first()
    if row is None or row.revoked_at is not None:
        return None

    if row.replaced_at is not None:
        if now - _as_utc(row.replaced_at) <= ROTATION_GRACE:
            user = _usable_user(session, row)
            return Refreshed(user, None, None) if user else None
        # An old token came back: someone kept a copy. Sign the user out everywhere.
        logger.warning("Refresh token reuse detected (user_id=%s); all sessions revoked", row.user_id)
        revoke_user(session, row.user_id, now)
        session.commit()
        return None

    if _as_utc(row.expires_at) <= now or _as_utc(row.family_expires_at) <= now:
        return None
    user = _usable_user(session, row)
    if user is None:
        return None

    # Claim atomically, so two concurrent refreshes can't both rotate it.
    claimed = session.execute(
        update(RefreshToken)
        .where(RefreshToken.id == row.id, RefreshToken.replaced_at.is_(None),
               RefreshToken.revoked_at.is_(None))
        .values(replaced_at=now)
    ).rowcount == 1
    if not claimed:
        session.rollback()
        return Refreshed(user, None, None)  # lost the race: treat as within grace

    new_raw, new_row = _new_row(
        session, user, row.family_id, _as_utc(row.family_expires_at),
        now, timedelta(hours=settings.refresh_token_idle_hours),
    )
    session.commit()
    return Refreshed(user, new_raw, new_row.expires_at)


def revoke_family(session: Session, raw: str) -> None:
    """Logout: end this browser's sign-in. Unknown tokens are ignored. Commits."""
    row = session.exec(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw))).first()
    if row is None:
        return
    session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == row.family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    session.commit()


def delete_for_user(session: Session, user_id: int) -> None:
    """Account deletion. Caller commits."""
    session.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))


def purge_old(engine: Engine, days: int = PURGE_AFTER_DAYS) -> int:
    """Delete rows expired or revoked more than `days` ago. Returns rows removed."""
    cutoff = utcnow() - timedelta(days=days)
    with Session(engine) as session:
        result = session.execute(
            delete(RefreshToken).where(
                or_(RefreshToken.expires_at < cutoff, RefreshToken.revoked_at < cutoff)
            )
        )
        session.commit()
        return result.rowcount
