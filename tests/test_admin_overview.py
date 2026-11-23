"""Admin overview endpoint (Admin > Overview tab).

Reuses the isolated temp-DB fixture from test_history_paging (superadmin,
alice, bob). Records are inserted with explicit created_at values so the
7-day / 30-day windows are tested deterministically.
"""
from datetime import datetime, timedelta, timezone

from sqlmodel import Session

from app.db.models import SearchRecord, User
from test_history_paging import api, login, user_id  # noqa: F401  (api is a fixture)

URL = "/api/v1/admin/overview"


def add(engine, owner, days_ago, status="SUCCESS", matches=True, error=None, query="Topic"):
    created = datetime.now(timezone.utc) - timedelta(days=days_ago)
    with Session(engine) as session:
        session.add(SearchRecord(query=query, status=status, matches=matches, error_message=error,
                                 user_id=owner, created_at=created))
        session.commit()


def overview(client):
    resp = client.get(URL, headers=login(client, "superadmin"))
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_admin_only(api):
    client, _ = api
    assert client.get(URL).status_code == 401
    assert client.get(URL, headers=login(client, "alice")).status_code == 403


def test_empty_database_is_all_zeros(api):
    client, _ = api
    data = overview(client)
    assert data["users"] == {"total": 3, "admins": 1, "inactive": 0, "active_admins": 1, "active_users": 2}
    assert data["last_period"]["total"] == 0 and data["last_period"]["active_users"] == 0
    assert len(data["daily"]) == 30 and all(d["match"] == d["error"] == 0 for d in data["daily"])
    assert data["top_users"] == [] and data["recent_errors"] == [] and data["error_causes"] == []
    assert data["idle_users"]["count"] == 3


def test_user_counts_include_inactive(api):
    client, engine = api
    with Session(engine) as session:
        session.add(User(username="carol", hashed_password="x", role="user", is_active=False))
        session.add(User(username="dave", hashed_password="x", role="admin", is_active=False))
        session.commit()
    users = overview(client)["users"]
    assert users == {"total": 5, "admins": 2, "inactive": 2, "active_admins": 1, "active_users": 2}
    # The account-mix parts always add up to the total.
    assert users["active_users"] + users["active_admins"] + users["inactive"] == users["total"]


def test_periods_and_outcome_buckets(api):
    client, engine = api
    alice, bob = user_id(engine, "alice"), user_id(engine, "bob")
    add(engine, alice, 0)                                   # last 7 days: match
    add(engine, alice, 2, matches=False)                    # no match
    add(engine, bob, 3, status="ERROR", matches=None, error="TimeoutError")
    add(engine, bob, 9)                                     # previous 7 days
    add(engine, bob, 40)                                    # outside every window
    data = overview(client)
    last, prev = data["last_period"], data["previous_period"]
    assert (last["total"], last["match"], last["no_match"], last["error"]) == (3, 1, 1, 1)
    assert last["active_users"] == 2
    assert (prev["total"], prev["match"], prev["active_users"]) == (1, 1, 1)
    # The daily series covers 30 days, so the 40-day-old record is excluded.
    assert sum(d["match"] + d["no_match"] + d["error"] + d["other"] for d in data["daily"]) == 4
    assert data["daily"][-1]["date"] == datetime.now(timezone.utc).date().isoformat()


def test_top_users_and_idle_accounts(api):
    client, engine = api
    alice, bob = user_id(engine, "alice"), user_id(engine, "bob")
    for _ in range(3):
        add(engine, alice, 1)
    add(engine, bob, 1)
    data = overview(client)
    assert [(u["username"], u["searches"]) for u in data["top_users"]] == [("alice", 3), ("bob", 1)]
    # superadmin is active and hasn't searched in 30 days.
    assert data["idle_users"]["count"] == 1
    assert [u["username"] for u in data["idle_users"]["sample"]] == ["superadmin"]


def test_inactive_accounts_are_not_counted_as_idle(api):
    client, engine = api
    with Session(engine) as session:
        session.add(User(username="carol", hashed_password="x", role="user", is_active=False))
        session.commit()
    names = [u["username"] for u in overview(client)["idle_users"]["sample"]]
    assert "carol" not in names


def test_recent_errors_and_causes(api):
    client, engine = api
    alice = user_id(engine, "alice")
    add(engine, alice, 1, status="ERROR", matches=None, error="TimeoutError", query="BMW")
    add(engine, alice, 1, status="ERROR", matches=None, error="TimeoutError", query="Tea")
    add(engine, None, 1, status="ERROR", matches=None, error="GeminiVerificationError", query="Moon")
    data = overview(client)
    newest = data["recent_errors"][0]
    assert (newest["query"], newest["username"], newest["code"]) == ("Moon", None, "GeminiVerificationError")
    assert newest["label"] == "Gemini returned an unusable answer"
    assert newest["created_at"].endswith("+00:00")
    assert data["error_causes"][0] == {"code": "TimeoutError", "label": "Timed out", "count": 2}
