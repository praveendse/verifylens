"""Authentication tests use an isolated SQLite file and never touch real user data."""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.auth_dependencies import require_admin
from app.infra.db.database import get_session
from app.infra.db.models import User
from app.main import app
from security.passwords import hash_password


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "this-is-a-test-secret-only-do-not-use-in-production-123")
    db_engine = create_engine(
        f"sqlite:///{tmp_path / 'auth_api_test.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(db_engine)
    with Session(db_engine) as session:
        session.add(User(username="admin_test", hashed_password=hash_password("testing-password-123"), role="admin"))
        session.add(User(username="user_test", hashed_password=hash_password("testing-password-456"), role="user"))
        session.commit()

    def test_session():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_session] = test_session
    try:
        with TestClient(app) as client:
            yield client, db_engine
    finally:
        app.dependency_overrides.pop(get_session, None)
        db_engine.dispose()


def login(api, username="admin_test", password="testing-password-123"):
    client, _ = api
    return client.post("/api/v1/auth/login", data={"username": username, "password": password})


def test_valid_login_and_me(api):
    response = login(api)
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    me = api[0].get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text
    assert me.json()["username"] == "admin_test"
    assert me.json()["role"] == "admin"
    assert "hashed_password" not in me.json()


def test_bad_password_is_rejected(api):
    assert login(api, password="wrong").status_code == 401


def test_missing_and_invalid_tokens_are_rejected(api):
    client, _ = api
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.value"}).status_code == 401


def test_disabled_user_is_rejected(api):
    client, engine = api
    token = login(api).json()["access_token"]
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == "admin_test")).one()
        user.is_active = False
        session.add(user)
        session.commit()
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert login(api).status_code == 401


def test_user_role_not_admin(api):
    client, engine = api
    token = login(api, "user_test", "testing-password-456").json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "user"
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == "user_test")).one()
        with pytest.raises(HTTPException) as exc_info:
            require_admin(user)
        assert exc_info.value.status_code == 403


@pytest.mark.parametrize("typed", ["Admin_Test", "ADMIN_TEST", "  admin_test  "])
def test_login_username_ignores_case_and_surrounding_spaces(api, typed):
    """AUTH-02: usernames are stored lowercase, so login must match them the same way."""
    response = login(api, username=typed)
    assert response.status_code == 200, response.text


def test_login_username_case_does_not_bypass_password(api):
    """AUTH-02: case-insensitive username matching still requires the right password."""
    assert login(api, username="ADMIN_TEST", password="wrong").status_code == 401
