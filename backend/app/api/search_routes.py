from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.auth_dependencies import get_current_user
from app.api.dependencies import get_pipeline_service
from app.api.rate_limit import limit_search
from app.dto.models import SearchRequest, SearchResponse
from app.infra.db.database import get_session
from app.infra.db.models import User
from app.services import search_service
from app.services.pipeline_service import PipelineService
from app.services.search_errors import describe

router = APIRouter(tags=["Search"])

# 503 = temporary (try again later), 422 = nothing to verify for this topic,
# 500 = our fault.
FAILURE_STATUS = {"unavailable": 503, "topic": 422, "internal": 500}


@router.post(
    "/search",
    response_model=SearchResponse,
    # Runs before the record is saved, so blocked searches leave no history
    dependencies=[Depends(limit_search)],
)
def search_wikipedia(
    request: SearchRequest,
    session: Session = Depends(get_session),
    pipeline: PipelineService = Depends(get_pipeline_service),
    current_user: User = Depends(get_current_user),
):
    try:
        return search_service.run_search(session, pipeline, current_user, request)
    except search_service.SearchFailedError as exc:
        raise HTTPException(
            status_code=FAILURE_STATUS[exc.kind],
            detail=describe(exc.code).message,  # record id stays in the logs and History, not the message
        ) from exc
