"""A per-client token bucket on the endpoints that cost a model call.

Limits are per server instance, which the README says plainly. Behind
Cloud Run the client is the first entry of ``X-Forwarded-For``; locally it
is the socket address.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.config import Settings
from app.errors import RateLimitExceeded

FORWARDED_FOR = "x-forwarded-for"
RETRY_AFTER_HEADER = "Retry-After"
UNKNOWN_CLIENT = "unknown"
WINDOW_SECONDS = 60

Handler = Callable[[Request], Awaitable[Response]]


def client_key(request: Request, *, trust_proxy: bool) -> str:
    """Identify the client behind *request*.

    Args:
        request: The incoming request.
        trust_proxy: Whether to believe ``X-Forwarded-For``. True on Cloud
            Run, where the proxy sets it; false locally, where a caller
            could set it themselves.

    Returns:
        A stable key for the caller.
    """
    if trust_proxy:
        forwarded = request.headers.get(FORWARDED_FOR)
        if forwarded:
            first = forwarded.split(",")[0].strip()
            if first:
                return first
    client = request.client
    return client.host if client else UNKNOWN_CLIENT


@dataclass
class _Bucket:
    """Tokens left for one client, and when they were last topped up."""

    tokens: float
    updated_at: float


class RateLimiter:
    """A fixed-rate token bucket per client."""

    def __init__(self, settings: Settings, clock: Callable[[], float] = time.monotonic) -> None:
        """Build a limiter sized from *settings*."""
        self._capacity = float(settings.rate_limit_per_minute)
        self._refill_per_second = self._capacity / WINDOW_SECONDS
        self._clock = clock
        self._buckets: dict[str, _Bucket] = {}

    def take(self, key: str) -> float | None:
        """Spend one token for *key*.

        Returns:
            None if the request may proceed, otherwise the number of
            seconds to wait before trying again.
        """
        now = self._clock()
        bucket = self._buckets.get(key)
        if bucket is None:
            self._buckets[key] = _Bucket(tokens=self._capacity - 1, updated_at=now)
            return None

        elapsed = now - bucket.updated_at
        bucket.tokens = min(self._capacity, bucket.tokens + elapsed * self._refill_per_second)
        bucket.updated_at = now

        if bucket.tokens >= 1:
            bucket.tokens -= 1
            return None
        return max(1.0, (1 - bucket.tokens) / self._refill_per_second)


class RateLimitMiddleware:
    """Apply the limiter to state-changing API calls."""

    def __init__(self, app: ASGIApp, settings: Settings, limiter: RateLimiter) -> None:
        self.app = app
        self._settings = settings
        self._limiter = limiter

    async def __call__(self, request: Request, call_next: Handler) -> Response:
        """Let the request through, or raise so the handler returns 429."""
        if request.method == "POST" and request.url.path.startswith("/api/"):
            key = client_key(request, trust_proxy=self._settings.trust_proxy)
            wait = self._limiter.take(key)
            if wait is not None:
                raise RateLimitExceeded(wait)
        return await call_next(request)
