from datetime import datetime
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    from app.config import Settings


# --- Pipeline: data passed between scraper, Gemini, label check and report ---

class ArticleDTO(BaseModel):
    title: str
    paragraph: str
    source_url: str
    image_url: str
    fields: dict[str, str]
    # Wikipedia's own labels for the image (spec SRCH-14); any may be missing.
    image_caption: str | None = None
    image_alt: str | None = None
    image_file: str | None = None


class VerificationDTO(BaseModel):
    description: str
    matches: bool = Field(strict=True)
    reason: str


LabelStatus = Literal["agrees", "unclear", "no_labels"]


class LabelCheckResult(BaseModel):
    """Label check (spec SRCH-14): do Wikipedia's labels name the subject?"""
    status: LabelStatus
    matched_in: list[str] = Field(default_factory=list)  # display names, e.g. "File name"


class GeminiConfig(BaseModel):
    """Everything a Gemini call needs, built once from Settings.

    New options (temperature, retries...) are added here instead of to every
    function signature.
    """
    model_config = ConfigDict(frozen=True)

    # repr=False keeps the key out of logs and tracebacks.
    api_key: str = Field(repr=False)
    model: str
    thinking_level: str = "low"
    # Each request is cut off after this; see gemini_service for the overall budget.
    timeout_s: float = 75

    @classmethod
    def from_settings(cls, settings: "Settings") -> "GeminiConfig":
        return cls(
            api_key=settings.gemini_api_key or "",
            model=settings.gemini_model,
            thinking_level=settings.gemini_thinking_level,
            timeout_s=settings.gemini_timeout_seconds,
        )


class ErrorReason(BaseModel):
    """Plain-language explanation of a stored search failure code."""
    model_config = ConfigDict(frozen=True)

    label: str     # short, for the admin overview
    message: str   # sentence for the person who searched


# --- Health -------------------------------------------------------------------

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


# --- Search -------------------------------------------------------------------

VerificationMode = Literal["standard", "thorough"]


class SearchRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    # Spec SRCH-15: "thorough" adds a blind image description (a second
    # Gemini call: about twice the time and cost). Default "standard".
    mode: VerificationMode = "standard"

    @field_validator("topic")
    @classmethod
    def clean_topic(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Topic cannot be empty")
        return value


class SearchSummary(BaseModel):
    """Fields every view of a search record shares."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    query: str
    article_title: str | None
    status: str
    matches: bool | None


class SearchResultBase(SearchSummary):
    """A search with its report: shared by POST /search and GET /history/{id}."""
    report_markdown: str | None
    image_url: str | None = None
    fields: dict[str, str] = Field(default_factory=dict)
    # NULL on records saved before modes and the label check existed.
    verification_mode: VerificationMode | None = None
    label_check: LabelStatus | None = None
    needs_review: bool | None = None


class SearchResponse(SearchResultBase):
    review_reason: str | None = None  # only known right after the search runs
