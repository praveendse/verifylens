"""Admin password reset, forced change, and self-service password change."""
import sqlite3

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as sa_create_engine
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.dependencies import get_pipeline_service
from app.db.database import get_session
from app.db.migrations import upgrade_schema
from app.db.models import User
from app.main import app
from security.passwords import hash_password, verify_password
from security.tokens import create_access_token

ADMIN_PW = "secure-admin-pass-123"
ALICE_PW = "secure-alice-pass-123"
TEMP_PW = "temporary-pass-456"
NEW_PW = "brand-new-pass-789"


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-key-only-do-not-use-in-production-very-long-secret-123")
    engine = create_engine(f"sqlite:///{tmp_path / 'pw.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(User(username="boss", hashed_password=hash_password(ADMIN_PW), role="admin"))
        s.add(User(username="alice", hashed_password=hash_password(ALICE_PW), role="user"))
        s.commit()

    def session_override():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_pipeline_service] = lambda: None
    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_pipeline_service, None)
        engine.dispose()


def login(client, username, password):
    return client.post("/api/v1/auth/login", data={"username": username, "password": password})


def auth(client, username, password):
    resp = login(client, username, password)
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def user_id(engine, username):
    with Session(engine) as s:
        return s.exec(select(User.id).where(User.username == username)).one()


# ---------- admin reset ----------

def test_admin_reset_forces_change_and_logs_out_old_sessions(api):
    client, engine = api
    admin = auth(client, "boss", ADMIN_PW)
    old_alice = auth(client, "alice", ALICE_PW)
    alice_id = user_id(engine, "alice")

    resp = client.post(f"/api/v1/users/{alice_id}/password", json={"new_password": TEMP_PW}, headers=admin)
    assert resp.status_code == 200
    assert resp.json()["must_change_password"] is True
    assert "hashed_password" not in resp.json()

    # Old session is revoked immediately.
    assert client.get("/api/v1/auth/me", headers=old_alice).status_code == 401
    # Old password no longer works; temporary one does.
    assert login(client, "alice", ALICE_PW).status_code == 401
    temp = auth(client, "alice", TEMP_PW)

    # With a temporary password: /me works (shows the flag), nothing else does.
    me = client.get("/api/v1/auth/me", headers=temp)
    assert me.status_code == 200 and me.json()["must_change_password"] is True
    blocked = client.get("/api/v1/history", headers=temp)
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "Password change required"
    assert client.post("/api/v1/search", json={"topic": "x"}, headers=temp).status_code == 403

    # Choosing a new password unlocks the account.
    changed = client.post(
        "/api/v1/auth/password",
        json={"current_password": TEMP_PW, "new_password": NEW_PW},
        headers=temp,
    )
    assert changed.status_code == 200
    fresh = {"Authorization": f"Bearer {changed.json()['access_token']}"}
    assert client.get("/api/v1/history", headers=fresh).status_code == 200
    assert client.get("/api/v1/auth/me", headers=fresh).json()["must_change_password"] is False
    # The temporary-password session is revoked too.
    assert client.get("/api/v1/auth/me", headers=temp).status_code == 401


def test_non_admin_cannot_reset(api):
    client, engine = api
    alice = auth(client, "alice", ALICE_PW)
    boss_id = user_id(engine, "boss")
    resp = client.post(f"/api/v1/users/{boss_id}/password", json={"new_password": TEMP_PW}, headers=alice)
    assert resp.status_code == 403
    assert login(client, "boss", ADMIN_PW).status_code == 200  # unchanged


def test_anonymous_cannot_reset(api):
    client, engine = api
    resp = client.post(f"/api/v1/users/{user_id(engine, 'alice')}/password", json={"new_password": TEMP_PW})
    assert resp.status_code == 401


def test_admin_cannot_reset_own_password_via_admin_route(api):
    client, engine = api
    admin = auth(client, "boss", ADMIN_PW)
    resp = client.post(f"/api/v1/users/{user_id(engine, 'boss')}/password", json={"new_password": TEMP_PW}, headers=admin)
    assert resp.status_code == 400


def test_reset_unknown_user_is_404(api):
    client, _ = api
    admin = auth(client, "boss", ADMIN_PW)
    assert client.post("/api/v1/users/9999/password", json={"new_password": TEMP_PW}, headers=admin).status_code == 404


@pytest.mark.parametrize("bad", ["short", "my-alice-password-1", " " * 12])
def test_reset_enforces_password_rules(api, bad):
    client, engine = api
    admin = auth(client, "boss", ADMIN_PW)
    resp = client.post(f"/api/v1/users/{user_id(engine, 'alice')}/password", json={"new_password": bad}, headers=admin)
    assert resp.status_code == 422
    assert login(client, "alice", ALICE_PW).status_code == 200  # unchanged


# ---------- self-service change ----------

def test_user_changes_own_password(api):
    client, _ = api
    alice = auth(client, "alice", ALICE_PW)
    resp = client.post(
        "/api/v1/auth/password",
        json={"current_password": ALICE_PW, "new_password": NEW_PW},
        headers=alice,
    )
    assert resp.status_code == 200
    assert login(client, "alice", ALICE_PW).status_code == 401
    assert login(client, "alice", NEW_PW).status_code == 200
    # Other sessions (the token used for the change) are logged out.
    assert client.get("/api/v1/auth/me", headers=alice).status_code == 401


def test_change_requires_correct_current_password(api):
    client, _ = api
    alice = auth(client, "alice", ALICE_PW)
    resp = client.post(
        "/api/v1/auth/password",
        json={"current_password": "wrong-password-000", "new_password": NEW_PW},
        headers=alice,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Current password is incorrect"
    assert login(client, "alice", ALICE_PW).status_code == 200


@pytest.mark.parametrize("bad", ["short", "xx-ALICE-xx-123", ALICE_PW])
def test_change_enforces_password_rules(api, bad):
    client, _ = api
    alice = auth(client, "alice", ALICE_PW)
    resp = client.post(
        "/api/v1/auth/password",
        json={"current_password": ALICE_PW, "new_password": bad},
        headers=alice,
    )
    assert resp.status_code == 422


def test_change_requires_login(api):
    client, _ = api
    resp = client.post("/api/v1/auth/password", json={"current_password": ALICE_PW, "new_password": NEW_PW})
    assert resp.status_code == 401


def test_change_is_rate_limited(api):
    client, _ = api
    alice = auth(client, "alice", ALICE_PW)
    codes = [
        client.post(
            "/api/v1/auth/password",
            json={"current_password": f"wrong-guess-{i:04d}", "new_password": NEW_PW},
            headers=alice,
        ).status_code
        for i in range(8)
    ]
    assert codes[0] == 400
    assert codes[-1] == 429


# ---------- tokens and schema upgrade ----------

def test_tokens_without_version_claim_still_work_until_first_change(api):
    """Tokens issued before this release have no 'tv' claim (= version 0)."""
    client, engine = api
    import jwt
    from security.tokens import JWTSettings

    settings = JWTSettings()
    alice_id = user_id(engine, "alice")
    good = create_access_token(alice_id, 0)
    payload = jwt.decode(good, settings.jwt_secret_key, algorithms=["HS256"], audience=settings.jwt_audience)
    payload.pop("tv")
    legacy = jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {legacy}"}).status_code == 200


def test_schema_upgrade_adds_columns_to_old_database(tmp_path):
    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE user (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL, role TEXT NOT NULL, is_active BOOLEAN NOT NULL,
            created_at DATETIME);
        CREATE TABLE searchrecord (id INTEGER PRIMARY KEY, query TEXT, status TEXT, created_at DATETIME);
        INSERT INTO user VALUES (1, 'old', 'hash', 'user', 1, NULL);
        INSERT INTO searchrecord VALUES (1, 'q', 'SUCCESS', NULL);
        """
    )
    con.commit()
    con.close()

    engine = sa_create_engine(f"sqlite:///{db}")
    added = upgrade_schema(engine)
    assert {"user.token_version", "user.must_change_password", "user.full_name", "searchrecord.user_id"} <= set(added)
    assert upgrade_schema(engine) == []  # idempotent
    engine.dispose()

    con = sqlite3.connect(db)
    assert con.execute("SELECT token_version, must_change_password FROM user").fetchone() == (0, 0)
    assert con.execute("SELECT COUNT(*) FROM searchrecord").fetchone()[0] == 1  # data kept
    con.close()


def test_cli_reset(api, monkeypatch):
    client, engine = api
    from scripts import reset_password

    monkeypatch.setattr(reset_password, "engine", engine)
    user = reset_password.reset("ALICE", NEW_PW, temporary=True)
    assert user.must_change_password is True
    with Session(engine) as s:
        assert verify_password(NEW_PW, s.get(User, user.id).hashed_password)
    with pytest.raises(LookupError):
        reset_password.reset("nobody", NEW_PW, temporary=False)
    with pytest.raises(ValueError):
        reset_password.reset("alice", "short", temporary=False)
