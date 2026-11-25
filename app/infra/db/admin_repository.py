"""Database queries for the admin overview dashboard.

Everything is computed with aggregate queries (COUNT / GROUP BY) or small
LIMITed selects, so the cost stays flat as the history grows; no record bodies
(reports, infobox data) are loaded.
"""
from datetime import datetime

from sqlalchemy import case, func
from sqlmodel import Session, select

from app.infra.db.models import SearchRecord, User


def _outcome():
    """Same buckets as the History donut (repository.count_outcomes)."""
    return case(
        (SearchRecord.status == "ERROR", "error"),
        ((SearchRecord.status == "SUCCESS") & (SearchRecord.matches == True), "match"),  # noqa: E712
        ((SearchRecord.status == "SUCCESS") & (SearchRecord.matches == False), "no_match"),  # noqa: E712
        else_="other",
    )


class AdminRepository:

    def __init__(self, session: Session):
        self.session = session

    def get_user_counts(self) -> tuple[int, int, int, int]:
        """Total, admin, inactive and active-admin counts."""
        def tally(condition):
            return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)

        statement = select(
            func.count(),
            tally(User.role == "admin"),
            tally(User.is_active == False),  # noqa: E712
            tally((User.role == "admin") & (User.is_active == True)),  # noqa: E712
        ).select_from(User)
        return self.session.exec(statement).one()

    def get_period_outcomes(self, start: datetime, end: datetime) -> list[tuple[str, int]]:
        statement = (
            select(_outcome(), func.count())
            .where(SearchRecord.created_at >= start, SearchRecord.created_at < end)
            .group_by(_outcome())
        )
        return self.session.exec(statement).all()

    def count_active_users(self, start: datetime, end: datetime) -> int:
        statement = (
            select(func.count(func.distinct(SearchRecord.user_id)))
            .where(SearchRecord.created_at >= start, SearchRecord.created_at < end,
                   SearchRecord.user_id.is_not(None))
        )
        return self.session.exec(statement).one()

    def get_daily_activity(self, since: datetime) -> list[tuple[str, str, int]]:
        """(day, outcome, count) rows; days with no searches are absent."""
        day = func.date(SearchRecord.created_at)
        statement = (
            select(day, _outcome(), func.count())
            .where(SearchRecord.created_at >= since)
            .group_by(day, _outcome())
        )
        return self.session.exec(statement).all()

    def get_top_users(self, since: datetime, limit: int) -> list[tuple[User, int]]:
        searches = func.count(SearchRecord.id).label("searches")
        statement = (
            select(User, searches)
            .join(SearchRecord, SearchRecord.user_id == User.id)
            .where(SearchRecord.created_at >= since)
            .group_by(User.id)
            .order_by(searches.desc(), User.id)
            .limit(limit)
        )
        return self.session.exec(statement).all()

    @staticmethod
    def _idle_filter(since: datetime):
        """Active accounts with no searches since the given time."""
        recent_searchers = (
            select(SearchRecord.user_id)
            .where(SearchRecord.created_at >= since, SearchRecord.user_id.is_not(None))
            .distinct()
        )
        return (User.is_active == True) & User.id.not_in(recent_searchers)  # noqa: E712

    def count_idle_users(self, since: datetime) -> int:
        statement = select(func.count()).select_from(User).where(self._idle_filter(since))
        return self.session.exec(statement).one()

    def get_idle_users(self, since: datetime, limit: int) -> list[User]:
        statement = select(User).where(self._idle_filter(since)).order_by(User.id).limit(limit)
        return self.session.exec(statement).all()

    def get_recent_errors(self, limit: int) -> list[tuple[int, str, str | None, datetime, str | None]]:
        """(id, query, error code, created_at, username) of the latest failed searches."""
        statement = (
            select(SearchRecord.id, SearchRecord.query, SearchRecord.error_message,
                   SearchRecord.created_at, User.username)
            .join(User, User.id == SearchRecord.user_id, isouter=True)
            .where(SearchRecord.status == "ERROR")
            .order_by(SearchRecord.id.desc())
            .limit(limit)
        )
        return self.session.exec(statement).all()

    def get_error_causes(self, since: datetime) -> list[tuple[str, int]]:
        cause = func.coalesce(SearchRecord.error_message, "Unknown")
        statement = (
            select(cause, func.count())
            .where(SearchRecord.status == "ERROR", SearchRecord.created_at >= since)
            .group_by(cause)
        )
        return self.session.exec(statement).all()
