"""Authenticated search history with per-user ownership enforcement."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlmodel import Session

from app.api.auth_dependencies import get_current_user
from app.infra.db.database import get_session
from app.infra.db.models import User
from app.dto.history_models import HistoryDetail, HistoryItem, HistoryQuery, HistoryStats
from app.services import history_service

router = APIRouter(tags=["History"])


@router.get("/history", response_model=list[HistoryItem])
def get_search_history(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    params: Annotated[HistoryQuery, Query()],
):
    """Newest-first history. With no query parameters this behaves exactly as
    before (latest 20), so existing clients keep working."""
    return history_service.list_history(session, current_user, params)


@router.delete("/history/{record_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_search_history_record(
    record_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Owner or admin may delete. The report lives in this row (the pipeline's
    working files are temporary), so nothing else needs cleaning up."""
    try:
        history_service.delete_record(session, current_user, record_id)
    except history_service.RecordNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# Declared before /history/{record_id} so "stats" is never parsed as an id.
@router.get("/history/stats", response_model=HistoryStats)
def get_search_history_stats(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Outcome totals over all of the caller's records (admins: all records)."""
    return history_service.get_stats(session, current_user)


@router.get("/history/{record_id}", response_model=HistoryDetail)
def get_search_history_detail(
    record_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
):
    try:
        return history_service.get_detail(session, current_user, record_id)
    except history_service.RecordNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
