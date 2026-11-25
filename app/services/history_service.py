"""Search history access rules and responses (docs/specs/history.md)."""
import json

from sqlmodel import Session

from app.dto.history_models import HistoryDetail, HistoryItem, HistoryQuery, HistoryStats
from app.infra.db.models import SearchRecord, User
from app.infra.db.repository import SearchRepository
from app.services.search_errors import describe


class RecordNotFoundError(Exception):
    pass


def can_access(record: SearchRecord, user: User) -> bool:
    # Legacy rows without user_id belong to no user: admins can review them.
    return user.role == "admin" or record.user_id == user.id


def owner_scope(user: User) -> int | None:
    """Admins see every record; everyone else only their own."""
    return None if user.role == "admin" else user.id


def _get_accessible(repository: SearchRepository, user: User, record_id: int) -> SearchRecord:
    record = repository.get_by_id(record_id)
    if record is None or not can_access(record, user):
        # Same error for missing and not-yours: don't reveal other users' ids.
        raise RecordNotFoundError("Search record not found")
    return record


def list_history(session: Session, user: User, params: HistoryQuery) -> list[HistoryItem]:
    rows = SearchRepository(session).list_recent(
        limit=params.limit,
        user_id=owner_scope(user),
        before_id=params.before_id,
        query=(params.q or "").strip() or None,
        status=params.status,
    )
    return [HistoryItem.model_validate(r) for r in rows]


def get_stats(session: Session, user: User) -> HistoryStats:
    return SearchRepository(session).count_outcomes(user_id=owner_scope(user))


def get_detail(session: Session, user: User, record_id: int) -> HistoryDetail:
    record = _get_accessible(SearchRepository(session), user, record_id)
    return HistoryDetail(
        id=record.id,
        query=record.query,
        article_title=record.article_title,
        status=record.status,
        matches=record.matches,
        source_url=record.source_url,
        image_url=record.image_url,
        fields=json.loads(record.fields_json) if record.fields_json else {},
        report_markdown=record.report_markdown,
        # NULL on records saved before modes and the label check existed.
        verification_mode=record.verification_mode,
        label_check=record.label_check,
        needs_review=record.needs_review,
        # Plain-language reason, never the stored code.
        error_message=describe(record.error_message).message if record.status == "ERROR" else None,
        created_at=record.created_at,
    )


def delete_record(session: Session, user: User, record_id: int) -> None:
    repository = SearchRepository(session)
    repository.delete(_get_accessible(repository, user, record_id))
    session.commit()
