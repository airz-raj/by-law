"""Application errors and problem codes."""

from __future__ import annotations


class MohlatError(Exception):
    """Base class for all domain errors."""


class InputRejected(MohlatError):
    """The input file or text was rejected (e.g. too large, scanned PDF)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class LLMUnavailable(MohlatError):
    """The AI backend is unreachable, timed out, or returning 5xx."""


class LLMOutputInvalid(MohlatError):
    """The AI backend returned unparseable output after retries."""
