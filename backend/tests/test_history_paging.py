"""History paging, filters and outcome stats.

Isolated temporary SQLite DB; records are inserted directly (no Wikipedia or
Gemini calls) and requests go through real login, so ownership rules are
exercised end to end.
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app.infra.db.database import get_session
from app.infra.db.models import SearchRecord, User
from app.main import app
from security.passwords import hash_password

PASSWORDS = {
    "superadmin": "secure-admin-pass-123",
    "alice": "secure-alice-pass-123",
    "bob": "secure-bob-pass-123",
}


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-key-only-do-not-use-in-production-very-long-secret-123")
    engine = create_engine(f"sqlite:///{tmp_path / 'history_test.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(username="superadmin", hashed_password=hash_password(PASSWORDS["superadmin"]), role="admin"))
        session.add(User(username="alice", hashed_password=hash_password(PASSWORDS["alice"]), role="user"))
        session.add(User(username="bob", hashed_password=hash_password(PASSWORDS["bob"]), role="user"))
        session.commit()

    def test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = test_session
    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        app.dependency_overrides.pop(get_session, None)
        engine.dispose()


def login(client, username):
    resp = client.post("/api/v1/auth/login", data={"username": username, "password": PASSWORDS[username]})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def user_id(engine, username):
    with Session(engine) as session:
        return session.exec(select(User).where(User.username == username)).one().id


def add(engine, owner, query, status="SUCCESS", matches=True, title=None):
    with Session(engine) as session:
        record = SearchRecord(query=query, article_title=title, status=status, matches=matches, user_id=owner)
        session.add(record)
        session.commit()
        return record.id


# Paging -----------------------------------------------------------------

def test_pages_are_newest_first_without_gaps_or_duplicates(api):
    client, engine = api
    alice = user_id(engine, "alice")
    ids = [add(engine, alice, f"Topic {i}") for i in range(12)]
    headers = login(client, "alice")

    seen, before = [], None
    while True:
        params = {"limit": 5} | ({"before_id": before} if before else {})
        page = client.get("/api/v1/history", headers=headers, params=params).json()
        if not page:
            break
        assert len(page) <= 5
        seen += [r["id"] for r in page]
        before = page[-1]["id"]

    assert seen == sorted(ids, reverse=True)


def test_new_record_between_pages_does_not_shift_next_page(api):
    client, engine = api
    alice = user_id(engine, "alice")
    ids = [add(engine, alice, f"Topic {i}") for i in range(10)]
    headers = login(client, "alice")

    first = client.get("/api/v1/history", headers=headers, params={"limit": 5}).json()
    add(engine, alice, "Arrived later")  # would shift an OFFSET-based page
    second = client.get("/api/v1/history", headers=headers, params={"limit": 5, "before_id": first[-1]["id"]}).json()

    assert [r["id"] for r in first + second] == sorted(ids, reverse=True)


def test_default_is_still_latest_20(api):
    client, engine = api
    alice = user_id(engine, "alice")
    for i in range(25):
        add(engine, alice, f"Topic {i}")
    page = client.get("/api/v1/history", headers=login(client, "alice")).json()
    assert len(page) == 20


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 51}, {"limit": 1000}, {"before_id": 0}, {"status": "DROP TABLE"}])
def test_invalid_paging_params_are_rejected(api, params):
    client, _ = api
    resp = client.get("/api/v1/history", headers=login(client, "alice"), params=params)
    assert resp.status_code == 422


# Filters ----------------------------------------------------------------

def test_topic_filter_searches_whole_history_case_insensitively(api):
    client, engine = api
    alice = user_id(engine, "alice")
    old = add(engine, alice, "einstein", title="Albert Einstein")
    for i in range(30):  # bury the match below the default page
        add(engine, alice, f"Filler {i}")
    headers = login(client, "alice")

    by_title = client.get("/api/v1/history", headers=headers, params={"q": "ALBERT"}).json()
    by_query = client.get("/api/v1/history", headers=headers, params={"q": "Einst"}).json()
    assert [r["id"] for r in by_title] == [old]
    assert [r["id"] for r in by_query] == [old]


def test_topic_filter_treats_wildcards_literally(api):
    client, engine = api
    alice = user_id(engine, "alice")
    add(engine, alice, "100% Pure")
    add(engine, alice, "Plain topic")
    headers = login(client, "alice")
    assert [r["query"] for r in client.get("/api/v1/history", headers=headers, params={"q": "%"}).json()] == ["100% Pure"]
    assert client.get("/api/v1/history", headers=headers, params={"q": "_"}).json() == []


def test_status_filter_and_blank_topic(api):
    client, engine = api
    alice = user_id(engine, "alice")
    add(engine, alice, "Ok one")
    err = add(engine, alice, "Broken", status="ERROR", matches=None)
    headers = login(client, "alice")
    assert [r["id"] for r in client.get("/api/v1/history", headers=headers, params={"status": "ERROR"}).json()] == [err]
    assert len(client.get("/api/v1/history", headers=headers, params={"q": "   "}).json()) == 2


def test_filters_never_reveal_other_users_records(api):
    client, engine = api
    add(engine, user_id(engine, "bob"), "Secret Bob topic")
    headers = login(client, "alice")
    assert client.get("/api/v1/history", headers=headers, params={"q": "Secret"}).json() == []


# Stats ------------------------------------------------------------------

def test_stats_count_all_records_not_just_one_page(api):
    client, engine = api
    alice = user_id(engine, "alice")
    for i in range(23):
        add(engine, alice, f"Match {i}")
    for i in range(4):
        add(engine, alice, f"Miss {i}", matches=False)
    for i in range(2):
        add(engine, alice, f"Err {i}", status="ERROR", matches=None)
    add(engine, alice, "Running", status="PENDING", matches=None)

    stats = client.get("/api/v1/history/stats", headers=login(client, "alice")).json()
    assert stats == {"total": 30, "completed": 27, "match": 23, "no_match": 4, "error": 2, "other": 1}


def test_stats_are_scoped_per_user_and_admin_sees_all(api):
    client, engine = api
    add(engine, user_id(engine, "alice"), "A")
    add(engine, user_id(engine, "bob"), "B1")
    add(engine, user_id(engine, "bob"), "B2", status="ERROR", matches=None)

    assert client.get("/api/v1/history/stats", headers=login(client, "alice")).json()["total"] == 1
    bob = client.get("/api/v1/history/stats", headers=login(client, "bob")).json()
    assert (bob["total"], bob["error"]) == (2, 1)
    assert client.get("/api/v1/history/stats", headers=login(client, "superadmin")).json()["total"] == 3


def test_stats_empty_and_requires_login(api):
    client, _ = api
    assert client.get("/api/v1/history/stats").status_code == 401
    stats = client.get("/api/v1/history/stats", headers=login(client, "alice")).json()
    assert stats["total"] == 0


# Timestamps ---------------------------------------------------------------

def test_timestamps_carry_utc_offset(api):
    """created_at must be labelled UTC. Without an offset, browsers read the
    value as local time and the History page shows the wrong time."""
    from datetime import datetime, timedelta, timezone

    client, engine = api
    record_id = add(engine, user_id(engine, "alice"), "Timezone check")
    headers = login(client, "alice")

    listed = client.get("/api/v1/history", headers=headers).json()[0]["created_at"]
    detail = client.get(f"/api/v1/history/{record_id}", headers=headers).json()["created_at"]

    for value in (listed, detail):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        assert parsed.utcoffset() == timedelta(0), value
        assert abs(datetime.now(timezone.utc) - parsed) < timedelta(minutes=5)
