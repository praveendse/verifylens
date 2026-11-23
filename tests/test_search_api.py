
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app.main import app
from app.api.dependencies import get_pipeline_service
from app.db.database import get_session
from app.db.models import SearchRecord, User
from security.passwords import hash_password

TEST_USERNAME = "searcher"
TEST_PASSWORD = "secure-searcher-pass-123"


# Fake pipeline: no Wikipedia or Gemini requests
class FakePipeline:

    def __init__(self):
        self.fail = False

    def generate_with_details(
        self,
        topic: str,
        work_dir: Path,
    ):
        if self.fail:
            raise RuntimeError("Simulated pipeline failure")

        # Create a fake Markdown report
        report_path = work_dir / "report.md"

        report_path.write_text(
            f"# {topic}\n\n**Match Status: PASS**",
            encoding="utf-8",
        )

        return SimpleNamespace(
            report_path=report_path,
            article={
                "title": topic,
                "paragraph": "A test article.",
                "source_url": "https://en.wikipedia.org/wiki/Test",
                "image_url": "https://example.com/image.jpg",
                "fields": {
                    "born": "14 March 1879",
                    "known for": "Relativity",
                },
            },
            verification={
                "description": "A portrait.",
                "matches": True,
                "reason": "Matches the article.",
            },
        )


# Setup: temporary database and dependency overrides
@pytest.fixture
def test_setup(tmp_path, monkeypatch):

    monkeypatch.setenv(
        "JWT_SECRET_KEY",
        "test-key-only-do-not-use-in-production-very-long-secret-123",
    )

    db_path = tmp_path / "test_search.db"

    test_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    SQLModel.metadata.create_all(test_engine)

    # /search and /history require login, so create a normal user
    with Session(test_engine) as session:
        session.add(
            User(
                username=TEST_USERNAME,
                hashed_password=hash_password(TEST_PASSWORD),
                role="user",
            )
        )
        session.commit()

    def override_session():
        with Session(test_engine) as session:
            yield session

    fake_pipeline = FakePipeline()

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_pipeline_service] = (
        lambda: fake_pipeline
    )

    try:
        with TestClient(app) as client:
            # Log in once; every request in the test then sends the token
            login = client.post(
                "/api/v1/auth/login",
                data={"username": TEST_USERNAME, "password": TEST_PASSWORD},
            )
            assert login.status_code == 200, login.text
            client.headers["Authorization"] = (
                f"Bearer {login.json()['access_token']}"
            )

            yield client, test_engine, fake_pipeline
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(
            get_pipeline_service, None
        )
        test_engine.dispose()


# Test 1: Successful search and database storage
def test_successful_search(test_setup):

    client, engine, _ = test_setup

    response = client.post(
        "/api/v1/search",
        json={"topic": "Albert Einstein"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["query"] == "Albert Einstein"
    assert data["status"] == "SUCCESS"
    assert data["matches"] is True
    assert "# Albert Einstein" in data["report_markdown"]

    # Verify the actual SQLite record
    with Session(engine) as session:
        record = session.get(SearchRecord, data["id"])

        assert record is not None
        assert record.status == "SUCCESS"
        assert record.report_markdown is not None

        fields = json.loads(record.fields_json)

        assert fields["born"] == "14 March 1879"
        assert fields["known for"] == "Relativity"


# Test 2: Pipeline error is saved
def test_failed_search(test_setup):

    client, engine, fake_pipeline = test_setup

    fake_pipeline.fail = True

    response = client.post(
        "/api/v1/search",
        json={"topic": "Albert Einstein"},
    )

    assert response.status_code == 500

    with Session(engine) as session:
        records = session.exec(
            select(SearchRecord)
        ).all()

        assert len(records) == 1
        assert records[0].status == "ERROR"
        assert records[0].error_message == "unknown"


# Test 3: History endpoint retrieves stored searches
def test_search_history(test_setup):

    client, _, _ = test_setup

    client.post(
        "/api/v1/search",
        json={"topic": "Albert Einstein"},
    )

    client.post(
        "/api/v1/search",
        json={"topic": "Isaac Newton"},
    )

    response = client.get("/api/v1/history")

    assert response.status_code == 200

    history = response.json()

    assert len(history) == 2
    assert history[0]["query"] == "Isaac Newton"
    assert history[1]["query"] == "Albert Einstein"


# Test 4: Empty topics are rejected
def test_empty_topic(test_setup):

    client, engine, _ = test_setup

    response = client.post(
        "/api/v1/search",
        json={"topic": "   "},
    )

    assert response.status_code == 422

    with Session(engine) as session:
        records = session.exec(
            select(SearchRecord)
        ).all()

        assert len(records) == 0
