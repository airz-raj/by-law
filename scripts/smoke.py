"""Run the sample notices through the real model and report what came back.

Every other test in this repository runs against a fake, which is what
keeps the suite fast and offline. That leaves one thing unproven: whether
the prompts actually produce output that fits the schema, and whether the
model copies quotes exactly enough for them to be confirmed against the
source.

This is the check for that. It costs real model calls, so it is not part
of ``make test``.

    make smoke

It prints, per sample: which model answered, whether the rulebook matched,
the respond-by date, and how many of the model's quotes were confirmed in
the document. It exits non-zero if the confirmation rate falls below
:data:`MINIMUM_CONFIRMED`, because a report whose receipts nearly all say
"not found" is worse than no report.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from app.adapters.cache import TTLCache
from app.adapters.llm import GeminiLLM
from app.api.dependencies import get_rulebook
from app.config import Settings
from app.core.models import Language
from app.observability import configure_logging
from app.services import pipeline
from app.services.prompts import ReadingLevel

#: The share of quotes that must be found word for word in the source.
#: Receipts are the product's central claim; below this it is not working.
MINIMUM_CONFIRMED = 0.80

#: Samples to run, and the rule each should match.
SAMPLES: tuple[tuple[str, str | None], ...] = (
    ("cheque-demand-notice", "in.ni_act.s138_demand"),
    ("bank-demand-notice", "in.sarfaesi.s13_2_demand"),
    ("vacate-notice", "in.tpa.s106_termination"),
)

SAMPLES_DIR = "web/samples"
TICK = "✓"
CROSS = "✗"


@dataclass(frozen=True, slots=True)
class Outcome:
    """What one sample produced."""

    name: str
    expected_rule: str | None
    matched_rule: str | None
    respond_by: date | None
    confirmed: int
    total: int
    screening: tuple[str, ...]
    model: str | None = None
    error: str | None = None

    @property
    def rate(self) -> float:
        """The share of quotes confirmed in the source."""
        return self.confirmed / self.total if self.total else 0.0

    @property
    def rule_is_right(self) -> bool:
        """Whether the rulebook matched what this sample should match."""
        return self.matched_rule == self.expected_rule


def read_sample(name: str) -> str:
    """Read one sample document."""
    with open(f"{SAMPLES_DIR}/{name}.txt", encoding="utf-8") as handle:
        return handle.read()


def count_receipts(report: object) -> tuple[int, int]:
    """Count confirmed and total quotes across every part of a report."""
    decoded = report
    receipts = [
        *(demand.receipt for demand in decoded.demands),  # type: ignore[attr-defined]
        *(ref.receipt for ref in decoded.cited_references),  # type: ignore[attr-defined]
        *(mention.receipt for mention in decoded.dates),  # type: ignore[attr-defined]
    ]
    return sum(1 for receipt in receipts if receipt.found), len(receipts)


async def run_sample(
    name: str,
    expected: str | None,
    settings: Settings,
    llm: GeminiLLM,
    cache: TTLCache,
) -> Outcome:
    """Decode one sample against the real model."""
    today = datetime.now(UTC).date()
    try:
        report, _ = await pipeline.decode_notice(
            text=read_sample(name),
            receipt_date=today - timedelta(days=3),
            language=Language.EN,
            reading_level=ReadingLevel.SIMPLE,
            llm=llm,
            cache=cache,
            rules=get_rulebook(),
            today=today,
            settings=settings,
            request_id=f"smoke-{name}",
        )
    except Exception as error:  # The report is the point here, not a traceback.
        detail = str(error) or type(error).__name__
        return Outcome(name, expected, None, None, 0, 0, (), error=detail)

    confirmed, total = count_receipts(report)
    return Outcome(
        name=name,
        expected_rule=expected,
        matched_rule=report.classification.rule.id if report.classification.rule else None,
        respond_by=report.deadline.respond_by,
        confirmed=confirmed,
        total=total,
        screening=tuple(report.screening.ai_directed),
        model=llm.last_model,
    )


def describe(outcome: Outcome) -> str:
    """One line summarising a sample."""
    if outcome.error:
        return f"  {CROSS} {outcome.name}: failed ({outcome.error})"

    rule_mark = TICK if outcome.rule_is_right else CROSS
    quote_mark = TICK if outcome.rate >= MINIMUM_CONFIRMED else CROSS
    rule = outcome.matched_rule or "no rule matched"
    return (
        f"  {rule_mark} {outcome.name}\n"
        f"      answered by {outcome.model or 'unknown'}\n"
        f"      rule       {rule}\n"
        f"      respond by {outcome.respond_by or 'not established'}\n"
        f"      quotes     {quote_mark} {outcome.confirmed}/{outcome.total} "
        f"confirmed ({outcome.rate:.0%})"
        + (f"\n      screening  {', '.join(outcome.screening)}" if outcome.screening else "")
    )


async def main() -> int:
    """Run every sample and report. Returns the process exit code."""
    # The app configures JSON logging inside create_app, which this script
    # does not call. Without it the failover warnings print their message
    # and drop the model and reason, which are the useful parts.
    configure_logging("WARNING")
    logging.getLogger("google_genai").setLevel(logging.ERROR)

    settings = Settings()
    print(f"Model chain: {' -> '.join(settings.model_chain)}")
    print(f"Backend:     {settings.llm_backend}\n")

    # One client and one cache across the samples, as the running app has.
    llm = GeminiLLM(settings)
    cache = TTLCache(settings)
    outcomes = [await run_sample(name, rule, settings, llm, cache) for name, rule in SAMPLES]
    for outcome in outcomes:
        print(describe(outcome))
        print()

    failed = [o for o in outcomes if o.error]
    wrong_rule = [o for o in outcomes if not o.error and not o.rule_is_right]
    weak_quotes = [o for o in outcomes if not o.error and o.rate < MINIMUM_CONFIRMED]

    if failed:
        print(f"{CROSS} {len(failed)} sample(s) did not complete.")
    if wrong_rule:
        print(f"{CROSS} {len(wrong_rule)} sample(s) matched the wrong rule.")
    if weak_quotes:
        print(
            f"{CROSS} {len(weak_quotes)} sample(s) fell below "
            f"{MINIMUM_CONFIRMED:.0%} confirmed quotes. The model is paraphrasing "
            "rather than copying; tighten the quote instruction in "
            "app/services/prompts.py and bump PROMPT_VERSION."
        )
    if not (failed or wrong_rule or weak_quotes):
        print(f"{TICK} Every sample decoded, matched its rule, and confirmed its quotes.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
