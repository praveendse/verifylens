import logging

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.dto.user_models import PasswordReset, UserCreate, UserUpdate
from app.infra.db.models import User
from app.infra.db.repository import SearchRepository
from app.infra.db.user_repository import UserRepository
from app.services import refresh_token_service as refresh_svc
from app.services.password_reset_service import (
    cancel_unused_tokens,
    delete_tokens,
)
from security.password_policy import password_problem
from security.passwords import hash_password


logger = logging.getLogger(__name__)
EMAIL_TAKEN = "Email already in use"


class UserConflictError(Exception):
    pass

class UserNotFoundError(Exception):
    pass


class UserOperationError(Exception):
    pass


class UserValidationError(Exception):
    pass


def create_user(
    session: Session,
    payload: UserCreate,
) -> User:

    repository = UserRepository(session)

    if repository.email_taken(payload.email):
        raise UserConflictError(EMAIL_TAKEN)

    user = User(
        username=payload.username,
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        is_active=True,
        must_change_password=True,
    )

    session.add(user)

    try:
        session.commit()

    except IntegrityError as exc:
        session.rollback()

        detail = (
            EMAIL_TAKEN
            if repository.email_taken(payload.email)
            else "Username already exists"
        )

        raise UserConflictError(detail) from exc

    session.refresh(user)

    return user

def update_user(
    session: Session,
    user_id: int,
    payload: UserUpdate,
    admin: User,
) -> User:

    repository = UserRepository(session)

    target = repository.get_by_id(user_id)

    if target is None:
        raise UserNotFoundError("User not found")

    changes = payload.model_dump(exclude_unset=True)

    if not changes:
        return target

    if "role" in changes and changes["role"] is None:
        raise UserValidationError("Role cannot be null")

    if "is_active" in changes and changes["is_active"] is None:
        raise UserValidationError("is_active cannot be null")

    # Prevent administrators from demoting or deactivating themselves.
    if target.id == admin.id and (
        changes.get("role", target.role) != "admin"
        or changes.get("is_active", target.is_active) is False
    ):
        raise UserOperationError(
            "Cannot demote or deactivate your own admin account"
        )

    # Ensure at least one active administrator remains.
    removing_active_admin = (
        target.role == "admin"
        and target.is_active
        and (
            changes.get("role", target.role) != "admin"
            or changes.get("is_active", target.is_active) is False
        )
    )

    if removing_active_admin:
        if not repository.has_other_active_admin(target.id):
            raise UserOperationError(
                "At least one active admin must remain"
            )

    # Check email uniqueness.
    if "email" in changes and repository.email_taken(
        changes["email"],
        except_id=target.id,
    ):
        raise UserConflictError(EMAIL_TAKEN)

    # Apply the requested changes.
    for field, value in changes.items():
        setattr(target, field, value)

    session.add(target)

    try:
        session.commit()

    except IntegrityError as exc:
        session.rollback()
        raise UserConflictError(EMAIL_TAKEN) from exc

    session.refresh(target)

    return target

def reset_password(
    session: Session,
    user_id: int,
    payload: PasswordReset,
    admin: User,
) -> User:

    repository = UserRepository(session)

    target = repository.get_by_id(user_id)

    if target is None:
        raise UserNotFoundError("User not found")

    if target.id == admin.id:
        raise UserOperationError(
            "Use 'Change password' for your own account"
        )

    problem = password_problem(
        target.username,
        payload.new_password,
    )

    if problem:
        raise UserValidationError(problem)

    target.hashed_password = hash_password(
        payload.new_password
    )

    target.must_change_password = True
    target.token_version += 1

    # PWR-10: old reset links stop working.
    cancel_unused_tokens(session, target.id)

    session.add(target)
    session.commit()
    session.refresh(target)

    logger.info(
        "Admin user_id=%s reset password for user_id=%s",
        admin.id,
        target.id,
    )

    return target

def delete_user(
    session: Session,
    user_id: int,
    admin: User,
) -> None:
    """Permanently remove an account while preserving search history."""

    repository = UserRepository(session)
    search_repository = SearchRepository(session)

    target = repository.get_by_id(user_id)

    if target is None:
        raise UserNotFoundError("User not found")

    if target.id == admin.id:
        raise UserOperationError(
            "You cannot delete your own account"
        )

    if target.role == "admin" and target.is_active:
        if not repository.has_other_active_admin(target.id):
            raise UserOperationError(
                "At least one active admin must remain"
            )

    # Perform all database changes within one transaction.
    search_repository.unlink_user(target.id)

    delete_tokens(session, target.id)

    refresh_svc.delete_for_user(session, target.id)

    repository.delete(target)

    session.commit()