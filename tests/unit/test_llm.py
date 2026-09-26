"""Tests for the Gemini adapter. The SDK client is faked; nothing hits the network."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from pydantic import BaseModel

from app.adapters.llm import REPAIR_INSTRUCTION, GeminiLLM
from app.config import Settings
from app.errors import LLMOutputInvalid, LLMUnavailable


class Answer(BaseModel):
    """A minimal schema for adapter tests."""

    name: str


class FakeUsage:
    """Stand-in for the SDK's usage metadata."""

    prompt_token_count = 10
    candidates_token_count = 5
    total_token_count = 15


class FakeResponse:
    """Stand-in for the SDK's response object."""

    def __init__(self, parsed: object = None) -> None:
        self.parsed = parsed
        self.usage_metadata = FakeUsage()


GenerateFn = Callable[..., Awaitable[FakeResponse]]


class FakeModels:
    """Records the calls the adapter makes and returns scripted responses."""

    def __init__(self, generate: GenerateFn) -> None:
        self._generate = generate
        self.calls: list[dict[str, Any]] = []

    async def generate_content(self, *, model: str, contents: str, config: Any) -> FakeResponse:
        self.calls.append({"model": model, "contents": contents, "config": config})
        return await self._generate(model=model, contents=contents, config=config)


@pytest.fixture
def settings() -> Settings:
    """One model, so a test exercises the call rather than the chain."""
    return Settings(
        llm_backend="aistudio",
        gemini_api_key="not-a-real-key",
        gemini_model="gemini-flash-test",
        gemini_fallback_models="",
        llm_timeout_seconds=0.25,
    )


@pytest.fixture
def chained() -> Settings:
    """Three models, to exercise failover."""
    return Settings(
        llm_backend="aistudio",
        gemini_api_key="not-a-real-key",
        gemini_model="first-model",
        gemini_fallback_models="second-model, third-model",
        llm_timeout_seconds=0.25,
    )


class FakeAPIError(Exception):
    """Stands in for the SDK's APIError, which carries an HTTP code."""

    def __init__(self, code: int) -> None:
        super().__init__(f"status {code}")
        self.code = code


def build_llm(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, generate: GenerateFn
) -> tuple[GeminiLLM, FakeModels]:
    """Build an adapter whose SDK client is a fake."""
    models = FakeModels(generate)
    client = type("FakeClient", (), {"aio": type("Aio", (), {"models": models})()})()
    monkeypatch.setattr("google.genai.Client", lambda **_: client)
    return GeminiLLM(settings), models


async def call(llm: GeminiLLM) -> Answer:
    """Make one adapter call with fixed arguments."""
    return await llm.generate(
        task="decode",
        system="system text",
        prompt="prompt text",
        schema=Answer,
        max_output_tokens=100,
    )


async def test_valid_output_is_returned(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def generate(**_: Any) -> FakeResponse:
        return FakeResponse(parsed=Answer(name="Asha"))

    llm, models = build_llm(settings, monkeypatch, generate)
    assert (await call(llm)).name == "Asha"
    assert len(models.calls) == 1


async def test_a_dict_answer_is_validated_into_the_schema(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def generate(**_: Any) -> FakeResponse:
        return FakeResponse(parsed={"name": "Bhavna"})

    llm, _ = build_llm(settings, monkeypatch, generate)
    assert (await call(llm)).name == "Bhavna"


async def test_a_timeout_is_reported_as_unavailable(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def generate(**_: Any) -> FakeResponse:
        await asyncio.sleep(5)
        return FakeResponse()

    llm, _ = build_llm(settings, monkeypatch, generate)
    with pytest.raises(LLMUnavailable, match="no model could answer"):
        await call(llm)


async def test_a_backend_error_is_reported_as_unavailable(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("google.genai.errors.APIError", FakeAPIError)

    async def generate(**_: Any) -> FakeResponse:
        raise FakeAPIError(401)

    llm, _ = build_llm(settings, monkeypatch, generate)
    with pytest.raises(LLMUnavailable, match="refused"):
        await call(llm)


async def test_a_transport_error_is_reported_as_unavailable(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def generate(**_: Any) -> FakeResponse:
        raise OSError("connection reset")

    llm, _ = build_llm(settings, monkeypatch, generate)
    with pytest.raises(LLMUnavailable, match="no model could answer"):
        await call(llm)


async def test_invalid_output_is_repaired_on_the_second_attempt(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts = 0

    async def generate(**_: Any) -> FakeResponse:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return FakeResponse(parsed={"wrong_field": 1})
        return FakeResponse(parsed={"name": "Chetan"})

    llm, models = build_llm(settings, monkeypatch, generate)
    assert (await call(llm)).name == "Chetan"
    assert attempts == 2
    repair_opening = REPAIR_INSTRUCTION.split("\n", 1)[0]
    assert repair_opening in models.calls[1]["contents"]
    assert repair_opening not in models.calls[0]["contents"]


async def test_the_repair_attempt_names_the_validation_error(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def generate(**_: Any) -> FakeResponse:
        return FakeResponse(parsed={"wrong_field": 1})

    llm, models = build_llm(settings, monkeypatch, generate)
    with pytest.raises(LLMOutputInvalid):
        await call(llm)
    assert "name" in models.calls[1]["contents"]


async def test_output_that_stays_invalid_raises_after_one_repair(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts = 0

    async def generate(**_: Any) -> FakeResponse:
        nonlocal attempts
        attempts += 1
        return FakeResponse(parsed={"wrong_field": 1})

    llm, _ = build_llm(settings, monkeypatch, generate)
    with pytest.raises(LLMOutputInvalid, match="Answer"):
        await call(llm)
    assert attempts == 2


async def test_a_missing_answer_raises_after_one_repair(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts = 0

    async def generate(**_: Any) -> FakeResponse:
        nonlocal attempts
        attempts += 1
        return FakeResponse(parsed=None)

    llm, _ = build_llm(settings, monkeypatch, generate)
    with pytest.raises(LLMOutputInvalid):
        await call(llm)
    assert attempts == 2


async def test_the_schema_and_json_mime_type_are_sent(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def generate(**_: Any) -> FakeResponse:
        return FakeResponse(parsed=Answer(name="Divya"))

    llm, models = build_llm(settings, monkeypatch, generate)
    await call(llm)
    config = models.calls[0]["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema is Answer
    assert config.max_output_tokens == 100
    assert config.system_instruction == "system text"


async def test_the_configured_model_is_used(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def generate(**_: Any) -> FakeResponse:
        return FakeResponse(parsed=Answer(name="Esha"))

    llm, models = build_llm(settings, monkeypatch, generate)
    await call(llm)
    assert models.calls[0]["model"] == "gemini-flash-test"


def test_the_vertex_backend_uses_the_service_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("google.genai.Client", FakeClient)
    GeminiLLM(Settings(llm_backend="vertex", gcp_project="a-project", gcp_location="asia-south1"))
    assert captured["vertexai"] is True
    assert captured["project"] == "a-project"
    assert "api_key" not in captured


def test_the_aistudio_backend_uses_the_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("google.genai.Client", FakeClient)
    GeminiLLM(Settings(llm_backend="aistudio", gemini_api_key="not-a-real-key"))
    assert captured["api_key"] == "not-a-real-key"
    assert "vertexai" not in captured


# --- failover -------------------------------------------------------------
# gemini-2.0-flash was retired while this project was being built, and the
# only symptom was a generic outage message. A model that cannot answer
# should cost a fallback, not the product.


@pytest.mark.parametrize("status", [404, 429, 500, 502, 503, 504])
async def test_a_model_that_cannot_answer_costs_a_fallback(
    chained: Settings, monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    monkeypatch.setattr("google.genai.errors.APIError", FakeAPIError)
    tried: list[str] = []

    async def generate(*, model: str, **_: Any) -> FakeResponse:
        tried.append(model)
        if model == "first-model":
            raise FakeAPIError(status)
        return FakeResponse(parsed=Answer(name="Farah"))

    llm, _ = build_llm(chained, monkeypatch, generate)
    assert (await call(llm)).name == "Farah"
    assert tried == ["first-model", "second-model"]


@pytest.mark.parametrize("status", [400, 401, 403])
async def test_a_request_the_backend_rejects_is_not_retried_elsewhere(
    chained: Settings, monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    """A bad key or a malformed request fails the same way on every model."""
    monkeypatch.setattr("google.genai.errors.APIError", FakeAPIError)
    tried: list[str] = []

    async def generate(*, model: str, **_: Any) -> FakeResponse:
        tried.append(model)
        raise FakeAPIError(status)

    llm, _ = build_llm(chained, monkeypatch, generate)
    with pytest.raises(LLMUnavailable, match="refused"):
        await call(llm)
    assert tried == ["first-model"]


async def test_a_retired_primary_model_does_not_take_the_product_down(
    chained: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("google.genai.errors.APIError", FakeAPIError)

    async def generate(*, model: str, **_: Any) -> FakeResponse:
        if model in {"first-model", "second-model"}:
            raise FakeAPIError(404)
        return FakeResponse(parsed=Answer(name="Gita"))

    llm, _ = build_llm(chained, monkeypatch, generate)
    assert (await call(llm)).name == "Gita"


async def test_the_whole_chain_failing_is_reported_as_unavailable(
    chained: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("google.genai.errors.APIError", FakeAPIError)
    tried: list[str] = []

    async def generate(*, model: str, **_: Any) -> FakeResponse:
        tried.append(model)
        raise FakeAPIError(503)

    llm, _ = build_llm(chained, monkeypatch, generate)
    with pytest.raises(LLMUnavailable, match="3 tried"):
        await call(llm)
    assert tried == ["first-model", "second-model", "third-model"]


async def test_a_timeout_on_one_model_moves_to_the_next(
    chained: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def generate(*, model: str, **_: Any) -> FakeResponse:
        if model == "first-model":
            await asyncio.sleep(5)
        return FakeResponse(parsed=Answer(name="Hema"))

    llm, _ = build_llm(chained, monkeypatch, generate)
    assert (await call(llm)).name == "Hema"


async def test_the_first_model_is_preferred_when_it_answers(
    chained: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    tried: list[str] = []

    async def generate(*, model: str, **_: Any) -> FakeResponse:
        tried.append(model)
        return FakeResponse(parsed=Answer(name="Ira"))

    llm, _ = build_llm(chained, monkeypatch, generate)
    await call(llm)
    assert tried == ["first-model"]


def test_the_chain_drops_repeats_and_blanks() -> None:
    settings = Settings(gemini_api_key="x", gemini_model="a", gemini_fallback_models=" b , a ,, c ")
    assert settings.model_chain == ("a", "b", "c")


def test_failover_can_be_turned_off() -> None:
    settings = Settings(gemini_api_key="x", gemini_model="a", gemini_fallback_models="")
    assert settings.model_chain == ("a",)


# --- truncation -----------------------------------------------------------
# A cut-off answer is invalid JSON, so it fails validation looking exactly
# like a schema mistake. The two need different fixes, so they are told
# apart and reported differently.


class Candidate:
    """Stands in for one SDK candidate, carrying a finish reason."""

    def __init__(self, reason: str) -> None:
        self.finish_reason = type("Reason", (), {"name": reason})()


def truncated_response() -> FakeResponse:
    """A response the model ran out of output budget on."""
    response = FakeResponse(parsed={"wrong_field": 1})
    response.candidates = [Candidate("MAX_TOKENS")]  # type: ignore[attr-defined]
    return response


async def test_a_cut_off_answer_is_reported_as_cut_off(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def generate(**_: Any) -> FakeResponse:
        return truncated_response()

    llm, _ = build_llm(settings, monkeypatch, generate)
    with pytest.raises(LLMOutputInvalid, match="cut off"):
        await call(llm)


async def test_a_cut_off_answer_names_the_budget_that_ran_out(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def generate(**_: Any) -> FakeResponse:
        return truncated_response()

    llm, _ = build_llm(settings, monkeypatch, generate)
    with pytest.raises(LLMOutputInvalid, match="100 output tokens"):
        await call(llm)


async def test_a_cut_off_answer_is_asked_to_be_shorter_not_corrected(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Naming a validation error is useless advice when nothing was wrong
    with the shape; the answer simply did not finish."""

    async def generate(**_: Any) -> FakeResponse:
        return truncated_response()

    llm, models = build_llm(settings, monkeypatch, generate)
    with pytest.raises(LLMOutputInvalid):
        await call(llm)
    second = models.calls[1]["contents"]
    assert "cut off" in second
    assert "shorter" in second
    assert "did not fit the schema" not in second


async def test_a_cut_off_first_answer_can_still_be_repaired(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts = 0

    async def generate(**_: Any) -> FakeResponse:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return truncated_response()
        return FakeResponse(parsed={"name": "Jaya"})

    llm, _ = build_llm(settings, monkeypatch, generate)
    assert (await call(llm)).name == "Jaya"


async def test_an_answer_that_finished_is_not_called_cut_off(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def generate(**_: Any) -> FakeResponse:
        response = FakeResponse(parsed={"wrong_field": 1})
        response.candidates = [Candidate("STOP")]  # type: ignore[attr-defined]
        return response

    llm, _ = build_llm(settings, monkeypatch, generate)
    with pytest.raises(LLMOutputInvalid, match="did not fit"):
        await call(llm)


def test_the_output_budget_leaves_room_for_reasoning_tokens() -> None:
    """The newer models spend thinking tokens from the same budget, so a
    cap that only just fits the answer truncates it."""
    settings = Settings(gemini_api_key="x")
    assert settings.max_output_tokens_decode >= 8192
    assert settings.max_output_tokens_cross_check >= 8192
