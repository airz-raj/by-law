"""Give every request an id, and echo it back.

A caller may supply ``X-Request-ID``; it is accepted only if it looks like
an id we would have generated ourselves, so nothing arbitrary reaches the
logs or a response body.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

HEADER_NAME = "X-Request-ID"
REQUEST_ID_STATE_KEY = "request_id"

_WELL_FORMED = re.compile(r"\A[A-Za-z0-9._-]{8,64}\Z")

Handler = Callable[[Request], Awaitable[Response]]


def new_request_id() -> str:
    """Return a fresh request id."""
    return uuid.uuid4().hex


def accept(candidate: str | None) -> str:
    """Return *candidate* if it is well formed, otherwise a fresh id."""
    if candidate and _WELL_FORMED.match(candidate):
        return candidate
    return new_request_id()


def request_id_of(request: Request) -> str:
    """Return the id assigned to *request*."""
    value = getattr(request.state, REQUEST_ID_STATE_KEY, None)
    return value if isinstance(value, str) else new_request_id()


class RequestIdMiddleware:
    """Assign a request id, expose it on ``request.state`` and echo it."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, request: Request, call_next: Handler) -> Response:
        """Attach an id to the request and the response."""
        request_id = accept(request.headers.get(HEADER_NAME))
        setattr(request.state, REQUEST_ID_STATE_KEY, request_id)
        response = await call_next(request)
        response.headers[HEADER_NAME] = request_id
        return response
