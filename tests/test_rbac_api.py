"""End-to-end API authorization tests using an isolated temporary SQLite DB.

No Wikipedia or Gemini calls. No changes to real user/search data.
"""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.dependencies import get_pipeline_service
from app.db.database import get_session
from app.db.models import SearchRecord, User
from app.dto.models import ArticleDTO, LabelCheckResult, VerificationDTO
from app.services.pipeline_service import PipelineResult
from app.main import app
from security.passwords import hash_password


class FakePipeline:
    def generate_with_details(self, topic: str, work_dir: Path, mode: str = "standard"):
        report_path = work_dir / "report.md"
        report_path.write_text(f"# {topic}\n\n**Match Status: PASS**", encoding="utf-8")
        return PipelineResult(
            report_path=report_path,
            article=ArticleDTO.model_validate({
                "title": topic,
                "paragraph": "An example article.",
                "source_url": "https://en.wikipedia.org/wiki/Test",
                "image_url": "https://example.com/image.jpg",
                "fields": {"known for": "A test"},
            }),
            verification=VerificationDTO.model_validate({"description": "Example image", "matches": True, "reason": "Matched"}),
            labels=LabelCheckResult(status="agrees", matched_in=["File name"]),
            review_reason=None,
        )


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-key-only-do-not-use-in-production-very-long-secret-123")
    test_engine = create_engine(
        f"sqlite:///{tmp_path / 'rbac_test.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        session.add(User(username="superadmin", hashed_password=hash_password("secure-admin-pass-123"), role="admin"))
        session.add(User(username="alice", hashed_password=hash_password("secure-alice-pass-123"), role="user"))
        session.add(User(username="bob", hashed_password=hash_password("secure-bob-pass-123"), role="user"))
        session.commit()

    def test_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = test_session
    app.dependency_overrides[get_pipeline_service] = lambda: FakePipeline()
    try:
        with TestClient(app) as client:
            yield client, test_engine
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_pipeline_service, None)
        test_engine.dispose()


def authorization(client, username, password):
    resp = client.post("/api/v1/auth/login", data={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_anonymous_cannot_search_or_read_history(api):
    client, engine = api
    assert client.post("/api/v1/search", json={"topic": "Einstein"}).status_code == 401
    assert client.get("/api/v1/history").status_code == 401
    assert client.get("/api/v1/history/1").status_code == 401
    with Session(engine) as session:
        assert session.exec(select(SearchRecord)).all() == []


def test_only_admin_can_manage_users(api):
    client, _ = api
    user_headers = authorization(client, "alice", "secure-alice-pass-123")
    admin_headers = authorization(client, "superadmin", "secure-admin-pass-123")
    body = {
        "username": "new.researcher", "full_name": "New Researcher",
        "password": "secure-new-user-pass-123", "role": "user",
    }
    assert client.get("/api/v1/users", headers=user_headers).status_code == 403
    assert client.post("/api/v1/users", headers=user_headers, json=body).status_code == 403
    created = client.post("/api/v1/users", headers=admin_headers, json=body)
    assert created.status_code == 201, created.text
    assert created.json()["full_name"] == "New Researcher"
    assert "hashed_password" not in created.json()
    # Admin-chosen password is temporary: nothing works until it's replaced.
    assert created.json()["must_change_password"] is True
    new_user = authorization(client, "new.researcher", "secure-new-user-pass-123")
    assert client.get("/api/v1/history", headers=new_user).status_code == 403
    assert client.get("/api/v1/auth/me", headers=new_user).json()["must_change_password"] is True
    users = client.get("/api/v1/users", headers=admin_headers)
    assert users.status_code == 200
    assert "new.researcher" in [x["username"] for x in users.json()]
    duplicate = client.post("/api/v1/users", headers=admin_headers, json=body)
    assert duplicate.status_code == 409


def test_password_must_not_contain_username(api):
    client, _ = api
    admin_headers = authorization(client, "superadmin", "secure-admin-pass-123")
    body = {"username": "Carol.Smith", "password": "my-CAROL.SMITH-pass-1", "role": "user"}
    rejected = client.post("/api/v1/users", headers=admin_headers, json=body)
    assert rejected.status_code == 422
    assert "must not contain the username" in rejected.text


def test_history_is_owned_by_user(api):
    client, engine = api
    alice = authorization(client, "alice", "secure-alice-pass-123")
    bob = authorization(client, "bob", "secure-bob-pass-123")
    admin = authorization(client, "superadmin", "secure-admin-pass-123")
    a = client.post("/api/v1/search", headers=alice, json={"topic": "Albert Einstein"})
    b = client.post("/api/v1/search", headers=bob, json={"topic": "Isaac Newton"})
    assert a.status_code == 200, a.text
    assert b.status_code == 200, b.text
    alice_history = client.get("/api/v1/history", headers=alice).json()
    bob_history = client.get("/api/v1/history", headers=bob).json()
    admin_history = client.get("/api/v1/history", headers=admin).json()
    assert [x["query"] for x in alice_history] == ["Albert Einstein"]
    assert [x["query"] for x in bob_history] == ["Isaac Newton"]
    assert len(admin_history) == 2
    search_id = a.json()["id"]
    assert client.get(f"/api/v1/history/{search_id}", headers=bob).status_code == 404
    detail = client.get(f"/api/v1/history/{search_id}", headers=alice)
    assert detail.status_code == 200
    assert detail.json()["fields"]["known for"] == "A test"
    assert client.get(f"/api/v1/history/{search_id}", headers=admin).status_code == 200
    with Session(engine) as session:
        saved = session.get(SearchRecord, search_id)
        alice_user = session.exec(select(User).where(User.username == "alice")).one()
        assert saved.user_id == alice_user.id
        assert json.loads(saved.fields_json)["known for"] == "A test"


def test_admin_cannot_deactivate_or_demote_self(api):
    client, engine = api
    headers = authorization(client, "superadmin", "secure-admin-pass-123")
    with Session(engine) as session:
        admin = session.exec(select(User).where(User.username == "superadmin")).one()
        admin_id = admin.id
    assert client.patch(f"/api/v1/users/{admin_id}", headers=headers, json={"role": "user"}).status_code == 400
    assert client.patch(f"/api/v1/users/{admin_id}", headers=headers, json={"is_active": False}).status_code == 400


def test_admin_can_deactivate_user_and_block_login(api):
    client, engine = api
    headers = authorization(client, "superadmin", "secure-admin-pass-123")
    with Session(engine) as session:
        user_id = session.exec(select(User).where(User.username == "bob")).one().id
    resp = client.patch(f"/api/v1/users/{user_id}", headers=headers, json={"is_active": False})
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_active"] is False
    assert client.post("/api/v1/auth/login", data={"username": "bob", "password": "secure-bob-pass-123"}).status_code == 401


@pytest.mark.parametrize("password", [" " * 12, "\t" * 12, " \n " * 5])
def test_create_rejects_whitespace_only_password(api, password):
    """AUTH-08 / USR-03: create applies the same password rules as reset and change."""
    client, engine = api
    admin_headers = authorization(client, "superadmin", "secure-admin-pass-123")
    body = {"username": "dave", "password": password, "role": "user"}
    rejected = client.post("/api/v1/users", headers=admin_headers, json=body)
    assert rejected.status_code == 422, rejected.text
    assert "only spaces" in rejected.text
    with Session(engine) as session:
        assert session.exec(select(User).where(User.username == "dave")).first() is None
