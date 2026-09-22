"""Compute the respond-by date from a rule and from what the notice says.

Counting follows the General Clauses Act, 1897, s.9: the first day is
excluded, so ``respond_by = anchor + period``. Nothing here reads the
clock; callers pass ``today``.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.core.models import (
    ClockStart,
    Deadline,
    DeadlineBasis,
    DeadlineStatus,
    ExplanationStep,
    Rule,
    StepCode,
)


def _step(code: StepCode, **params: str | int) -> ExplanationStep:
    """Build one explanation step."""
    return ExplanationStep(code=code, params=params)


def _add_period(anchor: date, period_days: int) -> date:
    """Add *period_days* to *anchor*, excluding the first day (s.9)."""
    return anchor + timedelta(days=period_days)


def _status_for(days_left: int) -> DeadlineStatus:
    """Classify a deadline from the days remaining."""
    if days_left < 0:
        return DeadlineStatus.OVERDUE
    if days_left == 0:
        return DeadlineStatus.DUE_TODAY
    return DeadlineStatus.UPCOMING


def _finish(
    *,
    respond_by: date,
    basis: DeadlineBasis,
    provisional: bool,
    steps: list[ExplanationStep],
    today: date,
) -> Deadline:
    """Close out a computed deadline with its status and closing steps."""
    days_left = (respond_by - today).days
    status = _status_for(days_left)

    steps.append(_step(StepCode.RESPOND_BY, date=respond_by.isoformat()))
    if status is DeadlineStatus.OVERDUE:
        steps.append(_step(StepCode.OVERDUE_WARNING, days=abs(days_left)))
    elif status is DeadlineStatus.DUE_TODAY:
        steps.append(_step(StepCode.DUE_TODAY_WARNING))
    steps.append(_step(StepCode.DAYS_LEFT, days=days_left))
    steps.append(_step(StepCode.NO_HOLIDAY_ADJUSTMENT))

    return Deadline(
        respond_by=respond_by,
        days_left=days_left,
        status=status,
        basis=basis,
        provisional=provisional,
        steps=tuple(steps),
    )


def _nothing_found(basis: DeadlineBasis, provisional: bool) -> Deadline:
    """Return the deadline used when no date can be worked out at all."""
    steps = [_step(StepCode.NO_DEADLINE_FOUND), _step(StepCode.NO_HOLIDAY_ADJUSTMENT)]
    return Deadline(
        respond_by=None,
        days_left=None,
        status=DeadlineStatus.UNKNOWN,
        basis=basis,
        provisional=provisional,
        steps=tuple(steps),
    )


def _anchor_for_rule(
    rule: Rule, notice_date: date | None, receipt_date: date | None
) -> tuple[date | None, bool, ExplanationStep | None]:
    """Pick the rule's anchor date and say whether it had to fall back.

    Returns the anchor, whether the result is provisional, and the step
    describing which date started the clock.
    """
    if rule.clock_starts is ClockStart.RECEIPT:
        if receipt_date is not None:
            return (
                receipt_date,
                False,
                _step(StepCode.CLOCK_STARTS_RECEIPT, date=receipt_date.isoformat()),
            )
        if notice_date is not None:
            return notice_date, True, _step(StepCode.RECEIPT_DATE_MISSING)
        return None, True, None

    if notice_date is not None:
        return (
            notice_date,
            False,
            _step(StepCode.CLOCK_STARTS_NOTICE_DATE, date=notice_date.isoformat()),
        )
    if receipt_date is not None:
        return receipt_date, True, _step(StepCode.RECEIPT_DATE_MISSING)
    return None, True, None


def _date_the_notice_asks_for(
    *,
    notice_date: date | None,
    receipt_date: date | None,
    stated_period_days: int | None,
    stated_by_date: date | None,
) -> date | None:
    """Work out the date the notice itself sets, if it sets one."""
    if stated_by_date is not None:
        return stated_by_date
    if stated_period_days is None:
        return None
    anchor = receipt_date or notice_date
    return None if anchor is None else _add_period(anchor, stated_period_days)


def _from_rule(
    *,
    rule: Rule,
    notice_date: date | None,
    receipt_date: date | None,
    stated_period_days: int | None,
    stated_by_date: date | None,
    today: date,
) -> Deadline:
    """Compute the deadline a matched rule gives, honouring a sooner notice."""
    anchor, provisional, anchor_step = _anchor_for_rule(rule, notice_date, receipt_date)
    if anchor is None:
        return _nothing_found(DeadlineBasis.RULEBOOK, provisional=True)

    steps: list[ExplanationStep] = []
    if anchor_step is not None:
        steps.append(anchor_step)
    steps.append(_step(StepCode.RULE_MATCHED, rule_id=rule.id))
    steps.append(_step(StepCode.PERIOD_DAYS, days=rule.period_days))
    steps.append(_step(StepCode.EXCLUDE_FIRST_DAY))

    respond_by = _add_period(anchor, rule.period_days)
    asked = _date_the_notice_asks_for(
        notice_date=notice_date,
        receipt_date=receipt_date,
        stated_period_days=stated_period_days,
        stated_by_date=stated_by_date,
    )
    if asked is not None and asked < respond_by:
        steps.append(
            _step(
                StepCode.NOTICE_ASKS_SOONER,
                rule_date=respond_by.isoformat(),
                notice_date=asked.isoformat(),
            )
        )
        respond_by = asked
        steps.append(_step(StepCode.PLAN_FOR_EARLIER, date=respond_by.isoformat()))

    return _finish(
        respond_by=respond_by,
        basis=DeadlineBasis.RULEBOOK,
        provisional=provisional,
        steps=steps,
        today=today,
    )


def _from_notice(
    *,
    notice_date: date | None,
    receipt_date: date | None,
    stated_period_days: int | None,
    stated_by_date: date | None,
    today: date,
) -> Deadline:
    """Compute the deadline from what the notice states, with no rule matched."""
    if stated_by_date is not None:
        steps = [_step(StepCode.STATED_DATE_USED, date=stated_by_date.isoformat())]
        return _finish(
            respond_by=stated_by_date,
            basis=DeadlineBasis.STATED_IN_NOTICE,
            provisional=False,
            steps=steps,
            today=today,
        )

    anchor = receipt_date or notice_date
    if stated_period_days is None or anchor is None:
        return _nothing_found(DeadlineBasis.UNKNOWN, provisional=False)

    provisional = receipt_date is None
    steps = []
    if provisional:
        steps.append(_step(StepCode.RECEIPT_DATE_MISSING))
    steps.append(_step(StepCode.STATED_PERIOD_USED, days=stated_period_days))
    steps.append(_step(StepCode.EXCLUDE_FIRST_DAY))

    return _finish(
        respond_by=_add_period(anchor, stated_period_days),
        basis=DeadlineBasis.STATED_IN_NOTICE,
        provisional=provisional,
        steps=steps,
        today=today,
    )


def compute_deadline(
    *,
    rule: Rule | None,
    notice_date: date | None,
    receipt_date: date | None,
    stated_period_days: int | None,
    stated_by_date: date | None,
    today: date,
) -> Deadline:
    """Compute the respond-by date, its status, and the working shown.

    A matched rule takes precedence, except that a sooner date asked for by
    the notice itself becomes the date to plan for. With no rule, the period
    or date stated in the notice is used. With neither, the status is
    ``UNKNOWN``.

    Args:
        rule: The matched rule, or None if the rulebook did not match.
        notice_date: The date printed on the notice, if one was found.
        receipt_date: The date the user says they received it, if given.
        stated_period_days: A period the notice states, in days.
        stated_by_date: A date the notice states as its cut-off.
        today: The date to measure ``days_left`` against.

    Returns:
        The computed deadline and its explanation steps.
    """
    if rule is not None:
        return _from_rule(
            rule=rule,
            notice_date=notice_date,
            receipt_date=receipt_date,
            stated_period_days=stated_period_days,
            stated_by_date=stated_by_date,
            today=today,
        )
    return _from_notice(
        notice_date=notice_date,
        receipt_date=receipt_date,
        stated_period_days=stated_period_days,
        stated_by_date=stated_by_date,
        today=today,
    )
