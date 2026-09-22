"""Mask personal identifiers before text reaches the model.

Order: email → Aadhaar (Verhoeff-validated) → PAN → phone → bank account.
The same value always gets the same placeholder within one call.
Placeholders already in the text pass through unchanged.
"""

from __future__ import annotations

import re

from app.core.models import Redaction

# ---------------------------------------------------------------------------
# Verhoeff checksum tables for Aadhaar validation
# ---------------------------------------------------------------------------

_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]

_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]

_VERHOEFF_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def _verhoeff_checksum(number: str) -> bool:
    """Validate a number string using the Verhoeff algorithm."""
    c = 0
    digits = [int(d) for d in reversed(number)]
    for i, digit in enumerate(digits):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][digit]]
    return c == 0


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

_EMAIL_PAT = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

_AADHAAR_PAT = re.compile(r"(?<![\d])([2-9]\d{3})[\s\-.]{0,2}(\d{4})[\s\-.]{0,2}(\d{4})(?![\d])")

_PAN_PAT = re.compile(r"\b[A-Za-z]{5}[0-9]{4}[A-Za-z]\b")

# Ten digits beginning 6-9, however they are grouped: a separator may sit
# between any two of them. The lookarounds stop a longer digit run matching
# its own tail.
_PHONE_PAT = re.compile(r"(?<![\d])(?:\+91[\s\-.]?|0)?([6-9](?:[\s\-.]?\d){9})(?![\d])")

_ACCOUNT_KEYWORD_PAT = re.compile(
    r"(?:a/c|account\s*no|account|acct)[\s.:]*",
    re.IGNORECASE,
)

_DIGITS_IN_WINDOW = re.compile(r"\d[\d\s\-]{7,22}\d")

_PLACEHOLDER_PAT = re.compile(r"\[(EMAIL|AADHAAR|PAN|PHONE|ACCOUNT)-\d+\]")


def redact(text: str) -> Redaction:
    """Mask personal identifiers and return the masked text with counts.

    The same value always gets the same placeholder within one call.
    Placeholders already in the text pass through unchanged.
    """
    seen: dict[str, str] = {}
    counts: dict[str, int] = {
        "EMAIL": 0,
        "AADHAAR": 0,
        "PAN": 0,
        "PHONE": 0,
        "ACCOUNT": 0,
    }

    def _placeholder(category: str, value: str) -> str:
        if value in seen:
            return seen[value]
        counts[category] += 1
        tag = f"[{category}-{counts[category]}]"
        seen[value] = tag
        return tag

    # 1. Email
    def _replace_email(m: re.Match[str]) -> str:
        return _placeholder("EMAIL", m.group())

    text = _EMAIL_PAT.sub(_replace_email, text)

    # 2. Aadhaar (Verhoeff-validated)
    def _replace_aadhaar(m: re.Match[str]) -> str:
        digits = m.group(1) + m.group(2) + m.group(3)
        if _verhoeff_checksum(digits):
            return _placeholder("AADHAAR", digits)
        return m.group()

    text = _AADHAAR_PAT.sub(_replace_aadhaar, text)

    # 3. PAN
    def _replace_pan(m: re.Match[str]) -> str:
        return _placeholder("PAN", m.group().upper())

    text = _PAN_PAT.sub(_replace_pan, text)

    # 4. Phone
    def _replace_phone(m: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", m.group(1))
        return _placeholder("PHONE", digits)

    text = _PHONE_PAT.sub(_replace_phone, text)

    # 5. Bank account numbers (only near a keyword)
    def _replace_accounts(text: str) -> str:
        result = text
        for kw_match in _ACCOUNT_KEYWORD_PAT.finditer(text):
            window_start = kw_match.end()
            window_end = min(window_start + 25, len(text))
            window = text[window_start:window_end]
            for digit_match in _DIGITS_IN_WINDOW.finditer(window):
                raw = digit_match.group()
                digits_only = re.sub(r"[\s\-]", "", raw)
                if 9 <= len(digits_only) <= 18:
                    placeholder = _placeholder("ACCOUNT", digits_only)
                    abs_start = window_start + digit_match.start()
                    abs_end = window_start + digit_match.end()
                    result = result[:abs_start] + placeholder + result[abs_end:]
                    break
        return result

    text = _replace_accounts(text)

    return Redaction(text=text, counts={k: v for k, v in counts.items() if v > 0})
