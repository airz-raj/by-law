"""Pydantic schemas for structured LLM outputs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Notice Extraction
# ---------------------------------------------------------------------------


class ExtractedDate(BaseModel):
    """A date found in the text."""
    date_str: str = Field(description="The date exactly as written in the text")
    context: str = Field(description="A short snippet showing why this date is relevant")


class ExtractedDemand(BaseModel):
    """A specific demand made in the notice."""
    amount_or_action: str = Field(description="What is being demanded (e.g. Rs 50,000 or 'vacate premises')")
    deadline: str | None = Field(description="The deadline given for this demand, if any")
    quote: str = Field(description="Exact 5-10 word quote from the text stating this demand")


class NoticeExtraction(BaseModel):
    """The key details extracted from a legal notice."""
    sender_name: str | None = Field(description="Name of the person or entity sending the notice")
    recipient_name: str | None = Field(description="Name of the person receiving the notice")
    dates_found: list[ExtractedDate] = Field(description="All dates mentioned in the notice")
    demands: list[ExtractedDemand] = Field(description="The specific actions or payments demanded")
    stated_deadline_days: int | None = Field(description="Number of days given to respond, if stated as a period")
    stated_deadline_date: str | None = Field(description="Exact date given to respond by, if stated as a date")


# ---------------------------------------------------------------------------
# Cross-Check Extraction
# ---------------------------------------------------------------------------


class ClaimExtraction(BaseModel):
    """A factual claim made by the sender."""
    claim: str = Field(description="The factual claim made by the sender")
    quote: str = Field(description="Exact 5-10 word quote from the text stating this claim")


class CrossCheckExtraction(BaseModel):
    """Factual claims that need to be verified by the recipient."""
    claims_to_verify: list[ClaimExtraction] = Field(
        description="List of factual claims the recipient should confirm or deny"
    )


# ---------------------------------------------------------------------------
# Lawyer Questions
# ---------------------------------------------------------------------------


class QuestionForLawyer(BaseModel):
    """A drafted question for a lawyer."""
    question: str = Field(description="The question to ask the lawyer")
    reasoning: str = Field(description="Why this question is important to ask")


class DraftQuestions(BaseModel):
    """Questions drafted for the user to ask a lawyer."""
    questions: list[QuestionForLawyer] = Field(description="List of questions to ask the lawyer")
