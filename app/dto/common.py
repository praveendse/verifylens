"""Small DTOs shared by several routes."""
from pydantic import BaseModel, Field

MAX_PAGE_SIZE = 50  # no client can pull a whole table in one request


class MessageResponse(BaseModel):
    detail: str


class CountResponse(BaseModel):
    total: int


class PageQuery(BaseModel):
    """Base for keyset-paged list query parameters. Subclasses add the cursor
    (before_id / after_id) and their own search filter."""
    limit: int = Field(default=20, ge=1, le=MAX_PAGE_SIZE)
