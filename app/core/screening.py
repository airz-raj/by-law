"""Screen documents for AI-directed instructions and urgent legal signals.

Returns signal codes, not matched text, to avoid leaking document content.
"""

from __future__ import annotations

import re

from app.core.models import Screening

# ---------------------------------------------------------------------------
# AI-directed instruction patterns
# ---------------------------------------------------------------------------

_AI_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(?:all|any|the)\s+(?:previous|prior|above)\s+instructions", re.I),
    re.compile(r"disregard\s+[\w\s]*instructions", re.I),
    re.compile(r"system\s+prompt", re.I),
    re.compile(r"you\s+are\s+(?:now\s+)?(?:an?\s+AI|ChatGPT|Gemini|an?\s+assistant)", re.I),
    re.compile(r"note\s+to\s+AI", re.I),
    re.compile(r"respond\s+only\s+with", re.I),
    re.compile(r"\bact\s+as\s+(?:a\s+|an\s+)?(?:AI|assistant|bot|model|language\s+model)\b", re.I),
    re.compile(r"(?:describe|report|state)\s+(?:this|the)\s+(?:notice|document)\s+as\s+(?:fully\s+)?valid", re.I),  # noqa: E501
    # Hindi equivalents
    re.compile(r"पिछले\s+(?:सभी\s+)?निर्देशों?\s+को\s+(?:अनदेखा|नज़रअंदाज़)\s+कर", re.I),
    re.compile(r"आप\s+(?:अब\s+)?(?:एक\s+)?(?:AI|एआई)\s+(?:हैं|हो)", re.I),
]

_AI_CODES: list[str] = [
    "IGNORE_PREVIOUS",
    "DISREGARD_INSTRUCTIONS",
    "SYSTEM_PROMPT",
    "ROLE_ASSIGNMENT",
    "NOTE_TO_AI",
    "RESPOND_ONLY_WITH",
    "ACT_AS_AI",
    "DESCRIBE_AS_VALID",
    "IGNORE_PREVIOUS_HI",
    "ROLE_ASSIGNMENT_HI",
]

# ---------------------------------------------------------------------------
# Urgent legal patterns
# ---------------------------------------------------------------------------

_URGENT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bsummons\b", re.I),
    re.compile(r"\bwarrant\b", re.I),
    re.compile(r"\barrest\b", re.I),
    re.compile(r"\bFIR\b"),
    re.compile(r"appear\s+before", re.I),
    re.compile(r"hearing\s+on", re.I),
    re.compile(r"police\s+station", re.I),
    re.compile(r"possession\s+notice", re.I),
    re.compile(r"\bauction\b", re.I),
]

_URGENT_CODES: list[str] = [
    "SUMMONS",
    "WARRANT",
    "ARREST",
    "FIR",
    "APPEAR_BEFORE",
    "HEARING_ON",
    "POLICE_STATION",
    "POSSESSION_NOTICE",
    "AUCTION",
]


def screen(text: str) -> Screening:
    """Screen text for AI-directed instructions and urgent legal signals.

    Returns signal codes only, never the matched text itself.
    """
    ai_directed: list[str] = []
    for pattern, code in zip(_AI_PATTERNS, _AI_CODES, strict=True):
        if pattern.search(text):
            ai_directed.append(code)

    urgent: list[str] = []
    for pattern, code in zip(_URGENT_PATTERNS, _URGENT_CODES, strict=True):
        if pattern.search(text):
            urgent.append(code)

    return Screening(
        ai_directed=tuple(ai_directed),
        urgent=tuple(urgent),
    )


def neutralise_delimiters(text: str) -> str:
    """Break any ``<document`` or ``</document`` sequence in user text.

    This prevents user-supplied text from closing the prompt's XML-like
    delimiters.
    """
    text = re.sub(r"<(/?)document", r"＜\1document", text)
    return text
