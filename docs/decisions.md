# Design decisions

One line per choice, with the alternative considered and why. Written as the
build went, not afterwards.

| Date | Decision | Rationale |
|---|---|---|
| 2026-09-21 | Repository hosted at `github.com/airz-raj/by-law` | Existing repository; the project is called Mohlat in code, in the interface and in this documentation |
| 2026-09-21 | Gemini model `gemini-2.0-flash` | Newest generally available Flash-tier model in Google AI Studio at build time; set only in `app/config.py` and `.env.example` |
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
