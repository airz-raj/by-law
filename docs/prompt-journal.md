# Prompt journal

What was built in each phase, and the prompts behind it. Evidence that the work
is original, and the raw material for a write-up afterwards.

## Build log

| Phase | What was built | Date |
|---|---|---|
| 0 | Repository set up: the README as the product contract, `.gitignore`, the docs skeleton | 2026-09-21 |
| 1 | Tooling and gates: ruff, `mypy --strict`, pytest with a coverage gate, bandit, pip-audit, the web toolchain, and CI running all of it | 2026-09-21 |
| 2 | The domain core, tests first: date parsing in Indian formats, quote confirmation, identifier masking, respond-by computation, the rulebook, screening, the Section 12 check, and an architecture test that fails the build if the dependencies ever point outward | 2026-09-21 |
| 3 | Adapters: upload validation and text extraction, the content-hash cache, the Gemini port with schema-validated output, and versioned prompts | 2026-09-21 |
| 4 | The model contract rewritten to match the report the product promises; the pipeline, the seven endpoints, RFC 9457 problem responses, request ids, security headers, rate limiting and a body-size guard | 2026-09-22 |
| 5 | The design plan, then the page: semantic HTML, four stylesheets, sixteen ES modules, and the Hindi interface | 2026-09-22 |
| 6 | The four sample documents and the model fixtures built against them | 2026-09-22 |
| 7 | The container image and the deployment guide for both Cloud Run options | 2026-09-22 |
| 8 | The quality gate: dependency upgrades away from fifteen advisories, the hygiene and secret sweeps, and the measured results in the README | 2026-09-22 |

## What each phase was asked for

Phases 0 to 3 were built from `.agents/workflows/build-mohlat.md`, which sets
the contract: the README is the product, the model reads and the code decides,
and no phase is done with a failing check.

The later phases were driven by the same document, with these specific
instructions worth recording because they shaped the result:

- **"Every quote is a receipt."** The model must return the exact line, and the
  code locates it in the source. If it is not there, the claim is shown as
  unconfirmed rather than passed off as fact. This is why `app/core/evidence.py`
  does no fuzzy matching at all.
- **"Classification needs two votes."** A notice is matched to a rule only when
  the model's label and keyword evidence in the text agree. A confident but
  wrong label cannot on its own decide a deadline.
- **"The model reads; the code decides."** Nothing a reader might rely on comes
  from the model's arithmetic. The deadline comes from `app/core/deadlines.py`
  and a rulebook of statutory periods.
- **"Documents are data."** Text inside a document is never treated as an
  instruction, and text that tries to instruct a reading model is surfaced to
  the user instead.
- **"Never state a number you didn't measure."** Every row of the README's
  Measured table was produced by running the command next to it. The rows that
  need a deployment say so rather than carrying an estimate.

## Where the build pushed back

Three things in the plan turned out to be wrong when they met the code, and were
changed rather than worked around:

1. The rulebook and the deadline calculator used two different rule types, so
   the pipeline could not connect them. Both now use one type.
2. Middleware that raised an error produced a bare 500, because Starlette runs
   middleware outside the exception-handling layer. The oversized-body test
   caught it.
3. The screening patterns did not catch the line planted in the vacate sample,
   which was the one thing that sample existed to demonstrate.

A browser test also caught advice-shaped wording in the interface copy — "you
should know it is there" — which the product is not supposed to use. The copy
changed, not the test.
