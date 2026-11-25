"""Default paths must point into this repository.

conftest.py overrides DATABASE_PATH, so the rest of the suite would still pass
if moving a config module silently changed these defaults (a new, empty
database would be created on the next real start).
"""
from pathlib import Path

from app.config import JWTSettings, Settings
from app.config.settings import ENV_FILE, PROJECT_ROOT

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_project_root_is_the_repository_root():
    assert PROJECT_ROOT == REPO_ROOT
    assert (PROJECT_ROOT / "docker-compose.yml").is_file()


def test_default_database_path():
    default = Settings.model_fields["database_path"].default
    assert default == REPO_ROOT / "data" / "search_history.db"


def test_default_frontend_dist():
    default = Settings.model_fields["frontend_dist"].default
    assert default == REPO_ROOT / "frontend" / "dist"
    assert (default.parent / "package.json").is_file()


def test_both_settings_classes_read_the_same_env_file():
    assert ENV_FILE == REPO_ROOT / ".env"
    assert Settings.model_config["env_file"] == ENV_FILE
    assert JWTSettings.model_config["env_file"] == ENV_FILE
