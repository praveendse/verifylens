"""Admin overview: the numbers behind the Admin > Overview tab.

Everything is computed with aggregate queries (COUNT / GROUP BY) or small
LIMITed selects, so the cost stays flat as the history grows; no record bodies
(reports, infobox data) are loaded. Days are UTC calendar days.
"""
from datetime import datetime, time, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from sqlmodel import Session, select

from app.api.auth_dependencies import require_admin
from app.db.database import get_session
from app.db.models import SearchRecord, User

router = APIRouter(prefix="/admin", tags=["Admin"])

TREND_DAYS = 30        # activity chart, top users, idle accounts, error causes
KPI_DAYS = 7           # headline tiles, compared with the 7 days before
TOP_USERS = 5
IDLE_SAMPLE = 5
RECENT_ERRORS = 8
ERROR_CAUSES = 3

# Search errors are stored as the exception class name only (see search_routes),
# so they are safe to show. Known ones get a readable label.
ERROR_LABELS = {
    "GeminiVerificationError": "Gemini returned an unusable answer",
    "GeminiUnavailableError": "Gemini unavailable (timeout or rate limit)",
    "TimeoutError": "Timed out",
    "PlaywrightTimeoutError": "Wikipedia page timed out",
    "ValueError": "Invalid article or image",
    "RuntimeError": "Download failed",
}


def _outcome():
    """Same buckets as the History donut (repository.count_outcomes)."""
    return case(
        (SearchRecord.status == "ERROR", "error"),
        ((SearchRecord.status == "SUCCESS") & (SearchRecord.matches == True), "match"),  # noqa: E712
        ((SearchRecord.status == "SUCCESS") & (SearchRecord.matches == False), "no_match"),  # noqa: E712
        else_="other",
    )


def _window(session: Session, start: datetime, end: datetime) -> dict:
    rows = session.exec(
        select(_outcome(), func.count())
        .where(SearchRecord.created_at >= start, SearchRecord.created_at < end)
        .group_by(_outcome())
    ).all()
    counts = {"total": 0, "match": 0, "no_match": 0, "error": 0, "other": 0}
    for bucket, n in rows:
        counts[bucket] += n
        counts["total"] += n
    active = session.exec(
        select(func.count(func.distinct(SearchRecord.user_id)))
        .where(SearchRecord.created_at >= start, SearchRecord.created_at < end,
               SearchRecord.user_id.is_not(None))
    ).one()
    counts["active_users"] = active
    return counts


def _iso_utc(value: datetime | None) -> str | None:
    """Stored datetimes are naive UTC; label them so browsers convert correctly."""
    if value is None:
        return None
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()


def _user_brief(user: User) -> dict:
    return {"id": user.id, "username": user.username, "full_name": user.full_name}


@router.get("/overview")
def admin_overview(
    admin: Annotated[User, Depends(require_admin)],
    session: Annotated[Session, Depends(get_session)],
):
    now = datetime.now(timezone.utc)
    # The datetime column requires timezone-aware values (stored as UTC).
    today = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    tomorrow = today + timedelta(days=1)
    trend_start = today - timedelta(days=TREND_DAYS - 1)
    kpi_start = tomorrow - timedelta(days=KPI_DAYS)
    prev_start = kpi_start - timedelta(days=KPI_DAYS)

    # Users ------------------------------------------------------------------
    def tally(condition):
        return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)

    total, admins, inactive, active_admins = session.exec(
        select(
            func.count(),
            tally(User.role == "admin"),
            tally(User.is_active == False),  # noqa: E712
            tally((User.role == "admin") & (User.is_active == True)),  # noqa: E712
        ).select_from(User)
    ).one()

    # Daily activity, zero-filled so the chart has one bar per day -----------
    day = func.date(SearchRecord.created_at)
    daily_rows = session.exec(
        select(day, _outcome(), func.count())
        .where(SearchRecord.created_at >= trend_start)
        .group_by(day, _outcome())
    ).all()
    daily = {
        (trend_start + timedelta(days=i)).date().isoformat(): {"match": 0, "no_match": 0, "error": 0, "other": 0}
        for i in range(TREND_DAYS)
    }
    for d, bucket, n in daily_rows:
        key = str(d)[:10]
        if key in daily:
            daily[key][bucket] += n

    # Most active users (30 days) ----------------------------------------------
    searches = func.count(SearchRecord.id).label("searches")
    top = session.exec(
        select(User, searches)
        .join(SearchRecord, SearchRecord.user_id == User.id)
        .where(SearchRecord.created_at >= trend_start)
        .group_by(User.id)
        .order_by(searches.desc(), User.id)
        .limit(TOP_USERS)
    ).all()

    # Active accounts with no searches in 30 days ------------------------------
    recent_searchers = (
        select(SearchRecord.user_id)
        .where(SearchRecord.created_at >= trend_start, SearchRecord.user_id.is_not(None))
        .distinct()
    )
    idle_filter = (User.is_active == True) & User.id.not_in(recent_searchers)  # noqa: E712
    idle_count = session.exec(select(func.count()).select_from(User).where(idle_filter)).one()
    idle_sample = session.exec(select(User).where(idle_filter).order_by(User.id).limit(IDLE_SAMPLE)).all()

    # Errors -----------------------------------------------------------------
    recent_errors = session.exec(
        select(SearchRecord.id, SearchRecord.query, SearchRecord.error_message,
               SearchRecord.created_at, User.username)
        .join(User, User.id == SearchRecord.user_id, isouter=True)
        .where(SearchRecord.status == "ERROR")
        .order_by(SearchRecord.id.desc())
        .limit(RECENT_ERRORS)
    ).all()
    cause = func.coalesce(SearchRecord.error_message, "Unknown")
    causes = session.exec(
        select(cause, func.count())
        .where(SearchRecord.status == "ERROR", SearchRecord.created_at >= trend_start)
        .group_by(cause)
        .order_by(func.count().desc())
        .limit(ERROR_CAUSES)
    ).all()

    def label(code):
        return ERROR_LABELS.get(code or "", code or "Unknown")

    return {
        "generated_at": now.isoformat(),
        "trend_days": TREND_DAYS,
        "kpi_days": KPI_DAYS,
        "users": {
            "total": total, "admins": admins, "inactive": inactive,
            # Account mix for the overview bar: these three add up to total.
            "active_admins": active_admins, "active_users": total - inactive - active_admins,
        },
        "last_period": _window(session, kpi_start, tomorrow),
        "previous_period": _window(session, prev_start, kpi_start),
        "daily": [{"date": d, **counts} for d, counts in daily.items()],
        "top_users": [{**_user_brief(u), "searches": n} for u, n in top],
        "idle_users": {"count": idle_count, "sample": [_user_brief(u) for u in idle_sample]},
        "recent_errors": [
            {"id": rid, "query": q, "code": code, "label": label(code),
             "created_at": _iso_utc(created),
             "username": username}
            for rid, q, code, created, username in recent_errors
        ],
        "error_causes": [{"code": c, "label": label(c), "count": n} for c, n in causes],
    }
