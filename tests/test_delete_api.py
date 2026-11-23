"""Deleting searches and user accounts.

Reuses the isolated temp-DB fixture and helpers from test_history_paging.
"""
from sqlmodel import Session, select

from app.db.models import SearchRecord, User
from test_history_paging import add, api, login, user_id  # noqa: F401  (api is a fixture)


# Searches ---------------------------------------------------------------

def test_owner_can_delete_own_search(api):
    client, engine = api
    rid = add(engine, user_id(engine, "alice"), "Mine")
    headers = login(client, "alice")
    assert client.delete(f"/api/v1/history/{rid}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/history/{rid}", headers=headers).status_code == 404
    with Session(engine) as session:
        assert session.get(SearchRecord, rid) is None


def test_user_cannot_delete_someone_elses_search(api):
    client, engine = api
    rid = add(engine, user_id(engine, "bob"), "Bob's")
    resp = client.delete(f"/api/v1/history/{rid}", headers=login(client, "alice"))
    assert resp.status_code == 404  # same answer as "doesn't exist"
    with Session(engine) as session:
        assert session.get(SearchRecord, rid) is not None


def test_admin_can_delete_any_search(api):
    client, engine = api
    rid = add(engine, user_id(engine, "bob"), "Bob's")
    assert client.delete(f"/api/v1/history/{rid}", headers=login(client, "superadmin")).status_code == 204


def test_delete_search_requires_login_and_existing_record(api):
    client, engine = api
    rid = add(engine, user_id(engine, "alice"), "Mine")
    assert client.delete(f"/api/v1/history/{rid}").status_code == 401
    assert client.delete("/api/v1/history/99999", headers=login(client, "alice")).status_code == 404


def test_deleted_search_leaves_stats(api):
    client, engine = api
    alice = user_id(engine, "alice")
    keep = add(engine, alice, "Keep")
    gone = add(engine, alice, "Gone", status="ERROR", matches=None)
    headers = login(client, "alice")
    client.delete(f"/api/v1/history/{gone}", headers=headers)
    stats = client.get("/api/v1/history/stats", headers=headers).json()
    assert (stats["total"], stats["error"]) == (1, 0)
    assert [r["id"] for r in client.get("/api/v1/history", headers=headers).json()] == [keep]


# Users ------------------------------------------------------------------

def test_admin_deletes_user_and_searches_are_kept_unlinked(api):
    client, engine = api
    bob = user_id(engine, "bob")
    rid = add(engine, bob, "Bob's search")
    admin = login(client, "superadmin")

    assert client.delete(f"/api/v1/users/{bob}", headers=admin).status_code == 204
    assert "bob" not in [u["username"] for u in client.get("/api/v1/users", headers=admin).json()]

    with Session(engine) as session:
        record = session.get(SearchRecord, rid)
        assert record is not None and record.user_id is None
    # Unowned records remain visible to admins only.
    assert client.get(f"/api/v1/history/{rid}", headers=admin).status_code == 200
    assert client.get(f"/api/v1/history/{rid}", headers=login(client, "alice")).status_code == 404


def test_deleted_users_token_stops_working(api):
    client, engine = api
    bob_headers = login(client, "bob")
    client.delete(f"/api/v1/users/{user_id(engine, 'bob')}", headers=login(client, "superadmin"))
    assert client.get("/api/v1/history", headers=bob_headers).status_code == 401


def test_reused_username_does_not_inherit_old_searches(api):
    client, engine = api
    add(engine, user_id(engine, "bob"), "Old Bob search")
    admin = login(client, "superadmin")
    client.delete(f"/api/v1/users/{user_id(engine, 'bob')}", headers=admin)
    created = client.post("/api/v1/users", headers=admin, json={
        "username": "bob", "password": "brand-new-pass-456789", "role": "user"})
    assert created.status_code == 201, created.text
    resp = client.post("/api/v1/auth/login", data={"username": "bob", "password": "brand-new-pass-456789"})
    temp = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    # New accounts must replace the admin-chosen password first.
    changed = client.post("/api/v1/auth/password", headers=temp, json={
        "current_password": "brand-new-pass-456789", "new_password": "own-chosen-pass-987654"})
    assert changed.status_code == 200, changed.text
    headers = {"Authorization": f"Bearer {changed.json()['access_token']}"}
    assert client.get("/api/v1/history", headers=headers).json() == []


def test_admin_cannot_delete_self(api):
    client, engine = api
    resp = client.delete(f"/api/v1/users/{user_id(engine, 'superadmin')}", headers=login(client, "superadmin"))
    assert resp.status_code == 400


def test_admin_can_delete_another_admin_and_an_active_admin_remains(api):
    # The deleting admin is active and can't delete itself, so an active admin
    # always remains. (The server's last-admin check is a safety net on top.)
    client, engine = api
    admin = login(client, "superadmin")
    alice = user_id(engine, "alice")
    client.patch(f"/api/v1/users/{alice}", headers=admin, json={"role": "admin"})
    assert client.delete(f"/api/v1/users/{alice}", headers=admin).status_code == 204
    with Session(engine) as session:
        active_admins = session.exec(select(User).where(User.role == "admin", User.is_active == True)).all()  # noqa: E712
        assert [u.username for u in active_admins] == ["superadmin"]


def test_only_admins_can_delete_users(api):
    client, engine = api
    bob = user_id(engine, "bob")
    assert client.delete(f"/api/v1/users/{bob}", headers=login(client, "alice")).status_code == 403
    assert client.delete(f"/api/v1/users/{bob}").status_code == 401
    assert client.delete("/api/v1/users/99999", headers=login(client, "superadmin")).status_code == 404
