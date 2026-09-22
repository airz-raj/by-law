"""The port the model sits behind, and its Gemini implementation.

The rest of the app depends on :class:`LLMPort`, never on the SDK, so
tests run against a fake and no test touches the network. Output is
validated against a Pydantic schema; invalid output gets one repair
attempt naming the validation error, then fails loudly.

Logs record the task, model, latency and token counts. They never record
prompts, documents or model output.
"""

from __future__ import annotations

import asyncio
import time
from typing import Protocol

from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.errors import LLMOutputInvalid, LLMUnavailable
from app.observability import get_logger

TEMPERATURE = 0.2

REPAIR_INSTRUCTION = (
    "Your previous answer did not fit the schema. The validation error was:\n"
    "{error}\n"
    "Answer again. Return only JSON matching the schema, with every required "
    "field present and every quote copied exactly from the document."
)

logger = get_logger(__name__)


class LLMPort(Protocol):
    """One structured call to a language model."""

    async def generate[T: BaseModel](
        self,
        *,
        task: str,
        system: str,
        prompt: str,
        schema: type[T],
        max_output_tokens: int,
    ) -> T:
        """Return one instance of *schema* filled in by the model."""
        ...


class GeminiLLM:
    """A :class:`LLMPort` backed by Gemini through the ``google-genai`` SDK."""

    def __init__(self, settings: Settings) -> None:
        """Build the client for the configured backend.

        Args:
            settings: Chooses Vertex AI through the service identity or an
                AI Studio key, and supplies the model id and timeout.
        """
        self._settings = settings
        if settings.llm_backend == "vertex":
            self.client = genai.Client(
                vertexai=True,
                project=settings.gcp_project,
                location=settings.gcp_location,
            )
        else:
            self.client = genai.Client(api_key=settings.gemini_api_key)

    async def generate[T: BaseModel](
        self,
        *,
        task: str,
        system: str,
        prompt: str,
        schema: type[T],
        max_output_tokens: int,
    ) -> T:
        """Call the model and return validated output.

        Args:
            task: Task name used in logs and the cache key.
            system: The system instruction.
            prompt: The task prompt, documents already delimited.
            schema: The shape the answer must take.
            max_output_tokens: Cap on the answer's length.

        Returns:
            The validated answer.

        Raises:
            LLMUnavailable: The backend timed out, errored, or was unreachable.
            LLMOutputInvalid: The answer did not fit *schema*, twice.
        """
        attempt_prompt = prompt
        last_error: ValidationError | None = None

        for attempt in (1, 2):
            response = await self._call(
                task=task,
                system=system,
                prompt=attempt_prompt,
                schema=schema,
                max_output_tokens=max_output_tokens,
                attempt=attempt,
            )
            try:
                return self._validate(response.parsed, schema)
            except ValidationError as error:
                last_error = error
                attempt_prompt = f"{prompt}\n\n{REPAIR_INSTRUCTION.format(error=error)}"

        raise LLMOutputInvalid(f"model output did not fit {schema.__name__}: {last_error}")

    async def _call(
        self,
        *,
        task: str,
        system: str,
        prompt: str,
        schema: type[BaseModel],
        max_output_tokens: int,
        attempt: int,
    ) -> types.GenerateContentResponse:
        """Make one SDK call, turning every transport failure into LLMUnavailable."""
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=TEMPERATURE,
            max_output_tokens=max_output_tokens,
        )
        started = time.monotonic()
        try:
            response = await asyncio.wait_for(
                self.client.aio.models.generate_content(
                    model=self._settings.gemini_model,
                    contents=prompt,
                    config=config,
                ),
                timeout=self._settings.llm_timeout_seconds,
            )
        except TimeoutError as error:
            raise LLMUnavailable(f"the model did not answer {task} in time") from error
        except APIError as error:
            raise LLMUnavailable(f"the model backend refused {task}") from error
        except Exception as error:
            # The SDK raises httpx errors, which inherit from neither OSError
            # nor RuntimeError, so narrowing here would let a real outage
            # surface as an unhandled 500 instead of a 503.
            raise LLMUnavailable(f"the model backend was unreachable for {task}") from error

        self._log_usage(task=task, attempt=attempt, started=started, response=response)
        return response

    def _log_usage(
        self,
        *,
        task: str,
        attempt: int,
        started: float,
        response: types.GenerateContentResponse,
    ) -> None:
        """Record timing and token counts, never content."""
        usage = response.usage_metadata
        logger.info(
            "llm call",
            extra={
                "task": task,
                "model": self._settings.gemini_model,
                "attempt": attempt,
                "latency_ms": round((time.monotonic() - started) * 1000),
                "prompt_tokens": getattr(usage, "prompt_token_count", None),
                "output_tokens": getattr(usage, "candidates_token_count", None),
                "total_tokens": getattr(usage, "total_token_count", None),
            },
        )

    @staticmethod
    def _validate[T: BaseModel](parsed: object, schema: type[T]) -> T:
        """Coerce the SDK's parsed field into *schema*.

        Raises:
            ValidationError: The value is absent or does not fit the schema.
        """
        if isinstance(parsed, schema):
            return parsed
        if parsed is None:
            return schema.model_validate({})
        if isinstance(parsed, BaseModel):
            return schema.model_validate(parsed.model_dump())
        return schema.model_validate(parsed)
