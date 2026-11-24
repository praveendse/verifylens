from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.dependencies import get_pipeline_service
from app.settings import Settings
from app.services.pipeline_service import PipelineService


def test_legacy_report_route_is_removed():
    """GET /report ran the pipeline anonymously; it must stay gone.

    The pipeline dependency is overridden with one that fails loudly, so this
    also proves no request path reaches the pipeline through /report.
    """

    class ExplodingPipeline:
        def generate(self, topic, work_dir):
            raise AssertionError("Pipeline must not run via /report")

        def generate_with_details(self, topic, work_dir, mode="standard"):
            raise AssertionError("Pipeline must not run via /report")

    app.dependency_overrides[get_pipeline_service] = lambda: ExplodingPipeline()

    try:
        with TestClient(app) as client:
            for params in ({}, {"topic": "World War II"}):
                response = client.get("/api/v1/report", params=params)
                assert response.status_code == 404

            # No other HTTP method should be routed there either.
            assert client.post("/api/v1/report").status_code in (404, 405)
    finally:
        app.dependency_overrides.clear()


def test_report_not_in_openapi_schema():
    paths = app.openapi()["paths"]
    assert "/api/v1/report" not in paths


def test_missing_gemini_api_key(monkeypatch, tmp_path: Path):
    """Without a Gemini key the pipeline fails fast, before launching a browser."""

    from app.services import pipeline_service

    def unexpected_browser_call():
        raise AssertionError("Playwright should not start")

    monkeypatch.setattr(pipeline_service, "sync_playwright", unexpected_browser_call)

    pipeline = PipelineService(settings=Settings(gemini_api_key=None))

    with pytest.raises(ValueError, match="Gemini API key not found"):
        pipeline.generate(topic="World War II", work_dir=tmp_path)
