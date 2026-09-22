"""Contract tests for the Section 12 legal-aid check. No model call is made."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.fakes import FakeLLM

CHECK = "/api/v1/legal-aid/check"

CATEGORIES = (
    "sc_st",
    "trafficking_begar",
    "woman_or_child",
    "disability",
    "undeserved_want",
    "industrial_workman",
    "custody",
)


@pytest.mark.parametrize("category", CATEGORIES)
def test_each_category_on_its_own_is_enough(client: TestClient, category: str) -> None:
    body = client.post(CHECK, json={category: True, "income_below_state_limit": "no"}).json()
    assert body["likely_eligible"] is True
    assert len(body["matched"]) == 1


def test_no_category_means_no_indication_of_eligibility(client: TestClient) -> None:
    body = client.post(CHECK, json={"income_below_state_limit": "no"}).json()
    assert body["likely_eligible"] is False
    assert body["matched"] == []


def test_being_unsure_about_income_asks_for_the_state_limit(client: TestClient) -> None:
    body = client.post(CHECK, json={"income_below_state_limit": "unsure"}).json()
    assert body["income_check_needed"] is True
    assert "CHECK_STATE_INCOME_LIMIT" in body["next_steps"]


def test_income_below_the_limit_is_itself_a_category(client: TestClient) -> None:
    body = client.post(CHECK, json={"income_below_state_limit": "yes"}).json()
    assert body["likely_eligible"] is True
    assert "INCOME_BELOW_LIMIT" in body["matched"]
    assert body["income_check_needed"] is False


def test_several_categories_are_all_reported(client: TestClient) -> None:
    body = client.post(
        CHECK,
        json={"sc_st": True, "woman_or_child": True, "income_below_state_limit": "yes"},
    ).json()
    assert sorted(body["matched"]) == ["INCOME_BELOW_LIMIT", "SC_ST", "WOMAN_OR_CHILD"]


def test_every_answer_offers_the_authority_and_the_helpline(client: TestClient) -> None:
    body = client.post(CHECK, json={}).json()
    assert "CONTACT_DLSA" in body["next_steps"]
    assert "CALL_NALSA_15100" in body["next_steps"]


def test_every_answer_notes_that_a_prima_facie_case_is_still_required(
    client: TestClient,
) -> None:
    body = client.post(CHECK, json={}).json()
    assert "PRIMA_FACIE_REQUIRED" in body["next_steps"]


def test_the_check_never_calls_the_model(client: TestClient, llm: FakeLLM) -> None:
    client.post(CHECK, json={"woman_or_child": True})
    assert llm.calls == []


def test_an_unknown_income_answer_is_refused(client: TestClient) -> None:
    response = client.post(CHECK, json={"income_below_state_limit": "maybe"})
    assert response.status_code == 422
