"""Schemas the model must fill.

Every field the model returns is declared here, so an answer that does not
fit the shape is rejected before it reaches the pipeline. Quotes are
constrained in length because a quote is only useful if it can be found
word for word in the source document.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

QUOTE_MIN_LENGTH = 12
QUOTE_MAX_LENGTH = 200


class OptionKind(StrEnum):
    """The kinds of option Mohlat will describe. It never ranks them."""

    COMPLY = "COMPLY"
    REPLY_IN_WRITING = "REPLY_IN_WRITING"
    NEGOTIATE = "NEGOTIATE"
    DISPUTE_WITH_HELP = "DISPUTE_WITH_HELP"
    FREE_LEGAL_AID = "FREE_LEGAL_AID"


class DateKind(StrEnum):
    """What a date in the notice refers to."""

    NOTICE_DATE = "NOTICE_DATE"
    DUE_DATE = "DUE_DATE"
    EVENT_DATE = "EVENT_DATE"
    OTHER = "OTHER"


class Verdict(StrEnum):
    """How a claim in the notice stands against the agreement."""

    CONSISTENT = "CONSISTENT"
    CONFLICTS = "CONFLICTS"
    NOT_IN_AGREEMENT = "NOT_IN_AGREEMENT"
    UNCLEAR = "UNCLEAR"


class ClaimCategory(StrEnum):
    """What kind of thing a claim asserts."""

    AMOUNT = "AMOUNT"
    PERIOD = "PERIOD"
    CLAUSE = "CLAUSE"
    DATE = "DATE"
    OBLIGATION = "OBLIGATION"
    OTHER = "OTHER"


Quote = Field(min_length=QUOTE_MIN_LENGTH, max_length=QUOTE_MAX_LENGTH)
OptionalQuote = Field(default=None, min_length=QUOTE_MIN_LENGTH, max_length=QUOTE_MAX_LENGTH)


class Demand(BaseModel):
    """Something the sender asks the recipient to do or pay."""

    what: str = Field(max_length=300)
    amount_text: str | None = Field(default=None, max_length=60)
    quote: str = Quote


class CitedReference(BaseModel):
    """A law, section, clause or earlier letter the notice relies on."""

    reference: str = Field(max_length=200)
    quote: str = Quote


class DateMention(BaseModel):
    """A date written in the notice, with what it refers to."""

    kind: DateKind
    label: str = Field(max_length=200)
    quote: str = Quote


class StatedDeadline(BaseModel):
    """The period or cut-off date the notice sets for itself."""

    period_days: int | None = Field(default=None, ge=1, le=3650)
    by_date_quote: str | None = OptionalQuote
    quote: str | None = OptionalQuote


class OptionItem(BaseModel):
    """One course of action open to the recipient."""

    kind: OptionKind
    what_it_involves: str = Field(max_length=600)
    prepare: list[str] = Field(default_factory=list, max_length=8)
    if_ignored: str = Field(max_length=600)


class PlainTerm(BaseModel):
    """A legal term from the notice, explained in one sentence."""

    term: str = Field(max_length=120)
    meaning: str = Field(max_length=400)


class NoticeExtraction(BaseModel):
    """Everything the model reads out of a single notice."""

    notice_label: str = Field(max_length=80)
    summary: str = Field(max_length=3000)
    sender_role: str = Field(max_length=160)
    recipient_role: str = Field(max_length=160)
    demands: list[Demand] = Field(default_factory=list)
    cited_references: list[CitedReference] = Field(default_factory=list)
    dates: list[DateMention] = Field(default_factory=list)
    stated_deadline: StatedDeadline = Field(default_factory=StatedDeadline)
    options: list[OptionItem] = Field(default_factory=list)
    documents_to_gather: list[str] = Field(default_factory=list)
    questions_for_lawyer: list[str] = Field(default_factory=list)
    plain_terms: list[PlainTerm] = Field(default_factory=list)


class ClaimCheck(BaseModel):
    """One claim in the notice, checked against the agreement."""

    claim: str = Field(max_length=400)
    category: ClaimCategory
    notice_quote: str = Quote
    agreement_quote: str | None = OptionalQuote
    verdict: Verdict
    explanation: str = Field(max_length=800)


class CrossCheckExtraction(BaseModel):
    """The model's comparison of a notice against the agreement behind it."""

    agreement_summary: str = Field(max_length=2000)
    claims: list[ClaimCheck] = Field(default_factory=list)


class GroundedAnswer(BaseModel):
    """An answer drawn only from the documents the user supplied."""

    answer: str = Field(max_length=2000)
    supported: bool
    quotes: list[str] = Field(default_factory=list)
