"""Form-based login endpoint, authenticated user info, and password change."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from app.api.auth_dependencies import get_authenticated_user
from app.api.rate_limit import limit_login, limit_password_change
from app.db.database import get_session
from app.db.models import User
from app.dto.auth_models import AccessToken, PasswordChange, UserPublic
from security.password_policy import password_problem
from security.passwords import hash_password, verify_password
from security.tokens import create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=AccessToken,
    dependencies=[Depends(limit_login)],
)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_session)],
):
    user = session.exec(select(User).where(User.username == form.username)).first()
    if user is None or not user.is_active or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return AccessToken(access_token=create_access_token(user.id, user.token_version))


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
    payload: PasswordChange,
    current_user: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Change your own password (also completes an admin reset).

    Returns a fresh token: every other session of this user is logged out.
    """
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if payload.new_password == payload.current_password:
        raise HTTPException(status_code=422, detail="New password must be different from the current one.")
    problem = password_problem(current_user.username, payload.new_password)
    if problem:
        raise HTTPException(status_code=422, detail=problem)

    current_user.hashed_password = hash_password(payload.new_password)
    current_user.must_change_password = False
    current_user.token_version += 1
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return AccessToken(access_token=create_access_token(current_user.id, current_user.token_version))
