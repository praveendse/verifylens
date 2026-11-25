"""Public authentication response DTOs: never expose hashed_password."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AccessToken(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str | None = None
    role: Literal["admin", "user"]
    is_active: bool
    must_change_password: bool = False
    email: str | None = None


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class PasswordResetRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=254)  # username or email

    @field_validator("identifier")
    @classmethod
    def normalize(cls, value: str) -> str:
        value = value.strip().lower()
        if not value:
            raise ValueError("Enter your username or email.")
        return value


class ResetAvailability(BaseModel):
    enabled: bool


class MailContent(BaseModel):
    """Subject and plain-text body of an outgoing email."""
    model_config = ConfigDict(frozen=True)

    subject: str
    body: str


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=1, max_length=128)
    # No min_length here: the token is checked first (400), then the password
    # rules (422) via password_problem, without using up the token.
    new_password: str = Field(max_length=256)
