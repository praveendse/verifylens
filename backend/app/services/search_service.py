"""Search lifecycle: save the request, run the pipeline, record the outcome."""
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from sqlmodel import Session

from app.dto.models import SearchRequest, SearchResponse
from app.infra.db.models import User
from app.infra.db.repository import SearchRepository
from app.services.gemini_service import GeminiUnavailableError
from app.services.pipeline_service import PipelineService
from app.services.search_errors import code_for

logger = logging.getLogger(__name__)

# Failures caused by the topic itself: there is nothing to verify for it.
TOPIC_ERRORS = frozenset({"no_article", "ambiguous", "no_text", "no_image", "image_format"})

FailureKind = Literal["unavailable", "topic", "internal"]


class SearchFailedError(Exception):
    """The search failed and was saved as ERROR. `code` is a search_errors code."""

    def __init__(self, code: str, kind: FailureKind):
        super().__init__(code)
        self.code = code
        self.kind = kind


def run_search(
    session: Session, pipeline: PipelineService, user: User, request: SearchRequest,
) -> SearchResponse:
    repository = SearchRepository(session)
    # Saved before processing, so every attempt appears in History.
    record = repository.create(request.topic, user_id=user.id)

    try:
        # The pipeline's working files are temporary; the report is kept in the record.
        with TemporaryDirectory() as temp_dir:
            result = pipeline.generate_with_details(
                topic=request.topic, work_dir=Path(temp_dir), mode=request.mode,
            )
            markdown = result.report_path.read_text(encoding="utf-8")

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
        logger.exception("Search processing failed for record %s", record.id)

        # Store a short code; the user gets a plain-language reason for it.
        code = code_for(exc)
        repository.mark_error(record=record, message=code)

        if isinstance(exc, GeminiUnavailableError):
            kind: FailureKind = "unavailable"
        elif code in TOPIC_ERRORS:
            kind = "topic"
        else:
            kind = "internal"
        raise SearchFailedError(code, kind) from exc
