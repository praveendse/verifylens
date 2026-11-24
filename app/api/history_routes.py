"""Authenticated search history with per-user ownership enforcement."""
import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlmodel import Session

from app.api.auth_dependencies import get_current_user
from app.db.database import get_session
from app.db.models import SearchRecord, User
from app.db.repository import SearchRepository
from app.services.search_errors import describe

router = APIRouter(tags=["History"])

MAX_PAGE_SIZE = 50


def allowed(record: SearchRecord, user: User) -> bool:
    # Legacy rows without user_id belong to no user: admins can review them.
    return user.role == "admin" or record.user_id == user.id


def owner_scope(user: User) -> int | None:
    """Admins see every record; everyone else only their own."""
    return None if user.role == "admin" else user.id


@router.get("/history")
def get_search_history(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    # Page size is capped so no client can pull the whole table in one request.
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
    # Keyset cursor: id of the oldest record the client already has.
    before_id: Annotated[int | None, Query(ge=1)] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    status: Annotated[Literal["SUCCESS", "ERROR", "PENDING"] | None, Query()] = None,
):
    """Newest-first history. With no query parameters this behaves exactly as
    before (latest 20), so existing clients keep working."""
    repository = SearchRepository(session)
    rows = repository.list_recent(
        limit=limit,
        user_id=owner_scope(current_user),
        before_id=before_id,
        query=(q or "").strip() or None,
        status=status,
    )
    return [
        {
            "id": r.id,
            "query": r.query,
            "article_title": r.article_title,
            "status": r.status,
            "matches": r.matches,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.delete("/history/{record_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_search_history_record(
    record_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Owner or admin may delete. The report lives in this row (the pipeline's
    working files are temporary), so nothing else needs cleaning up."""
    record = session.get(SearchRecord, record_id)
    if record is None or not allowed(record, current_user):
        # Same 404 for missing and not-yours: don't reveal other users' ids.
        raise HTTPException(status_code=404, detail="Search record not found")
    session.delete(record)
    session.commit()


# Declared before /history/{record_id} so "stats" is never parsed as an id.
@router.get("/history/stats")
def get_search_history_stats(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Outcome totals over all of the caller's records (admins: all records)."""
    return SearchRepository(session).count_outcomes(user_id=owner_scope(current_user))


@router.get("/history/{record_id}")
def get_search_history_detail(
    record_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
):
    record = session.get(SearchRecord, record_id)
    if record is None or not allowed(record, current_user):
        # Return the same 404 for missing and unauthorized records.
        raise HTTPException(status_code=404, detail="Search record not found")
    return {
        "id": record.id,
        "query": record.query,
        "article_title": record.article_title,
        "status": record.status,
        "matches": record.matches,
        "source_url": record.source_url,
        "image_url": record.image_url,
        "fields": json.loads(record.fields_json) if record.fields_json else {},
        "report_markdown": record.report_markdown,
        # NULL on records saved before modes and the label check existed.
        "verification_mode": record.verification_mode,
        "label_check": record.label_check,
        "needs_review": record.needs_review,
        # Plain-language reason, never the stored code.
        "error_message": describe(record.error_message)[1] if record.status == "ERROR" else None,
        "created_at": record.created_at,
    }
