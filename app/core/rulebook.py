"""Load and match statutory rules against notices."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from app.core.models import ClockStart, MatchReason
from app.core.deadlines import Rule


@dataclass(frozen=True, slots=True)
class LocalisedText:
    en: str
    hi: str


@dataclass(frozen=True, slots=True)
class Source:
    label: str
    url: str


@dataclass(frozen=True, slots=True)
class RuleDetails:
    id: str
    title: LocalisedText
    clock_starts: ClockStart
    period_days: int
    what_you_must_do: LocalisedText
    what_can_happen_next: LocalisedText
    your_rights: tuple[LocalisedText, ...]
    trigger_terms: tuple[str, ...]
    min_trigger_hits: int
    sources: tuple[Source, ...]
    caveats: tuple[LocalisedText, ...]
    last_reviewed: str


@dataclass(frozen=True, slots=True)
class Rulebook:
    rules: tuple[RuleDetails, ...]

    def get(self, rule_id: str) -> RuleDetails | None:
        for r in self.rules:
            if r.id == rule_id:
                return r
        return None


@dataclass(frozen=True, slots=True)
class RuleMatch:
    rule: RuleDetails | None
    reason: MatchReason
    matched_terms: tuple[str, ...]


def load_rulebook(path: Path) -> Rulebook:
    """Load and validate the rulebook from a JSON file."""
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Rulebook must be a JSON array of objects")

    parsed_rules: list[RuleDetails] = []
    seen_ids: set[str] = set()

    for item in data:
        rule_id = item.get("id")
        if not rule_id:
            raise ValueError("Rule missing id")
        if rule_id in seen_ids:
            raise ValueError(f"Duplicate rule id: {rule_id}")
        seen_ids.add(rule_id)

        period_days = item.get("period_days")
        if not isinstance(period_days, int) or period_days <= 0:
            raise ValueError(f"Rule {rule_id} has invalid period_days: {period_days}")

        def _parse_text(obj: dict[str, str] | None, field_name: str) -> LocalisedText:
            if not obj or not isinstance(obj, dict):
                raise ValueError(f"Rule {rule_id} missing {field_name}")
            en = obj.get("en")
            hi = obj.get("hi")
            if not en or not hi:
                raise ValueError(f"Rule {rule_id} {field_name} missing en or hi")
            return LocalisedText(en=en, hi=hi)

        title = _parse_text(item.get("title"), "title")
        wymd = _parse_text(item.get("what_you_must_do"), "what_you_must_do")
        wchn = _parse_text(item.get("what_can_happen_next"), "what_can_happen_next")

        your_rights = tuple(
            _parse_text(yr, "your_rights item") for yr in item.get("your_rights", [])
        )
        caveats = tuple(
            _parse_text(cv, "caveats item") for cv in item.get("caveats", [])
        )

        sources = tuple(
            Source(label=s.get("label", ""), url=s.get("url", ""))
            for s in item.get("sources", [])
        )

        parsed_rules.append(
            RuleDetails(
                id=rule_id,
                title=title,
                clock_starts=ClockStart(item.get("clock_starts")),
                period_days=period_days,
                what_you_must_do=wymd,
                what_can_happen_next=wchn,
                your_rights=your_rights,
                trigger_terms=tuple(item.get("trigger_terms", [])),
                min_trigger_hits=item.get("min_trigger_hits", 1),
                sources=sources,
                caveats=caveats,
                last_reviewed=item.get("last_reviewed", ""),
            )
        )

    return Rulebook(rules=tuple(parsed_rules))


def match_rule(rulebook: Rulebook, text: str, model_label: str) -> RuleMatch:
    """Match a rule by model label and trigger term counts in text."""
    rule = rulebook.get(model_label)
    if not rule:
        return RuleMatch(rule=None, reason=MatchReason.UNKNOWN_LABEL, matched_terms=())

    matched_terms: set[str] = set()
    text_lower = text.lower()

    for term in rule.trigger_terms:
        # Case-insensitive, word-boundary match
        pattern = re.compile(rf"\b{re.escape(term.lower())}\b")
        if pattern.search(text_lower):
            matched_terms.add(term)

    if len(matched_terms) < rule.min_trigger_hits:
        return RuleMatch(
            rule=None,
            reason=MatchReason.TOO_FEW_TRIGGERS,
            matched_terms=tuple(sorted(matched_terms)),
        )

    return RuleMatch(
        rule=rule,
        reason=MatchReason.MATCHED,
        matched_terms=tuple(sorted(matched_terms)),
    )
