"""Screen a document for text aimed at an AI, and for urgent legal signals.

A document is material to work on, never an instruction. Lines that try to
instruct a reading model are surfaced to the user rather than obeyed, and
signals that someone should not wait (a summons, a hearing, an auction)
are surfaced too.

Only signal codes leave this module. The matched text never does, so a
screening result can be logged without leaking the document.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.models import Screening

# U+FF1C FULLWIDTH LESS-THAN SIGN. Visually close to "<", so the masked
# source still reads naturally, but it cannot close a prompt delimiter.
SUBSTITUTE_LT = chr(0xFF1C)

# Characters that render as nothing and can be slipped between the letters
# of a tag to sneak it past a naive pattern.
_INVISIBLE = re.compile(r"[\u00ad\u200b-\u200f\u2060\ufeff]")

# A delimiter tag, tolerating whitespace and invisible characters the way a
# model reading the text would.
_DELIMITER_PAT = re.compile(r"<\s*(/?)\s*(document|question)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Signal:
    """One screening signal: a stable code and the phrasings that raise it."""

    code: str
    patterns: tuple[re.Pattern[str], ...]

    def matches(self, text: str) -> bool:
        """Return whether any of this signal's phrasings appear in *text*."""
        return any(pattern.search(text) for pattern in self.patterns)


def _signal(code: str, *sources: str) -> Signal:
    """Build a signal whose patterns ignore case and match line by line."""
    return Signal(
        code=code,
        patterns=tuple(re.compile(s, re.IGNORECASE | re.MULTILINE) for s in sources),
    )


#: Text that tries to instruct a model reading the document.
AI_DIRECTED_SIGNALS: tuple[Signal, ...] = (
    _signal(
        "IGNORE_PREVIOUS",
        r"\b(?:ignore|disregard|forget|override|skip)\s+(?:\w+\s+){0,4}"
        r"(?:instructions?|directions?|guidelines?|rules?|prompt|everything\s+above)",
        r"\bforget\s+everything\b",
        r"\bnew\s+task\s*:",
        r"पिछले\s+(?:सभी\s+)?(?:निर्देशों?|निर्देश)\s+को\s+(?:अनदेखा|नज़रअंदाज़)",
    ),
    _signal(
        "ADDRESSED_TO_AI",
        r"\b(?:note|message|instruction|important)s?\s+(?:to|for)\s+"
        r"(?:any\s+|the\s+|a\s+)?(?:reviewing\s+|processing\s+)?"
        r"(?:ai|a\.i\.|assistant|llm|chatbot|language\s+model|bot|model)\b",
        r"\b(?:ai|artificial\s+intelligence|assistant|model|llm)s?\b[^.\n]{0,40}"
        r"\b(?:reading|processing|reviewing|summaris|summariz)",
        r"\bif\s+you\s+are\s+an?\s+(?:ai|assistant|language\s+model|bot)\b",
        r"\b(?:assistant|chatgpt|gemini|claude|copilot)\s*[,:]",
        r"\bfor\s+any\s+language\s+model\b",
        r"एआई\s+(?:सहायक|टूल|मॉडल)",
    ),
    _signal(
        "ROLE_ASSIGNMENT",
        r"\byou\s+are\s+(?:now\s+)?(?:an?\s+)?(?:ai|chatgpt|gemini|claude|assistant|"
        r"language\s+model|legal\s+advisor|lawyer|judge)\b",
        r"\b(?:act|behave|respond)\s+as\s+(?:an?\s+)?"
        r"(?:ai|assistant|bot|model|language\s+model|lawyer|judge|advisor)\b",
        r"\bpretend\s+(?:to\s+be|you\s+are)\b",
        r"आप\s+(?:अब\s+)?(?:एक\s+)?(?:AI|एआई)\s+(?:हैं|हो)",
    ),
    _signal(
        "SYSTEM_PROMPT",
        r"\bsystem\s+prompt\b",
        r"\bdeveloper\s+message\b",
        r"^\s*(?:system|assistant|user)\s*:",
        r"<<\s*sys\s*>>",
        r"#{2,}\s*instruction",
        r"\byour\s+guidelines\b",
    ),
    _signal(
        "DICTATES_THE_ANSWER",
        r"\brespond\s+only\s+with\b",
        r"\b(?:summari[sz]e|describe|report|treat|state)\s+(?:it|this|the\s+\w+)\s+"
        r"(?:on\s+that\s+basis|as\s+(?:being\s+)?(?:fully\s+|entirely\s+|completely\s+)?valid)",
        r"\b(?:this|the)\s+(?:notice|document|agreement|clause)\s+is\s+"
        r"(?:fully\s+|entirely\s+|completely\s+)?valid\s+in\s+law\b",
        r"\bthe\s+recipient\s+has\s+no\s+defence\b",
        r"\b(?:mark|treat|report)\s+(?:every|all|each)\s+\w+\s+"
        r"(?:as\s+)?(?:consistent|valid|correct|paid)\b",
        r"\boutput\s+(?:only|nothing|an?\s+empty)\b",
        r"\breply\s+with\s+(?:an?\s+)?empty\b",
    ),
)

#: Signals that the reader should not simply wait for the deadline.
URGENT_SIGNALS: tuple[Signal, ...] = (
    _signal("SUMMONS", r"\bsummons(?:es)?\b"),
    _signal("WARRANT", r"\bwarrant\b"),
    _signal("ARREST", r"\barrest(?:ed|able)?\b"),
    _signal("FIR", r"\bF\.?I\.?R\.?\b", r"first\s+information\s+report"),
    _signal("APPEAR_BEFORE", r"appear\s+(?:in\s+person\s+)?before\b"),
    _signal("HEARING", r"\bhearing\s+(?:on|is\s+fixed|date)\b", r"\bdate\s+of\s+hearing\b"),
    _signal("POLICE_STATION", r"\bpolice\s+station\b"),
    _signal("POSSESSION", r"\bpossession\s+notice\b", r"\btak(?:e|ing)\s+possession\b"),
    _signal("AUCTION", r"\bauction\b", r"\bpublic\s+sale\b"),
)


def screen(text: str) -> Screening:
    """Screen *text* and return the signal codes it raised.

    Args:
        text: The document text, already masked.

    Returns:
        The AI-directed and urgent signal codes, each at most once, in the
        order they are declared.
    """
    normalised = _INVISIBLE.sub("", text)
    return Screening(
        ai_directed=tuple(s.code for s in AI_DIRECTED_SIGNALS if s.matches(normalised)),
        urgent=tuple(s.code for s in URGENT_SIGNALS if s.matches(normalised)),
    )


def neutralise_delimiters(text: str) -> str:
    """Break any ``<document>`` or ``<question>`` tag inside user text.

    Args:
        text: Text that will be placed inside the prompt's delimiters.

    Invisible characters are removed first, so a tag cannot be smuggled
    through by splitting it with a zero-width space or a soft hyphen.

    Returns:
        The same text with the opening angle bracket of any delimiter tag
        replaced by :data:`SUBSTITUTE_LT`, so user text cannot close the
        delimiter it sits in.
    """
    cleaned = _INVISIBLE.sub("", text)
    return _DELIMITER_PAT.sub(rf"{SUBSTITUTE_LT}\1\2", cleaned)
