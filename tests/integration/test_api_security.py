"""Security behaviour at the API boundary: headers, limits and failures."""

from __future__ import annotations

from typing import Any, ClassVar

from fastapi.testclient import TestClient

from app.config import Settings
from app.security.headers import CONTENT_SECURITY_POLICY, SECURITY_HEADERS
from app.security.rate_limit import MAX_TRACKED_CLIENTS, RateLimiter, client_key
from tests.conftest import build_client, make_settings
from tests.fakes import FakeLLM, UnavailableLLM, load_fixture

DECODE = "/api/v1/notices/decode"
HEALTH = "/api/v1/health"


def test_every_security_header_is_present_on_an_api_response(client: TestClient) -> None:
    response = client.get(HEALTH)
    for name, value in SECURITY_HEADERS.items():
        assert response.headers[name] == value


def test_the_policy_allows_nothing_from_another_origin() -> None:
    assert "default-src 'self'" in CONTENT_SECURITY_POLICY
    assert "object-src 'none'" in CONTENT_SECURITY_POLICY
    assert "frame-ancestors 'none'" in CONTENT_SECURITY_POLICY
    assert "unsafe-inline" not in CONTENT_SECURITY_POLICY
    assert "unsafe-eval" not in CONTENT_SECURITY_POLICY


def test_api_answers_are_never_stored(client: TestClient) -> None:
    assert client.get(HEALTH).headers["Cache-Control"] == "no-store"


def test_a_request_id_is_returned_and_appears_in_the_body(client: TestClient) -> None:
    response = client.get(HEALTH)
    assert response.headers["X-Request-ID"]


def test_a_well_formed_request_id_from_the_caller_is_kept(client: TestClient) -> None:
    response = client.get(HEALTH, headers={"X-Request-ID": "trace-0123456789"})
    assert response.headers["X-Request-ID"] == "trace-0123456789"


def test_a_malformed_request_id_is_replaced(client: TestClient) -> None:
    response = client.get(HEALTH, headers={"X-Request-ID": "<script>alert(1)</script>"})
    assert response.headers["X-Request-ID"] != "<script>alert(1)</script>"


def test_the_request_id_reaches_the_problem_body(client: TestClient) -> None:
    response = client.post(DECODE, data={}, headers={"X-Request-ID": "trace-0123456789"})
    assert response.json()["request_id"] == "trace-0123456789"


def test_problem_responses_use_the_problem_media_type(client: TestClient) -> None:
    response = client.post(DECODE, data={})
    assert response.headers["content-type"].startswith("application/problem+json")


def test_a_problem_body_carries_no_internals(client: TestClient) -> None:
    body = client.post(DECODE, data={}).json()
    assert set(body) == {"type", "title", "status", "detail", "request_id"}
    assert "Traceback" not in body["detail"]
    assert "app/" not in body["detail"]


def test_an_unreachable_model_answers_503(settings: Settings, cheque_notice: str) -> None:
    with build_client(settings, UnavailableLLM()) as client:
        response = client.post(
            "/api/v1/questions",
            json={
                "question": "What?",
                "documents": [{"label": "doc", "text": cheque_notice}],
                "language": "en",
            },
        )
    assert response.status_code == 503
    assert response.json()["type"] == "mohlat:model-unavailable"


def test_output_that_never_fits_the_schema_answers_502(
    settings: Settings, cheque_notice: str
) -> None:
    llm = FakeLLM({"ask": {"answer": "x"}})
    with build_client(settings, llm) as client:
        response = client.post(
            "/api/v1/questions",
            json={
                "question": "What?",
                "documents": [{"label": "doc", "text": cheque_notice}],
                "language": "en",
            },
        )
    assert response.status_code == 502
    assert response.json()["type"] == "mohlat:model-output-invalid"
    assert "app/" not in response.json()["detail"]


def test_the_request_after_the_limit_is_refused_with_retry_after(
    settings: Settings, cheque_notice: str
) -> None:
    limited = settings.model_copy(update={"rate_limit_per_minute": 3})
    llm = FakeLLM({"decode": load_fixture("decode_cheque")})
    with build_client(limited, llm) as client:
        for _ in range(3):
            assert client.post(DECODE, data={"text": cheque_notice}).status_code == 200
        response = client.post(DECODE, data={"text": cheque_notice})
    assert response.status_code == 429
    assert response.json()["type"] == "mohlat:rate-limited"
    assert int(response.headers["Retry-After"]) >= 1


def test_reads_are_not_rate_limited(settings: Settings, llm: FakeLLM) -> None:
    limited = settings.model_copy(update={"rate_limit_per_minute": 1})
    with build_client(limited, llm) as client:
        for _ in range(5):
            assert client.get(HEALTH).status_code == 200


def fake_request(forwarded: str | None) -> Any:
    """A stand-in carrying just what client_key reads."""

    class Request:
        headers: ClassVar[dict[str, str]] = (
            {} if forwarded is None else {"x-forwarded-for": forwarded}
        )
        client = type("Client", (), {"host": "127.0.0.1"})()

    return Request()


def test_the_forwarded_client_is_ignored_unless_the_proxy_is_trusted() -> None:
    request = fake_request("203.0.113.9")
    assert client_key(request, trust_proxy=True) == "203.0.113.9"
    assert client_key(request, trust_proxy=False) == "127.0.0.1"


def test_a_client_supplied_forwarded_entry_cannot_impersonate_another_client() -> None:
    """The proxy appends, so only the rightmost entries can be believed.

    Trusting the leftmost entry would let one caller present a fresh
    address per request and spend the whole instance's model budget.
    """
    spoofed = fake_request("198.51.100.1, 203.0.113.9")
    assert client_key(spoofed, trust_proxy=True, proxy_hops=1) == "203.0.113.9"


def test_rotating_a_spoofed_entry_does_not_escape_the_limit() -> None:
    limiter = RateLimiter(make_settings(rate_limit_per_minute=3))
    refused = 0
    for attempt in range(10):
        request = fake_request(f"198.51.100.{attempt}, 203.0.113.9")
        key = client_key(request, trust_proxy=True, proxy_hops=1)
        if limiter.take(key) is not None:
            refused += 1
    assert refused == 7


def test_two_proxies_in_front_means_counting_two_in() -> None:
    request = fake_request("198.51.100.1, 203.0.113.9, 10.0.0.1")
    assert client_key(request, trust_proxy=True, proxy_hops=2) == "203.0.113.9"


def test_a_header_too_short_to_trust_falls_back_to_the_socket() -> None:
    request = fake_request("203.0.113.9")
    assert client_key(request, trust_proxy=True, proxy_hops=2) == "127.0.0.1"


def test_an_absent_header_falls_back_to_the_socket() -> None:
    assert client_key(fake_request(None), trust_proxy=True) == "127.0.0.1"


def test_the_tracked_clients_are_capped() -> None:
    """A flood of distinct keys must not grow the bucket map without bound."""
    limiter = RateLimiter(make_settings(rate_limit_per_minute=10))
    for n in range(MAX_TRACKED_CLIENTS + 500):
        limiter.take(f"client-{n}")
    assert len(limiter) <= MAX_TRACKED_CLIENTS


def test_the_interactive_docs_are_off_in_production(settings: Settings, llm: FakeLLM) -> None:
    production = settings.model_copy(update={"app_env": "prod"})
    with build_client(production, llm) as client:
        assert client.get("/api/docs").status_code == 404
        assert client.get("/api/redoc").status_code == 404
        assert client.get("/api/openapi.json").status_code == 200


def test_the_interactive_docs_are_available_in_development(client: TestClient) -> None:
    assert client.get("/api/docs").status_code == 200
