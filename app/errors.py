"""The errors Mohlat raises, and the problem codes they map to.

Every error carries text that is safe to show a person: what happened and
what to do about it. Internals stay in the logs.
"""

from __future__ import annotations


class MohlatError(Exception):
    """Base class for every error this application raises deliberately."""


class InputRejected(MohlatError):
    """The document or the form input could not be accepted."""

    def __init__(self, code: str, detail: str) -> None:
        """Record a stable code and a sentence safe to show the user."""
        super().__init__(detail)
        self.code = code
        self.detail = detail


class RateLimitExceeded(MohlatError):
    """The caller has spent its allowance for the moment."""

    def __init__(self, retry_after_seconds: float) -> None:
        """Record how long the caller should wait."""
        super().__init__("too many requests")
        self.retry_after_seconds = retry_after_seconds


class LLMUnavailable(MohlatError):
    """The model backend timed out, refused the call, or was unreachable."""


class LLMOutputInvalid(MohlatError):
    """The model's answer did not fit its schema, even after one repair."""
