import os
import tempfile
from pathlib import Path

import pytest

# Point the app's own engine at a throwaway file BEFORE any app import, so
# startup code (schema upgrade) never touches the real data/ database.
_TEST_DB_DIR = tempfile.mkdtemp(prefix="verifylens-tests-")
os.environ["DATABASE_PATH"] = str(Path(_TEST_DB_DIR) / "app_under_test.db")

from app.api.rate_limit import ALL_LIMITERS  # noqa: E402


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Rate-limit counters are process-wide; give every test a clean slate."""
    for limiter in ALL_LIMITERS:
        limiter.reset()
    yield
    for limiter in ALL_LIMITERS:
        limiter.reset()
