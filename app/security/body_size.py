"""Refuse an over-large request body.

A declared Content-Length above the limit is refused before anything is
read. A body that declares no length, or understates it, is counted as it
streams and cut off the moment it goes over, so a chunked upload cannot
walk past the limit either.

This is a pure ASGI middleware rather than a dispatch one because it has
to wrap ``receive`` to see the bytes at all.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import Settings
from app.errors import InputRejected, MohlatError

CONTENT_LENGTH = b"content-length"
CODE_BODY_TOO_LARGE = "BODY_TOO_LARGE"

Rejector = Callable[[Request, MohlatError], Response]


class _BodyTooLarge(BaseException):
    """Raised from inside ``receive`` when the body goes over the limit.

    It inherits from BaseException on purpose. The multipart parser wraps
    anything deriving from Exception into its own parse error, which would
    turn a clean 413 into a generic 400 naming no problem type.
    """


class BodySizeLimitMiddleware:
    """Cut off a request body that exceeds the upload limit."""

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

    def _too_large(self) -> InputRejected:
        """The rejection this guard raises."""
        return InputRejected(
            CODE_BODY_TOO_LARGE,
            f"That upload is larger than the {self._limit // 1_000_000} MB limit.",
        )

    def _declared_over_limit(self, scope: Scope) -> bool:
        """Whether the request declares a body larger than the limit."""
        for name, value in scope.get("headers", ()):
            if name.lower() == CONTENT_LENGTH and value.isdigit():
                return int(value) > self._limit
        return False

    def _counted(self, receive: Receive) -> Receive:
        """Wrap *receive* so the body is cut off once it exceeds the limit."""
        seen = 0

        async def counting_receive() -> Message:
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self._limit:
                    raise _BodyTooLarge
            return message

        return counting_receive

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Pass the request through, or answer 413 before it is parsed."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if self._declared_over_limit(scope):
            response = self._reject(Request(scope, receive), self._too_large())
            await response(scope, receive, send)
            return

        started = False

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, self._counted(receive), tracking_send)
        except _BodyTooLarge:
            if started:  # pragma: no cover - the app answered before we cut it off
                return
            response = self._reject(Request(scope, receive), self._too_large())
            await response(scope, receive, send)


Handler = Callable[[Request], Awaitable[Response]]
