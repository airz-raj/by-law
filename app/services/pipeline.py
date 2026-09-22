"""Business logic pipeline orchestrating models, adapters, and LLM."""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
from typing import Any

from app.adapters.cache import TTLCache
from app.adapters.llm import LLMPort
from app.api.schemas import (
    AnswerReport,
    CitedReferenceSchema,
    ClaimCheckSchema,
    ClassificationSchema,
    CrossCheckReport,
    DateSchema,
    DecodeReport,
    DeadlineSchema,
    DemandSchema,
    NoticeSourceSchema,
    OptionSchema,
    ScreeningSchema,
)
from app.config import Settings
from app.core import dates, deadlines, evidence, redaction, rulebook, screening
from app.services import llm_schemas, prompts

logger = logging.getLogger(__name__)

async def decode_notice(
    text: str,
    receipt_date: datetime.date | None,
    language: str,
    reading_level: str,
    *,
    llm: LLMPort,
    cache: TTLCache,
    rules: rulebook.Rulebook,
    today: datetime.date,
    settings: Settings,
    request_id: str,
) -> DecodeReport:
    # 1. Redact -> Screen -> Neutralise
    redaction_result = redaction.redact(text)
    masked_text = redaction_result.text
    scr = screening.screen(masked_text)
    safe_text = screening.neutralise_delimiters(masked_text)

    # 2. Cache lookup & LLM call
    cache_key_elements = [
        prompts.PROMPT_VERSION,
        settings.gemini_model,
        "decode",
        safe_text,
        {"lang": language, "level": reading_level},
    ]
    cache_key = hashlib.sha256(json.dumps(cache_key_elements, sort_keys=True).encode()).hexdigest()
    
    extracted = cache.get(*cache_key_elements)
    if not extracted:
        prompt = prompts.DECODE_TASK.format(
            rule_catalogue=", ".join(rules.rules.keys()),
            reading_level_instruction=reading_level,
            notice_text=safe_text,
        )
        sys_prompt = prompts.BASE_SYSTEM_INSTRUCTION.format(language=language)
        extracted = await llm.generate(
            task="decode",
            system=sys_prompt,
            prompt=prompt,
            schema=llm_schemas.NoticeExtraction,
            max_output_tokens=4096,
        )
        # Store dict representation
        cache.set(*cache_key_elements, value=extracted.model_dump(mode="json"))
    else:
        extracted = llm_schemas.NoticeExtraction.model_validate(extracted)

    # 3. Truncate lists & Locate quotes
    demands = extracted.demands[:settings.max_demands]
    refs = extracted.cited_references[:settings.max_references]
    options = extracted.options[:settings.max_options]
    
    out_demands = []
    for d in demands:
        rec = evidence.locate(d.quote, masked_text)
        out_demands.append(DemandSchema(
            what=d.what,
            amount_text=d.amount_text,
            receipt={"quote": d.quote, "found": rec.found, "start": rec.start, "end": rec.end, "reason": rec.reason.value if rec.reason else None}
        ))
        
    out_refs = []
    for r in refs:
        rec = evidence.locate(r.quote, masked_text)
        out_refs.append(CitedReferenceSchema(
            reference=r.reference,
            receipt={"quote": r.quote, "found": rec.found, "start": rec.start, "end": rec.end, "reason": rec.reason.value if rec.reason else None}
        ))

    # 4. Resolve dates
    out_dates = []
    notice_date = None
    for dm in extracted.dates:
        rec = evidence.locate(dm.quote, masked_text)
        val = None
        if rec.found:
            found_ds = dates.find_dates(rec.quote)
            if found_ds:
                val = found_ds[0].value
                if dm.kind == llm_schemas.DateKind.NOTICE_DATE and notice_date is None:
                    notice_date = val
        out_dates.append(DateSchema(
            kind=dm.kind,
            label=dm.label,
            value=val.isoformat() if val else None,
            receipt={"quote": dm.quote, "found": rec.found, "start": rec.start, "end": rec.end, "reason": rec.reason.value if rec.reason else None}
        ))

    stated_by_date = None
    stated_period_days = extracted.stated_deadline.period_days
    if extracted.stated_deadline.by_date_quote:
        rec = evidence.locate(extracted.stated_deadline.by_date_quote, masked_text)
        if rec.found:
            fds = dates.find_dates(rec.quote)
            if fds:
                stated_by_date = fds[0].value

    # 5. Match rule and compute deadline
    rule_match = rulebook.match_rule(rules, masked_text, extracted.notice_label)
    dl = deadlines.compute_deadline(
        rule=rule_match.rule,
        notice_date=notice_date,
        receipt_date=receipt_date,
        stated_period_days=stated_period_days,
        stated_by_date=stated_by_date,
        today=today,
    )

    out_options = []
    for o in options:
        out_options.append(OptionSchema(
            kind=o.kind,
            what_it_involves=o.what_it_involves,
            prepare=o.prepare,
            if_ignored=o.if_ignored,
        ))

    return DecodeReport(
        request_id=request_id,
        notice=NoticeSourceSchema(text=masked_text, redactions=redaction_result.counts),
        classification=ClassificationSchema(
            label=extracted.notice_label,
            rule=rule_match.rule.id if rule_match.rule else None,
            reason=rule_match.reason.value,
            matched_terms=list(rule_match.matched_terms)
        ),
        summary=extracted.summary,
        sender_role=extracted.sender_role,
        recipient_role=extracted.recipient_role,
        demands=out_demands,
        cited_references=out_refs,
        dates=out_dates,
        deadline=DeadlineSchema(
            respond_by=dl.respond_by.isoformat() if dl.respond_by else None,
            days_left=dl.days_left,
            status=dl.status,
            basis=dl.basis,
            provisional=dl.provisional,
            steps=list(dl.steps)
        ),
        options=out_options,
        documents_to_gather=extracted.documents_to_gather[:settings.max_documents_to_gather],
        questions_for_lawyer=extracted.questions_for_lawyer[:settings.max_questions_for_lawyer],
        plain_terms=[{"term": pt.term, "meaning": pt.meaning} for pt in extracted.plain_terms[:settings.max_plain_terms]],
        screening=ScreeningSchema(ai_directed=list(scr.ai_directed), urgent=list(scr.urgent)),
    )
