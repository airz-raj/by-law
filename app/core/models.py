"""Shared domain types for the core package.

Frozen dataclasses and StrEnums used across core modules.
No I/O, no framework imports, standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping


# ---------------------------------------------------------------------------
# Receipt: proof that a model-generated quote exists in the source text
# ---------------------------------------------------------------------------


class ReceiptReason(StrEnum):
    """Why a quote was not confirmed."""

    NOT_FOUND = "NOT_FOUND"
    TOO_SHORT = "TOO_SHORT"


@dataclass(frozen=True, slots=True)
class Receipt:
    """Result of locating a model-generated quote in the source text."""

    quote: str
    found: bool
    start: int | None = None
    end: int | None = None
    reason: ReceiptReason | None = None


# ---------------------------------------------------------------------------
# Deadline
# ---------------------------------------------------------------------------


class DeadlineStatus(StrEnum):
    """Whether the respond-by date has passed."""

    UPCOMING = "UPCOMING"
    DUE_TODAY = "DUE_TODAY"
    OVERDUE = "OVERDUE"
    UNKNOWN = "UNKNOWN"


class DeadlineBasis(StrEnum):
    """How the deadline was determined."""

    RULEBOOK = "RULEBOOK"
    STATED_IN_NOTICE = "STATED_IN_NOTICE"
    UNKNOWN = "UNKNOWN"


class StepCode(StrEnum):
    """Codes for deadline explanation steps.

    The server returns codes and parameters; the browser turns them
    into English or Hindi sentences through i18n.
    """

    RULE_MATCHED = "RULE_MATCHED"
    CLOCK_STARTS_RECEIPT = "CLOCK_STARTS_RECEIPT"
    CLOCK_STARTS_NOTICE_DATE = "CLOCK_STARTS_NOTICE_DATE"
    PERIOD_DAYS = "PERIOD_DAYS"
    EXCLUDE_FIRST_DAY = "EXCLUDE_FIRST_DAY"
    RESPOND_BY = "RESPOND_BY"
    DAYS_LEFT = "DAYS_LEFT"
    RECEIPT_DATE_MISSING = "RECEIPT_DATE_MISSING"
    NOTICE_ASKS_SOONER = "NOTICE_ASKS_SOONER"
    PLAN_FOR_EARLIER = "PLAN_FOR_EARLIER"
    STATED_PERIOD_USED = "STATED_PERIOD_USED"
    STATED_DATE_USED = "STATED_DATE_USED"
    NO_DEADLINE_FOUND = "NO_DEADLINE_FOUND"
    NO_HOLIDAY_ADJUSTMENT = "NO_HOLIDAY_ADJUSTMENT"
    OVERDUE_WARNING = "OVERDUE_WARNING"
    DUE_TODAY_WARNING = "DUE_TODAY_WARNING"


@dataclass(frozen=True, slots=True)
class ExplanationStep:
    """One step in the deadline explanation shown to the user."""

    code: StepCode
    params: Mapping[str, str | int]


@dataclass(frozen=True, slots=True)
class Deadline:
    """Computed respond-by date with explanation."""

    respond_by: "date | None"  # noqa: F821 — forward ref resolved at runtime
    days_left: int | None
    status: DeadlineStatus
    basis: DeadlineBasis
    provisional: bool
    steps: tuple[ExplanationStep, ...]


# ---------------------------------------------------------------------------
# Rulebook
# ---------------------------------------------------------------------------


class ClockStart(StrEnum):
    """When the deadline clock begins."""

    RECEIPT = "receipt"
    NOTICE_DATE = "notice_date"


class MatchReason(StrEnum):
    """Why a rule was or was not matched."""

    MATCHED = "MATCHED"
    MODEL_SAID_OTHER = "MODEL_SAID_OTHER"
    UNKNOWN_LABEL = "UNKNOWN_LABEL"
    TOO_FEW_TRIGGERS = "TOO_FEW_TRIGGERS"


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FoundDate:
    """A date found in free text with its position."""

    value: "date"  # noqa: F821
    start: int
    end: int
    raw: str


# ---------------------------------------------------------------------------
# Screening
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Screening:
    """Result of screening a document for injected instructions and urgency."""

    ai_directed: tuple[str, ...]
    urgent: tuple[str, ...]


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Redaction:
    """Result of masking personal identifiers."""

    text: str
    counts: Mapping[str, int]


# ---------------------------------------------------------------------------
# Legal aid
# ---------------------------------------------------------------------------


class Section12Clause(StrEnum):
    """Categories from Section 12 of the Legal Services Authorities Act, 1987."""

    SC_ST = "SC_ST"
    TRAFFICKING_BEGAR = "TRAFFICKING_BEGAR"
    WOMAN_OR_CHILD = "WOMAN_OR_CHILD"
    DISABILITY = "DISABILITY"
    UNDESERVED_WANT = "UNDESERVED_WANT"
    INDUSTRIAL_WORKMAN = "INDUSTRIAL_WORKMAN"
    CUSTODY = "CUSTODY"
    INCOME_BELOW_LIMIT = "INCOME_BELOW_LIMIT"


@dataclass(frozen=True, slots=True)
class EligibilityResult:
    """Result of checking Section 12 legal-aid eligibility."""

    likely_eligible: bool
    matched: tuple[Section12Clause, ...]
    income_check_needed: bool
    next_steps: tuple[StepCode | str, ...]
