"""FastAPI serving the built React app (uses a fake dist folder)."""
from pathlib import Path

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from app.frontend import mount_frontend


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    d = tmp_path / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text("<html>APP</html>", encoding="utf-8")
    (d / "assets" / "app-123.js").write_text("console.log(1)", encoding="utf-8")
    (d / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("TOP SECRET", encoding="utf-8")
    return d


def make_app(dist: Path) -> tuple[FastAPI, bool]:
    app = FastAPI()
    api = APIRouter()

    @api.get("/health")
    def health():
        return {"status": "ok"}

    app.include_router(api, prefix="/api/v1")
    mounted = mount_frontend(app, dist)
    return app, mounted


def test_serves_index_and_assets(dist):
    app, mounted = make_app(dist)
    assert mounted
    client = TestClient(app)

    root = client.get("/")
    assert root.status_code == 200
    assert "APP" in root.text
    assert root.headers["cache-control"] == "no-cache"

    assert client.get("/assets/app-123.js").text == "console.log(1)"
    assert client.get("/favicon.svg").text == "<svg/>"


def test_unknown_page_falls_back_to_index(dist):
    client = TestClient(make_app(dist)[0])
    resp = client.get("/history/42")
    assert resp.status_code == 200
    assert "APP" in resp.text


def test_api_routes_win_and_unknown_api_is_json_404(dist):
    client = TestClient(make_app(dist)[0])
    assert client.get("/api/v1/health").json() == {"status": "ok"}

    missing = client.get("/api/v1/does-not-exist")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Not Found"}
    assert client.get("/api").status_code == 404


def test_cannot_read_files_outside_dist(dist):
    client = TestClient(make_app(dist)[0])
    for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt"):
        resp = client.get(path)
        assert "TOP SECRET" not in resp.text


def test_nothing_mounted_when_not_built(tmp_path):
    app, mounted = make_app(tmp_path / "missing")
    assert not mounted
    assert TestClient(app).get("/").status_code == 404
