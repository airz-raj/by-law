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

#: Status codes that mean "this model cannot answer right now" rather than
#: "this request is wrong". Only these are worth trying another model for:
#: a retired id (404), a rate limit (429), or capacity trouble (5xx).
FAILOVER_STATUS = frozenset({404, 429, 500, 502, 503, 504})

TRUNCATED_INSTRUCTION = (
    "Your previous answer was cut off before it finished, so it was not valid "
    "JSON. Answer again, more briefly: keep every required field, but make the "
    "summary and the explanations shorter."
)

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
        #: The model that answered the most recent call, for diagnostics.
        self.last_model: str | None = None
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
            truncated = self._was_truncated(response)
            try:
                return self._validate(response.parsed, schema)
            except ValidationError as error:
                last_error = error
                instruction = (
                    TRUNCATED_INSTRUCTION if truncated else REPAIR_INSTRUCTION.format(error=error)
                )
                attempt_prompt = f"{prompt}\n\n{instruction}"
                if truncated:
                    logger.warning(
                        "model output was cut off",
                        extra={"task": task, "max_output_tokens": max_output_tokens},
                    )

        if truncated:
            raise LLMOutputInvalid(
                f"the model's answer was cut off at {max_output_tokens} output tokens, "
                "twice. Raise MAX_OUTPUT_TOKENS_DECODE, or shorten the document."
            )
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
        chain = self._settings.model_chain
        last: Exception | None = None

        for position, model in enumerate(chain):
            started = time.monotonic()
            try:
                response = await asyncio.wait_for(
                    self.client.aio.models.generate_content(
                        model=model, contents=prompt, config=config
                    ),
                    timeout=self._settings.llm_timeout_seconds,
                )
            except TimeoutError as error:
                last = error
                self._log_failover(task=task, model=model, reason="timeout")
            except APIError as error:
                last = error
                status = getattr(error, "code", None)
                if status not in FAILOVER_STATUS:
                    # A bad key or a malformed request fails the same way on
                    # every model, so trying the next one only wastes time.
                    raise LLMUnavailable(f"the model backend refused {task}") from error
                self._log_failover(task=task, model=model, reason=f"status_{status}")
            except Exception as error:
                # The SDK raises httpx errors, which inherit from neither
                # OSError nor RuntimeError, so narrowing here would let a real
                # outage surface as an unhandled 500 instead of a 503.
                last = error
                self._log_failover(task=task, model=model, reason="unreachable")
            else:
                self.last_model = model
                self._log_usage(
                    task=task, attempt=attempt, started=started, response=response, model=model
                )
                if position:
                    logger.warning(
                        "answered by a fallback model",
                        extra={"task": task, "model": model, "position": position},
                    )
                return response

        raise LLMUnavailable(f"no model could answer {task} ({len(chain)} tried)") from last

    def _log_failover(self, *, task: str, model: str, reason: str) -> None:
        """Record that a model could not answer, before trying the next."""
        logger.warning(
            "model could not answer", extra={"task": task, "model": model, "reason": reason}
        )

    def _log_usage(
        self,
        *,
        task: str,
        attempt: int,
        started: float,
        response: types.GenerateContentResponse,
        model: str,
    ) -> None:
        """Record timing and token counts, never content."""
        usage = response.usage_metadata
        logger.info(
            "llm call",
            extra={
                "task": task,
                "model": model,
                "attempt": attempt,
                "latency_ms": round((time.monotonic() - started) * 1000),
                "prompt_tokens": getattr(usage, "prompt_token_count", None),
                "output_tokens": getattr(usage, "candidates_token_count", None),
                "total_tokens": getattr(usage, "total_token_count", None),
            },
        )

    @staticmethod
    def _was_truncated(response: types.GenerateContentResponse) -> bool:
        """Whether the model ran out of output budget mid-answer.

        A truncated answer is invalid JSON, so it fails validation looking
        exactly like a schema mistake. The two need different fixes, so they
        are told apart here.
        """
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            reason = getattr(candidate, "finish_reason", None)
            if reason is not None and getattr(reason, "name", str(reason)) == "MAX_TOKENS":
                return True
        return False

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
