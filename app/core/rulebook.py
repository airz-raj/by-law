"""Load the statutory rulebook and match a notice against it.

A notice is matched to a rule only when the model's label and keyword
evidence in the text agree, so a confident but wrong label cannot on its
own decide a deadline.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.core.models import (
    ClockStart,
    LocalisedText,
    MatchReason,
    Rule,
    Rulebook,
    RuleMatch,
    RuleSource,
)

_REQUIRED_TEXT_FIELDS = ("title", "what_you_must_do", "what_can_happen_next")


def _localised(raw: Any, rule_id: str, field: str) -> LocalisedText:
    """Build a LocalisedText from raw JSON, requiring both languages."""
    if not isinstance(raw, dict):
        raise ValueError(f"rule {rule_id}: {field} must be an object with en and hi")
    en, hi = raw.get("en"), raw.get("hi")
    if not isinstance(en, str) or not en.strip():
        raise ValueError(f"rule {rule_id}: {field} is missing English text")
    if not isinstance(hi, str) or not hi.strip():
        raise ValueError(f"rule {rule_id}: {field} is missing Hindi text")
    return LocalisedText(en=en, hi=hi)


def _localised_list(raw: Any, rule_id: str, field: str) -> tuple[LocalisedText, ...]:
    """Build a tuple of LocalisedText from a raw JSON list."""
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ValueError(f"rule {rule_id}: {field} must be a list")
    return tuple(_localised(item, rule_id, field) for item in raw)


def _sources(raw: Any, rule_id: str) -> tuple[RuleSource, ...]:
    """Build the citation tuple, requiring a label and a URL for each."""
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"rule {rule_id}: at least one source is required")
    built: list[RuleSource] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError(f"rule {rule_id}: each source must be an object")
        label, url = item.get("label"), item.get("url")
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"rule {rule_id}: a source is missing its label")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError(f"rule {rule_id}: source {label!r} needs an https URL")
        built.append(RuleSource(label=label, url=url))
    return tuple(built)


def _trigger_terms(raw: Any, rule_id: str) -> tuple[str, ...]:
    """Build the trigger-term tuple, requiring at least two distinct terms."""
    if not isinstance(raw, list) or len(raw) < 2:
        raise ValueError(f"rule {rule_id}: at least two trigger terms are required")
    terms = tuple(str(term) for term in raw)
    if len(set(terms)) != len(terms):
        raise ValueError(f"rule {rule_id}: trigger terms must be distinct")
    return terms


def _parse_rule(raw: Any, seen_ids: set[str]) -> Rule:
    """Validate one raw rule object and build a Rule."""
    if not isinstance(raw, dict):
        raise ValueError("every rule must be a JSON object")

    rule_id = raw.get("id")
    if not isinstance(rule_id, str) or not rule_id.strip():
        raise ValueError("a rule is missing its id")
    if rule_id in seen_ids:
        raise ValueError(f"duplicate rule id: {rule_id}")

    period_days = raw.get("period_days")
    if not isinstance(period_days, int) or isinstance(period_days, bool) or period_days <= 0:
        raise ValueError(f"rule {rule_id}: period_days must be a positive integer")

    clock_starts = raw.get("clock_starts")
    if not isinstance(clock_starts, str):
        raise ValueError(f"rule {rule_id}: clock_starts must be a string")
    try:
        clock = ClockStart(clock_starts)
    except ValueError as exc:
        raise ValueError(
            f"rule {rule_id}: clock_starts must be 'receipt' or 'notice_date'"
        ) from exc

    min_trigger_hits = raw.get("min_trigger_hits", 1)
    if not isinstance(min_trigger_hits, int) or min_trigger_hits < 1:
        raise ValueError(f"rule {rule_id}: min_trigger_hits must be 1 or more")

    last_reviewed = raw.get("last_reviewed")
    if not isinstance(last_reviewed, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", last_reviewed):
        raise ValueError(f"rule {rule_id}: last_reviewed must be a YYYY-MM-DD date")

    texts = {field: _localised(raw.get(field), rule_id, field) for field in _REQUIRED_TEXT_FIELDS}

    return Rule(
        id=rule_id,
        title=texts["title"],
        clock_starts=clock,
        period_days=period_days,
        what_you_must_do=texts["what_you_must_do"],
        what_can_happen_next=texts["what_can_happen_next"],
        your_rights=_localised_list(raw.get("your_rights"), rule_id, "your_rights"),
        trigger_terms=_trigger_terms(raw.get("trigger_terms"), rule_id),
        min_trigger_hits=min_trigger_hits,
        sources=_sources(raw.get("sources"), rule_id),
        caveats=_localised_list(raw.get("caveats"), rule_id, "caveats"),
        last_reviewed=last_reviewed,
    )


def load_rulebook(path: Path) -> Rulebook:
    """Load and validate the rulebook at *path*.

    Args:
        path: JSON file holding an array of rule objects.

    Returns:
        The validated rulebook.

    Raises:
        ValueError: If the file is not an array, an id repeats, a period is
            not positive, or any text is missing English or Hindi.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("the rulebook must be a JSON array of rule objects")

    rules: list[Rule] = []
    seen_ids: set[str] = set()
    for item in raw:
        rule = _parse_rule(item, seen_ids)
        seen_ids.add(rule.id)
        rules.append(rule)

    if not rules:
        raise ValueError("the rulebook is empty")
    return Rulebook(rules=tuple(rules))


def match_rule(rulebook: Rulebook, text: str, model_label: str) -> RuleMatch:
    """Match *text* to a rule, requiring the model label and keywords to agree.

    Args:
        rulebook: The loaded rulebook.
        text: The notice text, already masked.
        model_label: The rule id the model chose, or any other string.

    Returns:
        A RuleMatch carrying the rule when both votes agree, and otherwise
        no rule plus the reason it was rejected.
    """
    rule = rulebook.get(model_label)
    if rule is None:
        reason = (
            MatchReason.MODEL_SAID_OTHER if model_label == "other" else MatchReason.UNKNOWN_LABEL
        )
        return RuleMatch(rule=None, reason=reason, matched_terms=())

    lowered = text.lower()
    matched = tuple(
        sorted(
            term
            for term in rule.trigger_terms
            if re.search(rf"\b{re.escape(term.lower())}\b", lowered)
        )
    )

    if len(matched) < rule.min_trigger_hits:
        return RuleMatch(rule=None, reason=MatchReason.TOO_FEW_TRIGGERS, matched_terms=matched)

    return RuleMatch(rule=rule, reason=MatchReason.MATCHED, matched_terms=matched)
