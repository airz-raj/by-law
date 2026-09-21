# Design decisions

This log records choices made during the build. Each entry notes the decision, the alternative considered and why, and the date.

| Date | Decision | Rationale |
|---|---|---|
| 2026-09-21 | Repository hosted at `github.com/airz-raj/by-law` | Existing repo; project name remains Mohlat in code and UI |
| 2026-09-21 | Gemini model: `gemini-2.0-flash` | Newest GA Flash-tier model in Google AI Studio at build time |
| 2026-09-21 | No CORS middleware | Page and API share an origin; cross-origin calls stay blocked |
| 2026-09-21 | No CSRF protection | No cookies, so nothing for CSRF to ride on |
| 2026-09-21 | System fonts only, no external fonts | No third-party CDN requests; Devanagari coverage via Noto Sans Devanagari and Kohinoor Devanagari |
