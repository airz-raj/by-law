from app.core.legal_aid import LegalAidAnswers, check_eligibility
from app.core.models import Section12Clause


def test_eligibility_sc_st():
    answers = LegalAidAnswers(sc_st=True, income_below_state_limit="no")
    res = check_eligibility(answers)
    assert res.likely_eligible is True
    assert Section12Clause.SC_ST in res.matched
    assert res.income_check_needed is False
    assert "CONTACT_DLSA" in res.next_steps


def test_eligibility_none():
    answers = LegalAidAnswers()
    res = check_eligibility(answers)
    assert res.likely_eligible is False
    assert res.income_check_needed is True
    assert "CHECK_STATE_INCOME_LIMIT" in res.next_steps


def test_eligibility_income_unsure():
    answers = LegalAidAnswers(income_below_state_limit="unsure")
    res = check_eligibility(answers)
    assert res.likely_eligible is False
    assert res.income_check_needed is True


def test_eligibility_multiple():
    answers = LegalAidAnswers(woman_or_child=True, custody=True)
    res = check_eligibility(answers)
    assert res.likely_eligible is True
    assert Section12Clause.WOMAN_OR_CHILD in res.matched
    assert Section12Clause.CUSTODY in res.matched
