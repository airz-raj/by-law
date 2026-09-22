"""Table-driven tests for respond-by date computation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from app.core.deadlines import compute_deadline
from app.core.models import (
    ClockStart,
    DeadlineBasis,
    DeadlineStatus,
    LocalisedText,
    Rule,
    RuleSource,
    StepCode,
)

TODAY = date(2026, 3, 4)


def build_rule(clock_starts: ClockStart, period_days: int) -> Rule:
    """Build a complete Rule for deadline tests."""
    text = LocalisedText(en="text", hi="पाठ")
    return Rule(
        id="test.rule",
        title=text,
        clock_starts=clock_starts,
        period_days=period_days,
        what_you_must_do=text,
        what_can_happen_next=text,
        your_rights=(),
        trigger_terms=("alpha", "beta"),
        min_trigger_hits=2,
        sources=(RuleSource(label="Test Act", url="https://example.invalid/act"),),
        caveats=(),
        last_reviewed="2026-09-21",
    )


RECEIPT_RULE = build_rule(ClockStart.RECEIPT, 15)
NOTICE_RULE = build_rule(ClockStart.NOTICE_DATE, 60)


@dataclass(frozen=True)
class Case:
    """One deadline scenario and what it must produce."""

    name: str
    rule: Rule | None
    notice_date: date | None
    receipt_date: date | None
    stated_period_days: int | None
    stated_by_date: date | None
    today: date
    respond_by: date | None
    days_left: int | None
    status: DeadlineStatus
    basis: DeadlineBasis
    provisional: bool


CASES: tuple[Case, ...] = (
    Case(
        name="receipt rule",
        rule=RECEIPT_RULE,
        notice_date=None,
        receipt_date=date(2026, 3, 1),
        stated_period_days=None,
        stated_by_date=None,
        today=TODAY,
        respond_by=date(2026, 3, 16),
        days_left=12,
        status=DeadlineStatus.UPCOMING,
        basis=DeadlineBasis.RULEBOOK,
        provisional=False,
    ),
    Case(
        name="month end",
        rule=RECEIPT_RULE,
        notice_date=None,
        receipt_date=date(2026, 1, 31),
        stated_period_days=None,
        stated_by_date=None,
        today=date(2026, 2, 1),
        respond_by=date(2026, 2, 15),
        days_left=14,
        status=DeadlineStatus.UPCOMING,
        basis=DeadlineBasis.RULEBOOK,
        provisional=False,
    ),
    Case(
        name="leap year",
        rule=RECEIPT_RULE,
        notice_date=None,
        receipt_date=date(2028, 2, 20),
        stated_period_days=None,
        stated_by_date=None,
        today=date(2028, 2, 21),
        respond_by=date(2028, 3, 6),
        days_left=14,
        status=DeadlineStatus.UPCOMING,
        basis=DeadlineBasis.RULEBOOK,
        provisional=False,
    ),
    Case(
        name="notice-date rule",
        rule=NOTICE_RULE,
        notice_date=date(2026, 7, 10),
        receipt_date=date(2026, 7, 14),
        stated_period_days=None,
        stated_by_date=None,
        today=date(2026, 7, 14),
        respond_by=date(2026, 9, 8),
        days_left=56,
        status=DeadlineStatus.UPCOMING,
        basis=DeadlineBasis.RULEBOOK,
        provisional=False,
    ),
    Case(
        name="missing receipt date falls back to the notice date",
        rule=RECEIPT_RULE,
        notice_date=date(2026, 3, 1),
        receipt_date=None,
        stated_period_days=None,
        stated_by_date=None,
        today=TODAY,
        respond_by=date(2026, 3, 16),
        days_left=12,
        status=DeadlineStatus.UPCOMING,
        basis=DeadlineBasis.RULEBOOK,
        provisional=True,
    ),
    Case(
        name="notice asks sooner than the rule",
        rule=RECEIPT_RULE,
        notice_date=None,
        receipt_date=date(2026, 3, 1),
        stated_period_days=7,
        stated_by_date=None,
        today=TODAY,
        respond_by=date(2026, 3, 8),
        days_left=4,
        status=DeadlineStatus.UPCOMING,
        basis=DeadlineBasis.RULEBOOK,
        provisional=False,
    ),
    Case(
        name="notice asks later than the rule, so the rule stands",
        rule=RECEIPT_RULE,
        notice_date=None,
        receipt_date=date(2026, 3, 1),
        stated_period_days=30,
        stated_by_date=None,
        today=TODAY,
        respond_by=date(2026, 3, 16),
        days_left=12,
        status=DeadlineStatus.UPCOMING,
        basis=DeadlineBasis.RULEBOOK,
        provisional=False,
    ),
    Case(
        name="stated period only, no rule",
        rule=None,
        notice_date=None,
        receipt_date=date(2026, 5, 5),
        stated_period_days=10,
        stated_by_date=None,
        today=date(2026, 5, 6),
        respond_by=date(2026, 5, 15),
        days_left=9,
        status=DeadlineStatus.UPCOMING,
        basis=DeadlineBasis.STATED_IN_NOTICE,
        provisional=False,
    ),
    Case(
        name="stated period only, counted from the notice date",
        rule=None,
        notice_date=date(2026, 5, 5),
        receipt_date=None,
        stated_period_days=10,
        stated_by_date=None,
        today=date(2026, 5, 6),
        respond_by=date(2026, 5, 15),
        days_left=9,
        status=DeadlineStatus.UPCOMING,
        basis=DeadlineBasis.STATED_IN_NOTICE,
        provisional=True,
    ),
    Case(
        name="stated by-date, no rule",
        rule=None,
        notice_date=None,
        receipt_date=None,
        stated_period_days=None,
        stated_by_date=date(2026, 6, 20),
        today=date(2026, 6, 1),
        respond_by=date(2026, 6, 20),
        days_left=19,
        status=DeadlineStatus.UPCOMING,
        basis=DeadlineBasis.STATED_IN_NOTICE,
        provisional=False,
    ),
    Case(
        name="overdue",
        rule=RECEIPT_RULE,
        notice_date=None,
        receipt_date=date(2026, 3, 1),
        stated_period_days=None,
        stated_by_date=None,
        today=date(2026, 3, 20),
        respond_by=date(2026, 3, 16),
        days_left=-4,
        status=DeadlineStatus.OVERDUE,
        basis=DeadlineBasis.RULEBOOK,
        provisional=False,
    ),
    Case(
        name="due today",
        rule=RECEIPT_RULE,
        notice_date=None,
        receipt_date=date(2026, 3, 1),
        stated_period_days=None,
        stated_by_date=None,
        today=date(2026, 3, 16),
        respond_by=date(2026, 3, 16),
        days_left=0,
        status=DeadlineStatus.DUE_TODAY,
        basis=DeadlineBasis.RULEBOOK,
        provisional=False,
    ),
    Case(
        name="nothing known",
        rule=None,
        notice_date=None,
        receipt_date=None,
        stated_period_days=None,
        stated_by_date=None,
        today=TODAY,
        respond_by=None,
        days_left=None,
        status=DeadlineStatus.UNKNOWN,
        basis=DeadlineBasis.UNKNOWN,
        provisional=False,
    ),
    Case(
        name="rule matched but no date at all",
        rule=RECEIPT_RULE,
        notice_date=None,
        receipt_date=None,
        stated_period_days=None,
        stated_by_date=None,
        today=TODAY,
        respond_by=None,
        days_left=None,
        status=DeadlineStatus.UNKNOWN,
        basis=DeadlineBasis.RULEBOOK,
        provisional=True,
    ),
)


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_compute_deadline(case: Case) -> None:
    result = compute_deadline(
        rule=case.rule,
        notice_date=case.notice_date,
        receipt_date=case.receipt_date,
        stated_period_days=case.stated_period_days,
        stated_by_date=case.stated_by_date,
        today=case.today,
    )
    assert result.respond_by == case.respond_by
    assert result.days_left == case.days_left
    assert result.status == case.status
    assert result.basis == case.basis
    assert result.provisional is case.provisional


def test_holiday_caveat_is_always_present() -> None:
    for case in CASES:
        result = compute_deadline(
            rule=case.rule,
            notice_date=case.notice_date,
            receipt_date=case.receipt_date,
            stated_period_days=case.stated_period_days,
            stated_by_date=case.stated_by_date,
            today=case.today,
        )
        codes = [step.code for step in result.steps]
        assert StepCode.NO_HOLIDAY_ADJUSTMENT in codes, case.name


def test_a_sooner_notice_date_explains_both_dates() -> None:
    result = compute_deadline(
        rule=RECEIPT_RULE,
        notice_date=None,
        receipt_date=date(2026, 3, 1),
        stated_period_days=7,
        stated_by_date=None,
        today=TODAY,
    )
    steps = {step.code: step.params for step in result.steps}
    assert StepCode.NOTICE_ASKS_SOONER in steps
    assert steps[StepCode.NOTICE_ASKS_SOONER]["rule_date"] == "2026-03-16"
    assert steps[StepCode.NOTICE_ASKS_SOONER]["notice_date"] == "2026-03-08"
    assert StepCode.PLAN_FOR_EARLIER in steps


def test_missing_receipt_date_is_flagged_as_a_step() -> None:
    result = compute_deadline(
        rule=RECEIPT_RULE,
        notice_date=date(2026, 3, 1),
        receipt_date=None,
        stated_period_days=None,
        stated_by_date=None,
        today=TODAY,
    )
    assert StepCode.RECEIPT_DATE_MISSING in [step.code for step in result.steps]


def test_first_day_is_excluded_per_general_clauses_act() -> None:
    result = compute_deadline(
        rule=build_rule(ClockStart.RECEIPT, 1),
        notice_date=None,
        receipt_date=date(2026, 3, 1),
        stated_period_days=None,
        stated_by_date=None,
        today=TODAY,
    )
    assert result.respond_by == date(2026, 3, 2)
    assert StepCode.EXCLUDE_FIRST_DAY in [step.code for step in result.steps]


def test_a_notice_date_rule_falls_back_to_the_receipt_date() -> None:
    """A SARFAESI-style rule counts from the notice date, but a report is
    better than none when only the receipt date was found."""
    result = compute_deadline(
        rule=NOTICE_RULE,
        notice_date=None,
        receipt_date=date(2026, 7, 10),
        stated_period_days=None,
        stated_by_date=None,
        today=date(2026, 7, 14),
    )
    assert result.respond_by == date(2026, 9, 8)
    assert result.provisional is True
    assert StepCode.RECEIPT_DATE_MISSING in [step.code for step in result.steps]


def test_a_notice_date_rule_with_no_date_at_all_is_unknown() -> None:
    result = compute_deadline(
        rule=NOTICE_RULE,
        notice_date=None,
        receipt_date=None,
        stated_period_days=None,
        stated_by_date=None,
        today=TODAY,
    )
    assert result.respond_by is None
    assert result.status is DeadlineStatus.UNKNOWN
    assert result.basis is DeadlineBasis.RULEBOOK


def test_a_stated_period_with_no_anchor_cannot_be_counted() -> None:
    result = compute_deadline(
        rule=None,
        notice_date=None,
        receipt_date=None,
        stated_period_days=10,
        stated_by_date=None,
        today=TODAY,
    )
    assert result.respond_by is None
    assert result.status is DeadlineStatus.UNKNOWN
    assert StepCode.NO_DEADLINE_FOUND in [step.code for step in result.steps]


def test_a_stated_period_without_an_anchor_cannot_beat_a_rule() -> None:
    """The rule has a receipt date; the stated period has nothing to count from."""
    result = compute_deadline(
        rule=RECEIPT_RULE,
        notice_date=None,
        receipt_date=date(2026, 3, 1),
        stated_period_days=None,
        stated_by_date=None,
        today=TODAY,
    )
    assert result.respond_by == date(2026, 3, 16)
