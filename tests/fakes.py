"""Fakes used across the test suite. No test touches the network."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.errors import LLMOutputInvalid, LLMUnavailable
from tests.paths import LLM_FIXTURES


class FakeLLM:
    """A model port that replays recorded answers and records its calls.

    Answers are keyed by task name. A task may be given a list, in which
    case successive calls take the next answer, so a test can script a
    failure followed by a success.
    """

    def __init__(
        self,
        answers: Mapping[str, Any] | None = None,
        *,
        raises: Exception | None = None,
    ) -> None:
        """Build a fake.

        Args:
            answers: Raw answers per task name, as dicts or lists of dicts.
            raises: An error to raise instead of answering.
        """
        self._answers: dict[str, list[Any]] = {
            task: list(value) if isinstance(value, list) else [value]
            for task, value in (answers or {}).items()
        }
        self._raises = raises
        self.calls: list[dict[str, Any]] = []

    @property
    def prompts(self) -> list[str]:
        """Every prompt this fake was given, in order."""
        return [call["prompt"] for call in self.calls]

    @property
    def systems(self) -> list[str]:
        """Every system instruction this fake was given, in order."""
        return [call["system"] for call in self.calls]

    async def generate[T: BaseModel](
        self,
        *,
        task: str,
        system: str,
        prompt: str,
        schema: type[T],
        max_output_tokens: int,
    ) -> T:
        """Return the next scripted answer for *task*."""
        self.calls.append(
            {
                "task": task,
                "system": system,
                "prompt": prompt,
                "schema": schema.__name__,
                "max_output_tokens": max_output_tokens,
            }
        )
        if self._raises is not None:
            raise self._raises

        queued = self._answers.get(task)
        if not queued:
            raise LLMOutputInvalid(f"the fake has no answer for {task}")
        raw = queued.pop(0) if len(queued) > 1 else queued[0]
        return schema.model_validate(raw)


class UnavailableLLM:
    """A model port that is always down."""

    async def generate[T: BaseModel](
        self,
        *,
        task: str,
        system: str,
        prompt: str,
        schema: type[T],
        max_output_tokens: int,
    ) -> T:
        """Always fail."""
        raise LLMUnavailable("the fake backend is down")


def load_fixture(name: str) -> dict[str, Any]:
    """Load a recorded model answer from ``tests/fixtures/llm``."""
    path: Path = LLM_FIXTURES / f"{name}.json"
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):  # pragma: no cover - fixtures are objects
        raise TypeError(f"fixture {name} is not an object")
    return loaded
