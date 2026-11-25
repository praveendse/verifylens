"""Admin-only user creation, listing, and account administration.

All enforcement is server-side. Never trust a role passed by a React client.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.api.auth_dependencies import require_admin
from app.dto.auth_models import UserPublic
from app.dto.common import CountResponse
from app.dto.user_models import PasswordReset, UserCreate, UserListQuery, UserUpdate
from app.infra.db.database import get_session
from app.infra.db.models import User
from app.infra.db.user_repository import UserRepository
from app.services import user_service

router = APIRouter(prefix="/users", tags=["User management"])


@router.get("", response_model=list[UserPublic])
def list_users(
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
    params: Annotated[UserListQuery, Query()],
):
    """One page of accounts, oldest first.

    Keyset pagination: after_id is the id of the last account the client
    already has, so accounts created or deleted between page loads never cause
    duplicated or skipped rows (unlike OFFSET).
    """
    repository = UserRepository(session)

    return repository.list_users(
        q=params.q,
        after_id=params.after_id,
        limit=params.limit,
    )

@router.get("/count", response_model=CountResponse)
def count_users(
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
    q: Annotated[str | None, Query(max_length=100)] = None,
):
    """Number of accounts (optionally matching q), for "Showing N of total"."""
    repository = UserRepository(session)

    return CountResponse(
        total=repository.count_users(q)
    )


@router.post(
    "",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: UserCreate,
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
):
    try:
        return user_service.create_user(session, payload)

    except user_service.UserConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.patch("/{user_id}", response_model=UserPublic)
def update_user(
    user_id: int,
    payload: UserUpdate,
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
):
    try:
        return user_service.update_user(
            session=session,
            user_id=user_id,
            payload=payload,
            admin=admin,
        )

    except user_service.UserNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=str(exc)
        ) from exc

    except user_service.UserOperationError as exc:
        raise HTTPException(
            status_code=400, detail=str(exc)
        ) from exc

    except user_service.UserValidationError as exc:
        raise HTTPException(
            status_code=422, detail=str(exc)
        ) from exc

    except user_service.UserConflictError as exc:
        raise HTTPException(
            status_code=409, detail=str(exc)
        ) from exc


@router.post("/{user_id}/password", response_model=UserPublic)
def reset_password(
    user_id: int,
    payload: PasswordReset,
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
):
    """Admin sets a temporary password for a user who forgot theirs.

    The user's existing sessions are logged out, and they must choose a new
    password at next login before they can use anything else.
    """
    try:
        return user_service.reset_password(
            session=session,
            user_id=user_id,
            payload=payload,
            admin=admin,
        )

    except user_service.UserNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=str(exc)
        ) from exc

    except user_service.UserOperationError as exc:
        raise HTTPException(
            status_code=400, detail=str(exc)
        ) from exc

    except user_service.UserValidationError as exc:
        raise HTTPException(
            status_code=422, detail=str(exc)
        ) from exc


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_user(
    user_id: int,
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
):
    """Permanently remove an account.

    The user's searches are kept but unlinked (user_id = NULL), so the audit
    history survives and only admins can still see those records. Existing
    tokens for the account stop working at once, because every request
    re-loads the user.
    """
    try:
        user_service.delete_user(
            session=session,
            user_id=user_id,
            admin=admin,
        )

    except user_service.UserNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except user_service.UserOperationError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
