"""Admin overview response (Admin > Overview tab)."""
from pydantic import BaseModel

from app.dto.history_models import OutcomeBuckets, OutcomeCounts


class UserCounts(BaseModel):
    total: int
    admins: int
    inactive: int
    # Account mix for the overview bar: these three add up to total.
    active_admins: int
    active_users: int


class PeriodCounts(OutcomeCounts):
    active_users: int = 0  # distinct users who searched in the period


class DailyActivity(OutcomeBuckets):
    date: str  # UTC calendar day, YYYY-MM-DD


class UserBrief(BaseModel):
    id: int
    username: str
    full_name: str | None


class TopUser(UserBrief):
    searches: int


class IdleUsers(BaseModel):
    count: int
    sample: list[UserBrief]


class RecentError(BaseModel):
    id: int
    query: str
    code: str | None
    label: str
    created_at: str | None  # ISO 8601 with explicit UTC offset
    username: str | None    # None when the user was deleted


class ErrorCause(BaseModel):
    code: str
    label: str
    count: int


class AdminOverviewResponse(BaseModel):
    generated_at: str
    trend_days: int
    kpi_days: int
    users: UserCounts
    last_period: PeriodCounts
    previous_period: PeriodCounts
    daily: list[DailyActivity]
    top_users: list[TopUser]
    idle_users: IdleUsers
    recent_errors: list[RecentError]
    error_causes: list[ErrorCause]
