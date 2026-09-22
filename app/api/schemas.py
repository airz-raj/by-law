"""API request and response schemas."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from app.core.models import DeadlineStatus, DeadlineBasis, ExplanationStep
from app.services.llm_schemas import OptionKind, DateKind, ClaimCategory, Verdict

class ReceiptSchema(BaseModel):
    quote: str
    found: bool
    start: int | None = None
    end: int | None = None
    reason: str | None = None

class DemandSchema(BaseModel):
    what: str
    amount_text: str | None
    receipt: ReceiptSchema

class CitedReferenceSchema(BaseModel):
    reference: str
    receipt: ReceiptSchema

class DateSchema(BaseModel):
    kind: DateKind
    label: str
    value: str | None
    receipt: ReceiptSchema

class DeadlineSchema(BaseModel):
    respond_by: str | None
    days_left: int | None
    status: DeadlineStatus
    basis: DeadlineBasis
    provisional: bool
    steps: list[ExplanationStep]

class OptionSchema(BaseModel):
    kind: OptionKind
    what_it_involves: str
    prepare: list[str]
    if_ignored: str

class ScreeningSchema(BaseModel):
    ai_directed: list[str]
    urgent: list[str]

class ClassificationSchema(BaseModel):
    label: str
    rule: str | None
    reason: str
    matched_terms: list[str]

class NoticeSourceSchema(BaseModel):
    text: str
    redactions: dict[str, int]

class DecodeReport(BaseModel):
    request_id: str
    disclaimer: str = "Information, not legal advice."
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
    plain_terms: list[dict[str, str]]
    screening: ScreeningSchema

class ClaimCheckSchema(BaseModel):
    claim: str
    category: ClaimCategory
    notice_quote: str
    agreement_quote: str | None
    verdict: Verdict
    explanation: str

class CrossCheckReport(BaseModel):
    request_id: str
    disclaimer: str = "Information, not legal advice."
    agreement_summary: str
    claims: list[ClaimCheckSchema]

class AnswerReport(BaseModel):
    request_id: str
    disclaimer: str = "Information, not legal advice."
    answer: str
    supported: bool
    quotes: list[str]

class Section12ClauseSchema(BaseModel):
    code: str

class EligibilityResult(BaseModel):
    request_id: str
    disclaimer: str = "Information, not legal advice."
    likely_eligible: bool
    matched: list[str]
    income_check_needed: bool
    next_steps: list[ExplanationStep]

class QuestionRequest(BaseModel):
    question: str = Field(max_length=500)
    documents: list[dict[str, str]]
    language: str

class LegalAidAnswers(BaseModel):
    sc_st: bool = False
    trafficking_victim: bool = False
    woman_or_child: bool = False
    disability: bool = False
    mass_disaster_victim: bool = False
    industrial_workman: bool = False
    in_custody: bool = False
    income_below_state_limit: str = "no"  # "yes", "no", "unsure"
