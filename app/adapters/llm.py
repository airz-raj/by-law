"""Adapter for Google Gemini LLM API via google-genai."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol, TypeVar

from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.errors import LLMOutputInvalid, LLMUnavailable

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class LLMPort(Protocol):
    async def generate(
        self,
        *,
        task: str,
        system: str,
        prompt: str,
        schema: type[T],
        max_output_tokens: int,
    ) -> T:
        ...


class GeminiLLM:
    """Implementation of LLMPort using Google Gemini."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if settings.llm_backend == "vertex":
            self.client = genai.Client(
                vertexai=True,
                project=settings.gcp_project,
                location=settings.gcp_location,
            )
        else:
            self.client = genai.Client(api_key=settings.gemini_api_key)

    async def generate(
        self,
        *,
        task: str,
        system: str,
        prompt: str,
        schema: type[T],
        max_output_tokens: int,
    ) -> T:
        return await self._generate_with_retry(
            task=task,
            system=system,
            prompt=prompt,
            schema=schema,
            max_output_tokens=max_output_tokens,
            is_retry=False,
        )

    async def _generate_with_retry(
        self,
        *,
        task: str,
        system: str,
        prompt: str,
        schema: type[T],
        max_output_tokens: int,
        is_retry: bool,
    ) -> T:
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.2,
            max_output_tokens=max_output_tokens,
        )

        try:
            response = await asyncio.wait_for(
                self.client.aio.models.generate_content(
                    model=self.settings.gemini_model,
                    contents=prompt,
                    config=config,
                ),
                timeout=self.settings.llm_timeout_seconds,
            )
        except asyncio.TimeoutError as e:
            raise LLMUnavailable("LLM request timed out.") from e
        except APIError as e:
            raise LLMUnavailable(f"LLM API error: {e.message}") from e
        except Exception as e:
            raise LLMUnavailable(f"Unexpected LLM error: {e}") from e

        # Log usage metadata (never the prompt or output)
        if response.usage_metadata:
            logger.info(
                "LLM call completed",
                extra={
                    "task": task,
                    "model": self.settings.gemini_model,
                    "prompt_tokens": response.usage_metadata.prompt_token_count,
                    "candidates_tokens": response.usage_metadata.candidates_token_count,
                    "total_tokens": response.usage_metadata.total_token_count,
                    "retry": is_retry,
                },
            )

        if response.parsed:
            if isinstance(response.parsed, dict):
                try:
                    return schema.model_validate(response.parsed)
                except ValidationError as e:
                    if not is_retry:
                        return await self._generate_with_retry(
                            task=task,
                            system=system,
                            prompt=f"{prompt}\n\n[SYSTEM: Your previous output failed validation. Fix these errors: {e}]",
                            schema=schema,
                            max_output_tokens=max_output_tokens,
                            is_retry=True,
                        )
                    raise LLMOutputInvalid(f"Validation failed after retry: {e}") from e
            if isinstance(response.parsed, schema):
                return response.parsed

        # If parsed is None or parsing failed and we reached here
        if not is_retry:
            return await self._generate_with_retry(
                task=task,
                system=system,
                prompt=f"{prompt}\n\n[SYSTEM: Your previous output was invalid JSON or did not match the schema. Please try again.]",
                schema=schema,
                max_output_tokens=max_output_tokens,
                is_retry=True,
            )

        raise LLMOutputInvalid("LLM failed to produce valid parsed output.")
