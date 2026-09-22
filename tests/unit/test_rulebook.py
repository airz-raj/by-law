from app.core.models import MatchReason
from app.core.rulebook import load_rulebook, match_rule
from tests.paths import RULES_PATH


def test_load_rulebook():
    rulebook = load_rulebook(RULES_PATH)
    assert len(rulebook.rules) == 3

    rule = rulebook.get("in.ni_act.s138_demand")
    assert rule is not None
    assert rule.period_days == 15
    assert rule.clock_starts == "receipt"
    assert "section 138" in rule.trigger_terms


def test_match_rule_success():
    rulebook = load_rulebook(RULES_PATH)
    text = "This is a notice under section 138 for a dishonoured cheque."
    match = match_rule(rulebook, text, "in.ni_act.s138_demand")

    assert match.reason == MatchReason.MATCHED
    assert match.rule is not None
    assert match.rule.id == "in.ni_act.s138_demand"


def test_match_rule_too_few_triggers():
    rulebook = load_rulebook(RULES_PATH)
    text = "This is a notice under section 138."  # Only 1 trigger
    match = match_rule(rulebook, text, "in.ni_act.s138_demand")

    assert match.reason == MatchReason.TOO_FEW_TRIGGERS
    assert match.rule is None


def test_match_rule_unknown_label():
    rulebook = load_rulebook(RULES_PATH)
    text = "This is a notice."
    match = match_rule(rulebook, text, "unknown.rule")

    assert match.reason == MatchReason.UNKNOWN_LABEL
    assert match.rule is None
