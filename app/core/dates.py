"""Parse dates in Indian legal notice formats.

Supports DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, D Month YYYY,
Dth Month, YYYY, Month D, YYYY. Numeric dates are day-first.
Invalid calendar dates are skipped. Two-digit years are ignored.
"""

from __future__ import annotations

import re
from datetime import date

from app.core.models import FoundDate

_MONTHS: dict[str, int] = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

_ORDINAL_SUFFIX = r"(?:st|nd|rd|th)"

# DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY (4-digit year only)
_NUMERIC_PAT = re.compile(
    r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b"
)

# D Month YYYY or Dth Month, YYYY (with optional ordinal and comma)
_DMY_PAT = re.compile(
    r"\b(\d{1,2})" + _ORDINAL_SUFFIX + r"?\s+"
    r"(" + "|".join(_MONTHS) + r")"
    r",?\s+(\d{4})\b",
    re.IGNORECASE,
)

# Month D, YYYY or Month Dth, YYYY
_MDY_PAT = re.compile(
    r"\b(" + "|".join(_MONTHS) + r")\s+"
    r"(\d{1,2})" + _ORDINAL_SUFFIX + r"?"
    r",?\s+(\d{4})\b",
    re.IGNORECASE,
)


def _safe_date(year: int, month: int, day: int) -> date | None:
    """Return a date or None if the calendar values are invalid."""
    try:
        return date(year, month, day)
    except ValueError:
        return None


def find_dates(text: str) -> list[FoundDate]:
    """Find all dates in *text* and return them with their positions.

    Numeric dates are interpreted day-first (DD/MM/YYYY), the Indian
    convention.  Invalid calendar dates (e.g. 31/02/2026) are skipped.
    Two-digit years are ignored.
    """
    results: list[FoundDate] = []
    seen_spans: set[tuple[int, int]] = set()

    def _add(d: date, start: int, end: int, raw: str) -> None:
        span = (start, end)
        if span not in seen_spans:
            seen_spans.add(span)
            results.append(FoundDate(value=d, start=start, end=end, raw=raw))

    for m in _NUMERIC_PAT.finditer(text):
        day_s, month_s, year_s = m.group(1), m.group(2), m.group(3)
        d = _safe_date(int(year_s), int(month_s), int(day_s))
        if d is not None:
            _add(d, m.start(), m.end(), m.group())

    for m in _DMY_PAT.finditer(text):
        day_s, month_name, year_s = m.group(1), m.group(2), m.group(3)
        month_num = _MONTHS[month_name.lower()]
        d = _safe_date(int(year_s), month_num, int(day_s))
        if d is not None:
            _add(d, m.start(), m.end(), m.group())

    for m in _MDY_PAT.finditer(text):
        month_name, day_s, year_s = m.group(1), m.group(2), m.group(3)
        month_num = _MONTHS[month_name.lower()]
        d = _safe_date(int(year_s), month_num, int(day_s))
        if d is not None:
            _add(d, m.start(), m.end(), m.group())

    results.sort(key=lambda fd: fd.start)
    return results
