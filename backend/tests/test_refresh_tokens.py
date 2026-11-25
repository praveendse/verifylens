"""Refresh-token sessions (docs/specs/auth.md, AUTH-12..18). Isolated SQLite file."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.auth_routes import REFRESH_COOKIE
from app.infra.db.database import get_session
from app.infra.db.models import RefreshToken, User
from app.main import app
from app.services import refresh_token_service as svc
from security.passwords import hash_password

CSRF = {"X-Requested-With": "verifylens"}
ADMIN_PW = "testing-password-123"
USER_PW = "testing-password-456"


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "this-is-a-test-secret-only-do-not-use-in-production-123")
    # TestClient talks plain http; a Secure cookie would never be sent back.
    monkeypatch.setenv("REFRESH_COOKIE_SECURE", "false")
    engine = create_engine(f"sqlite:///{tmp_path / 'refresh.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(User(username="admin_test", hashed_password=hash_password(ADMIN_PW), role="admin"))
        s.add(User(username="user_test", hashed_password=hash_password(USER_PW), role="user"))
        s.commit()

    def test_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = test_session
    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        app.dependency_overrides.pop(get_session, None)
        engine.dispose()


def login(client, username="user_test", password=USER_PW):
    r = client.post("/api/v1/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r


def refresh(client, **kw):
    return client.post("/api/v1/auth/refresh", headers=CSRF, **kw)


def use_cookie(client, value):
    """Replace the browser's refresh cookie (a plain set() would add a duplicate)."""
    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, value)


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def user_id(engine, username="user_test"):
    with Session(engine) as s:
        return s.exec(select(User).where(User.username == username)).one().id


def test_login_sets_httponly_strict_cookie(api):
    client, _ = api
    r = login(client)
    cookie = r.headers["set-cookie"]
    assert cookie.startswith(f"{REFRESH_COOKIE}=")
    assert "HttpOnly" in cookie
    assert "samesite=strict" in cookie.lower()
    assert "Path=/api/v1/auth" in cookie
    assert REFRESH_COOKIE not in r.text  # raw token never in the body


def test_cookie_is_secure_by_default(api, monkeypatch):
    client, _ = api
    monkeypatch.delenv("REFRESH_COOKIE_SECURE")
    assert "Secure" in login(client).headers["set-cookie"]


def test_refresh_returns_working_access_token_and_rotates(api):
    client, _ = api
    login(client)
    first = client.cookies.get(REFRESH_COOKIE)
    r = refresh(client)
    assert r.status_code == 200, r.text
    assert client.get("/api/v1/auth/me", headers=bearer(r.json()["access_token"])).status_code == 200
    assert client.cookies.get(REFRESH_COOKIE) not in (None, first)


def test_refresh_without_cookie_is_401(api):
    client, _ = api
    assert refresh(client).status_code == 401


def test_refresh_requires_csrf_header(api):
    client, _ = api
    login(client)
    assert client.post("/api/v1/auth/refresh").status_code == 403
    assert client.post("/api/v1/auth/logout").status_code == 403


def test_reuse_after_grace_revokes_every_session(api, monkeypatch):
    client, engine = api
    login(client)
    stolen = client.cookies.get(REFRESH_COOKIE)
    assert refresh(client).status_code == 200
    current = client.cookies.get(REFRESH_COOKIE)

    monkeypatch.setattr(svc, "ROTATION_GRACE", timedelta(0))
    use_cookie(client, stolen)
    assert refresh(client).status_code == 401
    # The legitimate (newest) token is revoked too.
    use_cookie(client, current)
    assert refresh(client).status_code == 401
    with Session(engine) as s:
        rows = s.exec(select(RefreshToken).where(RefreshToken.user_id == user_id(engine))).all()
        assert rows and all(r.revoked_at is not None for r in rows)


def test_concurrent_refresh_within_grace_does_not_log_out(api):
    """Two tabs refreshing with the same cookie: the second gets a token, no alarm."""
    client, _ = api
    login(client)
    old = client.cookies.get(REFRESH_COOKIE)
    assert refresh(client).status_code == 200
    newest = client.cookies.get(REFRESH_COOKIE)

    use_cookie(client, old)
    r = refresh(client)
    assert r.status_code == 200
    assert "set-cookie" not in r.headers  # keeps the newer cookie the other tab got
    use_cookie(client, newest)
    assert refresh(client).status_code == 200


def test_logout_revokes_and_clears_cookie(api):
    client, _ = api
    login(client)
    cookie = client.cookies.get(REFRESH_COOKIE)
    r = client.post("/api/v1/auth/logout", headers=CSRF)
    assert r.status_code == 204
    assert f'{REFRESH_COOKIE}=""' in r.headers["set-cookie"] or "Max-Age=0" in r.headers["set-cookie"]
    use_cookie(client, cookie)
    assert refresh(client).status_code == 401


def test_logout_only_ends_this_sign_in(api):
    client, _ = api
    login(client)
    other_browser = client.cookies.get(REFRESH_COOKIE)
    client.cookies.clear()
    login(client)
    assert client.post("/api/v1/auth/logout", headers=CSRF).status_code == 204
    use_cookie(client, other_browser)
    assert refresh(client).status_code == 200


def test_password_change_revokes_other_refresh_tokens_and_issues_new(api):
    client, _ = api
    token = login(client).json()["access_token"]
    other_browser = client.cookies.get(REFRESH_COOKIE)
    r = client.post("/api/v1/auth/password", headers=bearer(token),
                    json={"current_password": USER_PW, "new_password": "a-brand-new-password-789"})
    assert r.status_code == 200, r.text
    assert refresh(client).status_code == 200  # the new cookie works
    use_cookie(client, other_browser)
    assert refresh(client).status_code == 401


def test_admin_reset_revokes_refresh_tokens(api):
    client, _ = api
    login(client)
    user_cookie = client.cookies.get(REFRESH_COOKIE)
    client.cookies.clear()
    admin_token = login(client, "admin_test", ADMIN_PW).json()["access_token"]
    uid = user_id(api[1])
    r = client.post(f"/api/v1/users/{uid}/password", headers=bearer(admin_token),
                    json={"new_password": "temporary-password-321"})
    assert r.status_code == 200, r.text
    use_cookie(client, user_cookie)
    assert refresh(client).status_code == 401


def test_inactive_user_cannot_refresh(api):
    client, engine = api
    login(client)
    with Session(engine) as s:
        u = s.exec(select(User).where(User.username == "user_test")).one()
        u.is_active = False
        s.add(u)
        s.commit()
    assert refresh(client).status_code == 401


def test_deleted_user_tokens_are_removed(api):
    client, engine = api
    login(client)
    user_cookie = client.cookies.get(REFRESH_COOKIE)
    client.cookies.clear()
    admin_token = login(client, "admin_test", ADMIN_PW).json()["access_token"]
    uid = user_id(engine)
    assert client.delete(f"/api/v1/users/{uid}", headers=bearer(admin_token)).status_code == 204
    with Session(engine) as s:
        assert not s.exec(select(RefreshToken).where(RefreshToken.user_id == uid)).all()
    use_cookie(client, user_cookie)
    assert refresh(client).status_code == 401


def test_idle_expiry(api):
    client, engine = api
    login(client)
    with Session(engine) as s:
        row = s.exec(select(RefreshToken)).one()
        row.expires_at = svc.utcnow() - timedelta(seconds=1)
        s.add(row)
        s.commit()
    assert refresh(client).status_code == 401


def test_absolute_expiry_survives_rotation(api):
    client, engine = api
    login(client)
    with Session(engine) as s:
        family_end = s.exec(select(RefreshToken)).one().family_expires_at
    assert refresh(client).status_code == 200
    with Session(engine) as s:
        rows = s.exec(select(RefreshToken)).all()
        assert len(rows) == 2 and {r.family_expires_at for r in rows} == {family_end}
        for r in rows:
            r.family_expires_at = svc.utcnow() - timedelta(seconds=1)
            s.add(r)
        s.commit()
    assert refresh(client).status_code == 401


def test_only_hash_is_stored(api):
    client, engine = api
    login(client)
    raw = client.cookies.get(REFRESH_COOKIE)
    with Session(engine) as s:
        row = s.exec(select(RefreshToken)).one()
    assert row.token_hash != raw and row.token_hash == svc.hash_token(raw)


def test_purge_removes_old_rows(api):
    client, engine = api
    login(client)
    with Session(engine) as s:
        row = s.exec(select(RefreshToken)).one()
        row.expires_at = svc.utcnow() - timedelta(days=8)
        s.add(row)
        s.commit()
    assert svc.purge_old(engine) == 1
