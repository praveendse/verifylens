"""User list paging, server-side search and count (admin-only).

Reuses the isolated temp-DB fixture and helpers from test_history_paging.
The fixture seeds superadmin, alice and bob (ids 1-3, in that order).
"""
from sqlmodel import Session

from app.infra.db.models import User
from security.passwords import hash_password
from test_history_paging import api, login  # noqa: F401  (api is a fixture)

URL = "/api/v1/users"


def add_users(engine, count, prefix="member"):
    with Session(engine) as session:
        for n in range(count):
            session.add(User(
                username=f"{prefix}{n:02d}", full_name=f"Member Number {n:02d}",
                hashed_password=hash_password("unused-password-123"), role="user",
            ))
        session.commit()


def usernames(resp):
    assert resp.status_code == 200, resp.text
    return [u["username"] for u in resp.json()]


def test_default_page_is_20_oldest_first(api):
    client, engine = api
    add_users(engine, 30)
    names = usernames(client.get(URL, headers=login(client, "superadmin")))
    assert len(names) == 20
    assert names[:3] == ["superadmin", "alice", "bob"]


def test_after_id_walks_every_user_once(api):
    client, engine = api
    add_users(engine, 30)
    headers = login(client, "superadmin")
    seen, after = [], None
    while True:
        params = {"limit": 7} | ({"after_id": after} if after else {})
        page = client.get(URL, headers=headers, params=params).json()
        if not page:
            break
        seen += [u["id"] for u in page]
        after = page[-1]["id"]
    assert len(seen) == 33 and seen == sorted(set(seen))


def test_new_account_between_pages_is_not_duplicated(api):
    client, engine = api
    add_users(engine, 10)
    headers = login(client, "superadmin")
    first = client.get(URL, headers=headers, params={"limit": 5}).json()
    add_users(engine, 1, prefix="late")
    second = client.get(URL, headers=headers, params={"limit": 50, "after_id": first[-1]["id"]}).json()
    ids = [u["id"] for u in first + second]
    assert len(ids) == len(set(ids)) == 14


def test_search_matches_username_or_full_name_case_insensitive(api):
    client, engine = api
    with Session(engine) as session:
        session.add(User(username="nimal", full_name="Nimal Hettiarachchi", hashed_password="x", role="user"))
        session.add(User(username="upeksha", full_name="Upeksha Perera", hashed_password="x", role="user"))
        session.commit()
    headers = login(client, "superadmin")
    assert usernames(client.get(URL, headers=headers, params={"q": "NIM"})) == ["nimal"]
    assert usernames(client.get(URL, headers=headers, params={"q": "perera"})) == ["upeksha"]
    # Every term must match (in either field), like the old in-browser filter.
    assert usernames(client.get(URL, headers=headers, params={"q": "nimal hetti"})) == ["nimal"]
    assert usernames(client.get(URL, headers=headers, params={"q": "nimal perera"})) == []


def test_search_treats_wildcards_literally(api):
    client, _ = api
    headers = login(client, "superadmin")
    assert usernames(client.get(URL, headers=headers, params={"q": "%"})) == []
    assert usernames(client.get(URL, headers=headers, params={"q": "_"})) == []


def test_search_and_paging_combine(api):
    client, engine = api
    add_users(engine, 25)
    headers = login(client, "superadmin")
    first = client.get(URL, headers=headers, params={"q": "member", "limit": 20}).json()
    rest = client.get(URL, headers=headers, params={"q": "member", "limit": 20, "after_id": first[-1]["id"]}).json()
    assert (len(first), len(rest)) == (20, 5)


def test_count_total_and_filtered(api):
    client, engine = api
    add_users(engine, 12)
    headers = login(client, "superadmin")
    assert client.get(f"{URL}/count", headers=headers).json() == {"total": 15}
    assert client.get(f"{URL}/count", headers=headers, params={"q": "member1"}).json() == {"total": 2}  # member10, member11


def test_validation_limits(api):
    client, _ = api
    headers = login(client, "superadmin")
    assert client.get(URL, headers=headers, params={"limit": 0}).status_code == 422
    assert client.get(URL, headers=headers, params={"limit": 51}).status_code == 422
    assert client.get(URL, headers=headers, params={"after_id": 0}).status_code == 422
    assert client.get(URL, headers=headers, params={"q": "x" * 101}).status_code == 422


def test_list_and_count_are_admin_only(api):
    client, _ = api
    alice = login(client, "alice")
    assert client.get(URL, headers=alice).status_code == 403
    assert client.get(f"{URL}/count", headers=alice).status_code == 403
    assert client.get(URL).status_code == 401
    assert client.get(f"{URL}/count").status_code == 401
