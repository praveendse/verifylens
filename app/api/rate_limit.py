"""In-memory rate limits for login and search.

Limits are per server process. That matches this app's deployment model (one
process, because SQLite allows only one writer); if it is ever scaled out to
several processes or machines, move these counters to a shared store such as
Redis.
"""
import math
import threading
import time
from collections import defaultdict, deque
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.auth_dependencies import get_authenticated_user, get_current_user
from app.db.models import User
from app.settings import Settings


class RateLimiter:
    """Sliding window: at most `limit` hits per `window_s` seconds per key."""

    def __init__(self, limit: int, window_s: float):
        self.limit = limit
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str) -> float | None:
        """Record one hit. Returns None if allowed, else seconds to wait."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window_s:
                hits.popleft()
            if len(hits) >= self.limit:
                return self.window_s - (now - hits[0])
            hits.append(now)
            if len(self._hits) > 10_000:  # keep memory bounded
                self._prune(now)
            return None

    def _prune(self, now: float) -> None:
        for key in [k for k, v in self._hits.items() if not v or now - v[-1] >= self.window_s]:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


_settings = Settings()
login_ip_limiter = RateLimiter(_settings.login_attempts_per_ip_per_minute, 60)
login_user_limiter = RateLimiter(_settings.login_attempts_per_username_per_minute, 60)
search_limiter = RateLimiter(_settings.searches_per_user_per_minute, 60)
password_change_limiter = RateLimiter(_settings.login_attempts_per_username_per_minute, 60)
# Password recovery (spec PWR-11). The per-identifier limit is applied after
# the response (see password_reset_routes) so it can't reveal which accounts exist.
reset_request_ip_limiter = RateLimiter(5, 60)
reset_request_identifier_limiter = RateLimiter(3, 15 * 60)
reset_confirm_ip_limiter = RateLimiter(10, 60)
ALL_LIMITERS = (
    login_ip_limiter, login_user_limiter, search_limiter, password_change_limiter,
    reset_request_ip_limiter, reset_request_identifier_limiter, reset_confirm_ip_limiter,
)


def _too_many(retry_after: float, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=message,
        headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
    )


def client_ip(request: Request) -> str:
    # Direct peer address. Behind a reverse proxy, run uvicorn with
    # --proxy-headers --forwarded-allow-ips=<proxy ip> so this is the real
    # client, not the proxy (otherwise all users share one limit).
    return request.client.host if request.client else "unknown"


def limit_login(
    request: Request,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> None:
    """Blocks password guessing: per IP, and per username across all IPs."""
    message = "Too many login attempts. Please wait a minute and try again."
    wait = login_ip_limiter.hit(client_ip(request))
    if wait is None:
        wait = login_user_limiter.hit(form.username.strip().lower())
    if wait is not None:
        raise _too_many(wait, message)


def limit_password_change(
    current_user: Annotated[User, Depends(get_authenticated_user)],
) -> None:
    """Stops guessing the current password with a stolen session token."""
    wait = password_change_limiter.hit(f"user:{current_user.id}")
    if wait is not None:
        raise _too_many(wait, "Too many password change attempts. Please wait a minute and try again.")


def limit_reset_request(request: Request) -> None:
    wait = reset_request_ip_limiter.hit(client_ip(request))
    if wait is not None:
        raise _too_many(wait, "Too many password reset requests. Please wait a minute and try again.")


def limit_reset_confirm(request: Request) -> None:
    """Stops guessing reset tokens from one address."""
    wait = reset_confirm_ip_limiter.hit(client_ip(request))
    if wait is not None:
        raise _too_many(wait, "Too many attempts. Please wait a minute and try again.")


def limit_search(current_user: Annotated[User, Depends(get_current_user)]) -> None:
    """Caps Gemini spend and browser launches per user."""
    wait = search_limiter.hit(f"user:{current_user.id}")
    if wait is not None:
        raise _too_many(wait, "Too many searches. Please wait a minute and try again.")
