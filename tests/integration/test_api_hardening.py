"""Regression tests for defects found by auditing the finished build.

Each test here exists because something was wrong and was fixed. They are
grouped together so the reason they exist stays visible.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient

from app.config import Settings
from app.security.headers import SECURITY_HEADERS
from tests.conftest import build_client
from tests.fakes import FakeLLM

DECODE = "/api/v1/notices/decode"


class Exploding:
    """A model port that fails in a way nothing maps, to force a 500."""

    async def generate(self, **_: object) -> object:
        """Raise something the error handlers do not know."""
        raise ZeroDivisionError("something nobody planned for")


def test_an_unhandled_failure_still_carries_the_security_headers(
    settings: Settings, cheque_notice: str
) -> None:
    """Starlette answers a 500 outside the middleware stack.

    The headers are attached where the problem is built, so a 500 is not
    the one response on the site served without a policy.
    """
    with build_client(settings, Exploding()) as client:
        response = client.post(DECODE, data={"text": cheque_notice})

    assert response.status_code == 500
    for name, value in SECURITY_HEADERS.items():
        assert response.headers[name] == value, name


def test_an_unhandled_failure_carries_a_request_id_and_no_store(
    settings: Settings, cheque_notice: str
) -> None:
    with build_client(settings, Exploding()) as client:
        response = client.post(DECODE, data={"text": cheque_notice})

    assert response.headers["X-Request-ID"]
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["content-type"].startswith("application/problem+json")


def test_an_unhandled_failure_tells_the_reader_nothing_about_the_cause(
    settings: Settings, cheque_notice: str
) -> None:
    with build_client(settings, Exploding()) as client:
        body = client.post(DECODE, data={"text": cheque_notice}).json()

    assert body["type"] == "mohlat:internal"
    assert "ZeroDivisionError" not in str(body)
    assert "app/" not in body["detail"]
    assert set(body) == {"type", "title", "status", "detail", "request_id"}


def test_a_body_with_no_declared_length_is_still_cut_off(settings: Settings, llm: FakeLLM) -> None:
    """A chunked upload cannot walk past the limit.

    The guard used to read only Content-Length, so a chunked request
    streamed megabytes in before anything refused it.
    """
    oversized = b"text=" + b"a" * (settings.max_upload_bytes + 1_000)

    def stream() -> Iterator[bytes]:
        """Yielding makes the client send without a Content-Length."""
        for start in range(0, len(oversized), 65_536):
            yield oversized[start : start + 65_536]

    with build_client(settings, llm) as client:
        response = client.post(
            DECODE,
            content=stream(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    assert "content-length" not in {k.lower() for k in response.request.headers}
    assert response.status_code == 413
    assert response.json()["type"] == "mohlat:body-too-large"


def test_a_declared_over_limit_body_is_refused_before_it_is_read(
    settings: Settings, llm: FakeLLM
) -> None:
    oversized = b"text=" + b"a" * (settings.max_upload_bytes + 1_000)
    with build_client(settings, llm) as client:
        response = client.post(
            DECODE,
            content=oversized,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    assert response.status_code == 413
    assert response.json()["type"] == "mohlat:body-too-large"


def test_a_body_under_the_limit_is_untouched(client: TestClient, cheque_notice: str) -> None:
    assert client.post(DECODE, data={"text": cheque_notice}).status_code == 200


def test_the_rules_payload_carries_the_disclaimer(client: TestClient) -> None:
    """It is the most advice-shaped thing the API returns."""
    body = client.get("/api/v1/rules").json()
    assert "not legal advice" in body["disclaimer"]


def test_a_cross_check_notice_longer_than_the_limit_is_refused(
    client: TestClient, rent_agreement: str
) -> None:
    response = client.post(
        "/api/v1/notices/cross-check",
        data={"notice_text": "x" * 60_001, "agreement_text": rent_agreement},
    )
    assert response.status_code == 422
    assert response.json()["type"] == "mohlat:invalid-request"


def test_a_question_document_longer_than_the_limit_is_refused(client: TestClient) -> None:
    response = client.post(
        "/api/v1/questions",
        json={
            "question": "What does it say?",
            "documents": [{"label": "notice", "text": "x" * 60_001}],
            "language": "en",
        },
    )
    assert response.status_code == 422
