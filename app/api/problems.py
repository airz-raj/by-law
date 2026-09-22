"""RFC 9457 problem responses.

Every failure answers with ``application/problem+json``: a stable type the
browser can branch on, a title, the status, a detail safe to show the
reader, and the request id. Stack traces and internals never leave the
server.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Final, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse

from app.errors import (
    InputRejected,
    LLMOutputInvalid,
    LLMUnavailable,
    MohlatError,
    RateLimitExceeded,
)
from app.observability import get_logger
from app.security.headers import NO_STORE, SECURITY_HEADERS
from app.security.request_id import HEADER_NAME as REQUEST_ID_HEADER
from app.security.request_id import request_id_of

Handler = Callable[[Request, Exception], Awaitable[JSONResponse]]

CONTENT_TYPE: Final = "application/problem+json"
TYPE_PREFIX: Final = "mohlat:"

GENERIC_DETAIL: Final = "Something went wrong at our end. Please try again."
RATE_LIMIT_DETAIL: Final = "You have made several requests in a row. Wait a moment and retry."
LLM_UNAVAILABLE_DETAIL: Final = (
    "The reading service is not answering right now. Wait a moment and try again."
)
LLM_INVALID_DETAIL: Final = (
    "We could not read this document reliably. Try pasting the text instead."
)
VALIDATION_DETAIL: Final = "Check the highlighted fields and try again."
MULTIPART_DETAIL: Final = (
    "That document is larger than Mohlat reads in one go. Send a shorter extract."
)

#: Which HTTP status each input-rejection code answers with.
_INPUT_STATUS: Final[dict[str, int]] = {
    "BODY_TOO_LARGE": HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
    "FILE_TOO_LARGE": HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
    "UNSUPPORTED_TYPE": HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
    "ENCRYPTED_PDF": HTTPStatus.UNPROCESSABLE_ENTITY,
    "INVALID_PDF": HTTPStatus.UNPROCESSABLE_ENTITY,
    "SCANNED_PDF": HTTPStatus.UNPROCESSABLE_ENTITY,
    "TOO_MANY_PAGES": HTTPStatus.UNPROCESSABLE_ENTITY,
    "TEXT_TOO_SHORT": HTTPStatus.UNPROCESSABLE_ENTITY,
    "DOCUMENT_TOO_LONG": HTTPStatus.UNPROCESSABLE_ENTITY,
    "RECEIPT_DATE_IN_FUTURE": HTTPStatus.UNPROCESSABLE_ENTITY,
    "NO_DOCUMENT": HTTPStatus.BAD_REQUEST,
    "BOTH_FILE_AND_TEXT": HTTPStatus.BAD_REQUEST,
}

logger = get_logger(__name__)


def problem_type(code: str) -> str:
    """Return the stable problem type for a code, such as ``mohlat:scanned-pdf``."""
    return f"{TYPE_PREFIX}{code.lower().replace('_', '-')}"


def problem(
    *,
    request: Request,
    code: str,
    status: int,
    detail: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build one problem+json response.

    The security headers are attached here rather than left to the
    middleware. Starlette's server-error handler sits outside the
    middleware stack, so a 500 built there would otherwise go out with no
    policy, no request id and no Cache-Control.
    """
    request_id = request_id_of(request)
    body = {
        "type": problem_type(code),
        "title": HTTPStatus(status).phrase,
        "status": status,
        "detail": detail,
        "request_id": request_id,
    }
    merged = {
        **SECURITY_HEADERS,
        "Cache-Control": NO_STORE,
        REQUEST_ID_HEADER: request_id,
        **(headers or {}),
    }
    return JSONResponse(body, status_code=status, media_type=CONTENT_TYPE, headers=merged)


def response_for(request: Request, error: MohlatError) -> JSONResponse:
    """Build the problem response for an error raised outside the handlers.

    Middleware runs outside the exception-handling layer, so a middleware
    that rejects a request builds its answer through this function rather
    than raising.
    """
    if isinstance(error, RateLimitExceeded):
        return _rate_limit_response(request, error)
    if isinstance(error, InputRejected):
        return _input_rejected_response(request, error)
    return problem(  # pragma: no cover - every middleware error is one of the above
        request=request,
        code="INTERNAL",
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
        detail=GENERIC_DETAIL,
    )


def _input_rejected_response(request: Request, exc: InputRejected) -> JSONResponse:
    """Build the response for an InputRejected."""
    status = _INPUT_STATUS.get(exc.code, HTTPStatus.BAD_REQUEST)
    return problem(request=request, code=exc.code, status=status, detail=exc.detail)


def _rate_limit_response(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Build the 429 response, with Retry-After."""
    return problem(
        request=request,
        code="RATE_LIMITED",
        status=HTTPStatus.TOO_MANY_REQUESTS,
        detail=RATE_LIMIT_DETAIL,
        headers={"Retry-After": str(max(1, round(exc.retry_after_seconds)))},
    )


async def _input_rejected(request: Request, exc: InputRejected) -> JSONResponse:
    """Answer an InputRejected with the status its code maps to."""
    return _input_rejected_response(request, exc)


async def _rate_limited(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Answer a rate-limit breach with 429 and Retry-After."""
    return _rate_limit_response(request, exc)


async def _llm_unavailable(request: Request, _exc: LLMUnavailable) -> JSONResponse:
    """Answer an unreachable model with 503."""
    logger.warning("llm unavailable", extra={"request_id": request_id_of(request)})
    return problem(
        request=request,
        code="MODEL_UNAVAILABLE",
        status=HTTPStatus.SERVICE_UNAVAILABLE,
        detail=LLM_UNAVAILABLE_DETAIL,
    )


async def _llm_output_invalid(request: Request, _exc: LLMOutputInvalid) -> JSONResponse:
    """Answer unusable model output with 502."""
    logger.warning("llm output invalid", extra={"request_id": request_id_of(request)})
    return problem(
        request=request,
        code="MODEL_OUTPUT_INVALID",
        status=HTTPStatus.BAD_GATEWAY,
        detail=LLM_INVALID_DETAIL,
    )


async def _validation_failed(request: Request, exc: Exception) -> JSONResponse:
    """Answer a malformed request with 422, naming only the fields."""
    fields: list[str] = []
    if isinstance(exc, RequestValidationError):
        fields = [
            ".".join(str(part) for part in error.get("loc", ())[1:]) for error in exc.errors()
        ]
    return problem(
        request=request,
        code="INVALID_REQUEST",
        status=HTTPStatus.UNPROCESSABLE_ENTITY,
        detail=f"{VALIDATION_DETAIL} ({', '.join(f for f in fields if f)})"
        if any(fields)
        else VALIDATION_DETAIL,
    )


async def _multipart_rejected(request: Request, _exc: MultiPartException) -> JSONResponse:
    """Answer Starlette's own multipart failure in the problem contract.

    Without this the framework answers with its own JSON shape, which
    carries no problem type and names an internal limit.
    """
    logger.info("multipart rejected", extra={"request_id": request_id_of(request)})
    return problem(
        request=request,
        code="DOCUMENT_TOO_LONG",
        status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        detail=MULTIPART_DETAIL,
    )


async def _unexpected(request: Request, _exc: Exception) -> JSONResponse:
    """Answer anything unforeseen with 500 and nothing about the cause."""
    logger.exception("unhandled error", extra={"request_id": request_id_of(request)})
    return problem(
        request=request,
        code="INTERNAL",
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
        detail=GENERIC_DETAIL,
    )


#: Each error and the handler that answers it. Starlette types handlers
#: against the base Exception, so each entry is cast at registration.
_HANDLERS: Final[tuple[tuple[type[Exception], Handler], ...]] = (
    (InputRejected, cast("Handler", _input_rejected)),
    (RateLimitExceeded, cast("Handler", _rate_limited)),
    (LLMUnavailable, cast("Handler", _llm_unavailable)),
    (LLMOutputInvalid, cast("Handler", _llm_output_invalid)),
    (RequestValidationError, cast("Handler", _validation_failed)),
    (MultiPartException, cast("Handler", _multipart_rejected)),
    (Exception, cast("Handler", _unexpected)),
)


def install(app: FastAPI) -> None:
    """Register every exception handler on *app*."""
    for error, handler in _HANDLERS:
        app.add_exception_handler(error, handler)
