"""Admin-only user creation, listing, and account administration.

All enforcement is server-side. Never trust a role passed by a React client.
"""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.api.auth_dependencies import require_admin
from app.db.database import get_session
from app.db.models import SearchRecord, User
from app.dto.auth_models import UserPublic
from app.dto.user_models import PasswordReset, UserCreate, UserUpdate
from app.services.password_reset_service import cancel_unused_tokens, delete_tokens
from security.password_policy import password_problem
from security.passwords import hash_password

router = APIRouter(prefix="/users", tags=["User management"])
logger = logging.getLogger(__name__)

EMAIL_TAKEN = "Email already in use"


def _email_taken(session: Session, email: str | None, except_id: int | None = None) -> bool:
    if email is None:
        return False
    statement = select(User.id).where(User.email == email)
    if except_id is not None:
        statement = statement.where(User.id != except_id)
    return session.exec(statement).first() is not None


MAX_PAGE_SIZE = 50
MAX_SEARCH_TERMS = 5


def _matching(statement, q: str | None):
    """Every whitespace-separated term must appear in the username or full name
    (case-insensitive substring). autoescape treats % and _ literally."""
    terms = (q or "").lower().split()[:MAX_SEARCH_TERMS]
    for term in terms:
        statement = statement.where(
            or_(
                func.lower(User.username).contains(term, autoescape=True),
                func.lower(User.full_name).contains(term, autoescape=True),
            )
        )
    return statement


@router.get("", response_model=list[UserPublic])
def list_users(
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
    after_id: Annotated[int | None, Query(ge=1)] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
):
    """One page of accounts, oldest first.

    Keyset pagination: after_id is the id of the last account the client
    already has, so accounts created or deleted between page loads never cause
    duplicated or skipped rows (unlike OFFSET).
    """
    statement = _matching(select(User), q)
    if after_id is not None:
        statement = statement.where(User.id > after_id)
    return session.exec(statement.order_by(User.id).limit(limit)).all()


@router.get("/count")
def count_users(
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
    q: Annotated[str | None, Query(max_length=100)] = None,
):
    """Number of accounts (optionally matching q), for "Showing N of total"."""
    total = session.exec(_matching(select(func.count()).select_from(User), q)).one()
    return {"total": total}


@router.post("", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
):
    if _email_taken(session, payload.email):
        raise HTTPException(status_code=409, detail=EMAIL_TAKEN)
    user = User(
        username=payload.username,
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        is_active=True,
        # The admin chose (and knows) this password: the user must replace it
        # at first sign-in before using anything else.
        must_change_password=True,
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        # Lost a race on the email, or the username already exists.
        detail = EMAIL_TAKEN if _email_taken(session, payload.email) else "Username already exists"
        raise HTTPException(status_code=409, detail=detail) from exc
    session.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserPublic)
def update_user(
    user_id: int,
    payload: UserUpdate,
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
):
    target = session.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return target
    if "role" in changes and changes["role"] is None:
        raise HTTPException(status_code=422, detail="Role cannot be null")
    if "is_active" in changes and changes["is_active"] is None:
        raise HTTPException(status_code=422, detail="is_active cannot be null")

    if target.id == admin.id and (
        changes.get("role", target.role) != "admin"
        or changes.get("is_active", target.is_active) is False
    ):
        raise HTTPException(status_code=400, detail="Cannot demote or deactivate your own admin account")

    removing_active_admin = target.role == "admin" and target.is_active and (
        changes.get("role", target.role) != "admin"
        or changes.get("is_active", target.is_active) is False
    )
    if removing_active_admin:
        other_active_admins = session.exec(
            select(User).where(User.role == "admin", User.is_active == True, User.id != target.id)  # noqa: E712
        ).first()
        if other_active_admins is None:
            raise HTTPException(status_code=400, detail="At least one active admin must remain")

    if "email" in changes and _email_taken(session, changes["email"], except_id=target.id):
        raise HTTPException(status_code=409, detail=EMAIL_TAKEN)

    for field, value in changes.items():
        setattr(target, field, value)
    session.add(target)
    try:
        session.commit()
    except IntegrityError as exc:  # lost a race on the email
        session.rollback()
        raise HTTPException(status_code=409, detail=EMAIL_TAKEN) from exc
    session.refresh(target)
    return target


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
    target = session.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id:
        # The admin knows their own password; use the normal change flow so
        # the current password is checked.
        raise HTTPException(status_code=400, detail="Use 'Change password' for your own account")
    problem = password_problem(target.username, payload.new_password)
    if problem:
        raise HTTPException(status_code=422, detail=problem)

    target.hashed_password = hash_password(payload.new_password)
    target.must_change_password = True
    target.token_version += 1
    cancel_unused_tokens(session, target.id)  # PWR-10: old reset links stop working
    session.add(target)
    session.commit()
    session.refresh(target)
    logger.info("Admin user_id=%s reset password for user_id=%s", admin.id, target.id)
    return target


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
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
    target = session.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    if target.role == "admin" and target.is_active:
        other_active_admin = session.exec(
            select(User).where(User.role == "admin", User.is_active == True, User.id != target.id)  # noqa: E712
        ).first()
        if other_active_admin is None:
            raise HTTPException(status_code=400, detail="At least one active admin must remain")

    # Unlink and delete in one transaction: either both happen or neither.
    session.execute(
        update(SearchRecord).where(SearchRecord.user_id == target.id).values(user_id=None)
    )
    delete_tokens(session, target.id)  # PWR-18
    session.delete(target)
    session.commit()
