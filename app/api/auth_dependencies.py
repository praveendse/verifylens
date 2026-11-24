"""Reusable backend authorization dependencies."""
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from app.infra.db.database import get_session
from app.infra.db.models import User
from security.tokens import decode_access_claims

bearer_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

PASSWORD_CHANGE_REQUIRED = "Password change required"


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_authenticated_user(
    token: Annotated[str, Depends(bearer_scheme)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    """Valid token for an active user, even one who must change their password.

    Only for /auth/me and /auth/password. Everything else uses get_current_user.
    """
    try:
        claims = decode_access_claims(token)
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise _unauthorized() from None

    user = session.get(User, claims.user_id)
    if user is None or not user.is_active:
        raise _unauthorized()
    # Password changed/reset since this token was issued: token is revoked.
    if claims.token_version != user.token_version:
        raise _unauthorized()
    return user


def get_current_user(
    user: Annotated[User, Depends(get_authenticated_user)],
) -> User:
    if user.must_change_password:
        # Enforced server-side, so a temporary password can't be used for
        # anything except choosing a new one, whatever the client does.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=PASSWORD_CHANGE_REQUIRED,
        )
    return user


def require_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user
