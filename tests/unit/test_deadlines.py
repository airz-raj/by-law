from datetime import date
from app.core.deadlines import compute_deadline, Rule
from app.core.models import ClockStart, DeadlineStatus, DeadlineBasis

def test_compute_receipt_rule():
    rule = Rule("rule_1", ClockStart.RECEIPT, 15)
    today = date(2026, 3, 1)
    res = compute_deadline(
        rule=rule,
        notice_date=None,
        receipt_date=date(2026, 3, 1),
        stated_period_days=None,
        stated_by_date=None,
        today=today,
    )
    assert res.respond_by == date(2026, 3, 16)
    assert res.basis == DeadlineBasis.RULEBOOK

def test_compute_month_end():
    rule = Rule("rule_1", ClockStart.RECEIPT, 15)
    res = compute_deadline(
        rule=rule,
        notice_date=None,
        receipt_date=date(2026, 1, 31),
        stated_period_days=None,
        stated_by_date=None,
        today=date(2026, 1, 31),
    )
    assert res.respond_by == date(2026, 2, 15)

def test_compute_leap_year():
    rule = Rule("rule_1", ClockStart.RECEIPT, 15)
    res = compute_deadline(
        rule=rule,
        notice_date=None,
        receipt_date=date(2028, 2, 20),
        stated_period_days=None,
        stated_by_date=None,
        today=date(2028, 2, 20),
    )
    assert res.respond_by == date(2028, 3, 6)

def test_compute_notice_date_rule():
    rule = Rule("rule_2", ClockStart.NOTICE_DATE, 60)
    res = compute_deadline(
        rule=rule,
        notice_date=date(2026, 7, 10),
        receipt_date=date(2026, 7, 15),
        stated_period_days=None,
        stated_by_date=None,
        today=date(2026, 7, 15),
    )
    assert res.respond_by == date(2026, 9, 8)

def test_compute_missing_receipt():
    rule = Rule("rule_1", ClockStart.RECEIPT, 15)
    res = compute_deadline(
        rule=rule,
        notice_date=date(2026, 3, 1),
        receipt_date=None,
        stated_period_days=None,
        stated_by_date=None,
        today=date(2026, 3, 10),
    )
    assert res.respond_by == date(2026, 3, 16)
    assert res.provisional is True

def test_notice_asks_sooner():
    rule = Rule("rule_1", ClockStart.RECEIPT, 15)
    res = compute_deadline(
        rule=rule,
        notice_date=None,
        receipt_date=date(2026, 3, 1),
        stated_period_days=7,
        stated_by_date=None,
        today=date(2026, 3, 1),
    )
    assert res.respond_by == date(2026, 3, 8)

def test_stated_only():
    res = compute_deadline(
        rule=None,
        notice_date=None,
        receipt_date=date(2026, 5, 5),
        stated_period_days=10,
        stated_by_date=None,
        today=date(2026, 5, 5),
    )
    assert res.respond_by == date(2026, 5, 15)
    assert res.basis == DeadlineBasis.STATED_IN_NOTICE

def test_stated_by_date():
    res = compute_deadline(
        rule=None,
        notice_date=None,
        receipt_date=None,
        stated_period_days=None,
        stated_by_date=date(2026, 6, 20),
        today=date(2026, 6, 1),
    )
    assert res.respond_by == date(2026, 6, 20)

def test_overdue():
    res = compute_deadline(
        rule=None,
        notice_date=None,
        receipt_date=None,
        stated_period_days=None,
        stated_by_date=date(2026, 6, 20),
        today=date(2026, 6, 25),
    )
    assert res.status == DeadlineStatus.OVERDUE
    assert res.days_left == -5

def test_due_today():
    res = compute_deadline(
        rule=None,
        notice_date=None,
        receipt_date=None,
        stated_period_days=None,
        stated_by_date=date(2026, 6, 20),
        today=date(2026, 6, 20),
    )
    assert res.status == DeadlineStatus.DUE_TODAY
    assert res.days_left == 0

def test_nothing():
    res = compute_deadline(
        rule=None,
        notice_date=None,
        receipt_date=None,
        stated_period_days=None,
        stated_by_date=None,
        today=date(2026, 6, 1),
    )
    assert res.respond_by is None

def test_missing_notice_date_for_notice_rule():
    rule = Rule("rule_2", ClockStart.NOTICE_DATE, 60)
    res = compute_deadline(
        rule=rule,
        notice_date=None,
        receipt_date=date(2026, 7, 10),
        stated_period_days=None,
        stated_by_date=None,
        today=date(2026, 7, 15),
    )
    assert res.respond_by == date(2026, 9, 8)
    assert res.provisional is True

def test_missing_both_for_rule():
    rule = Rule("rule_1", ClockStart.RECEIPT, 15)
    res = compute_deadline(
        rule=rule,
        notice_date=None,
        receipt_date=None,
        stated_period_days=None,
        stated_by_date=None,
        today=date(2026, 3, 1),
    )
    assert res.respond_by is None
    assert res.status == DeadlineStatus.UNKNOWN
    assert res.provisional is True

def test_stated_period_missing_receipt():
    res = compute_deadline(
        rule=None,
        notice_date=date(2026, 5, 1),
        receipt_date=None,
        stated_period_days=10,
        stated_by_date=None,
        today=date(2026, 5, 5),
    )
    assert res.respond_by == date(2026, 5, 11)
    assert res.provisional is True

def test_stated_period_overdue():
    res = compute_deadline(
        rule=None,
        notice_date=date(2026, 5, 1),
        receipt_date=date(2026, 5, 5),
        stated_period_days=10,
        stated_by_date=None,
        today=date(2026, 5, 20),
    )
    assert res.status == DeadlineStatus.OVERDUE
    assert res.days_left == -5

def test_stated_period_due_today():
    res = compute_deadline(
        rule=None,
        notice_date=date(2026, 5, 1),
        receipt_date=date(2026, 5, 5),
        stated_period_days=10,
        stated_by_date=None,
        today=date(2026, 5, 15),
    )
    assert res.status == DeadlineStatus.DUE_TODAY
    assert res.days_left == 0

def test_stated_period_missing_both():
    res = compute_deadline(
        rule=None,
        notice_date=None,
        receipt_date=None,
        stated_period_days=10,
        stated_by_date=None,
        today=date(2026, 5, 5),
    )
    assert res.respond_by is None
    assert res.status == DeadlineStatus.UNKNOWN
