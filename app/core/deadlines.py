"""Compute respond-by dates from rules and notices.

Counting follows the General Clauses Act, 1897, s.9: exclude the first
day, so respond_by = anchor + timedelta(days=period).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from app.core.models import (
    ClockStart,
    Deadline,
    DeadlineBasis,
    DeadlineStatus,
    ExplanationStep,
    StepCode,
)


@dataclass(frozen=True, slots=True)
class Rule:
    """A statutory rule from the rulebook, carrying only the fields needed for deadline computation."""

    rule_id: str
    clock_starts: ClockStart
    period_days: int


def _compute_respond_by(anchor: date, period_days: int) -> date:
    """General Clauses Act s.9: exclude the first day."""
    return anchor + timedelta(days=period_days)


def _status_from_days(days_left: int) -> DeadlineStatus:
    """Determine deadline status from days remaining."""
    if days_left < 0:
        return DeadlineStatus.OVERDUE
    if days_left == 0:
        return DeadlineStatus.DUE_TODAY
    return DeadlineStatus.UPCOMING


def compute_deadline(
    *,
    rule: Rule | None,
    notice_date: date | None,
    receipt_date: date | None,
    stated_period_days: int | None,
    stated_by_date: date | None,
    today: date,
) -> Deadline:
    """Compute the respond-by date, explanation steps, and status.

    See workflow section 5.4 for the full precedence logic.
    """
    steps: list[ExplanationStep] = []

    # --- Case 1: Rule matched ---
    if rule is not None:
        provisional = False
        if rule.clock_starts == ClockStart.RECEIPT:
            anchor = receipt_date
            if anchor is None:
                anchor = notice_date
                provisional = True
                steps.append(ExplanationStep(
                    code=StepCode.RECEIPT_DATE_MISSING,
                    params={},
                ))
            else:
                steps.append(ExplanationStep(
                    code=StepCode.CLOCK_STARTS_RECEIPT,
                    params={"date": str(anchor)},
                ))
        else:
            anchor = notice_date
            if anchor is None:
                anchor = receipt_date
                provisional = True
                steps.append(ExplanationStep(
                    code=StepCode.RECEIPT_DATE_MISSING,
                    params={},
                ))
            else:
                steps.append(ExplanationStep(
                    code=StepCode.CLOCK_STARTS_NOTICE_DATE,
                    params={"date": str(anchor)},
                ))

        if anchor is None:
            steps.append(ExplanationStep(code=StepCode.NO_DEADLINE_FOUND, params={}))
            steps.append(ExplanationStep(code=StepCode.NO_HOLIDAY_ADJUSTMENT, params={}))
            return Deadline(
                respond_by=None,
                days_left=None,
                status=DeadlineStatus.UNKNOWN,
                basis=DeadlineBasis.RULEBOOK,
                provisional=True,
                steps=tuple(steps),
            )

        steps.append(ExplanationStep(
            code=StepCode.RULE_MATCHED,
            params={"rule_id": rule.rule_id},
        ))
        steps.append(ExplanationStep(
            code=StepCode.PERIOD_DAYS,
            params={"days": rule.period_days},
        ))
        steps.append(ExplanationStep(
            code=StepCode.EXCLUDE_FIRST_DAY,
            params={},
        ))

        respond_by = _compute_respond_by(anchor, rule.period_days)

        # Check if the notice states a sooner deadline
        notice_respond_by: date | None = None
        if stated_by_date is not None:
            notice_respond_by = stated_by_date
        elif stated_period_days is not None:
            stated_anchor = receipt_date or notice_date
            if stated_anchor is not None:
                notice_respond_by = _compute_respond_by(stated_anchor, stated_period_days)

        if notice_respond_by is not None and notice_respond_by < respond_by:
            steps.append(ExplanationStep(
                code=StepCode.NOTICE_ASKS_SOONER,
                params={
                    "rule_date": str(respond_by),
                    "notice_date": str(notice_respond_by),
                },
            ))
            respond_by = notice_respond_by
            steps.append(ExplanationStep(
                code=StepCode.PLAN_FOR_EARLIER,
                params={"date": str(respond_by)},
            ))

        steps.append(ExplanationStep(
            code=StepCode.RESPOND_BY,
            params={"date": str(respond_by)},
        ))

        days_left = (respond_by - today).days
        status = _status_from_days(days_left)

        if status == DeadlineStatus.OVERDUE:
            steps.append(ExplanationStep(
                code=StepCode.OVERDUE_WARNING,
                params={"days": abs(days_left)},
            ))
        elif status == DeadlineStatus.DUE_TODAY:
            steps.append(ExplanationStep(
                code=StepCode.DUE_TODAY_WARNING,
                params={},
            ))

        steps.append(ExplanationStep(
            code=StepCode.DAYS_LEFT,
            params={"days": days_left},
        ))
        steps.append(ExplanationStep(code=StepCode.NO_HOLIDAY_ADJUSTMENT, params={}))

        return Deadline(
            respond_by=respond_by,
            days_left=days_left,
            status=status,
            basis=DeadlineBasis.RULEBOOK,
            provisional=provisional,
            steps=tuple(steps),
        )

    # --- Case 2: No rule, stated deadline ---
    if stated_by_date is not None:
        steps.append(ExplanationStep(
            code=StepCode.STATED_DATE_USED,
            params={"date": str(stated_by_date)},
        ))
        steps.append(ExplanationStep(
            code=StepCode.RESPOND_BY,
            params={"date": str(stated_by_date)},
        ))

        days_left = (stated_by_date - today).days
        status = _status_from_days(days_left)

        if status == DeadlineStatus.OVERDUE:
            steps.append(ExplanationStep(
                code=StepCode.OVERDUE_WARNING,
                params={"days": abs(days_left)},
            ))
        elif status == DeadlineStatus.DUE_TODAY:
            steps.append(ExplanationStep(
                code=StepCode.DUE_TODAY_WARNING,
                params={},
            ))

        steps.append(ExplanationStep(
            code=StepCode.DAYS_LEFT,
            params={"days": days_left},
        ))
        steps.append(ExplanationStep(code=StepCode.NO_HOLIDAY_ADJUSTMENT, params={}))

        return Deadline(
            respond_by=stated_by_date,
            days_left=days_left,
            status=status,
            basis=DeadlineBasis.STATED_IN_NOTICE,
            provisional=False,
            steps=tuple(steps),
        )

    if stated_period_days is not None:
        anchor = receipt_date or notice_date
        provisional = receipt_date is None and notice_date is not None
        if anchor is None:
            provisional = True

        if anchor is not None:
            if provisional:
                steps.append(ExplanationStep(
                    code=StepCode.RECEIPT_DATE_MISSING,
                    params={},
                ))
            steps.append(ExplanationStep(
                code=StepCode.STATED_PERIOD_USED,
                params={"days": stated_period_days},
            ))
            steps.append(ExplanationStep(
                code=StepCode.EXCLUDE_FIRST_DAY,
                params={},
            ))

            respond_by = _compute_respond_by(anchor, stated_period_days)
            steps.append(ExplanationStep(
                code=StepCode.RESPOND_BY,
                params={"date": str(respond_by)},
            ))

            days_left = (respond_by - today).days
            status = _status_from_days(days_left)

            if status == DeadlineStatus.OVERDUE:
                steps.append(ExplanationStep(
                    code=StepCode.OVERDUE_WARNING,
                    params={"days": abs(days_left)},
                ))
            elif status == DeadlineStatus.DUE_TODAY:
                steps.append(ExplanationStep(
                    code=StepCode.DUE_TODAY_WARNING,
                    params={},
                ))

            steps.append(ExplanationStep(
                code=StepCode.DAYS_LEFT,
                params={"days": days_left},
            ))
            steps.append(ExplanationStep(code=StepCode.NO_HOLIDAY_ADJUSTMENT, params={}))

            return Deadline(
                respond_by=respond_by,
                days_left=days_left,
                status=status,
                basis=DeadlineBasis.STATED_IN_NOTICE,
                provisional=provisional,
                steps=tuple(steps),
            )

    # --- Case 3: Nothing known ---
    steps.append(ExplanationStep(code=StepCode.NO_DEADLINE_FOUND, params={}))
    steps.append(ExplanationStep(code=StepCode.NO_HOLIDAY_ADJUSTMENT, params={}))

    return Deadline(
        respond_by=None,
        days_left=None,
        status=DeadlineStatus.UNKNOWN,
        basis=DeadlineBasis.UNKNOWN,
        provisional=False,
        steps=tuple(steps),
    )
