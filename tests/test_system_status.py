"""Tests for GET /api/v1/health/systems and SystemHealthService (no network)."""

import urllib.error

from fastapi.testclient import TestClient

from app.api.auth_dependencies import get_current_user
from app.api.dependencies import get_health_service
from app.dto.models import ComponentStatus
from app.main import app
from app.services import health_service
from app.services.health_service import SystemHealthService
from app.settings import Settings


def _component(name, status="ok", detail=None):
    return ComponentStatus(name=name, label=name.title(), status=status, latency_ms=1, detail=detail)


def test_requires_authentication():
    app.dependency_overrides.clear()
    response = TestClient(app).get("/api/v1/health/systems")
    assert response.status_code in (401, 403)


class _FakeHealth:
    def status(self):
        return health_service.SystemStatusResponse(
            status="degraded",
            checked_at="2026-11-21T00:00:00Z",
            components=[_component("api"), _component("gemini", "down", "API key not configured")],
        )


def _get_as(role):
    class _User:
        pass
    user = _User()
    user.role = role
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_health_service] = lambda: _FakeHealth()
    try:
        return TestClient(app).get("/api/v1/health/systems")
    finally:
        app.dependency_overrides.clear()


def test_normal_user_gets_overall_status_only():
    response = _get_as("user")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["components"] == []


def test_returns_component_statuses_when_signed_in():
    class FakeHealth:
        def status(self):
            return health_service.SystemStatusResponse(
                status="degraded",
                checked_at="2026-11-21T00:00:00Z",
                components=[_component("api"), _component("gemini", "down", "API key not configured")],
            )

    class Admin:
        role = "admin"

    app.dependency_overrides[get_current_user] = lambda: Admin()
    app.dependency_overrides[get_health_service] = lambda: FakeHealth()
    try:
        response = TestClient(app).get("/api/v1/health/systems")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert [c["name"] for c in body["components"]] == ["api", "gemini"]
    assert body["components"][1] == {
        "name": "gemini", "label": "Gemini", "status": "down", "latency_ms": 1, "detail": "API key not configured",
    }


def test_overall_ok_only_when_every_component_ok(monkeypatch):
    monkeypatch.setattr(health_service, "check_database", lambda: _component("database"))
    monkeypatch.setattr(health_service, "check_gemini", lambda settings: _component("gemini"))
    monkeypatch.setattr(health_service, "check_wikipedia", lambda: _component("wikipedia"))
    assert SystemHealthService(Settings()).status().status == "ok"

    monkeypatch.setattr(health_service, "check_gemini", lambda settings: _component("gemini", "down", "Unreachable"))
    result = SystemHealthService(Settings()).status()
    assert result.status == "degraded"
    assert {c.name: c.status for c in result.components} == {
        "api": "ok", "database": "ok", "gemini": "down", "wikipedia": "ok",
    }


def test_external_checks_are_cached_within_ttl(monkeypatch):
    calls = {"gemini": 0, "wikipedia": 0}

    def fake_gemini(settings):
        calls["gemini"] += 1
        return _component("gemini")

    def fake_wikipedia():
        calls["wikipedia"] += 1
        return _component("wikipedia")

    monkeypatch.setattr(health_service, "check_database", lambda: _component("database"))
    monkeypatch.setattr(health_service, "check_gemini", fake_gemini)
    monkeypatch.setattr(health_service, "check_wikipedia", fake_wikipedia)

    service = SystemHealthService(Settings(), ttl_seconds=60)
    service.status()
    service.status()
    assert calls == {"gemini": 1, "wikipedia": 1}

    expired = SystemHealthService(Settings(), ttl_seconds=0)
    expired.status()
    expired.status()
    assert calls == {"gemini": 3, "wikipedia": 3}


def test_gemini_without_api_key_is_down_without_network():
    result = health_service.check_gemini(Settings(gemini_api_key=None))
    assert result.status == "down"
    assert result.detail == "API key not configured"


def test_wikipedia_unreachable_reports_safe_detail(monkeypatch):
    def fail(*args, **kwargs):
        raise urllib.error.URLError("dns failure for internal host")

    monkeypatch.setattr(health_service.urllib.request, "urlopen", fail)
    result = health_service.check_wikipedia()
    assert result.status == "down"
    assert result.detail == "Unreachable"  # upstream message is not leaked


def test_database_check_passes_against_app_engine():
    assert health_service.check_database().status == "ok"
