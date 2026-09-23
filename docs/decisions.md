# Design decisions

One line per choice, with the alternative considered and why. Written as the
build went, not afterwards.

| Date | Decision | Rationale |
|---|---|---|
| 2026-09-21 | Repository hosted at `github.com/airz-raj/by-law` | Existing repository; the project is called Mohlat in code, in the interface and in this documentation |
| 2026-09-22 | Gemini model defaults to the `gemini-flash-latest` alias | `gemini-2.0-flash` had already been retired by the time the app first ran against the real API, and the only symptom the reader saw was "the reading service is not answering". An alias cannot be retired out from under the project. An exact id can still be pinned in `.env` for a reproducible build. Set only in `app/config.py` and `.env.example` |
| 2026-09-21 | No CORS middleware | The page and the API share an origin, so cross-origin calls stay blocked by the browser without any configuration |
| 2026-09-21 | No CSRF protection | No cookies and no session, so there is nothing for a forged request to ride on |
| 2026-09-21 | System fonts only | No third-party request, so the Content-Security-Policy needs no exception; the stack includes Devanagari faces for Hindi |
| 2026-09-22 | One `Rule` type in `app/core/models.py` | The rulebook returned one type and `compute_deadline` expected another, so the two could not be connected. A single type removes the class of bug rather than adapting between them |
| 2026-09-22 | `app/errors.py` is exempt from ruff's `N818` | The build contract names these exceptions `InputRejected`, `LLMUnavailable` and `LLMOutputInvalid`. The exemption is one line in `pyproject.toml`, not a global rule change |
| 2026-09-22 | The pipeline assembles the response models from `app/api/schemas.py` | The contract puts the report shape at the API boundary and has the pipeline fill it. `tests/unit/test_architecture.py` enforces what the layering is actually for: `app/core` imports nothing outward, and `app/api` reaches adapters only through `dependencies.py` |
| 2026-09-22 | Middleware returns problem responses rather than raising | Starlette runs middleware outside the exception-handling layer, so a raised error there surfaces as a bare 500. The rate limiter and the body-size guard are given a builder and return the response themselves |
| 2026-09-22 | No module-level `app` object | Importing `app.main` must not build a model client or read the environment. Uvicorn is pointed at the factory with `--factory` |
| 2026-09-22 | Settings refuse to start when the backend has no credentials | A missing key should fail at start-up with a sentence naming the variable, not on the first user's request |
| 2026-09-22 | `starlette` pinned explicitly, outside the six runtime dependencies | `pip-audit` reported seven advisories against the version `fastapi` resolved to. Pinning it stops a resolver picking a vulnerable one again. This is the one addition to the allowed runtime set, and it is a security fix |
| 2026-09-22 | `httpx2` instead of `httpx` as a development dependency | Starlette 1.6 deprecates using `httpx` with its test client. `httpx` remains installed as a runtime dependency of `google-genai` |
| 2026-09-22 | Delimiter tags are neutralised with U+FF1C, not stripped | The masked source is shown back to the reader, so the text should still read naturally. A full-width less-than sign looks like the original and cannot close a prompt delimiter |
| 2026-09-22 | Screening signals are grouped objects, not two parallel lists | The previous shape needed a list of patterns and a list of codes to stay in the same order. The planted line in the vacate sample was not caught by the old patterns |
| 2026-09-22 | Model fixtures are hand-written, not recorded from Gemini | `generativelanguage.googleapis.com` is not reachable from the build environment. Every quote in every fixture was checked to resolve against the masked sample before being committed, and no claim is made anywhere that they were recorded live |
| 2026-09-22 | Rule sources cite the India Code page for the Act | Each of the three URLs was fetched and confirmed to be the right Act. India Code disallows automated fetching of its section pages, so the section text itself was not machine-diffed — see the note below |
| 2026-09-23 | The model is a chain, not an id | `gemini-2.0-flash` was retired mid-build and `gemini-flash-latest` then returned `503 UNAVAILABLE — high demand` for an afternoon. Both took the whole product down with a generic outage message. A retired (404), rate-limited (429) or overloaded (5xx) model now costs a fallback; a rejected request (400/401/403) fails at once, because it would fail identically on every model |
| 2026-09-23 | `scripts/smoke.py`, outside the specified layout | Every other test runs against a fake, which leaves the prompts themselves unproven. This is the only check that calls the real model, so it is a separate target rather than part of `make test`, and it is excluded from the container image |
| 2026-09-23 | The Makefile resolves its own interpreter | Targets called `python`, which macOS does not ship, so `make smoke` failed with "No such file or directory" outside an activated venv. `PYTHON` now prefers `.venv/bin/python`, then an active venv, then `python3`, and every target runs it as `$(PYTHON) -m <tool>` so the tools come from the same environment as the code |

## Still to be checked by a person

India Code serves its section pages behind a `robots.txt` that disallows
automated fetching, so the three statutory rules in `app/data/rules_in.json`
were written from the statutes and their citations confirmed at the Act level,
but the section text was not diffed line by line by the build.

Before submission, confirm on India Code:

- Negotiable Instruments Act, 1881, s.138 proviso (b) and (c), and s.142(1)(b)
  — the 15 days from receipt, and the one month for the complaint.
- SARFAESI Act, 2002, s.13(2), s.13(3A) and s.13(4) — the 60 days from the date
  of the notice, and the 15 days for the lender's reasons.
- Transfer of Property Act, 1882, s.106 as amended in 2002 — the 15 days, and
  that the period runs from receipt of the notice.

The Section 12 categories and the NALSA helpline in `app/core/legal_aid.py`
were confirmed against nalsa.gov.in during the build.

## Hindi strings to review

The Hindi in `web/i18n/hi.json` and in the rulebook is written as Hindi rather
than translated word for word. These are worth a native reader's eye:

- `step_EXCLUDE_FIRST_DAY` — "साधारण खंड अधिनियम" for the General Clauses Act.
- `ai_body` — the sentence about text addressed to an AI has no settled Hindi
  idiom yet.
- `clause_UNDESERVED_WANT` — "अनुचित अभाव" is the phrase used for the Section 12
  category; the Act's own Hindi text may word it differently.

## Changed after auditing the finished build

A fresh-eyes audit was run over the completed repository, checking every
claim in the README against the code and probing the defences. It found
real defects; these are what changed.

| Finding | Change |
|---|---|
| The rate limiter read the **leftmost** `X-Forwarded-For` entry, which a caller writes. Rotating a fake address walked straight past the limit, and a test asserted that behaviour as correct | The client is counted in from the right by `trusted_proxy_hops`, because each proxy appends and only the rightmost entries are written by infrastructure we control. The test that certified the bug was replaced by one that rotates a spoofed entry and expects it to be refused |
| Bucket storage was an unbounded dict, so the same flood was also a slow memory leak | Buckets are an `OrderedDict` capped at 4096 least-recently-seen clients |
| The model adapter caught only `OSError` and `RuntimeError`. The SDK raises httpx errors, which are neither, so a real outage surfaced as an unhandled 500 rather than the 503 the front end knows how to explain | Any exception from the SDK call becomes `LLMUnavailable`. The test that "covered" this raised an `OSError` the SDK never produces |
| A 500 went out with no Content-Security-Policy, no request id and no `Cache-Control`, because Starlette's server-error handler sits outside the middleware stack | The headers are attached where the problem response is built, so they reach every answer including that one |
| The README said PDF parsing loaded only when a PDF arrived; `import pypdf` was at module level | The import moved inside the PDF branch, and the claim is now true |
| A 101 KB PDF whose streams expanded to 33 MB took 27 seconds and ~100 MB before the length check ran | Extraction stops as soon as the accumulated text passes the limit |
| A `Transfer-Encoding: chunked` body walked past the size guard, which read only `Content-Length` | The guard is now pure ASGI and counts the bytes as they arrive |
| An over-large form part produced Starlette's own JSON error, outside the problem contract, naming an internal limit | Mapped to a problem response like every other failure |
| The PAN pattern was case-sensitive, so a lowercase PAN reached the model. Aadhaar and phone numbers leaked in several common groupings | Patterns widened; the leaking forms are now parametrised tests |
| Screening caught 1 of 11 realistic injection attempts, and the delimiter neutraliser was bypassable with a zero-width space or a soft hyphen | Signals were widened to 11 of 11 with no false positives on the ordinary legal language tested, and invisible characters are stripped before matching. The README no longer presents this as more than a pattern list |
| `escapeText` in the calendar export used `'\;'`, which is not an escape in JavaScript, so semicolons were never escaped. The test's expectation carried the same broken escape, so it passed either way | Fixed, and the test rewritten with `String.raw` plus an assertion that escaping changes the string at all |
| The agreement file input had no label — an axe violation of critical impact. The accessibility tests never rendered the four interactive sections, so they could not see it | Labelled, and the axe tests now render the full report state and assert on `incomplete` as well as `violations` |
| `aria-labelledby="report-heading"` pointed at an element that did not exist | The heading exists; a test now checks every `aria-labelledby` and `aria-describedby` on the page resolves |
| The briefing sheet read `report.notice_label`, which the API never returns, so the notice type showed as a dash whenever no rule matched | Reads the classification, with a translated fallback |
| Switching language moved focus to the top of the report, and left model-written prose in the previous language with no explanation | Focus stays where it is, and a note says the explanation was written in the language chosen before reading |
| A network failure rendered the literal string `network_error` | Mapped to a translated sentence |
| `notice_text` and question documents had no length cap, so `max_document_chars` never applied to them | Both capped at the document limit |
| `isSafeHref` accepted `//evil.com` as same-origin | Protocol-relative URLs are refused |
| Dead code: an unused `SECTIONS` export, an unused `EXTRA_SECTIONS` kept alive by `void`, a pointless re-export, and an unused placeholder pattern | Removed |
