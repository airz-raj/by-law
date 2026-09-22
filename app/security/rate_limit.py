"""A per-client token bucket on the endpoints that cost a model call.

Limits are per server instance, which the README says plainly.

Identifying the client behind a proxy is the security-sensitive part. A
caller can put anything in ``X-Forwarded-For``, and Cloud Run appends to
whatever arrives rather than replacing it, so the leftmost entry is
attacker-controlled and the trustworthy entries are at the right-hand
end. The client is therefore counted in from the right by the number of
proxies actually in front of the app.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.config import Settings
from app.errors import MohlatError, RateLimitExceeded

FORWARDED_FOR = "x-forwarded-for"
RETRY_AFTER_HEADER = "Retry-After"
UNKNOWN_CLIENT = "unknown"
WINDOW_SECONDS = 60

#: Buckets are capped so a flood of distinct client keys cannot grow the
#: dictionary without bound.
MAX_TRACKED_CLIENTS = 4096

Handler = Callable[[Request], Awaitable[Response]]
Rejector = Callable[[Request, MohlatError], Response]


def client_key(request: Request, *, trust_proxy: bool, proxy_hops: int = 1) -> str:
    """Identify the client behind *request*.

    Args:
        request: The incoming request.
        trust_proxy: Whether there is a proxy in front whose
            ``X-Forwarded-For`` entries can be believed. True on Cloud Run;
            false anywhere the caller could set that header themselves.
        proxy_hops: How many proxies are in front of the app. The client is
            that many entries in from the right-hand end of the header,
            because each proxy appends and only the rightmost entries were
            written by infrastructure we control.

    Returns:
        A stable key for the caller, falling back to the socket address
        whenever the header is absent or too short to trust.
    """
    if trust_proxy and proxy_hops >= 1:
        forwarded = request.headers.get(FORWARDED_FOR)
        if forwarded:
            entries = [entry.strip() for entry in forwarded.split(",") if entry.strip()]
            if len(entries) >= proxy_hops:
                return entries[-proxy_hops]
    client = request.client
    return client.host if client else UNKNOWN_CLIENT


@dataclass
class _Bucket:
    """Tokens left for one client, and when they were last topped up."""

    tokens: float
    updated_at: float


class RateLimiter:
    """A fixed-rate token bucket per client, with a bounded set of clients."""

    def __init__(self, settings: Settings, clock: Callable[[], float] = time.monotonic) -> None:
        """Build a limiter sized from *settings*."""
        self._capacity = float(settings.rate_limit_per_minute)
        self._refill_per_second = self._capacity / WINDOW_SECONDS
        self._clock = clock
        self._buckets: OrderedDict[str, _Bucket] = OrderedDict()

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
            self._evict_oldest()
            return None

        self._buckets.move_to_end(key)
        elapsed = now - bucket.updated_at
        bucket.tokens = min(self._capacity, bucket.tokens + elapsed * self._refill_per_second)
        bucket.updated_at = now

        if bucket.tokens >= 1:
            bucket.tokens -= 1
            return None
        return max(1.0, (1 - bucket.tokens) / self._refill_per_second)

    def _evict_oldest(self) -> None:
        """Drop least recently seen clients once the cap is reached."""
        while len(self._buckets) > MAX_TRACKED_CLIENTS:
            self._buckets.popitem(last=False)

    def __len__(self) -> int:
        """Return how many clients are currently tracked."""
        return len(self._buckets)


class RateLimitMiddleware:
    """Apply the limiter to the API calls that cost a model call."""

    def __init__(
        self, app: ASGIApp, settings: Settings, limiter: RateLimiter, reject: Rejector
    ) -> None:
        """Build the middleware.

        Args:
            app: The application being wrapped.
            settings: Supplies proxy trust and the number of proxy hops.
            limiter: The shared token bucket.
            reject: Turns the refusal into a problem response.
        """
        self.app = app
        self._settings = settings
        self._limiter = limiter
        self._reject = reject

    async def __call__(self, request: Request, call_next: Handler) -> Response:
        """Let the request through, or answer 429 with Retry-After."""
        if request.method == "POST" and request.url.path.startswith("/api/"):
            key = client_key(
                request,
                trust_proxy=self._settings.trust_proxy,
                proxy_hops=self._settings.trusted_proxy_hops,
            )
            wait = self._limiter.take(key)
            if wait is not None:
                return self._reject(request, RateLimitExceeded(wait))
        return await call_next(request)
