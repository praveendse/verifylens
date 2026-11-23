from datetime import datetime, timezone
from sqlmodel import SQLModel, Field
from sqlalchemy import CheckConstraint

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

class User(SQLModel, table=True):
    """Account with an admin or user role; stores no plaintext passwords."""

    __table_args__ = (
        CheckConstraint("role IN ('admin', 'user')", name="ck_user_role"),
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