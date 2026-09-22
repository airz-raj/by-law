"""Shared fixtures: settings, a frozen today, sample documents and a client."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import today as today_dependency
from app.config import Settings
from app.main import create_app
from tests.fakes import FakeLLM, load_fixture
from tests.paths import SAMPLES_ROOT

#: Every test that involves a date measures against this one.
TODAY = date(2026, 9, 22)

#: The day the sample notices say they were received.
SAMPLE_RECEIPT_DATE = date(2026, 9, 16)


@pytest.fixture
def settings() -> Settings:
    """Settings with a placeholder key, so no test reads the environment."""
    return Settings(
        llm_backend="aistudio",
        gemini_api_key="not-a-real-key",
        gemini_model="gemini-flash-test",
        app_env="dev",
        rate_limit_per_minute=10,
    )


@pytest.fixture
def today() -> date:
    """The frozen date every test measures against."""
    return TODAY


def read_sample(name: str) -> str:
    """Return the text of a sample document."""
    return (SAMPLES_ROOT / f"{name}.txt").read_text(encoding="utf-8")


@pytest.fixture
def cheque_notice() -> str:
    return read_sample("cheque-demand-notice")


@pytest.fixture
def bank_notice() -> str:
    return read_sample("bank-demand-notice")


@pytest.fixture
def vacate_notice() -> str:
    return read_sample("vacate-notice")


@pytest.fixture
def rent_agreement() -> str:
    return read_sample("rent-agreement")


@pytest.fixture
def llm() -> FakeLLM:
    """A fake model answering every task from the recorded fixtures."""
    return FakeLLM(
        {
            "decode": load_fixture("decode_cheque"),
            "cross_check": load_fixture("cross_check_vacate"),
            "ask": load_fixture("ask_supported"),
        }
    )


def build_client(settings: Settings, llm: Any, *, on: date = TODAY) -> TestClient:
    """Build a test client whose model is *llm* and whose today is fixed."""
    app = create_app(settings, llm=llm)
    app.dependency_overrides[today_dependency] = lambda: on
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client(settings: Settings, llm: FakeLLM) -> Iterator[TestClient]:
    """A client wired to the fake model, with today frozen."""
    with build_client(settings, llm) as test_client:
        yield test_client
