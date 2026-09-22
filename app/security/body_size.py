"""Reject an over-large upload before multipart parsing starts.

A declared Content-Length above the limit is refused outright, so a large
body is never read into memory to find out it was too large. Middleware
runs outside the exception-handling layer, so the rejection is turned into
a response here rather than raised.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.config import Settings
from app.errors import InputRejected, MohlatError

CONTENT_LENGTH = "content-length"
CODE_BODY_TOO_LARGE = "BODY_TOO_LARGE"

Handler = Callable[[Request], Awaitable[Response]]
Rejector = Callable[[Request, MohlatError], Response]


class BodySizeLimitMiddleware:
    """Refuse a request whose declared body exceeds the upload limit."""

    def __init__(self, app: ASGIApp, settings: Settings, reject: Rejector) -> None:
        """Build the guard.

        Args:
            app: The application being wrapped.
            settings: Supplies ``max_upload_bytes``.
            reject: Turns the rejection into a problem response.
        """
        self.app = app
        self._limit = settings.max_upload_bytes
        self._reject = reject

    async def __call__(self, request: Request, call_next: Handler) -> Response:
        """Answer 413 before the body is read if it is declared too large."""
        declared = request.headers.get(CONTENT_LENGTH)
        if declared is not None and declared.isdigit() and int(declared) > self._limit:
            return self._reject(
                request,
                InputRejected(
                    CODE_BODY_TOO_LARGE,
                    f"That upload is larger than the {self._limit // 1_000_000} MB limit.",
                ),
            )
        return await call_next(request)
