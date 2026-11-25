"""Authentication workflows: login, sessions, refresh, password change, token checks."""
from dataclasses import dataclass
from datetime import datetime

import jwt
from sqlmodel import Session

from app.config import Settings
from app.dto.auth_models import PasswordChange
from app.infra.db.models import User
from app.infra.db.user_repository import UserRepository
from app.services import refresh_token_service as refresh_svc
from app.services.password_reset_service import cancel_unused_tokens
from security.password_policy import password_problem
from security.passwords import hash_password, verify_password
from security.tokens import create_access_token, decode_access_claims

INVALID_TOKEN = "Invalid or expired authentication token"


class InvalidCredentialsError(Exception):
    pass


class IncorrectPasswordError(Exception):
    pass


class PasswordValidationError(Exception):
    pass


class InvalidAccessTokenError(Exception):
    pass


@dataclass(frozen=True)
class SessionTokens:
    access_token: str
    refresh_token: str
    expires_at: datetime


@dataclass(frozen=True)
class RefreshedSession:
    access_token: str
    refresh_token: str | None  # None = keep the current cookie
    expires_at: datetime | None


def authenticate_user(session: Session, username: str, password: str) -> User:
    # Usernames are stored trimmed and lowercase; the login rate limiter uses the same key.
    user = UserRepository(session).get_by_username(username.strip().lower())
    if user is None or not user.is_active or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("Invalid username or password")
    return user


def create_session(session: Session, user: User, settings: Settings) -> SessionTokens:
    raw, expires_at = refresh_svc.issue(session, user, settings)
    return SessionTokens(create_access_token(user.id, user.token_version), raw, expires_at)


def refresh_session(session: Session, raw_token: str | None, settings: Settings) -> RefreshedSession | None:
    """Rotate the refresh token (AUTH-13). None if it can't be used."""
    if not raw_token:
        return None
    result = refresh_svc.rotate(session, raw_token, settings)
    if result is None:
        return None
    access_token = create_access_token(result.user.id, result.user.token_version)
    return RefreshedSession(access_token, result.raw, result.expires_at)


def change_password(
    session: Session, user: User, payload: PasswordChange, settings: Settings,
) -> SessionTokens:
    """Also completes an admin reset. Every other session of this user is logged out."""
    if not verify_password(payload.current_password, user.hashed_password):
        raise IncorrectPasswordError("Current password is incorrect")
    if payload.new_password == payload.current_password:
        raise PasswordValidationError("New password must be different from the current one.")
    problem = password_problem(user.username, payload.new_password)
    if problem:
        raise PasswordValidationError(problem)

    user.hashed_password = hash_password(payload.new_password)
    user.must_change_password = False
    user.token_version += 1
    cancel_unused_tokens(session, user.id)  # PWR-10: old reset links stop working
    refresh_svc.revoke_user(session, user.id)  # AUTH-16
    session.add(user)
    session.commit()
    session.refresh(user)
    return create_session(session, user, settings)


def authenticate_access_token(session: Session, token: str) -> User:
    try:
        claims = decode_access_claims(token)
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise InvalidAccessTokenError(INVALID_TOKEN) from None

    user = UserRepository(session).get_by_id(claims.user_id)
    if user is None or not user.is_active:
        raise InvalidAccessTokenError(INVALID_TOKEN)
    # Password changed/reset since this token was issued: token is revoked.
    if claims.token_version != user.token_version:
        raise InvalidAccessTokenError(INVALID_TOKEN)
    return user
