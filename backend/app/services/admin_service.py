"""Business logic and response preparation for the admin overview. Days are UTC calendar days."""
from datetime import datetime, time, timedelta, timezone

from sqlmodel import Session

from app.dto.admin_models import (
    AdminOverviewResponse,
    DailyActivity,
    ErrorCause,
    IdleUsers,
    PeriodCounts,
    RecentError,
    TopUser,
    UserBrief,
    UserCounts,
)
from app.infra.db.admin_repository import AdminRepository
from app.infra.db.models import User
from app.services.search_errors import describe

TREND_DAYS = 30        # activity chart, top users, idle accounts, error causes
KPI_DAYS = 7           # headline tiles, compared with the 7 days before
TOP_USERS = 5
IDLE_SAMPLE = 5
RECENT_ERRORS = 8
ERROR_CAUSES = 3


def _label(code: str) -> str:
    return describe(code).label


def _merge_causes(causes) -> list[ErrorCause]:
    """Old records store class names, new ones codes; both can share a label.
    Merge rows by label, then keep the most common few."""
    merged: dict[str, ErrorCause] = {}
    for code, n in causes:
        row = merged.setdefault(_label(code), ErrorCause(code=code, label=_label(code), count=0))
        row.count += n
    return sorted(merged.values(), key=lambda r: -r.count)[:ERROR_CAUSES]


def _window(repository: AdminRepository, start: datetime, end: datetime) -> PeriodCounts:
    counts = PeriodCounts()
    for bucket, n in repository.get_period_outcomes(start, end):
        setattr(counts, bucket, getattr(counts, bucket) + n)
        counts.total += n
    counts.active_users = repository.count_active_users(start, end)
    return counts


def _daily(repository: AdminRepository, start: datetime) -> list[DailyActivity]:
    """Zero-filled, so the chart has one bar per day."""
    dates = [(start + timedelta(days=i)).date().isoformat() for i in range(TREND_DAYS)]
    daily = {d: DailyActivity(date=d) for d in dates}
    for d, bucket, n in repository.get_daily_activity(start):
        key = str(d)[:10]
        if key in daily:
            setattr(daily[key], bucket, getattr(daily[key], bucket) + n)
    return list(daily.values())


def _iso_utc(value: datetime | None) -> str | None:
    """Stored datetimes are naive UTC; label them so browsers convert correctly."""
    if value is None:
        return None
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()


def _user_brief(user: User) -> UserBrief:
    return UserBrief(id=user.id, username=user.username, full_name=user.full_name)


def get_admin_overview(session: Session) -> AdminOverviewResponse:
    repository = AdminRepository(session)
    now = datetime.now(timezone.utc)
    # The datetime column requires timezone-aware values (stored as UTC).
    today = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    tomorrow = today + timedelta(days=1)
    trend_start = today - timedelta(days=TREND_DAYS - 1)
    kpi_start = tomorrow - timedelta(days=KPI_DAYS)
    prev_start = kpi_start - timedelta(days=KPI_DAYS)

    total, admins, inactive, active_admins = repository.get_user_counts()
    top = repository.get_top_users(trend_start, TOP_USERS)
    idle_sample = repository.get_idle_users(trend_start, IDLE_SAMPLE)

    return AdminOverviewResponse(
        generated_at=now.isoformat(),
        trend_days=TREND_DAYS,
        kpi_days=KPI_DAYS,
        users=UserCounts(
            total=total, admins=admins, inactive=inactive,
            # Account mix for the overview bar: these three add up to total.
            active_admins=active_admins, active_users=total - inactive - active_admins,
        ),
        last_period=_window(repository, kpi_start, tomorrow),
        previous_period=_window(repository, prev_start, kpi_start),
        daily=_daily(repository, trend_start),
        top_users=[TopUser(**_user_brief(u).model_dump(), searches=n) for u, n in top],
        idle_users=IdleUsers(
            count=repository.count_idle_users(trend_start),
            sample=[_user_brief(u) for u in idle_sample],
        ),
        recent_errors=[
            RecentError(id=rid, query=q, code=code, label=_label(code),
                        created_at=_iso_utc(created), username=username)
            for rid, q, code, created, username in repository.get_recent_errors(RECENT_ERRORS)
        ],
        error_causes=_merge_causes(repository.get_error_causes(trend_start)),
    )
