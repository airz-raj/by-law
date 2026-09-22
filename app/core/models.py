"""Shared domain types for the core package.

Frozen dataclasses and StrEnums used across core modules.
No I/O, no framework imports, standard library only.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

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

    respond_by: date | None
    days_left: int | None
    status: DeadlineStatus
    basis: DeadlineBasis
    provisional: bool
    steps: tuple[ExplanationStep, ...]


# ---------------------------------------------------------------------------
# Rulebook
# ---------------------------------------------------------------------------


class Language(StrEnum):
    """Languages the explanations can be written in."""

    EN = "en"
    HI = "hi"


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


@dataclass(frozen=True, slots=True)
class LocalisedText:
    """A string held in both supported languages."""

    en: str
    hi: str

    def into(self, language: Language) -> str:
        """Return the text in *language*."""
        return self.hi if language is Language.HI else self.en


@dataclass(frozen=True, slots=True)
class RuleSource:
    """A citation for a rule, with the URL that was checked."""

    label: str
    url: str


@dataclass(frozen=True, slots=True)
class Rule:
    """One statutory rule: a period, its anchor, and what the law provides."""

    id: str
    title: LocalisedText
    clock_starts: ClockStart
    period_days: int
    what_you_must_do: LocalisedText
    what_can_happen_next: LocalisedText
    your_rights: tuple[LocalisedText, ...]
    trigger_terms: tuple[str, ...]
    min_trigger_hits: int
    sources: tuple[RuleSource, ...]
    caveats: tuple[LocalisedText, ...]
    last_reviewed: str


@dataclass(frozen=True, slots=True)
class Rulebook:
    """The loaded set of rules for one jurisdiction."""

    rules: tuple[Rule, ...]

    def get(self, rule_id: str) -> Rule | None:
        """Return the rule with *rule_id*, or None if there is no such rule."""
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None

    def ids(self) -> tuple[str, ...]:
        """Return every rule id, in file order."""
        return tuple(rule.id for rule in self.rules)


@dataclass(frozen=True, slots=True)
class RuleMatch:
    """The outcome of matching a notice against the rulebook."""

    rule: Rule | None
    reason: MatchReason
    matched_terms: tuple[str, ...]


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FoundDate:
    """A date found in free text with its position."""

    value: date
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


class LegalAidStep(StrEnum):
    """Next steps offered after a Section 12 eligibility check."""

    CONTACT_DLSA = "CONTACT_DLSA"
    CALL_NALSA_15100 = "CALL_NALSA_15100"
    PRIMA_FACIE_REQUIRED = "PRIMA_FACIE_REQUIRED"
    CHECK_STATE_INCOME_LIMIT = "CHECK_STATE_INCOME_LIMIT"


@dataclass(frozen=True, slots=True)
class EligibilityResult:
    """Result of checking Section 12 legal-aid eligibility."""

    likely_eligible: bool
    matched: tuple[Section12Clause, ...]
    income_check_needed: bool
    next_steps: tuple[LegalAidStep, ...]
