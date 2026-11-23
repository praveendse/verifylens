"""POST /search when Gemini is unavailable vs. when processing fails.

Uses the isolated temp-DB fixture from test_history_paging (real login, no
Wikipedia or Gemini calls: the pipeline is replaced by a fake that raises).
"""
from sqlmodel import Session, select

from app.api.dependencies import get_pipeline_service
from app.db.models import SearchRecord
from app.main import app
from app.services.gemini_service import GeminiUnavailableError
from test_history_paging import api, login  # noqa: F401  (api is a fixture)


class FailingPipeline:
    def __init__(self, exc):
        self.exc = exc

    def generate_with_details(self, topic, work_dir):
        raise self.exc


def search_with(client, exc):
    app.dependency_overrides[get_pipeline_service] = lambda: FailingPipeline(exc)
    try:
        return client.post("/api/v1/search", json={"topic": "BMW"}, headers=login(client, "alice"))
    finally:
        app.dependency_overrides.pop(get_pipeline_service, None)


def test_gemini_unavailable_returns_503_and_records_the_error(api):
    client, engine = api
    resp = search_with(client, GeminiUnavailableError("Gemini unavailable after 3 attempts (HTTP 429)"))

    assert resp.status_code == 503
    assert "try again" in resp.json()["detail"]
    with Session(engine) as session:
        record = session.exec(select(SearchRecord)).one()
    assert (record.status, record.error_message) == ("ERROR", "ai_busy")


def test_other_failures_still_return_500(api):
    client, _ = api
    resp = search_with(client, RuntimeError("download failed"))

    assert resp.status_code == 500
    detail = resp.json()["detail"]
    assert "Something went wrong" in detail and "#" not in detail
    assert "RuntimeError" not in detail and "download failed" not in detail


def test_ambiguous_topic_returns_422_with_a_plain_reason(api):
    from app.services.search_errors import SearchFailure

    client, engine = api
    resp = search_with(client, SearchFailure("ambiguous"))

    assert resp.status_code == 422
    assert "more specific name" in resp.json()["detail"]
    with Session(engine) as session:
        record = session.exec(select(SearchRecord)).one()
    assert record.error_message == "ambiguous"
