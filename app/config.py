"""Application settings and limits from the environment."""

from __future__ import annotations
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration and hard limits."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_env: Literal["dev", "prod"] = "dev"
    trust_proxy: bool = False

    llm_backend: Literal["aistudio", "vertex"] = "aistudio"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
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
