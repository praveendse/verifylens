"""Search history responses, query parameters and outcome counts."""
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, PlainSerializer

from app.dto.common import PageQuery
from app.dto.models import SearchResultBase, SearchSummary


# Same text as before these DTOs existed (datetime.isoformat: "+00:00", not
# pydantic's "Z"), so API clients see no change.
IsoDatetime = Annotated[datetime, PlainSerializer(lambda v: v.isoformat(), return_type=str, when_used="json")]


class HistoryQuery(PageQuery):
    # Keyset cursor: id of the oldest record the client already has.
    before_id: int | None = Field(default=None, ge=1)
    q: str | None = Field(default=None, max_length=200)
    status: Literal["SUCCESS", "ERROR", "PENDING"] | None = None


class HistoryItem(SearchSummary):
    created_at: IsoDatetime


class HistoryDetail(SearchResultBase):
    source_url: str | None
    # Plain-language reason, never the stored code.
    error_message: str | None
    created_at: IsoDatetime


class OutcomeBuckets(BaseModel):
    """One count per outcome. The same buckets everywhere: the History donut,
    the admin overview tiles and the daily activity chart."""
    match: int = 0
    no_match: int = 0
    error: int = 0
    other: int = 0  # PENDING, SUCCESS without a verdict, or any unknown status


class OutcomeCounts(OutcomeBuckets):
    total: int = 0


class HistoryStats(OutcomeCounts):
    completed: int = 0  # every SUCCESS, with or without a verdict
