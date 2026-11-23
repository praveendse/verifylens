"""Public authentication response DTOs: never expose hashed_password."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)
