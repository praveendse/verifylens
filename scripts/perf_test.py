"""Data-volume performance test for the user and history endpoints.

For each scale (100 / 1,000 / 10,000 accounts, each with SEARCHES_PER_USER
saved searches) it builds a fresh temporary SQLite database, then times the
real FastAPI endpoints in-process (TestClient: no network, no Wikipedia or
Gemini calls) and reports median / p95 latency and response size.

"legacy: load all users" reproduces the old GET /users (every account,
serialised) for comparison with the new paged endpoint.

Run:  python -m scripts.perf_test            (all scales)
      python -m scripts.perf_test 100 1000   (chosen scales)
Never touches data/search_history.db.
"""
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "perf-test-key-only-not-for-production-0123456789abcdef")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import insert  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine, select  # noqa: E402

from app.infra.db.database import get_session  # noqa: E402
from app.infra.db.models import SearchRecord, User  # noqa: E402
from app.dto.auth_models import UserPublic  # noqa: E402
from app.main import app  # noqa: E402
from security.passwords import hash_password  # noqa: E402

SCALES = [100, 1_000, 10_000]
SEARCHES_PER_USER = 10
RUNS = 40
WARMUP = 3
ADMIN_PASSWORD = "perf-admin-password-123"
TOPICS = ["Albert Einstein", "World War II", "Sri Lanka", "BMW", "Python", "Moon landing", "Tea", "Colombo"]
FIRST = ["Nimal", "Upeksha", "Kasun", "Dilani", "Ruwan", "Ayesha", "Tharindu", "Sanduni", "Chamara", "Ishara"]
LAST = ["Perera", "Silva", "Fernando", "Hettiarachchi", "Jayasinghe", "Bandara", "Wickramasinghe", "Dias"]


def seed(engine, n_users):
    shared_hash = hash_password("unused-member-password-123")  # hashing 10k times would dominate setup
    with Session(engine) as session:
        session.add(User(username="perfadmin", full_name="Perf Admin",
                         hashed_password=hash_password(ADMIN_PASSWORD), role="admin"))
        session.commit()
        session.execute(insert(User), [
            {"username": f"member{i:05d}", "full_name": f"{FIRST[i % len(FIRST)]} {LAST[i % len(LAST)]} {i}",
             "hashed_password": shared_hash, "role": "user", "is_active": True}
            for i in range(n_users - 1)
        ])
        ids = session.exec(select(User.id)).all()
        session.execute(insert(SearchRecord), [
            {"query": TOPICS[(uid + k) % len(TOPICS)], "article_title": TOPICS[(uid + k) % len(TOPICS)],
             "status": "ERROR" if (uid + k) % 9 == 0 else "SUCCESS",
             "matches": None if (uid + k) % 9 == 0 else (uid + k) % 4 != 0,
             "user_id": uid, "report_markdown": "# Report\n\n" + "Lorem ipsum. " * 40}
            for uid in ids for k in range(SEARCHES_PER_USER)
        ])
        session.commit()
        return ids


def timed(fn):
    for _ in range(WARMUP):
        fn()
    samples, size = [], 0
    for _ in range(RUNS):
        start = time.perf_counter()
        size = fn()
        samples.append((time.perf_counter() - start) * 1000)
    samples.sort()
    return statistics.median(samples), samples[int(len(samples) * 0.95) - 1], size


def run_scale(n_users):
    tmp = tempfile.TemporaryDirectory()
    engine = create_engine(f"sqlite:///{Path(tmp.name) / 'perf.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    t0 = time.perf_counter()
    ids = seed(engine, n_users)
    seed_s = time.perf_counter() - t0

    def session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    results = []
    try:
        with TestClient(app) as client:
            token = client.post("/api/v1/auth/login",
                                data={"username": "perfadmin", "password": ADMIN_PASSWORD}).json()["access_token"]
            h = {"Authorization": f"Bearer {token}"}
            mid = ids[len(ids) // 2]
            newest_record = n_users * SEARCHES_PER_USER

            def get(url, **params):
                def call():
                    r = client.get(url, headers=h, params=params)
                    assert r.status_code == 200, (url, r.status_code, r.text[:200])
                    return len(r.content)
                return call

            def legacy_all_users():
                with Session(engine) as session:
                    rows = session.exec(select(User).order_by(User.id)).all()
                    body = "[" + ",".join(UserPublic.model_validate(u).model_dump_json() for u in rows) + "]"
                return len(body)

            cases = [
                ("users: first page (21 rows)", get("/api/v1/users", limit=21)),
                ("users: middle page (after_id)", get("/api/v1/users", limit=21, after_id=mid)),
                ("users: search 'nimal' (many hits)", get("/api/v1/users", limit=21, q="nimal")),
                ("users: search 'kasun 42' (2 words)", get("/api/v1/users", limit=21, q="kasun 42")),
                ("users: search, no match", get("/api/v1/users", limit=21, q="zzzz")),
                ("users: count", get("/api/v1/users/count")),
                ("legacy: load all users", legacy_all_users),
                ("history: first page (6 rows)", get("/api/v1/history", limit=6)),
                ("history: middle page (before_id)", get("/api/v1/history", limit=6, before_id=newest_record // 2)),
                ("history: topic filter 'colombo'", get("/api/v1/history", limit=6, q="colombo")),
                ("history: topic filter, no match", get("/api/v1/history", limit=6, q="zzzz")),
                ("history: status=ERROR", get("/api/v1/history", limit=6, status="ERROR")),
                ("history: stats (donut)", get("/api/v1/history/stats")),
            ]
            for name, fn in cases:
                results.append((name, *timed(fn)))
    finally:
        app.dependency_overrides.pop(get_session, None)
        engine.dispose()
        tmp.cleanup()
    return seed_s, results


def main():
    scales = [int(a) for a in sys.argv[1:]] or SCALES
    print(f"SQLite, in-process TestClient, {RUNS} timed runs per case after {WARMUP} warm-up\n")
    for n in scales:
        seed_s, results = run_scale(n)
        print(f"=== {n:,} users, {n * SEARCHES_PER_USER:,} searches (seeded in {seed_s:.1f}s) ===")
        print(f"{'case':<36}{'median ms':>11}{'p95 ms':>9}{'bytes':>11}")
        for name, med, p95, size in results:
            print(f"{name:<36}{med:>11.2f}{p95:>9.2f}{size:>11,}")
        print()


if __name__ == "__main__":
    main()
