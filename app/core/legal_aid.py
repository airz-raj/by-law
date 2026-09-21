"""Check Section 12 legal-aid eligibility under the Legal Services Authorities Act, 1987.

Categories verified against nalsa.gov.in and the Act on India Code.
Income limits vary by state; we never hard-code an amount.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.core.models import EligibilityResult, Section12Clause


@dataclass(frozen=True, slots=True)
class LegalAidAnswers:
    """User answers for the Section 12 eligibility check."""

    sc_st: bool = False
    trafficking_begar: bool = False
    woman_or_child: bool = False
    disability: bool = False
    undeserved_want: bool = False
    industrial_workman: bool = False
    custody: bool = False
    income_below_state_limit: Literal["yes", "no", "unsure"] = "unsure"


_CLAUSE_MAP: list[tuple[str, Section12Clause]] = [
    ("sc_st", Section12Clause.SC_ST),
    ("trafficking_begar", Section12Clause.TRAFFICKING_BEGAR),
    ("woman_or_child", Section12Clause.WOMAN_OR_CHILD),
    ("disability", Section12Clause.DISABILITY),
    ("undeserved_want", Section12Clause.UNDESERVED_WANT),
    ("industrial_workman", Section12Clause.INDUSTRIAL_WORKMAN),
    ("custody", Section12Clause.CUSTODY),
]

NEXT_STEP_CONTACT_DLSA = "CONTACT_DLSA"
NEXT_STEP_CALL_NALSA = "CALL_NALSA_15100"
NEXT_STEP_PRIMA_FACIE = "PRIMA_FACIE_REQUIRED"
NEXT_STEP_CHECK_INCOME_LIMIT = "CHECK_STATE_INCOME_LIMIT"


def check_eligibility(answers: LegalAidAnswers) -> EligibilityResult:
    """Evaluate Section 12 eligibility from user answers.

    Next steps always include contacting the DLSA and the NALSA helpline,
    and note that the authority must also be satisfied there is a prima
    facie case (s.13).
    """
    matched: list[Section12Clause] = []

    for field_name, clause in _CLAUSE_MAP:
        if getattr(answers, field_name):
            matched.append(clause)

    income_check_needed = False
    if answers.income_below_state_limit == "yes":
        matched.append(Section12Clause.INCOME_BELOW_LIMIT)
    elif answers.income_below_state_limit == "unsure":
        income_check_needed = True

    likely_eligible = len(matched) > 0

    next_steps: list[str] = [
        NEXT_STEP_CONTACT_DLSA,
        NEXT_STEP_CALL_NALSA,
        NEXT_STEP_PRIMA_FACIE,
    ]

    if income_check_needed:
        next_steps.append(NEXT_STEP_CHECK_INCOME_LIMIT)

    return EligibilityResult(
        likely_eligible=likely_eligible,
        matched=tuple(matched),
        income_check_needed=income_check_needed,
        next_steps=tuple(next_steps),
    )
