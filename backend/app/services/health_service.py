"""Live dependency checks for the system-status indicator.

Each check returns a ComponentStatus. External checks (Gemini, Wikipedia)
are cached for a short TTL so dashboards polling the endpoint cannot burn
API quota or hammer third parties. Checks run in parallel with timeouts so a
hung dependency cannot stall the response.

Failure details are deliberately coarse (exception class / HTTP status only):
never echo API keys, URLs with credentials, or upstream error bodies.
"""

from __future__ import annotations

import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import text
from sqlmodel import Session

from app.infra.db.database import engine
from app.dto.models import ComponentStatus, SystemStatusResponse
from app.config import Settings

EXTERNAL_TIMEOUT_SECONDS = 5
EXTERNAL_CACHE_TTL_SECONDS = 60
WIKIPEDIA_PROBE_URL = "https://en.wikipedia.org/w/api.php?action=query&meta=siteinfo&format=json"
USER_AGENT = "WikipediaImageVerifier-HealthCheck/1.0"


def _timed(name: str, label: str, probe: Callable[[], None]) -> ComponentStatus:
    """Run a probe; any exception marks the component as down."""
    started = time.perf_counter()
    try:
        probe()
        status, detail = "ok", None
    except _ProbeFailed as exc:
        status, detail = "down", str(exc)
    except Exception as exc:  # noqa: BLE001 - any failure means "not healthy"
        status, detail = "down", type(exc).__name__
    latency_ms = round((time.perf_counter() - started) * 1000)
    return ComponentStatus(name=name, label=label, status=status, latency_ms=latency_ms, detail=detail)


class _ProbeFailed(Exception):
    """A failure whose message is safe to show to the client."""


def check_database() -> ComponentStatus:
    def probe() -> None:
        with Session(engine) as session:
            session.exec(text("SELECT 1")).one()

    return _timed("database", "Saved data", probe)


def check_gemini(settings: Settings) -> ComponentStatus:
    def probe() -> None:
        if not settings.gemini_api_key:
            raise _ProbeFailed("API key not configured")
        # Imported lazily so the rest of the app does not depend on it at import time.
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=EXTERNAL_TIMEOUT_SECONDS * 1000),
        )
        # Metadata lookup: proves key validity + reachability without generating tokens.
        client.models.get(model=settings.gemini_model)

    return _timed("gemini", "Image check (Gemini)", probe)


def check_wikipedia() -> ComponentStatus:
    def probe() -> None:
        request = urllib.request.Request(WIKIPEDIA_PROBE_URL, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=EXTERNAL_TIMEOUT_SECONDS) as response:  # noqa: S310 - fixed https URL
                if response.status != 200:
                    raise _ProbeFailed(f"HTTP {response.status}")
        except urllib.error.HTTPError as exc:
            raise _ProbeFailed(f"HTTP {exc.code}") from None
        except urllib.error.URLError:
            raise _ProbeFailed("Unreachable") from None

    return _timed("wikipedia", "Wikipedia", probe)


class SystemHealthService:
    """Aggregates component checks; caches the external ones."""

    def __init__(self, settings: Settings, ttl_seconds: int = EXTERNAL_CACHE_TTL_SECONDS):
        self._settings = settings
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._external_cache: tuple[float, list[ComponentStatus]] | None = None

    def _external(self) -> list[ComponentStatus]:
        with self._lock:
            cached = self._external_cache
            if cached and time.monotonic() - cached[0] < self._ttl:
                return cached[1]
            with ThreadPoolExecutor(max_workers=2) as pool:
                gemini = pool.submit(check_gemini, self._settings)
                wikipedia = pool.submit(check_wikipedia)
                results = [gemini.result(), wikipedia.result()]
            self._external_cache = (time.monotonic(), results)
            return results

    def status(self) -> SystemStatusResponse:
        api = ComponentStatus(name="api", label="App server", status="ok", latency_ms=0, detail=None)
        components = [api, check_database(), *self._external()]
        overall = "ok" if all(c.status == "ok" for c in components) else "degraded"
        return SystemStatusResponse(
            status=overall,
            checked_at=datetime.now(timezone.utc),
            components=components,
        )
