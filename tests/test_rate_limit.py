"""Rate limits on login and search (isolated temp DB, fake pipeline)."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app.api import rate_limit
from app.api.dependencies import get_pipeline_service
from app.db.database import get_session
from app.db.models import SearchRecord, User
from app.main import app
from security.passwords import hash_password

PASSWORD = "secure-test-pass-123"


class FakePipeline:
    def __init__(self):
        self.runs = 0

    def generate_with_details(self, topic: str, work_dir: Path):
        self.runs += 1
        report_path = work_dir / "report.md"
        report_path.write_text(f"# {topic}", encoding="utf-8")
        return SimpleNamespace(
            report_path=report_path,
            article={
                "title": topic,
                "paragraph": "x",
                "source_url": "https://en.wikipedia.org/wiki/Test",
                "image_url": "https://example.com/i.jpg",
                "fields": {},
            },
            verification={"description": "x", "matches": True, "reason": "x"},
        )


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-key-only-do-not-use-in-production-very-long-secret-123")
    engine = create_engine(f"sqlite:///{tmp_path / 'rl.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        for name in ("alice", "bob"):
            s.add(User(username=name, hashed_password=hash_password(PASSWORD), role="user"))
        s.commit()

    def session_override():
        with Session(engine) as s:
            yield s

    pipeline = FakePipeline()
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_pipeline_service] = lambda: pipeline
    try:
        with TestClient(app) as client:
            yield client, engine, pipeline
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_pipeline_service, None)
        engine.dispose()


def login(client, username, password=PASSWORD):
    return client.post("/api/v1/auth/login", data={"username": username, "password": password})


def token(client, username):
    resp = login(client, username)
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_login_blocked_after_too_many_attempts_for_one_username(api):
    client, _, _ = api
    limit = rate_limit.login_user_limiter.limit
    for _ in range(limit):
        assert login(client, "alice", "wrong-password-123").status_code == 401

    blocked = login(client, "alice")  # even the correct password is refused now
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    assert "Too many login attempts" in blocked.json()["detail"]

    # Username key is case-insensitive, so "ALICE" cannot dodge the limit.
    assert login(client, "ALICE").status_code == 429
    # Another account is unaffected by alice's limit.
    assert login(client, "bob").status_code == 200


def test_login_blocked_per_ip_across_usernames(api):
    client, _, _ = api
    limit = rate_limit.login_ip_limiter.limit
    for i in range(limit):
        assert login(client, f"nobody{i}", "wrong-password-123").status_code == 401
    assert login(client, "bob").status_code == 429


def test_search_blocked_after_limit_and_no_record_saved(api):
    client, engine, pipeline = api
    alice = token(client, "alice")
    limit = rate_limit.search_limiter.limit

    for i in range(limit):
        assert client.post("/api/v1/search", json={"topic": f"T{i}"}, headers=alice).status_code == 200

    blocked = client.post("/api/v1/search", json={"topic": "one too many"}, headers=alice)
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    assert pipeline.runs == limit  # Gemini/browser never started for the blocked call
    with Session(engine) as s:
        assert len(s.exec(select(SearchRecord)).all()) == limit

    # Limit is per user: bob can still search.
    bob = token(client, "bob")
    assert client.post("/api/v1/search", json={"topic": "Bob"}, headers=bob).status_code == 200


def test_anonymous_search_is_401_not_429(api):
    client, _, _ = api
    for _ in range(rate_limit.search_limiter.limit + 2):
        assert client.post("/api/v1/search", json={"topic": "x"}).status_code == 401


def test_window_expires(monkeypatch):
    limiter = rate_limit.RateLimiter(limit=2, window_s=60)
    now = [1000.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: now[0])

    assert limiter.hit("k") is None
    assert limiter.hit("k") is None
    assert limiter.hit("k") == pytest.approx(60)
    now[0] += 59
    assert limiter.hit("k") == pytest.approx(1)
    now[0] += 1  # first hit is now 60s old
    assert limiter.hit("k") is None
