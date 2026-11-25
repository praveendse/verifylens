"""Login, refresh, logout, authenticated user info, and password change."""
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session

from app.api.auth_dependencies import get_authenticated_user
from app.api.rate_limit import limit_login, limit_password_change, limit_refresh
from app.infra.db.database import get_session
from app.infra.db.models import User
from app.dto.auth_models import AccessToken, PasswordChange, UserPublic
from app.services import auth_service
from app.services import refresh_token_service as refresh_svc
from app.services.password_reset_service import utcnow
from app.config import Settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

REFRESH_COOKIE = "verifylens_refresh"
# Sent only to /auth/* (login, refresh, logout), never to the rest of the API.
REFRESH_COOKIE_PATH = "/api/v1/auth"
# Custom header required on cookie-authenticated calls. A cross-site form
# can't set it, and a cross-site fetch with it needs CORS, which this API
# doesn't allow. Together with SameSite=Strict this blocks CSRF.
CSRF_HEADER_VALUE = "verifylens"
SESSION_EXPIRED = "Session expired. Please sign in again."


def set_refresh_cookie(response: Response, raw: str, expires_at: datetime) -> None:
    max_age = max(0, int((expires_at - utcnow()).total_seconds()))
    response.set_cookie(
        REFRESH_COOKIE, raw,
        max_age=max_age, path=REFRESH_COOKIE_PATH,
        httponly=True, secure=Settings().refresh_cookie_secure, samesite="strict",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        REFRESH_COOKIE, path=REFRESH_COOKIE_PATH,
        httponly=True, secure=Settings().refresh_cookie_secure, samesite="strict",
    )


def session_response(response: Response, tokens: auth_service.SessionTokens) -> AccessToken:
    """Set the refresh cookie and return the access token."""
    set_refresh_cookie(response, tokens.refresh_token, tokens.expires_at)
    return AccessToken(access_token=tokens.access_token)


def require_csrf_header(x_requested_with: Annotated[str | None, Header()] = None) -> None:
    if x_requested_with != CSRF_HEADER_VALUE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing X-Requested-With header")


@router.post("/login", response_model=AccessToken, dependencies=[Depends(limit_login)])
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_session)],
    response: Response,
):
    try:
        user = auth_service.authenticate_user(session, form.username, form.password)
    except auth_service.InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return session_response(response, auth_service.create_session(session, user, Settings()))


@router.post(
    "/refresh",
    response_model=AccessToken,
    dependencies=[Depends(require_csrf_header), Depends(limit_refresh)],
)
def refresh(
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    refresh_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
):
    """New access token from the refresh cookie. Rotates the cookie (AUTH-13)."""
    result = auth_service.refresh_session(session, refresh_cookie, Settings())
    if result is None:
        # Returned, not raised: an HTTPException would drop the cookie deletion.
        denied = JSONResponse(
            {"detail": SESSION_EXPIRED},
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )
        clear_refresh_cookie(denied)
        return denied
    if result.refresh_token is not None and result.expires_at is not None:
        set_refresh_cookie(response, result.refresh_token, result.expires_at)
    return AccessToken(access_token=result.access_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_header)],
)
def logout(
    session: Annotated[Session, Depends(get_session)],
    refresh_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
):
    """End this browser's sign-in. Works without an access token, which may have expired."""
    if refresh_cookie:
        refresh_svc.revoke_family(session, refresh_cookie)
    done = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_refresh_cookie(done)
    return done


@router.get("/me", response_model=UserPublic)
def me(current_user: Annotated[User, Depends(get_authenticated_user)]):
    # Also allowed while must_change_password is set, so the client can see
    # the flag and show the "choose a new password" screen.
    return UserPublic.model_validate(current_user)


@router.post(
    "/password",
    response_model=AccessToken,
    dependencies=[Depends(limit_password_change)],
)
def change_password(
    response: Response,
    payload: PasswordChange,
    current_user: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Change your own password (also completes an admin reset).

    Returns a fresh token and refresh cookie: every other session of this
    user is logged out.
    """
    try:
        tokens = auth_service.change_password(session, current_user, payload, Settings())
    except auth_service.IncorrectPasswordError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except auth_service.PasswordValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return session_response(response, tokens)
