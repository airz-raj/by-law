import asyncio
import pytest
from pydantic import BaseModel
from google.genai.errors import APIError

from app.adapters.llm import GeminiLLM
from app.config import Settings
from app.errors import LLMUnavailable, LLMOutputInvalid

class DummySchema(BaseModel):
    name: str

@pytest.fixture
def settings():
    return Settings(
        llm_backend="aistudio",
        gemini_api_key="fake-key",
        gemini_model="gemini-2.0-flash",
        llm_timeout_seconds=1.0,
    )

class MockUsage:
    prompt_token_count = 10
    candidates_token_count = 5
    total_token_count = 15

class MockResponse:
    def __init__(self, parsed=None):
        self.parsed = parsed
        self.usage_metadata = MockUsage()

class MockClient:
    def __init__(self, mock_aio):
        self.aio = mock_aio

class MockAio:
    def __init__(self, mock_models):
        self.models = mock_models

class MockModels:
    def __init__(self, generate_content_coro):
        self._generate_content = generate_content_coro

    async def generate_content(self, model, contents, config):
        return await self._generate_content(model, contents, config)

def get_llm(settings, monkeypatch, generate_content_coro):
    models = MockModels(generate_content_coro)
    aio = MockAio(models)
    client = MockClient(aio)
    monkeypatch.setattr("google.genai.Client", lambda **kwargs: client)
    return GeminiLLM(settings)

@pytest.mark.asyncio
async def test_llm_success(settings, monkeypatch):
    async def mock_generate(*args, **kwargs):
        return MockResponse(parsed=DummySchema(name="John Doe"))
    
    llm = get_llm(settings, monkeypatch, mock_generate)
    res = await llm.generate(
        task="test",
        system="sys",
        prompt="hello",
        schema=DummySchema,
        max_output_tokens=100
    )
    assert isinstance(res, DummySchema)
    assert res.name == "John Doe"

@pytest.mark.asyncio
async def test_llm_timeout(settings, monkeypatch):
    async def mock_generate(*args, **kwargs):
        await asyncio.sleep(2.0)
        return MockResponse()
    
    llm = get_llm(settings, monkeypatch, mock_generate)
    with pytest.raises(LLMUnavailable) as exc:
        await llm.generate(
            task="test",
            system="sys",
            prompt="hello",
            schema=DummySchema,
            max_output_tokens=100
        )
    assert "timed out" in str(exc.value).lower()

@pytest.mark.asyncio
async def test_llm_api_error(settings, monkeypatch):
    class FakeAPIError(Exception):
        message = "Bad request"
    monkeypatch.setattr("app.adapters.llm.APIError", FakeAPIError)

    async def mock_generate(*args, **kwargs):
        raise FakeAPIError()
    
    llm = get_llm(settings, monkeypatch, mock_generate)
    with pytest.raises(LLMUnavailable) as exc:
        await llm.generate(
            task="test",
            system="sys",
            prompt="hello",
            schema=DummySchema,
            max_output_tokens=100
        )
    assert "Bad request" in str(exc.value)

@pytest.mark.asyncio
async def test_llm_validation_retry_success(settings, monkeypatch):
    call_count = 0
    async def mock_generate(model, contents, config):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First time returns dict missing 'name'
            return MockResponse(parsed={"wrong": 123})
        # Second time succeeds
        assert "SYSTEM: Your previous output failed validation" in contents
        return MockResponse(parsed=DummySchema(name="Jane"))

    llm = get_llm(settings, monkeypatch, mock_generate)
    res = await llm.generate(
        task="test",
        system="sys",
        prompt="hello",
        schema=DummySchema,
        max_output_tokens=100
    )
    assert call_count == 2
    assert res.name == "Jane"

@pytest.mark.asyncio
async def test_llm_validation_retry_failure(settings, monkeypatch):
    call_count = 0
    async def mock_generate(model, contents, config):
        nonlocal call_count
        call_count += 1
        return MockResponse(parsed={"wrong": 123})

    llm = get_llm(settings, monkeypatch, mock_generate)
    with pytest.raises(LLMOutputInvalid):
        await llm.generate(
            task="test",
            system="sys",
            prompt="hello",
            schema=DummySchema,
            max_output_tokens=100
        )
    assert call_count == 2

@pytest.mark.asyncio
async def test_llm_parsed_none_retry(settings, monkeypatch):
    call_count = 0
    async def mock_generate(model, contents, config):
        nonlocal call_count
        call_count += 1
        return MockResponse(parsed=None)

    llm = get_llm(settings, monkeypatch, mock_generate)
    with pytest.raises(LLMOutputInvalid):
        await llm.generate(
            task="test",
            system="sys",
            prompt="hello",
            schema=DummySchema,
            max_output_tokens=100
        )
    assert call_count == 2

@pytest.mark.asyncio
async def test_llm_vertex_init(settings, monkeypatch):
    settings.llm_backend = "vertex"
    settings.gcp_project = "proj"
    settings.gcp_location = "loc"
    
    class MockClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
    
    monkeypatch.setattr("google.genai.Client", MockClient)
    llm = GeminiLLM(settings)
    assert getattr(llm.client, "kwargs", {}).get("vertexai") is True
