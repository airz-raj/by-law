"""Contract tests for the cross-check endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.services.pipeline import (
    AGREEMENT_QUOTE_NOT_FOUND,
    NOTICE_QUOTE_NOT_FOUND,
    TASK_CROSS_CHECK,
)
from tests.conftest import build_client
from tests.fakes import FakeLLM, load_fixture

CROSS_CHECK = "/api/v1/notices/cross-check"


def test_the_sample_pair_returns_two_conflicts(
    client: TestClient, vacate_notice: str, rent_agreement: str
) -> None:
    response = client.post(
        CROSS_CHECK, data={"notice_text": vacate_notice, "agreement_text": rent_agreement}
    )
    assert response.status_code == 200
    verdicts = [claim["verdict"] for claim in response.json()["claims"]]
    assert verdicts.count("CONFLICTS") == 2


def test_each_conflict_carries_both_receipts(
    client: TestClient, vacate_notice: str, rent_agreement: str
) -> None:
    body = client.post(
        CROSS_CHECK, data={"notice_text": vacate_notice, "agreement_text": rent_agreement}
    ).json()
    for claim in body["claims"]:
        if claim["verdict"] == "CONFLICTS":
            assert claim["notice_receipt"]["found"] is True
            assert claim["agreement_receipt"]["found"] is True


def test_a_claim_absent_from_the_agreement_keeps_its_verdict(
    client: TestClient, vacate_notice: str, rent_agreement: str
) -> None:
    body = client.post(
        CROSS_CHECK, data={"notice_text": vacate_notice, "agreement_text": rent_agreement}
    ).json()
    absent = [c for c in body["claims"] if c["verdict"] == "NOT_IN_AGREEMENT"]
    assert absent
    assert absent[0]["agreement_receipt"] is None


def test_an_unconfirmed_agreement_quote_is_downgraded_to_unclear(
    settings: Settings, vacate_notice: str, rent_agreement: str
) -> None:
    fixture = load_fixture("cross_check_vacate")
    fixture["claims"][0]["agreement_quote"] = "No such words appear anywhere in this agreement"
    llm = FakeLLM({TASK_CROSS_CHECK: fixture})
    with build_client(settings, llm) as client:
        body = client.post(
            CROSS_CHECK, data={"notice_text": vacate_notice, "agreement_text": rent_agreement}
        ).json()
    first = body["claims"][0]
    assert first["verdict"] == "UNCLEAR"
    assert first["downgraded_from"] == "CONFLICTS"
    assert first["explanation"] == AGREEMENT_QUOTE_NOT_FOUND


def test_an_unconfirmed_notice_quote_is_downgraded_to_unclear(
    settings: Settings, vacate_notice: str, rent_agreement: str
) -> None:
    fixture = load_fixture("cross_check_vacate")
    fixture["claims"][0]["notice_quote"] = "Words that were never written in this notice at all"
    llm = FakeLLM({TASK_CROSS_CHECK: fixture})
    with build_client(settings, llm) as client:
        body = client.post(
            CROSS_CHECK, data={"notice_text": vacate_notice, "agreement_text": rent_agreement}
        ).json()
    first = body["claims"][0]
    assert first["verdict"] == "UNCLEAR"
    assert first["explanation"] == NOTICE_QUOTE_NOT_FOUND


def test_both_documents_reach_the_model_separately_delimited(
    settings: Settings, vacate_notice: str, rent_agreement: str
) -> None:
    llm = FakeLLM({TASK_CROSS_CHECK: load_fixture("cross_check_vacate")})
    with build_client(settings, llm) as client:
        client.post(
            CROSS_CHECK, data={"notice_text": vacate_notice, "agreement_text": rent_agreement}
        )
    prompt = llm.prompts[0]
    assert 'name="notice"' in prompt
    assert 'name="agreement"' in prompt
    assert prompt.count("</document>") == 2


def test_the_agreement_may_be_uploaded_as_a_file(
    client: TestClient, vacate_notice: str, rent_agreement: str
) -> None:
    response = client.post(
        CROSS_CHECK,
        data={"notice_text": vacate_notice},
        files={"file": ("agreement.txt", rent_agreement.encode(), "text/plain")},
    )
    assert response.status_code == 200


def test_a_missing_agreement_is_refused(client: TestClient, vacate_notice: str) -> None:
    response = client.post(CROSS_CHECK, data={"notice_text": vacate_notice})
    assert response.status_code == 400
    assert response.json()["type"] == "mohlat:no-document"


def test_a_missing_notice_is_a_validation_failure(client: TestClient, rent_agreement: str) -> None:
    response = client.post(CROSS_CHECK, data={"agreement_text": rent_agreement})
    assert response.status_code == 422
    assert response.json()["type"] == "mohlat:invalid-request"
