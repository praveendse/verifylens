from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# class InfoboxDTO(BaseModel):
#     date: str
#     location: str
#     result: str


class ArticleDTO(BaseModel):
    title: str
    paragraph: str
    source_url: str
    image_url: str
    fields: dict[str, str]

class VerificationDTO(BaseModel):
    description: str
    matches: bool = Field(strict=True)
    reason: str


class HealthResponse(BaseModel):
    status: str
    message: str


class ComponentStatus(BaseModel):
    name: str                      # machine id: api, database, gemini, wikipedia
    label: str                     # human label for the UI
    status: Literal["ok", "down"]
    latency_ms: int
    detail: str | None = None      # coarse, safe reason when down (no secrets)


class SystemStatusResponse(BaseModel):
    status: Literal["ok", "degraded"]
    checked_at: datetime
    components: list[ComponentStatus]


# create DTO for file response

class SearchRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=200)

    @field_validator("topic")
    @classmethod
    def clean_topic(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Topic cannot be empty")
        return value


class SearchResponse(BaseModel):
    id: int
    query: str
    article_title: str | None
    status: str
    matches: bool | None
    report_markdown: str | None

    image_url: str | None = None
    fields: dict[str, str] = Field(default_factory=dict)