"""Password recovery (docs/specs/password-recovery.md): reset tokens (issue,
validate, cancel, purge), the request and confirm workflows, and their emails.

Only the SHA-256 of a token is stored. The raw token exists only in the
email link and is never logged.
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import Engine, delete, or_, update
from sqlmodel import Session, select

from app.infra.db.models import PasswordResetToken, User
from app.infra.db.user_repository import UserRepository
from app.dto.auth_models import MailContent
from app.config import Settings
from app.services.mail_service import MailSender
from security.password_policy import password_problem
from security.passwords import hash_password

logger = logging.getLogger(__name__)

PURGE_AFTER_DAYS = 7


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes; they are stored as UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def config_problem(settings: Settings) -> str | None:
    """Why an enabled feature can't work, for the startup warning. None if fine or off."""
    if not settings.password_reset_enabled:
        return None
    missing = [
        name
        for name, value in (
            ("SMTP_HOST", settings.smtp_host),
            ("SMTP_FROM", settings.smtp_from),
            ("APP_BASE_URL", settings.app_base_url),
        )
        if not (value or "").strip()
    ]
    if missing:
        return f"Password reset is enabled but not configured; missing: {', '.join(missing)}."
    return None


def is_available(settings: Settings) -> bool:
    return settings.password_reset_enabled and config_problem(settings) is None


def find_user(session: Session, identifier: str) -> User | None:
    """By username or email. Usernames can't contain '@', so at most one matches."""
    return UserRepository(session).get_by_username_or_email(identifier.strip().lower())


def cancel_unused_tokens(session: Session, user_id: int, now: datetime | None = None) -> None:
    """Mark every unused token of the user as used. Caller commits."""
    session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user_id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now or utcnow())
    )


def delete_tokens(session: Session, user_id: int) -> None:
    """Remove all of a user's tokens (account deletion). Caller commits."""
    session.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user_id))


def issue_token(session: Session, user: User, ip: str | None, minutes: int) -> str:
    """Cancel earlier links, store a new hashed token, return the raw token."""
    now = utcnow()
    cancel_unused_tokens(session, user.id, now)
    raw = secrets.token_urlsafe(32)
    session.add(PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw),
        created_at=now,
        expires_at=now + timedelta(minutes=minutes),
        requested_ip=ip,
    ))
    session.commit()
    return raw


def find_valid_token(session: Session, raw: str, now: datetime) -> tuple[PasswordResetToken, User] | None:
    """The token row and its user, if the token is unused, unexpired and the user active."""
    row = session.exec(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(raw))
    ).first()
    if row is None or row.used_at is not None or _as_utc(row.expires_at) <= now:
        return None
    user = session.get(User, row.user_id)
    if user is None or not user.is_active:
        return None
    return row, user


def claim_token(session: Session, token_id: int, now: datetime) -> bool:
    """Mark the token used only if still unused, so two concurrent confirms
    can't both succeed. Caller commits."""
    result = session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.id == token_id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    return result.rowcount == 1


def purge_old_tokens(engine: Engine, days: int = PURGE_AFTER_DAYS) -> int:
    """Delete tokens used or expired more than `days` ago. Returns rows removed."""
    cutoff = utcnow() - timedelta(days=days)
    with Session(engine) as session:
        result = session.execute(
            delete(PasswordResetToken).where(
                or_(PasswordResetToken.used_at < cutoff, PasswordResetToken.expires_at < cutoff)
            )
        )
        session.commit()
        return result.rowcount


def reset_link(base_url: str, raw: str) -> str:
    # Token in the fragment: browsers don't send it to the server, so it stays
    # out of access logs and Referer headers.
    return f"{base_url.rstrip('/')}/reset-password#token={raw}"


def reset_email(link: str, minutes: int) -> MailContent:
    subject = "VerifyLens password reset"
    body = (
        "Someone asked to reset the password for your VerifyLens account.\n\n"
        f"To choose a new password, open this link within {minutes} minutes:\n\n"
        f"{link}\n\n"
        "The link works once.\n\n"
        "If you didn't ask for this, ignore this email. Your password stays the same.\n"
    )
    return MailContent(subject=subject, body=body)


def changed_email() -> MailContent:
    subject = "Your VerifyLens password was changed"
    body = (
        "Your VerifyLens password was changed using a reset link, and all of\n"
        "your sessions were signed out.\n\n"
        "If this wasn't you, contact your admin right away.\n"
    )
    return MailContent(subject=subject, body=body)


class InvalidResetLinkError(Exception):
    pass


class WeakPasswordError(Exception):
    pass


def process_reset_request(
    identifier: str,
    ip: str,
    settings: Settings,
    mailer: MailSender,
    session_factory: Callable[[], Session],
    account_limit_hit: Callable[[str], float | None],
) -> None:
    """Runs after the response is sent, so the response looks and times the
    same whether or not an account matches. Never logs the token or link.

    account_limit_hit records one request for a key and returns None if allowed."""
    try:
        with session_factory() as session:
            user = find_user(session, identifier)
            if user is None or not user.is_active or not user.email:
                logger.info("Password reset requested (ip=%s): no eligible account", ip)
                return
            # Counted per account, so username and email share one limit.
            if account_limit_hit(f"user:{user.id}") is not None:
                logger.warning("Password reset over the per-account limit (user_id=%s, ip=%s); no email sent",
                               user.id, ip)
                return
            minutes = settings.password_reset_token_minutes
            raw = issue_token(session, user, ip, minutes)
            to, uid = user.email, user.id
        mail = reset_email(reset_link(settings.app_base_url, raw), minutes)
        mailer.send(to, mail.subject, mail.body)
        logger.info("Password reset link sent (user_id=%s, ip=%s)", uid, ip)
    except Exception as exc:  # noqa: BLE001 - background task: log, never raise
        logger.warning("Password reset request failed (ip=%s): %s", ip, type(exc).__name__)


def confirm_reset(session: Session, raw_token: str, new_password: str, ip: str) -> User:
    """Set the new password and use up the token. Returns the user."""
    now = utcnow()
    found = find_valid_token(session, raw_token, now)
    if found is None:
        logger.info("Password reset confirm rejected (ip=%s): invalid or expired link", ip)
        raise InvalidResetLinkError
    row, user = found

    # Checked before the token is used up, so the user can retry with a better password.
    problem = password_problem(user.username, new_password)
    if problem:
        raise WeakPasswordError(problem)

    if not claim_token(session, row.id, now):
        session.rollback()
        raise InvalidResetLinkError
    user.hashed_password = hash_password(new_password)
    user.must_change_password = False
    user.token_version += 1  # signs out every existing session
    cancel_unused_tokens(session, user.id, now)
    session.add(user)
    session.commit()
    logger.info("Password reset completed (user_id=%s, ip=%s)", user.id, ip)
    return user


def send_changed_notice(mailer: MailSender, to: str, uid: int) -> None:
    try:
        mail = changed_email()
        mailer.send(to, mail.subject, mail.body)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Password changed notice failed (user_id=%s): %s", uid, type(exc).__name__)
