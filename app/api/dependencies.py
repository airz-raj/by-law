"""What the handlers are given.

The rulebook, cache, limiter and model client are built once per process,
held in one :class:`Services` value on ``app.state``, and handed to
handlers by FastAPI. A test can replace any of them without touching a
route.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Annotated, BinaryIO

from fastapi import Depends, Request

from app.adapters.cache import TTLCache
from app.adapters.extract import extract_text
from app.adapters.llm import GeminiLLM, LLMPort
from app.config import Settings
from app.core.models import Rulebook
from app.core.rulebook import load_rulebook
from app.security.rate_limit import RateLimiter

RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "rules_in.json"

SERVICES_STATE_KEY = "services"


@dataclass(frozen=True, slots=True)
class Services:
    """Everything a handler may need, built once for the process."""

    settings: Settings
    rulebook: Rulebook
    cache: TTLCache
    limiter: RateLimiter
    llm: LLMPort


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings."""
    return Settings()


def get_rulebook(path: Path = RULES_PATH) -> Rulebook:
    """Load the rulebook at *path*."""
    return load_rulebook(path)


def build_services(settings: Settings, llm: LLMPort | None = None) -> Services:
    """Assemble the services for one application.

    Args:
        settings: Configuration and limits.
        llm: A model client to use instead of the real one, for tests.

    Returns:
        The assembled services.
    """
    return Services(
        settings=settings,
        rulebook=get_rulebook(),
        cache=TTLCache(settings),
        limiter=RateLimiter(settings),
        llm=llm if llm is not None else GeminiLLM(settings),
    )


def extract_document(data: BinaryIO, settings: Settings) -> str:
    """Validate and extract text from an upload.

    The API package reaches adapters only through this module, so this
    thin pass-through is what the handlers call.
    """
    return extract_text(data, settings)


def services_of(request: Request) -> Services:
    """Return the services the running app was built with."""
    services = getattr(request.app.state, SERVICES_STATE_KEY)
    if not isinstance(services, Services):  # pragma: no cover - set by the factory
        raise RuntimeError("application services were not configured")
    return services


def today() -> date:
    """Return today's date in UTC.

    Core never reads the clock, so this is the single place a request gets
    it and the single thing a test overrides to fix the date.
    """
    return datetime.now(UTC).date()


ServicesDep = Annotated[Services, Depends(services_of)]
TodayDep = Annotated[date, Depends(today)]
