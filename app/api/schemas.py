"""Request and response models at the API boundary.

Core returns frozen dataclasses and enums; these models are the wire
shape. Every response carries the disclaimer, because information is all
Mohlat offers.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.core.models import (
    DeadlineBasis,
    DeadlineStatus,
    LegalAidStep,
    MatchReason,
    ReceiptReason,
    Section12Clause,
    StepCode,
)
from app.services.llm_schemas import ClaimCategory, DateKind, OptionKind, Verdict

DISCLAIMER = (
    "Mohlat explains documents and procedures. It is information, not legal advice, "
    "and does not create a lawyer-client relationship."
)

MAX_QUESTION_CHARS = 500
MAX_DOCUMENT_LABEL_CHARS = 60
MAX_DOCUMENT_CHARS = 60_000


class StepSchema(BaseModel):
    """A code and its parameters; the browser turns it into a sentence."""

    code: StepCode
    params: dict[str, str | int]


class ReceiptSchema(BaseModel):
    """Whether a quote was confirmed in the source, and where it sits."""

    quote: str
    found: bool
    start: int | None = None
    end: int | None = None
    reason: ReceiptReason | None = None


class DemandSchema(BaseModel):
    """A demand from the notice, with its receipt."""

    what: str
    amount_text: str | None
    receipt: ReceiptSchema


class CitedReferenceSchema(BaseModel):
    """A reference the notice relies on, with its receipt."""

    reference: str
    receipt: ReceiptSchema


class DateSchema(BaseModel):
    """A date found in the notice, resolved where possible."""

    kind: DateKind
    label: str
    value: date | None
    receipt: ReceiptSchema


class DeadlineSchema(BaseModel):
    """The respond-by date and the working behind it."""

    respond_by: date | None
    days_left: int | None
    status: DeadlineStatus
    basis: DeadlineBasis
    provisional: bool
    steps: list[StepSchema]


class OptionSchema(BaseModel):
    """One option open to the reader."""

    kind: OptionKind
    what_it_involves: str
    prepare: list[str]
    if_ignored: str


class PlainTermSchema(BaseModel):
    """A legal term and its one-sentence meaning."""

    term: str
    meaning: str


class ScreeningSchema(BaseModel):
    """Signal codes for AI-directed and urgent content."""

    ai_directed: list[str]
    urgent: list[str]


class RuleSourceSchema(BaseModel):
    """A citation for a rule."""

    label: str
    url: str


class RuleCardSchema(BaseModel):
    """What the rulebook says, in the requested language."""

    id: str
    title: str
    clock_starts: str
    period_days: int
    what_you_must_do: str
    what_can_happen_next: str
    your_rights: list[str]
    caveats: list[str]
    sources: list[RuleSourceSchema]
    last_reviewed: str


class ClassificationSchema(BaseModel):
    """The model's label, the matched rule, and why it matched or did not."""

    label: str
    rule: RuleCardSchema | None
    reason: MatchReason
    matched_terms: list[str]


class NoticeSourceSchema(BaseModel):
    """The masked notice text and how many identifiers were masked."""

    text: str
    redactions: dict[str, int]


class DecodeReport(BaseModel):
    """Everything the report page renders for one notice."""

    request_id: str
    disclaimer: str = DISCLAIMER
    notice: NoticeSourceSchema
    classification: ClassificationSchema
    summary: str
    sender_role: str
    recipient_role: str
    demands: list[DemandSchema]
    cited_references: list[CitedReferenceSchema]
    dates: list[DateSchema]
    deadline: DeadlineSchema
    options: list[OptionSchema]
    documents_to_gather: list[str]
    questions_for_lawyer: list[str]
    plain_terms: list[PlainTermSchema]
    screening: ScreeningSchema


class ClaimCheckSchema(BaseModel):
    """One claim checked against the agreement, with both receipts."""

    claim: str
    category: ClaimCategory
    verdict: Verdict
    explanation: str
    notice_receipt: ReceiptSchema
    agreement_receipt: ReceiptSchema | None
    downgraded_from: Verdict | None = None


class CrossCheckReport(BaseModel):
    """The comparison of a notice against the agreement behind it."""

    request_id: str
    disclaimer: str = DISCLAIMER
    agreement_summary: str
    claims: list[ClaimCheckSchema]


class AnswerReport(BaseModel):
    """An answer drawn from the user's documents, with its receipts."""

    request_id: str
    disclaimer: str = DISCLAIMER
    answer: str
    supported: bool
    unsupported_code: str | None = None
    receipts: list[ReceiptSchema]


class QuestionDocument(BaseModel):
    """One document to answer a question from."""

    label: str = Field(min_length=1, max_length=MAX_DOCUMENT_LABEL_CHARS)
    text: str = Field(min_length=1, max_length=MAX_DOCUMENT_CHARS)


class QuestionRequest(BaseModel):
    """A question and the one or two documents to answer it from."""

    question: str = Field(min_length=3, max_length=MAX_QUESTION_CHARS)
    documents: list[QuestionDocument] = Field(min_length=1, max_length=2)
    language: Literal["en", "hi"] = "en"


class LegalAidRequest(BaseModel):
    """Answers to the Section 12 categories."""

    sc_st: bool = False
    trafficking_begar: bool = False
    woman_or_child: bool = False
    disability: bool = False
    undeserved_want: bool = False
    industrial_workman: bool = False
    custody: bool = False
    income_below_state_limit: Literal["yes", "no", "unsure"] = "unsure"


class EligibilityReport(BaseModel):
    """The outcome of the Section 12 check."""

    request_id: str
    disclaimer: str = DISCLAIMER
    likely_eligible: bool
    matched: list[Section12Clause]
    income_check_needed: bool
    next_steps: list[LegalAidStep]


class HealthReport(BaseModel):
    """Liveness and the running version."""

    status: Literal["ok"] = "ok"
    version: str


class RulesReport(BaseModel):
    """The public rule cards.

    This is the most advice-shaped payload the API returns, so it carries
    the disclaimer like every other report.
    """

    disclaimer: str = DISCLAIMER
    rules: list[RuleCardSchema]
