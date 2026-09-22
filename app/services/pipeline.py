"""The pipeline: mask, screen, ask the model once, then decide in code.

The model reads; the code decides. Deadlines come from the rulebook and
:mod:`app.core.deadlines`, never from the model's arithmetic, and every
quote the model returns is confirmed against the masked source before it
is shown as fact.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from datetime import date

from app.adapters.cache import TTLCache
from app.adapters.llm import LLMPort
from app.api.schemas import (
    AnswerReport,
    CitedReferenceSchema,
    ClaimCheckSchema,
    ClassificationSchema,
    CrossCheckReport,
    DateSchema,
    DeadlineSchema,
    DecodeReport,
    DemandSchema,
    NoticeSourceSchema,
    OptionSchema,
    PlainTermSchema,
    ReceiptSchema,
    RuleCardSchema,
    RuleSourceSchema,
    ScreeningSchema,
    StepSchema,
)
from app.config import Settings
from app.core import dates, deadlines, evidence, redaction, rulebook, screening
from app.core.models import Language, Receipt, Rule, Rulebook
from app.services import prompts
from app.services.llm_schemas import (
    ClaimCheck,
    CrossCheckExtraction,
    DateKind,
    GroundedAnswer,
    NoticeExtraction,
    Verdict,
)
from app.services.prompts import ReadingLevel

logger = logging.getLogger(__name__)

TASK_DECODE = "decode"
TASK_CROSS_CHECK = "cross_check"
TASK_ASK = "ask"

#: Returned instead of the model's words when no quote could be confirmed.
UNSUPPORTED_ANSWER_CODE = "ANSWER_NOT_IN_DOCUMENTS"

#: Why a cross-check verdict was downgraded to UNCLEAR.
NOTICE_QUOTE_NOT_FOUND = "NOTICE_QUOTE_NOT_FOUND"
AGREEMENT_QUOTE_NOT_FOUND = "AGREEMENT_QUOTE_NOT_FOUND"


def _receipt_schema(receipt: Receipt) -> ReceiptSchema:
    """Convert a core Receipt to its wire shape."""
    return ReceiptSchema(
        quote=receipt.quote,
        found=receipt.found,
        start=receipt.start,
        end=receipt.end,
        reason=receipt.reason,
    )


def _rule_card(rule: Rule, language: Language) -> RuleCardSchema:
    """Render a rule for the report in the requested language."""
    return RuleCardSchema(
        id=rule.id,
        title=rule.title.into(language),
        clock_starts=rule.clock_starts.value,
        period_days=rule.period_days,
        what_you_must_do=rule.what_you_must_do.into(language),
        what_can_happen_next=rule.what_can_happen_next.into(language),
        your_rights=[text.into(language) for text in rule.your_rights],
        caveats=[text.into(language) for text in rule.caveats],
        sources=[RuleSourceSchema(label=s.label, url=s.url) for s in rule.sources],
        last_reviewed=rule.last_reviewed,
    )


def rule_cards(rules: Rulebook, language: Language) -> list[RuleCardSchema]:
    """Render every rule for the public rules endpoint."""
    return [_rule_card(rule, language) for rule in rules.rules]


def _first_date_in(quote: str) -> date | None:
    """Return the first date written inside *quote*, if there is one."""
    found = dates.find_dates(quote)
    return found[0].value if found else None


async def _generate[T: (NoticeExtraction, CrossCheckExtraction, GroundedAnswer)](
    *,
    llm: LLMPort,
    cache: TTLCache,
    settings: Settings,
    task: str,
    texts: tuple[str, ...],
    options: Mapping[str, str | int | None],
    system: str,
    prompt: str,
    schema: type[T],
    max_output_tokens: int,
) -> tuple[T, bool]:
    """Return validated model output for one task, from cache when possible.

    Returns:
        The validated output and whether it came from the cache.
    """
    key = TTLCache.key(
        prompt_version=prompts.PROMPT_VERSION,
        model=settings.gemini_model,
        task=task,
        texts=texts,
        options=options,
    )
    cached = cache.get(key)
    if cached is not None:
        return schema.model_validate(cached), True

    result = await llm.generate(
        task=task,
        system=system,
        prompt=prompt,
        schema=schema,
        max_output_tokens=max_output_tokens,
    )
    cache.set(key, result.model_dump(mode="json"))
    return result, False


def _decode_demands(extraction: NoticeExtraction, source: str, limit: int) -> list[DemandSchema]:
    """Confirm each demand's quote against the masked source."""
    return [
        DemandSchema(
            what=demand.what,
            amount_text=demand.amount_text,
            receipt=_receipt_schema(evidence.locate(demand.quote, source)),
        )
        for demand in extraction.demands[:limit]
    ]


def _decode_references(
    extraction: NoticeExtraction, source: str, limit: int
) -> list[CitedReferenceSchema]:
    """Confirm each cited reference's quote against the masked source."""
    return [
        CitedReferenceSchema(
            reference=reference.reference,
            receipt=_receipt_schema(evidence.locate(reference.quote, source)),
        )
        for reference in extraction.cited_references[:limit]
    ]


def _decode_dates(
    extraction: NoticeExtraction, source: str, limit: int
) -> tuple[list[DateSchema], date | None]:
    """Confirm and resolve every date, and pick the notice date.

    The notice date is the first confirmed ``NOTICE_DATE`` mention, so an
    unconfirmed quote can never set the clock.
    """
    resolved: list[DateSchema] = []
    notice_date: date | None = None
    for mention in extraction.dates[:limit]:
        receipt = evidence.locate(mention.quote, source)
        value = _first_date_in(mention.quote) if receipt.found else None
        if value is not None and mention.kind is DateKind.NOTICE_DATE and notice_date is None:
            notice_date = value
        resolved.append(
            DateSchema(
                kind=mention.kind,
                label=mention.label,
                value=value,
                receipt=_receipt_schema(receipt),
            )
        )
    return resolved, notice_date


def _stated_by_date(extraction: NoticeExtraction, source: str) -> date | None:
    """Resolve the cut-off date the notice states, if its quote is confirmed."""
    quote = extraction.stated_deadline.by_date_quote
    if quote is None:
        return None
    if not evidence.locate(quote, source).found:
        return None
    return _first_date_in(quote)


async def decode_notice(
    *,
    text: str,
    receipt_date: date | None,
    language: Language,
    reading_level: ReadingLevel,
    llm: LLMPort,
    cache: TTLCache,
    rules: Rulebook,
    today: date,
    settings: Settings,
    request_id: str,
) -> tuple[DecodeReport, bool]:
    """Read one notice and build its report.

    Args:
        text: The notice text as supplied, unmasked.
        receipt_date: The day the user says they received it, if given.
        language: The language to explain in.
        reading_level: How much detail the summary should carry.
        llm: The model port.
        cache: The result cache.
        rules: The loaded rulebook.
        today: The date to measure the deadline against.
        settings: Limits and the model id.
        request_id: The id echoed back to the caller.

    Returns:
        The report and whether the model output came from the cache.
    """
    masked = redaction.redact(text)
    signals = screening.screen(masked.text)
    safe_text = screening.neutralise_delimiters(masked.text)

    extraction, cache_hit = await _generate(
        llm=llm,
        cache=cache,
        settings=settings,
        task=TASK_DECODE,
        texts=(safe_text,),
        options={"language": language.value, "reading_level": reading_level.value},
        system=prompts.system_prompt(language.value),
        prompt=prompts.decode_prompt(
            notice_text=safe_text, rule_ids=rules.ids(), level=reading_level
        ),
        schema=NoticeExtraction,
        max_output_tokens=settings.max_output_tokens_decode,
    )

    resolved_dates, notice_date = _decode_dates(extraction, masked.text, settings.max_dates)
    match = rulebook.match_rule(rules, masked.text, extraction.notice_label)
    deadline = deadlines.compute_deadline(
        rule=match.rule,
        notice_date=notice_date,
        receipt_date=receipt_date,
        stated_period_days=extraction.stated_deadline.period_days,
        stated_by_date=_stated_by_date(extraction, masked.text),
        today=today,
    )

    report = DecodeReport(
        request_id=request_id,
        notice=NoticeSourceSchema(text=masked.text, redactions=dict(masked.counts)),
        classification=ClassificationSchema(
            label=extraction.notice_label,
            rule=_rule_card(match.rule, language) if match.rule else None,
            reason=match.reason,
            matched_terms=list(match.matched_terms),
        ),
        summary=extraction.summary,
        sender_role=extraction.sender_role,
        recipient_role=extraction.recipient_role,
        demands=_decode_demands(extraction, masked.text, settings.max_demands),
        cited_references=_decode_references(extraction, masked.text, settings.max_cited_references),
        dates=resolved_dates,
        deadline=DeadlineSchema(
            respond_by=deadline.respond_by,
            days_left=deadline.days_left,
            status=deadline.status,
            basis=deadline.basis,
            provisional=deadline.provisional,
            steps=[StepSchema(code=step.code, params=dict(step.params)) for step in deadline.steps],
        ),
        options=[
            OptionSchema(
                kind=option.kind,
                what_it_involves=option.what_it_involves,
                prepare=list(option.prepare),
                if_ignored=option.if_ignored,
            )
            for option in extraction.options[: settings.max_options]
        ],
        documents_to_gather=extraction.documents_to_gather[: settings.max_documents_to_gather],
        questions_for_lawyer=extraction.questions_for_lawyer[: settings.max_questions_for_lawyer],
        plain_terms=[
            PlainTermSchema(term=term.term, meaning=term.meaning)
            for term in extraction.plain_terms[: settings.max_plain_terms]
        ],
        screening=ScreeningSchema(
            ai_directed=list(signals.ai_directed), urgent=list(signals.urgent)
        ),
    )
    return report, cache_hit


def _check_claim(claim: ClaimCheck, notice: str, agreement: str) -> ClaimCheckSchema:
    """Confirm both quotes for one claim and downgrade it if either is absent.

    A verdict that rests on words nobody can find is not a finding, so it
    becomes ``UNCLEAR`` with the reason recorded.
    """
    notice_receipt = evidence.locate(claim.notice_quote, notice)
    agreement_receipt = (
        evidence.locate(claim.agreement_quote, agreement)
        if claim.agreement_quote is not None
        else None
    )

    verdict = claim.verdict
    explanation = claim.explanation
    downgraded_from: Verdict | None = None

    if not notice_receipt.found:
        downgraded_from, verdict = verdict, Verdict.UNCLEAR
        explanation = NOTICE_QUOTE_NOT_FOUND
    elif verdict in (Verdict.CONSISTENT, Verdict.CONFLICTS) and (
        agreement_receipt is None or not agreement_receipt.found
    ):
        downgraded_from, verdict = verdict, Verdict.UNCLEAR
        explanation = AGREEMENT_QUOTE_NOT_FOUND

    return ClaimCheckSchema(
        claim=claim.claim,
        category=claim.category,
        verdict=verdict,
        explanation=explanation,
        notice_receipt=_receipt_schema(notice_receipt),
        agreement_receipt=_receipt_schema(agreement_receipt) if agreement_receipt else None,
        downgraded_from=downgraded_from,
    )


async def cross_check(
    *,
    notice_text: str,
    agreement_text: str,
    language: Language,
    llm: LLMPort,
    cache: TTLCache,
    settings: Settings,
    request_id: str,
) -> tuple[CrossCheckReport, bool]:
    """Compare a notice with the agreement it relies on.

    Args:
        notice_text: The masked notice text returned by an earlier decode.
        agreement_text: The agreement, unmasked as supplied.
        language: The language to explain in.
        llm: The model port.
        cache: The result cache.
        settings: Limits and the model id.
        request_id: The id echoed back to the caller.

    Returns:
        The report and whether the model output came from the cache.
    """
    masked_notice = redaction.redact(notice_text).text
    masked_agreement = redaction.redact(agreement_text).text
    safe_notice = screening.neutralise_delimiters(masked_notice)
    safe_agreement = screening.neutralise_delimiters(masked_agreement)

    extraction, cache_hit = await _generate(
        llm=llm,
        cache=cache,
        settings=settings,
        task=TASK_CROSS_CHECK,
        texts=(safe_notice, safe_agreement),
        options={"language": language.value},
        system=prompts.system_prompt(language.value),
        prompt=prompts.cross_check_prompt(notice_text=safe_notice, agreement_text=safe_agreement),
        schema=CrossCheckExtraction,
        max_output_tokens=settings.max_output_tokens_cross_check,
    )

    report = CrossCheckReport(
        request_id=request_id,
        agreement_summary=extraction.agreement_summary,
        claims=[
            _check_claim(claim, masked_notice, masked_agreement)
            for claim in extraction.claims[: settings.max_claims]
        ],
    )
    return report, cache_hit


async def answer_question(
    *,
    question: str,
    documents: Sequence[tuple[str, str]],
    language: Language,
    llm: LLMPort,
    cache: TTLCache,
    settings: Settings,
    request_id: str,
) -> tuple[AnswerReport, bool]:
    """Answer a question from the user's documents alone.

    An answer the model calls supported but cannot quote is not returned:
    the report says the documents do not answer it.

    Args:
        question: The user's question.
        documents: ``(label, text)`` pairs to answer from.
        language: The language to answer in.
        llm: The model port.
        cache: The result cache.
        settings: Limits and the model id.
        request_id: The id echoed back to the caller.

    Returns:
        The report and whether the model output came from the cache.
    """
    masked = tuple(
        (label, screening.neutralise_delimiters(redaction.redact(text).text))
        for label, text in documents
    )
    safe_question = screening.neutralise_delimiters(question)

    extraction, cache_hit = await _generate(
        llm=llm,
        cache=cache,
        settings=settings,
        task=TASK_ASK,
        texts=tuple(text for _, text in masked),
        options={"language": language.value, "question": safe_question},
        system=prompts.system_prompt(language.value),
        prompt=prompts.ask_prompt(question=safe_question, documents=masked),
        schema=GroundedAnswer,
        max_output_tokens=settings.max_output_tokens_ask,
    )

    haystack = "\n".join(text for _, text in masked)
    receipts = [
        evidence.locate(quote, haystack)
        for quote in extraction.quotes[: settings.max_grounded_quotes]
    ]
    confirmed = [receipt for receipt in receipts if receipt.found]

    supported = extraction.supported and bool(confirmed)
    report = AnswerReport(
        request_id=request_id,
        answer="" if not supported else extraction.answer,
        supported=supported,
        unsupported_code=None if supported else UNSUPPORTED_ANSWER_CODE,
        receipts=[_receipt_schema(receipt) for receipt in receipts],
    )
    return report, cache_hit
