from datetime import datetime, timezone
from sqlmodel import SQLModel, Field
from sqlalchemy import CheckConstraint, Index

class SearchRecord(SQLModel, table=True):
    """Stores each Wikipedia search and its results."""

    # Primary Key
    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    query: str = Field(index=True)

    article_title: str | None = None
    source_url: str | None = None
    image_url: str | None = None

    # Dynamic Wikipedia infobox data
    fields_json: str | None = None

    status: str = "PENDING"
    matches: bool | None = None

    report_markdown: str | None = None
    error_message: str | None = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Link each search to its owner
    user_id: int | None = Field(
        default=None,
        foreign_key="user.id",
        index=True,
    )

    # Verification mode and the label check (spec SRCH-14, SRCH-15).
    # NULL on records saved before these existed.
    verification_mode: str | None = None   # "standard" or "thorough"
    label_check: str | None = None         # "agrees", "unclear" or "no_labels"
    needs_review: bool | None = None       # the visual verdict and the labels disagree

class User(SQLModel, table=True):
    """Account with an admin or user role; stores no plaintext passwords."""

    __table_args__ = (
        CheckConstraint("role IN ('admin', 'user')", name="ck_user_role"),
        # Unique when set; SQLite allows many NULLs. Same name as in migrations.
        Index("ux_user_email", "email", unique=True),
    )

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, nullable=False)
    hashed_password: str = Field(nullable=False)
    role: str = Field(default="user", nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    full_name: str | None = None
    # Bumped on every password change/reset; tokens carrying an older value
    # are rejected, so a reset logs out every existing session at once.
    token_version: int = Field(default=0, nullable=False)
    # Set when an admin resets the password: the user must choose a new one
    # before using anything else (enforced in get_current_user).
    must_change_password: bool = Field(default=False, nullable=False)
    # Where password-reset links go. Stored trimmed and lowercase; set by
    # admins only, so a stolen session cannot redirect recovery.
    email: str | None = None


class PasswordResetToken(SQLModel, table=True):
    """One-time password-reset link. Only the SHA-256 of the token is stored."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    token_hash: str = Field(unique=True, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(nullable=False)
    used_at: datetime | None = None  # also set when the token is cancelled
    requested_ip: str | None = None


class RefreshToken(SQLModel, table=True):
    """Long-lived sign-in, kept in an HttpOnly cookie. Only the SHA-256 is stored.

    Rotated on every use: the old row gets replaced_at, a new row joins the
    same family (one family = one sign-in on one browser).
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    token_hash: str = Field(unique=True, nullable=False)
    family_id: str = Field(index=True, nullable=False)
    # Must equal User.token_version, so a password change/reset revokes it.
    token_version: int = Field(nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(nullable=False)         # idle timeout (sliding)
    family_expires_at: datetime = Field(nullable=False)  # absolute cap for the sign-in
    replaced_at: datetime | None = None  # rotated; presenting it again = reuse
    revoked_at: datetime | None = None   # logout, reuse detected, or user gone