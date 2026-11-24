import json

from sqlalchemy import func, or_
from sqlmodel import Session, select
from app.db.models import SearchRecord


class SearchRepository:

    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        query: str,
        user_id: int | None = None,
    ) -> SearchRecord:

        record = SearchRecord(
            query=query,
            user_id=user_id,
            status="PENDING",
        )

        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)

        return record


    def mark_success(
        self,
        record: SearchRecord,
        article_title: str,
        source_url: str,
        image_url: str,
        fields: dict[str, str],
        matches: bool,
        report_markdown: str,
        label_check: str | None = None,
        needs_review: bool | None = None,
        verification_mode: str | None = None,
    ) -> SearchRecord:

        record.article_title = article_title
        record.source_url = source_url
        record.image_url = image_url

        # Store dynamic Wikipedia infobox fields as JSON
        record.fields_json = json.dumps(
            fields,
            ensure_ascii=False,
        )

        record.matches = matches
        record.report_markdown = report_markdown
        record.label_check = label_check
        record.needs_review = needs_review
        record.verification_mode = verification_mode

        record.status = "SUCCESS"
        record.error_message = None

        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)

        return record


    def mark_error(
        self,
        record: SearchRecord,
        message: str,
    ) -> SearchRecord:

        record.status = "ERROR"
        record.error_message = message

        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)

        return record

    @staticmethod
    def _owned_by(statement, user_id: int | None):
        """Restrict to one user's records; None means no restriction (admin)."""
        if user_id is not None:
            statement = statement.where(SearchRecord.user_id == user_id)
        return statement

    def list_recent(
        self,
        limit: int = 20,
        user_id: int | None = None,
        *,
        before_id: int | None = None,
        query: str | None = None,
        status: str | None = None,
    ):
        """Newest-first page of records.

        Keyset pagination: before_id is the id of the last row the client
        already has, so new searches arriving between page loads never cause
        duplicated or skipped rows (unlike OFFSET).
        """
        statement = self._owned_by(select(SearchRecord), user_id)

        if before_id is not None:
            statement = statement.where(SearchRecord.id < before_id)

        if status is not None:
            statement = statement.where(SearchRecord.status == status)

        if query:
            # Case-insensitive substring match on the typed query or the
            # resolved article title. autoescape treats % and _ literally.
            needle = query.lower()
            statement = statement.where(
                or_(
                    func.lower(SearchRecord.query).contains(needle, autoescape=True),
                    func.lower(SearchRecord.article_title).contains(needle, autoescape=True),
                )
            )

        statement = (
            statement
            .order_by(SearchRecord.id.desc())
            .limit(limit)
        )

        return self.session.exec(statement).all()

    def count_outcomes(self, user_id: int | None = None) -> dict[str, int]:
        """Totals per outcome over ALL of a user's records (admin: all records).

        One GROUP BY query; no rows are loaded into memory.
        """
        statement = self._owned_by(
            select(SearchRecord.status, SearchRecord.matches, func.count())
            .group_by(SearchRecord.status, SearchRecord.matches),
            user_id,
        )

        counts = {"total": 0, "completed": 0, "match": 0, "no_match": 0, "error": 0, "other": 0}
        for status, matches, n in self.session.exec(statement).all():
            counts["total"] += n
            if status == "SUCCESS":
                counts["completed"] += n
            if status == "SUCCESS" and matches is True:
                counts["match"] += n
            elif status == "SUCCESS" and matches is False:
                counts["no_match"] += n
            elif status == "ERROR":
                counts["error"] += n
            else:
                # PENDING, SUCCESS without a verdict, or any unknown status
                counts["other"] += n
        return counts
