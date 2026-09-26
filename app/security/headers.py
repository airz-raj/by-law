"""Security headers applied to every response.

The Content-Security-Policy needs no exceptions because the page carries
no inline script or style and loads nothing from another origin.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

CONTENT_SECURITY_POLICY = "; ".join(
    (
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "connect-src 'self'",
        "font-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "frame-ancestors 'none'",
        "form-action 'self'",
        "require-trusted-types-for 'script'",
    )
)

SECURITY_HEADERS: Mapping[str, str] = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-Frame-Options": "DENY",
}

API_PREFIX = "/api/"
NO_STORE = "no-store"
STATIC_CACHE_CONTROL = "public, max-age=3600"
PAGE_CACHE_CONTROL = "no-cache"

_STATIC_PREFIXES = ("/css/", "/js/", "/i18n/", "/samples/")

Handler = Callable[[Request], Awaitable[Response]]


def cache_control_for(path: str) -> str:
    """Return the Cache-Control value for *path*.

    API answers are never stored. Static assets may be cached for an hour;
    the page itself is revalidated so a deploy is picked up at once.
    """
    if path.startswith(API_PREFIX):
        return NO_STORE
    if path.startswith(_STATIC_PREFIXES):
        return STATIC_CACHE_CONTROL
    return PAGE_CACHE_CONTROL


class SecurityHeadersMiddleware:
    """Add the security headers and the right Cache-Control to every response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, request: Request, call_next: Handler) -> Response:
        """Apply the headers to the response for *request*."""
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers[name] = value
        response.headers["Cache-Control"] = cache_control_for(request.url.path)
        return response
