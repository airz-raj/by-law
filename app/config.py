"""Application settings and limits from the environment."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration and hard limits."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["dev", "prod"] = "dev"
    trust_proxy: bool = False
    # How many proxies sit in front of the app. The client address is that
    # many entries in from the right of X-Forwarded-For, because a caller
    # can write anything into the left of it.
    trusted_proxy_hops: int = 1
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    llm_backend: Literal["aistudio", "vertex"] = "aistudio"
    gemini_api_key: str | None = None
    # An alias that always resolves to the current Flash-tier model. A pinned
    # id was the default until gemini-2.0-flash was retired out from under the
    # project, which the app could only report as "the reading service is not
    # answering". Pin an exact id here or in .env when a build needs to be
    # reproducible.
    gemini_model: str = "gemini-flash-latest"

    # Tried in order when the model above is retired, overloaded or rate
    # limited. A comma-separated list; empty disables failover.
    gemini_fallback_models: str = "gemini-3.8-flash,gemini-2.5-flash"
    gcp_project: str | None = None
    gcp_location: str | None = None

    rate_limit_per_minute: int = 10
    cache_ttl_seconds: int = 900
    cache_max_entries: int = 128
    llm_timeout_seconds: float = 30.0

    max_upload_bytes: int = 5_000_000
    max_pdf_pages: int = 30
    max_document_chars: int = 60_000
    min_notice_chars: int = 80
    max_question_chars: int = 500

    max_demands: int = 6
    max_cited_references: int = 10
    max_dates: int = 10
    max_options: int = 5
    max_documents_to_gather: int = 6
    max_questions_for_lawyer: int = 6
    max_plain_terms: int = 6
    max_claims: int = 10
    max_grounded_quotes: int = 3

    max_output_tokens_decode: int = 4096
    max_output_tokens_cross_check: int = 4096
    max_output_tokens_ask: int = 1024

    @property
    def model_chain(self) -> tuple[str, ...]:
        """The models to try, in order, without repeats."""
        candidates = [self.gemini_model, *self.gemini_fallback_models.split(",")]
        seen: dict[str, None] = {}
        for candidate in candidates:
            name = candidate.strip()
            if name:
                seen.setdefault(name, None)
        return tuple(seen)

    @model_validator(mode="after")
    def _check_backend_is_configured(self) -> Self:
        """Fail at start-up, not mid-request, if the backend cannot be reached.

        Raises:
            ValueError: The chosen backend is missing what it needs.
        """
        if self.llm_backend == "aistudio" and not self.gemini_api_key:
            raise ValueError(
                "LLM_BACKEND=aistudio needs GEMINI_API_KEY. "
                "Copy .env.example to .env and add a key, or set LLM_BACKEND=vertex."
            )
        if self.llm_backend == "vertex" and not (self.gcp_project and self.gcp_location):
            raise ValueError("LLM_BACKEND=vertex needs GCP_PROJECT and GCP_LOCATION.")
        return self
