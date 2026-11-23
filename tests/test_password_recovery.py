"""Self-service password recovery by email link (docs/specs/password-recovery.md).

Isolated temp DB and a fake mail sender: no real SMTP, no real user data.
"""
import hashlib
import logging
import re
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine as sa_create_engine
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.dependencies import get_mail_sender, get_settings
from app.db.database import get_session, get_session_factory
from app.db.migrations import upgrade_schema
from app.db.models import PasswordResetToken, User
from app.main import app
from app.services.password_reset_service import config_problem, purge_old_tokens
from app.settings import Settings
from security.passwords import hash_password

ADMIN_PW = "secure-admin-pass-123"
ALICE_PW = "secure-alice-pass-123"
NEW_PW = "brand-new-pass-789"
BASE_URL = "https://verifylens.test"
INVALID = "Invalid or expired reset link"
TOKEN_RE = re.compile(r"#token=([A-Za-z0-9_-]+)")


def enabled_settings(**overrides) -> Settings:
    values = dict(
        password_reset_enabled=True,
        smtp_host="smtp.test",
        smtp_from="noreply@verifylens.test",
        app_base_url=BASE_URL,
    )
    values.update(overrides)
    return Settings(**values)


class FakeMailer:
    def __init__(self):
        self.sent: list[tuple[str, str, str]] = []
        self.fail = False

    def send(self, to: str, subject: str, body: str) -> None:
        if self.fail:
            raise ConnectionRefusedError("smtp down")
        self.sent.append((to, subject, body))

    def links(self) -> list[str]:
        return [m.group(1) for _, _, body in self.sent if (m := TOKEN_RE.search(body))]


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-key-only-do-not-use-in-production-very-long-secret-123")
    engine = create_engine(f"sqlite:///{tmp_path / 'recovery.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(User(username="boss", hashed_password=hash_password(ADMIN_PW), role="admin", email="boss@rad.test"))
        s.add(User(username="alice", hashed_password=hash_password(ALICE_PW), role="user", email="alice@example.com"))
        s.add(User(username="bob", hashed_password=hash_password(ALICE_PW), role="user"))  # no email
        s.add(User(username="carol", hashed_password=hash_password(ALICE_PW), role="user",
                   email="carol@example.com", is_active=False))
        s.commit()

    def session_override():
        with Session(engine) as s:
            yield s

    mailer = FakeMailer()
    state = {"settings": enabled_settings()}
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_session_factory] = lambda: (lambda: Session(engine))
    app.dependency_overrides[get_mail_sender] = lambda: mailer
    app.dependency_overrides[get_settings] = lambda: state["settings"]
    try:
        with TestClient(app) as client:
            yield client, engine, mailer, state
    finally:
        for dep in (get_session, get_session_factory, get_mail_sender, get_settings):
            app.dependency_overrides.pop(dep, None)
        engine.dispose()


# ---------- helpers ----------

def login(client, username, password):
    return client.post("/api/v1/auth/login", data={"username": username, "password": password})


def auth(client, username, password):
    resp = login(client, username, password)
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def request_reset(client, identifier):
    return client.post("/api/v1/auth/password-reset/request", json={"identifier": identifier})


def confirm(client, token, password=NEW_PW):
    return client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": password})


def user_id(engine, username):
    with Session(engine) as s:
        return s.exec(select(User.id).where(User.username == username)).one()


def token_rows(engine, username=None):
    with Session(engine) as s:
        stmt = select(PasswordResetToken)
        if username:
            stmt = stmt.where(PasswordResetToken.user_id == user_id(engine, username))
        return s.exec(stmt).all()


def link_for(client, mailer, identifier="alice"):
    assert request_reset(client, identifier).status_code == 202
    return mailer.links()[-1]


# ---------- PWR-01 / PWR-02: email on accounts ----------

def test_admin_sets_email_on_create_normalized(api):
    """PWR-01"""
    client, *_ = api
    admin = auth(client, "boss", ADMIN_PW)
    body = {"username": "dave", "password": "secure-new-pass-1", "email": "  Dave.Smith@Example.COM "}
    resp = client.post("/api/v1/users", headers=admin, json=body)
    assert resp.status_code == 201, resp.text
    assert resp.json()["email"] == "dave.smith@example.com"


@pytest.mark.parametrize("bad", ["not-an-email", "a@b", "a b@c.com", "x@" + "y" * 250 + ".com"])
def test_invalid_email_is_rejected(api, bad):
    """PWR-01"""
    client, *_ = api
    admin = auth(client, "boss", ADMIN_PW)
    body = {"username": "dave", "password": "secure-new-pass-1", "email": bad}
    assert client.post("/api/v1/users", headers=admin, json=body).status_code == 422


def test_blank_email_on_create_is_stored_as_none(api):
    """PWR-01"""
    client, *_ = api
    admin = auth(client, "boss", ADMIN_PW)
    body = {"username": "dave", "password": "secure-new-pass-1", "email": "   "}
    resp = client.post("/api/v1/users", headers=admin, json=body)
    assert resp.status_code == 201, resp.text
    assert resp.json()["email"] is None


def test_duplicate_email_conflicts_ignoring_case(api):
    """PWR-01"""
    client, engine, *_ = api
    admin = auth(client, "boss", ADMIN_PW)
    body = {"username": "dave", "password": "secure-new-pass-1", "email": "ALICE@example.com"}
    created = client.post("/api/v1/users", headers=admin, json=body)
    assert created.status_code == 409
    assert created.json()["detail"] == "Email already in use"

    bob = user_id(engine, "bob")
    updated = client.patch(f"/api/v1/users/{bob}", headers=admin, json={"email": "Alice@Example.com"})
    assert updated.status_code == 409


def test_admin_can_change_and_clear_email(api):
    """PWR-01"""
    client, engine, *_ = api
    admin = auth(client, "boss", ADMIN_PW)
    alice = user_id(engine, "alice")
    changed = client.patch(f"/api/v1/users/{alice}", headers=admin, json={"email": "New.Alice@Example.com"})
    assert changed.status_code == 200, changed.text
    assert changed.json()["email"] == "new.alice@example.com"
    # Keeping your own email is not a conflict.
    same = client.patch(f"/api/v1/users/{alice}", headers=admin, json={"email": "new.alice@example.com"})
    assert same.status_code == 200
    cleared = client.patch(f"/api/v1/users/{alice}", headers=admin, json={"email": None})
    assert cleared.status_code == 200
    assert cleared.json()["email"] is None


def test_user_sees_own_email_but_cannot_change_it(api):
    """PWR-01, PWR-02"""
    client, engine, *_ = api
    alice = auth(client, "alice", ALICE_PW)
    assert client.get("/api/v1/auth/me", headers=alice).json()["email"] == "alice@example.com"
    resp = client.patch(f"/api/v1/users/{user_id(engine, 'alice')}", headers=alice, json={"email": "evil@x.com"})
    assert resp.status_code == 403


def test_schema_upgrade_adds_email_and_token_table(tmp_path):
    """PLT-05 for this feature: old databases gain the new column, index and table."""
    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE user (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL, role TEXT NOT NULL, is_active BOOLEAN NOT NULL,
            created_at DATETIME);
        CREATE TABLE searchrecord (id INTEGER PRIMARY KEY, query TEXT, status TEXT, created_at DATETIME);
        INSERT INTO user VALUES (1, 'old', 'hash', 'user', 1, NULL);
        """
    )
    con.commit()
    con.close()

    engine = sa_create_engine(f"sqlite:///{db}")
    assert "user.email" in upgrade_schema(engine)
    assert upgrade_schema(engine) == []  # idempotent
    engine.dispose()

    con = sqlite3.connect(db)
    assert con.execute("SELECT email FROM user").fetchone() == (None,)
    assert con.execute("SELECT COUNT(*) FROM passwordresettoken").fetchone() == (0,)
    con.execute("UPDATE user SET email = 'a@b.com'")
    con.execute("INSERT INTO user (id, username, hashed_password, role, is_active, email) "
                "VALUES (2, 'new', 'h', 'user', 1, NULL)")
    with pytest.raises(sqlite3.IntegrityError):  # unique index on email
        con.execute("INSERT INTO user (id, username, hashed_password, role, is_active, email) "
                    "VALUES (3, 'dup', 'h', 'user', 1, 'a@b.com')")
    con.close()


# ---------- PWR-03 / PWR-04: request ----------

@pytest.mark.parametrize("identifier", ["alice", "  ALICE ", "Alice@Example.com"])
def test_request_by_username_or_email_sends_one_link(api, identifier):
    """PWR-04, PWR-06, PWR-12"""
    client, engine, mailer, _ = api
    resp = request_reset(client, identifier)
    assert resp.status_code == 202
    assert len(mailer.sent) == 1
    to, subject, body = mailer.sent[0]
    assert to == "alice@example.com"
    assert f"{BASE_URL}/reset-password#token=" in body
    assert "15 minutes" in body
    assert "If you didn't ask for this" in body
    assert len(token_rows(engine, "alice")) == 1


@pytest.mark.parametrize("identifier", ["ghost", "ghost@example.com", "bob", "carol", "carol@example.com"])
def test_no_link_for_unknown_emailless_or_inactive_accounts(api, identifier):
    """PWR-03, PWR-04"""
    client, engine, mailer, _ = api
    resp = request_reset(client, identifier)
    assert resp.status_code == 202
    assert resp.json() == request_reset(client, "alice").json()  # same body as a real account
    assert [to for to, *_ in mailer.sent] == ["alice@example.com"]
    assert len(token_rows(engine)) == 1  # only Alice's


def test_request_validates_identifier(api):
    client, *_ = api
    assert request_reset(client, "").status_code == 422
    assert request_reset(client, "x" * 255).status_code == 422


def test_new_request_cancels_earlier_link(api):
    """PWR-04"""
    client, _, mailer, _ = api
    first = link_for(client, mailer)
    second = link_for(client, mailer)
    assert confirm(client, first).status_code == 400
    assert confirm(client, second).status_code == 200


# ---------- PWR-05 / PWR-13: token storage and logging ----------

def test_token_stored_only_as_hash_and_never_logged(api, caplog):
    """PWR-05, PWR-13"""
    client, engine, mailer, _ = api
    with caplog.at_level(logging.DEBUG):
        raw = link_for(client, mailer)
        assert confirm(client, raw).status_code == 200
    assert len(raw) >= 43  # 32 random bytes, url-safe base64
    (row,) = token_rows(engine, "alice")
    assert row.token_hash == hashlib.sha256(raw.encode()).hexdigest()
    assert raw not in caplog.text
    assert "reset-password" not in caplog.text
    assert "password reset" in caplog.text.lower()  # but the events are logged


def test_token_expiry_follows_setting(api):
    """PWR-05"""
    client, engine, mailer, state = api
    state["settings"] = enabled_settings(password_reset_token_minutes=30)
    before = datetime.now(timezone.utc)
    link_for(client, mailer)
    (row,) = token_rows(engine, "alice")
    expires = row.expires_at.replace(tzinfo=timezone.utc) if row.expires_at.tzinfo is None else row.expires_at
    assert timedelta(minutes=29) < expires - before < timedelta(minutes=31)
    assert "30 minutes" in mailer.sent[-1][2]


@pytest.mark.parametrize("minutes", [4, 61])
def test_token_minutes_setting_is_bounded(minutes):
    """PWR-05"""
    with pytest.raises(ValidationError):
        Settings(password_reset_token_minutes=minutes)


# ---------- PWR-07 .. PWR-09: confirm ----------

def test_confirm_resets_password_and_signs_out_everywhere(api):
    """PWR-09, PWR-12"""
    client, _, mailer, _ = api
    phone = auth(client, "alice", ALICE_PW)
    laptop = auth(client, "alice", ALICE_PW)
    raw = link_for(client, mailer)

    resp = confirm(client, raw)
    assert resp.status_code == 200, resp.text
    assert "access_token" not in resp.json()  # does not sign the user in

    assert client.get("/api/v1/auth/me", headers=phone).status_code == 401
    assert client.get("/api/v1/auth/me", headers=laptop).status_code == 401
    assert login(client, "alice", ALICE_PW).status_code == 401
    assert login(client, "alice", NEW_PW).status_code == 200
    assert confirm(client, raw, "another-new-pass-1").status_code == 400  # single use

    to, subject, body = mailer.sent[-1]
    assert to == "alice@example.com"
    assert "password was changed" in body.lower()
    assert "#token=" not in body


def test_confirm_clears_must_change_password(api):
    """PWR-09"""
    client, engine, mailer, _ = api
    admin = auth(client, "boss", ADMIN_PW)
    resp = client.post(f"/api/v1/users/{user_id(engine, 'alice')}/password", headers=admin,
                       json={"new_password": "temporary-pass-456"})
    assert resp.status_code == 200
    assert confirm(client, link_for(client, mailer)).status_code == 200
    alice = auth(client, "alice", NEW_PW)
    assert client.get("/api/v1/history", headers=alice).status_code == 200


@pytest.mark.parametrize("case", ["made_up", "expired", "used"])
def test_confirm_rejects_bad_tokens_the_same_way(api, case):
    """PWR-07"""
    client, engine, mailer, _ = api
    raw = link_for(client, mailer)
    if case == "made_up":
        raw = "x" * 43
    elif case == "expired":
        with Session(engine) as s:
            row = s.exec(select(PasswordResetToken)).one()
            row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            s.add(row)
            s.commit()
    else:
        assert confirm(client, raw).status_code == 200
    resp = confirm(client, raw, "yet-another-pass-1")
    assert resp.status_code == 400
    assert resp.json()["detail"] == INVALID
    assert login(client, "alice", "yet-another-pass-1").status_code == 401


def test_confirm_rejects_link_of_deactivated_user(api):
    """PWR-07"""
    client, engine, mailer, _ = api
    raw = link_for(client, mailer)
    with Session(engine) as s:
        alice = s.get(User, user_id(engine, "alice"))
        alice.is_active = False
        s.add(alice)
        s.commit()
    resp = confirm(client, raw)
    assert resp.status_code == 400
    assert resp.json()["detail"] == INVALID


@pytest.mark.parametrize("bad", ["short", "my-ALICE-pass-123", " " * 12])
def test_confirm_enforces_password_rules_and_keeps_link_usable(api, bad):
    """PWR-08"""
    client, _, mailer, _ = api
    raw = link_for(client, mailer)
    assert confirm(client, raw, bad).status_code == 422
    assert confirm(client, raw).status_code == 200


# ---------- PWR-10 / PWR-18: other paths cancel links ----------

def test_admin_reset_cancels_pending_link(api):
    """PWR-10"""
    client, engine, mailer, _ = api
    raw = link_for(client, mailer)
    admin = auth(client, "boss", ADMIN_PW)
    client.post(f"/api/v1/users/{user_id(engine, 'alice')}/password", headers=admin,
                json={"new_password": "temporary-pass-456"})
    assert confirm(client, raw).status_code == 400


def test_self_change_cancels_pending_link(api):
    """PWR-10"""
    client, _, mailer, _ = api
    raw = link_for(client, mailer)
    alice = auth(client, "alice", ALICE_PW)
    changed = client.post("/api/v1/auth/password", headers=alice,
                          json={"current_password": ALICE_PW, "new_password": NEW_PW})
    assert changed.status_code == 200
    assert confirm(client, raw, "yet-another-pass-1").status_code == 400


def test_cli_reset_cancels_pending_link(api, monkeypatch):
    """PWR-10"""
    client, engine, mailer, _ = api
    from scripts import reset_password

    raw = link_for(client, mailer)
    monkeypatch.setattr(reset_password, "engine", engine)
    reset_password.reset("alice", NEW_PW, temporary=False)
    assert confirm(client, raw, "yet-another-pass-1").status_code == 400


def test_deleting_user_removes_their_reset_tokens(api):
    """PWR-18"""
    client, engine, mailer, _ = api
    link_for(client, mailer)
    admin = auth(client, "boss", ADMIN_PW)
    assert client.delete(f"/api/v1/users/{user_id(engine, 'alice')}", headers=admin).status_code == 204
    assert token_rows(engine) == []


# ---------- PWR-11: rate limits ----------

def test_identifier_limit_returns_202_but_stops_sending(api):
    """PWR-11"""
    client, _, mailer, _ = api
    codes = [request_reset(client, "alice").status_code for _ in range(4)]
    assert codes == [202, 202, 202, 202]
    assert len(mailer.sent) == 3


def test_request_ip_limit_returns_429(api):
    """PWR-11"""
    client, *_ = api
    codes = [request_reset(client, f"ghost{i}").status_code for i in range(6)]
    assert codes[:5] == [202] * 5
    last = request_reset(client, "ghost-last")
    assert last.status_code == 429
    assert "Retry-After" in last.headers


def test_confirm_ip_limit_returns_429(api):
    """PWR-11"""
    client, *_ = api
    codes = [confirm(client, f"made-up-token-{i:02d}").status_code for i in range(11)]
    assert codes[:10] == [400] * 10
    assert codes[10] == 429


# ---------- PWR-12 / PWR-13: email failures ----------

def test_mail_failure_still_returns_202_and_logs_safely(api, caplog):
    """PWR-03, PWR-13"""
    client, _, mailer, _ = api
    mailer.fail = True
    with caplog.at_level(logging.WARNING):
        assert request_reset(client, "alice").status_code == 202
    assert "ConnectionRefusedError" in caplog.text
    assert "#token=" not in caplog.text


# ---------- PWR-15: off unless configured ----------

@pytest.mark.parametrize("settings", [
    Settings(password_reset_enabled=False, smtp_host="smtp.test", smtp_from="a@b.co", app_base_url=BASE_URL),
    Settings(password_reset_enabled=True, smtp_host=None, smtp_from="a@b.co", app_base_url=BASE_URL),
    Settings(password_reset_enabled=True, smtp_host="smtp.test", smtp_from=None, app_base_url=BASE_URL),
    Settings(password_reset_enabled=True, smtp_host="smtp.test", smtp_from="a@b.co", app_base_url=None),
], ids=["disabled", "no-host", "no-from", "no-base-url"])
def test_endpoints_are_404_unless_enabled_and_configured(api, settings):
    """PWR-15"""
    client, _, mailer, state = api
    state["settings"] = settings
    assert request_reset(client, "alice").status_code == 404
    assert confirm(client, "x" * 43).status_code == 404
    assert client.get("/api/v1/auth/password-reset/status").json() == {"enabled": False}
    assert mailer.sent == []


def test_status_reports_enabled_when_configured(api):
    """PWR-15"""
    client, *_ = api
    resp = client.get("/api/v1/auth/password-reset/status")
    assert resp.status_code == 200
    assert resp.json() == {"enabled": True}


def test_config_problem_names_missing_settings():
    """PWR-15: used for the startup warning."""
    assert config_problem(enabled_settings()) is None
    assert config_problem(Settings(password_reset_enabled=False)) is None  # off: nothing to warn about
    problem = config_problem(Settings(password_reset_enabled=True, smtp_host=None, smtp_from=None,
                                      app_base_url=None))
    for name in ("SMTP_HOST", "SMTP_FROM", "APP_BASE_URL"):
        assert name in problem


# ---------- PWR-16: cleanup ----------

def test_purge_removes_only_old_used_or_expired_tokens(api):
    """PWR-16"""
    _, engine, *_ = api
    now = datetime.now(timezone.utc)
    alice = user_id(engine, "alice")
    old = now - timedelta(days=8)
    with Session(engine) as s:
        s.add(PasswordResetToken(user_id=alice, token_hash="a" * 64, created_at=old,
                                 expires_at=old + timedelta(minutes=15)))                 # expired long ago
        s.add(PasswordResetToken(user_id=alice, token_hash="b" * 64, created_at=old,
                                 expires_at=old + timedelta(minutes=15), used_at=old))     # used long ago
        s.add(PasswordResetToken(user_id=alice, token_hash="c" * 64, created_at=now,
                                 expires_at=now - timedelta(minutes=1)))                   # expired recently
        s.add(PasswordResetToken(user_id=alice, token_hash="d" * 64, created_at=now,
                                 expires_at=now + timedelta(minutes=15)))                  # live
        s.commit()
    assert purge_old_tokens(engine) == 2
    assert sorted(r.token_hash[0] for r in token_rows(engine)) == ["c", "d"]


# ---------- SMTP sender ----------

def test_smtp_sender_uses_starttls_login_and_from(monkeypatch):
    """PWR-14"""
    from app.services import mail_service

    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(("connect", host, port, timeout))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self, context=None):
            calls.append(("starttls",))

        def login(self, user, password):
            calls.append(("login", user, password))

        def send_message(self, msg):
            calls.append(("send", msg["From"], msg["To"], msg["Subject"], msg.get_content()))

    monkeypatch.setattr(mail_service.smtplib, "SMTP", FakeSMTP)
    settings = enabled_settings(smtp_port=2525, smtp_username="mailer", smtp_password="pw")
    mail_service.SmtpMailSender(settings).send("alice@example.com", "Subject", "Body text")
    assert calls[0][:3] == ("connect", "smtp.test", 2525)
    assert ("starttls",) in calls
    assert ("login", "mailer", "pw") in calls
    sent = calls[-1]
    assert sent[1:4] == ("noreply@verifylens.test", "alice@example.com", "Subject")
    assert sent[4].strip() == "Body text"
