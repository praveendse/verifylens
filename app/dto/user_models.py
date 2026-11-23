"""Validation for admin-managed application users."""
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9._-]+$")
    full_name: str | None = Field(default=None, max_length=100)
    password: str = Field(min_length=12, max_length=256)
    role: Literal["admin", "user"] = "user"

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None

    @model_validator(mode="after")
    def password_must_not_contain_username(self) -> "UserCreate":
        # Same rule as scripts/bootstrap_admin.py; username is already lowercased.
        if self.username in self.password.lower():
            raise ValueError("Password must not contain the username.")
        return self


class PasswordReset(BaseModel):
    """Admin sets a temporary password; the user must change it on next login."""
    new_password: str = Field(min_length=12, max_length=256)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=100)
    role: Literal["admin", "user"] | None = None
    is_active: bool | None = None

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None
