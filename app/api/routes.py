"""The endpoints. Handlers validate, call the pipeline, and answer.

No logic lives here: the pipeline decides, core computes, and these
functions only move values between the wire and those layers.
"""

from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Annotated, BinaryIO, Literal

from fastapi import APIRouter, File, Form, Request, UploadFile

from app.api.dependencies import ServicesDep, TodayDep, extract_document
from app.api.schemas import (
    MAX_DOCUMENT_CHARS,
    AnswerReport,
    CrossCheckReport,
    DecodeReport,
    EligibilityReport,
    HealthReport,
    LegalAidRequest,
    QuestionRequest,
    RulesReport,
)
from app.core.legal_aid import LegalAidAnswers, check_eligibility
from app.core.models import Language
from app.errors import InputRejected
from app.observability import get_logger
from app.security.request_id import request_id_of
from app.services import pipeline
from app.services.prompts import ReadingLevel
from app.version import VERSION

router = APIRouter()
logger = get_logger(__name__)

CODE_NO_DOCUMENT = "NO_DOCUMENT"
CODE_BOTH_FILE_AND_TEXT = "BOTH_FILE_AND_TEXT"
CODE_RECEIPT_DATE_IN_FUTURE = "RECEIPT_DATE_IN_FUTURE"

DETAIL_NO_DOCUMENT = "Attach a file or paste the text of your notice."
DETAIL_BOTH = "Send either a file or pasted text, not both."
DETAIL_FUTURE_DATE = "The date you received the notice cannot be in the future."

LanguageForm = Annotated[Literal["en", "hi"], Form()]
ReadingLevelForm = Annotated[Literal["simple", "detailed"], Form()]


async def _document_text(
    *, file: UploadFile | None, text: str | None, services: ServicesDep
) -> str:
    """Return the document text from whichever input was supplied.

    Raises:
        InputRejected: Neither or both inputs were supplied, or the file
            could not be accepted.
    """
    has_file = file is not None and bool(file.filename)
    has_text = text is not None and bool(text.strip())

    if has_file and has_text:
        raise InputRejected(CODE_BOTH_FILE_AND_TEXT, DETAIL_BOTH)
    if has_file and file is not None:
        return extract_document(file.file, services.settings)
    if has_text and text is not None:
        return extract_document(_as_stream(text), services.settings)
    raise InputRejected(CODE_NO_DOCUMENT, DETAIL_NO_DOCUMENT)


def _as_stream(text: str) -> BinaryIO:
    """Wrap pasted text so it goes through the same validation as a file."""
    return BytesIO(text.encode("utf-8"))


def _check_receipt_date(receipt_date: date | None, today: date) -> date | None:
    """Reject a receipt date in the future.

    Raises:
        InputRejected: The date is after today.
    """
    if receipt_date is not None and receipt_date > today:
        raise InputRejected(CODE_RECEIPT_DATE_IN_FUTURE, DETAIL_FUTURE_DATE)
    return receipt_date


@router.get("/health", response_model=HealthReport, summary="Liveness and version")
async def health() -> HealthReport:
    """Report that the service is up, and which version is running."""
    return HealthReport(version=VERSION)


@router.get("/rules", response_model=RulesReport, summary="The published rulebook")
async def rules(services: ServicesDep, language: Literal["en", "hi"] = "en") -> RulesReport:
    """Return every rule with its statutory source and review date."""
    return RulesReport(rules=pipeline.rule_cards(services.rulebook, Language(language)))


@router.post(
    "/notices/decode",
    response_model=DecodeReport,
    summary="Read a notice and work out the respond-by date",
)
async def decode(
    request: Request,
    services: ServicesDep,
    today: TodayDep,
    language: LanguageForm = "en",
    reading_level: ReadingLevelForm = "simple",
    receipt_date: Annotated[date | None, Form()] = None,
    text: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> DecodeReport:
    """Read one notice and return its report."""
    document = await _document_text(file=file, text=text, services=services)
    report, cache_hit = await pipeline.decode_notice(
        text=document,
        receipt_date=_check_receipt_date(receipt_date, today),
        language=Language(language),
        reading_level=ReadingLevel(reading_level),
        llm=services.llm,
        cache=services.cache,
        rules=services.rulebook,
        today=today,
        settings=services.settings,
        request_id=request_id_of(request),
    )
    logger.info("decoded notice", extra={"cache_hit": cache_hit, "route": "decode"})
    return report


@router.post(
    "/notices/cross-check",
    response_model=CrossCheckReport,
    summary="Check a notice against the agreement it relies on",
)
async def cross_check(
    request: Request,
    services: ServicesDep,
    notice_text: Annotated[str, Form(min_length=1, max_length=MAX_DOCUMENT_CHARS)],
    language: LanguageForm = "en",
    agreement_text: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> CrossCheckReport:
    """Compare a notice with the agreement behind it."""
    agreement = await _document_text(file=file, text=agreement_text, services=services)
    report, cache_hit = await pipeline.cross_check(
        notice_text=notice_text,
        agreement_text=agreement,
        language=Language(language),
        llm=services.llm,
        cache=services.cache,
        settings=services.settings,
        request_id=request_id_of(request),
    )
    logger.info("cross-checked notice", extra={"cache_hit": cache_hit, "route": "cross_check"})
    return report


@router.post(
    "/questions",
    response_model=AnswerReport,
    summary="Answer a question from the supplied documents",
)
async def ask(request: Request, services: ServicesDep, body: QuestionRequest) -> AnswerReport:
    """Answer a question using only the documents supplied."""
    report, cache_hit = await pipeline.answer_question(
        question=body.question,
        documents=[(doc.label, doc.text) for doc in body.documents],
        language=Language(body.language),
        llm=services.llm,
        cache=services.cache,
        settings=services.settings,
        request_id=request_id_of(request),
    )
    logger.info("answered question", extra={"cache_hit": cache_hit, "route": "ask"})
    return report


@router.post(
    "/legal-aid/check",
    response_model=EligibilityReport,
    summary="Check the Section 12 free legal aid criteria",
)
async def legal_aid(request: Request, body: LegalAidRequest) -> EligibilityReport:
    """Check the Section 12 categories. This is a rule, not a model call."""
    result = check_eligibility(
        LegalAidAnswers(
            sc_st=body.sc_st,
            trafficking_begar=body.trafficking_begar,
            woman_or_child=body.woman_or_child,
            disability=body.disability,
            undeserved_want=body.undeserved_want,
            industrial_workman=body.industrial_workman,
            custody=body.custody,
            income_below_state_limit=body.income_below_state_limit,
        )
    )
    return EligibilityReport(
        request_id=request_id_of(request),
        likely_eligible=result.likely_eligible,
        matched=list(result.matched),
        income_check_needed=result.income_check_needed,
        next_steps=list(result.next_steps),
    )
