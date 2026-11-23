"""Validation for admin-managed application users."""
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from security.password_policy import password_problem

# Deliberately simple: one "@", no spaces, a dot in the domain. Real
# deliverability is proven by the reset email arriving, not by a regex.
_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
MAX_EMAIL_LENGTH = 254


def normalize_email(value: str | None) -> str | None:
    """Trimmed and lowercase; blank means "no email"."""
    if value is None:
        return None
    value = value.strip().lower()
    if not value:
        return None
    if len(value) > MAX_EMAIL_LENGTH or not _EMAIL_RE.fullmatch(value):
        raise ValueError("Enter a valid email address.")
    return value


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9._-]+$")
    full_name: str | None = Field(default=None, max_length=100)
    password: str = Field(min_length=12, max_length=256)
    role: Literal["admin", "user"] = "user"
    email: str | None = None

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str | None) -> str | None:
        return normalize_email(value)

    @model_validator(mode="after")
    def password_must_meet_policy(self) -> "UserCreate":
        # The same rules as admin reset, self change and the CLI scripts.
        problem = password_problem(self.username, self.password)
        if problem:
            raise ValueError(problem)
        return self


class PasswordReset(BaseModel):
    """Admin sets a temporary password; the user must change it on next login."""
    new_password: str = Field(min_length=12, max_length=256)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=100)
    role: Literal["admin", "user"] | None = None
    is_active: bool | None = None
    email: str | None = None  # null or blank clears it

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str | None) -> str | None:
        return normalize_email(value)
