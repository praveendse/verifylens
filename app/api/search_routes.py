import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.dependencies import get_pipeline_service
from app.infra.db.database import get_session
from app.infra.db.repository import SearchRepository
from app.dto.models import SearchRequest, SearchResponse
from app.services.gemini_service import GeminiUnavailableError
from app.services.search_errors import code_for, describe
from app.services.pipeline_service import PipelineService

from app.api.auth_dependencies import get_current_user
from app.api.rate_limit import limit_search
from app.infra.db.models import User

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
                mode=request.mode,
            )

            markdown = result.report_path.read_text(
                encoding="utf-8"
            )

            # Step 3: Save successful result to SQLite
            record = repository.mark_success(
                record=record,
                article_title=result.article.title,
                source_url=result.article.source_url,
                image_url=result.article.image_url,
                fields=result.article.fields,
                matches=result.verification.matches,
                report_markdown=markdown,
                # Super mode only; NULL in standard mode (spec SRCH-14)
                label_check=result.labels.status if result.labels else None,
                needs_review=(result.review_reason is not None) if result.labels else None,
                verification_mode=request.mode,
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
                fields=result.article.fields,
                verification_mode=record.verification_mode,
                label_check=record.label_check,
                needs_review=record.needs_review,
                review_reason=result.review_reason,
            )

    except Exception as exc:
        logger.exception(
            "Search processing failed for record %s",
            record.id,
        )

        # Store a short code; the user gets a plain-language reason for it.
        code = code_for(exc)
        repository.mark_error(record=record, message=code)

        # 503 = temporary (try again later), 422 = nothing to verify for this
        # topic, 500 = our fault.
        if isinstance(exc, GeminiUnavailableError):
            status = 503
        elif code in ("no_article", "ambiguous", "no_text", "no_image", "image_format"):
            status = 422
        else:
            status = 500

        raise HTTPException(
            status_code=status,
            detail=describe(code).message,  # record id stays in the logs and History, not the message
        ) from exc
