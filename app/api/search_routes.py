import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.dependencies import get_pipeline_service
from app.db.database import get_session
from app.db.repository import SearchRepository
from app.dto.models import SearchRequest, SearchResponse
from app.services.gemini_service import GeminiUnavailableError
from app.services.pipeline_service import PipelineService

from app.api.auth_dependencies import get_current_user
from app.api.rate_limit import limit_search
from app.db.models import User

router = APIRouter(tags=["Search"])
logger = logging.getLogger(__name__)

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
    repository = SearchRepository(session)

    # Step 1: Save search before processing
    record = repository.create(
        request.topic,
        user_id=current_user.id,
    )

    try:
        # Step 2: Run Wikipedia + Gemini pipeline
        with TemporaryDirectory() as temp_dir:
            result = pipeline.generate_with_details(
                topic=request.topic,
                work_dir=Path(temp_dir),
            )

            markdown = result.report_path.read_text(
                encoding="utf-8"
            )

            # Step 3: Save successful result to SQLite
            record = repository.mark_success(
                record=record,
                article_title=result.article["title"],
                source_url=result.article["source_url"],
                image_url=result.article["image_url"],
                fields=result.article["fields"],
                matches=result.verification["matches"],
                report_markdown=markdown,
            )

            # Step 4: Return API response
            return SearchResponse(
                id=record.id,
                query=record.query,
                article_title=record.article_title,
                status=record.status,
                matches=record.matches,
                report_markdown=record.report_markdown,
                image_url=record.image_url,
                fields=result.article["fields"],
            )

    except Exception as exc:
        logger.exception(
            "Search processing failed for record %s",
            record.id,
        )

        repository.mark_error(
            record=record,
            message=type(exc).__name__,
        )

        if isinstance(exc, GeminiUnavailableError):
            # Temporary: timeouts, rate limits or Gemini server errors that
            # persisted through the retries. Tell the user to try again.
            raise HTTPException(
                status_code=503,
                detail=f"Gemini is busy or unreachable right now. Please try again in a minute. Record ID: {record.id}",
            ) from exc

        raise HTTPException(
            status_code=500,
            detail=f"Search processing failed. Record ID: {record.id}",
        ) from exc
