import logging

import pytest
from fastapi.testclient import TestClient

from app.main import app
from security import secrets as secrets_mod
from security.secrets import validate_secrets
from security.tokens import JWTSettings

GOOD_KEY = "k" * 20 + "-strong-enough-test-key-123456"


def test_app_refuses_to_start_with_weak_jwt_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "too-short")  # env beats .env
    with pytest.raises(RuntimeError) as exc:
        with TestClient(app):
            pass
    message = str(exc.value)
    assert "jwt_secret_key" in message
    assert "too-short" not in message  # never echo the secret


def test_app_starts_with_valid_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", GOOD_KEY)
    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200


def test_missing_gemini_key_only_warns(monkeypatch, caplog):
    monkeypatch.setenv("JWT_SECRET_KEY", GOOD_KEY)
    monkeypatch.setenv("GEMINI_API_KEY", "")
    with caplog.at_level(logging.WARNING):
        validate_secrets()
    assert "GEMINI_API_KEY is not set" in caplog.text


def test_secret_can_come_from_a_secret_file(tmp_path, monkeypatch):
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    (tmp_path / "jwt_secret_key").write_text(GOOD_KEY, encoding="utf-8")
    settings = JWTSettings(_env_file=None, _secrets_dir=tmp_path)
    assert settings.jwt_secret_key == GOOD_KEY


def test_environment_variable_beats_secret_file(tmp_path, monkeypatch):
    (tmp_path / "jwt_secret_key").write_text("f" * 40, encoding="utf-8")
    monkeypatch.setenv("JWT_SECRET_KEY", GOOD_KEY)
    settings = JWTSettings(_env_file=None, _secrets_dir=tmp_path)
    assert settings.jwt_secret_key == GOOD_KEY


def test_secrets_dir_only_used_if_it_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path / "missing"))
    assert secrets_mod.secrets_dir() is None
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path))
    assert secrets_mod.secrets_dir() == tmp_path
