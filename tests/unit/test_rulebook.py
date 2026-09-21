import pytest
from pathlib import Path
from app.core.rulebook import load_rulebook, match_rule
from app.core.models import MatchReason

def test_load_rulebook():
    path = Path("app/data/rules_in.json")
    rulebook = load_rulebook(path)
    assert len(rulebook.rules) == 3
    
    rule = rulebook.get("in.ni_act.s138_demand")
    assert rule is not None
    assert rule.period_days == 15
    assert rule.clock_starts == "receipt"
    assert "section 138" in rule.trigger_terms

def test_match_rule_success():
    path = Path("app/data/rules_in.json")
    rulebook = load_rulebook(path)
    text = "This is a notice under section 138 for a dishonoured cheque."
    match = match_rule(rulebook, text, "in.ni_act.s138_demand")
    
    assert match.reason == MatchReason.MATCHED
    assert match.rule is not None
    assert match.rule.id == "in.ni_act.s138_demand"

def test_match_rule_too_few_triggers():
    path = Path("app/data/rules_in.json")
    rulebook = load_rulebook(path)
    text = "This is a notice under section 138."  # Only 1 trigger
    match = match_rule(rulebook, text, "in.ni_act.s138_demand")
    
    assert match.reason == MatchReason.TOO_FEW_TRIGGERS
    assert match.rule is None

def test_match_rule_unknown_label():
    path = Path("app/data/rules_in.json")
    rulebook = load_rulebook(path)
    text = "This is a notice."
    match = match_rule(rulebook, text, "unknown.rule")
    
    assert match.reason == MatchReason.UNKNOWN_LABEL
    assert match.rule is None
