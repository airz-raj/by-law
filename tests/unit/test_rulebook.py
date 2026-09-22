"""Tests for loading the rulebook and matching a notice against it.

The loader guards the legal data, so every way a rule can be malformed is
exercised here: a bad rule must fail the build, not reach a reader.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.core.models import ClockStart, Language, MatchReason
from app.core.rulebook import load_rulebook, match_rule
from tests.paths import RULES_PATH

CHEQUE = "in.ni_act.s138_demand"
SARFAESI = "in.sarfaesi.s13_2_demand"
TENANCY = "in.tpa.s106_termination"


@pytest.fixture(scope="module")
def rulebook():
    return load_rulebook(RULES_PATH)


def valid_rule(**overrides: Any) -> dict[str, Any]:
    """Build a minimal rule that loads, with the given fields replaced."""
    text = {"en": "English text", "hi": "हिन्दी पाठ"}
    rule: dict[str, Any] = {
        "id": "test.rule",
        "title": text,
        "clock_starts": "receipt",
        "period_days": 15,
        "what_you_must_do": text,
        "what_can_happen_next": text,
        "your_rights": [text],
        "trigger_terms": ["alpha", "beta"],
        "min_trigger_hits": 2,
        "sources": [{"label": "Test Act", "url": "https://example.invalid/act"}],
        "caveats": [text],
        "last_reviewed": "2026-09-22",
    }
    rule.update(overrides)
    return rule


def load(rules: list[Any], tmp_path: Path) -> Any:
    """Write *rules* to a temporary file and load it."""
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(rules), encoding="utf-8")
    return load_rulebook(path)


# --- the shipped rulebook --------------------------------------------------


def test_the_shipped_rulebook_loads(rulebook) -> None:
    assert rulebook.ids() == (CHEQUE, SARFAESI, TENANCY)


def test_the_cheque_rule_runs_fifteen_days_from_receipt(rulebook) -> None:
    rule = rulebook.get(CHEQUE)
    assert rule is not None
    assert rule.period_days == 15
    assert rule.clock_starts is ClockStart.RECEIPT


def test_the_sarfaesi_rule_runs_sixty_days_from_the_notice_date(rulebook) -> None:
    rule = rulebook.get(SARFAESI)
    assert rule is not None
    assert rule.period_days == 60
    assert rule.clock_starts is ClockStart.NOTICE_DATE


def test_the_tenancy_rule_runs_fifteen_days_from_receipt(rulebook) -> None:
    rule = rulebook.get(TENANCY)
    assert rule is not None
    assert rule.period_days == 15
    assert rule.clock_starts is ClockStart.RECEIPT


@pytest.mark.parametrize("rule_id", [CHEQUE, SARFAESI, TENANCY])
def test_every_rule_cites_an_official_source(rulebook, rule_id: str) -> None:
    rule = rulebook.get(rule_id)
    assert rule is not None
    assert rule.sources
    assert all(source.url.startswith("https://www.indiacode.nic.in") for source in rule.sources)


@pytest.mark.parametrize("rule_id", [CHEQUE, SARFAESI, TENANCY])
def test_every_rule_reads_in_both_languages(rulebook, rule_id: str) -> None:
    rule = rulebook.get(rule_id)
    assert rule is not None
    assert rule.title.into(Language.EN) != rule.title.into(Language.HI)
    assert rule.what_you_must_do.into(Language.HI)
    assert any("ऀ" <= ch <= "ॿ" for ch in rule.title.into(Language.HI))


def test_an_unknown_rule_id_returns_nothing(rulebook) -> None:
    assert rulebook.get("in.nowhere.s1") is None


# --- matching --------------------------------------------------------------


def test_the_label_and_the_keywords_must_agree(rulebook) -> None:
    text = "This notice under section 138 concerns a dishonoured cheque."
    match = match_rule(rulebook, text, CHEQUE)
    assert match.reason is MatchReason.MATCHED
    assert match.rule is not None
    assert len(match.matched_terms) >= 2


def test_a_right_label_without_the_keywords_does_not_match(rulebook) -> None:
    match = match_rule(rulebook, "This notice concerns a payment.", CHEQUE)
    assert match.reason is MatchReason.TOO_FEW_TRIGGERS
    assert match.rule is None


def test_one_keyword_alone_is_not_enough(rulebook) -> None:
    match = match_rule(rulebook, "This notice is under section 138.", CHEQUE)
    assert match.reason is MatchReason.TOO_FEW_TRIGGERS
    assert match.matched_terms == ("section 138",)


def test_a_label_outside_the_rulebook_is_reported_as_unknown(rulebook) -> None:
    match = match_rule(rulebook, "Any text at all.", "in.nowhere.s1")
    assert match.reason is MatchReason.UNKNOWN_LABEL


def test_the_model_saying_other_is_reported_as_such(rulebook) -> None:
    match = match_rule(rulebook, "Any text at all.", "other")
    assert match.reason is MatchReason.MODEL_SAID_OTHER


def test_matching_ignores_case(rulebook) -> None:
    text = "NOTICE UNDER SECTION 138 FOR A DISHONOURED CHEQUE"
    assert match_rule(rulebook, text, CHEQUE).reason is MatchReason.MATCHED


def test_a_keyword_inside_a_longer_word_does_not_count(rulebook) -> None:
    match = match_rule(rulebook, "The chequered history of the tenancy.", CHEQUE)
    assert "cheque" not in match.matched_terms


# --- the loader rejects malformed data ------------------------------------


def test_a_duplicate_id_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="duplicate rule id"):
        load([valid_rule(), valid_rule()], tmp_path)


def test_a_zero_period_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="period_days"):
        load([valid_rule(period_days=0)], tmp_path)


def test_a_negative_period_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="period_days"):
        load([valid_rule(period_days=-5)], tmp_path)


def test_a_boolean_period_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="period_days"):
        load([valid_rule(period_days=True)], tmp_path)


def test_a_missing_hindi_string_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing Hindi"):
        load([valid_rule(title={"en": "only English"})], tmp_path)


def test_a_missing_english_string_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing English"):
        load([valid_rule(title={"hi": "केवल हिन्दी"})], tmp_path)


def test_a_blank_string_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing English"):
        load([valid_rule(title={"en": "  ", "hi": "पाठ"})], tmp_path)


def test_a_text_field_that_is_not_an_object_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must be an object"):
        load([valid_rule(title="a plain string")], tmp_path)


def test_a_missing_id_is_rejected(tmp_path: Path) -> None:
    rule = valid_rule()
    del rule["id"]
    with pytest.raises(ValueError, match="missing its id"):
        load([rule], tmp_path)


def test_an_unknown_clock_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="clock_starts"):
        load([valid_rule(clock_starts="when_posted")], tmp_path)


def test_a_non_string_clock_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="clock_starts must be a string"):
        load([valid_rule(clock_starts=7)], tmp_path)


def test_a_rule_without_a_source_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least one source"):
        load([valid_rule(sources=[])], tmp_path)


def test_a_source_without_an_https_url_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="https URL"):
        load([valid_rule(sources=[{"label": "Act", "url": "http://example.invalid"}])], tmp_path)


def test_a_source_without_a_label_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing its label"):
        load([valid_rule(sources=[{"url": "https://example.invalid"}])], tmp_path)


def test_a_source_that_is_not_an_object_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="each source must be an object"):
        load([valid_rule(sources=["https://example.invalid"])], tmp_path)


def test_fewer_than_two_trigger_terms_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="two trigger terms"):
        load([valid_rule(trigger_terms=["only one"])], tmp_path)


def test_repeated_trigger_terms_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="distinct"):
        load([valid_rule(trigger_terms=["same", "same"])], tmp_path)


def test_a_zero_trigger_threshold_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="min_trigger_hits"):
        load([valid_rule(min_trigger_hits=0)], tmp_path)


def test_a_malformed_review_date_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="last_reviewed"):
        load([valid_rule(last_reviewed="September 2026")], tmp_path)


def test_a_missing_review_date_is_rejected(tmp_path: Path) -> None:
    rule = valid_rule()
    del rule["last_reviewed"]
    with pytest.raises(ValueError, match="last_reviewed"):
        load([rule], tmp_path)


def test_a_rule_that_is_not_an_object_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must be a JSON object"):
        load(["not a rule"], tmp_path)


def test_a_rulebook_that_is_not_an_array_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "rules.json"
    path.write_text(json.dumps({"id": "x"}), encoding="utf-8")
    with pytest.raises(ValueError, match="JSON array"):
        load_rulebook(path)


def test_an_empty_rulebook_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="empty"):
        load([], tmp_path)


def test_a_rights_entry_that_is_not_an_object_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="your_rights"):
        load([valid_rule(your_rights=["a plain string"])], tmp_path)


def test_a_rights_list_that_is_not_a_list_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must be a list"):
        load([valid_rule(your_rights={"en": "x", "hi": "y"})], tmp_path)


def test_omitting_optional_lists_is_allowed(tmp_path: Path) -> None:
    rule = valid_rule()
    del rule["your_rights"]
    del rule["caveats"]
    loaded = load([rule], tmp_path)
    assert loaded.rules[0].your_rights == ()
    assert loaded.rules[0].caveats == ()
