# Design plan

Written before any CSS, so the page has a point of view rather than a theme.

## Who is reading this

Someone who has just opened a registered-post envelope and found a legal
notice inside. They are anxious, they may be on a phone, and they may be
more comfortable reading Hindi than English. They are not browsing. They
want one thing first: **by when, and what now?**

Everything on the page is ordered by that. The respond-by date is the only
element allowed to be loud. Everything else stays quiet so the date can be
heard.

## The one bold element: the postmark

The respond-by date is drawn as a postmark: a circular double ring, rotated
a few degrees off true, the date large inside it, the days remaining beneath.
It is navy ink normally. It turns maroon when three days or fewer remain, or
when the date has passed.

Colour is never the only signal. The stamp's own text says which state it is
in — "Overdue by 4 days", "Due today", "12 days left" — so the state survives
greyscale, colour blindness and a screen reader.

It is the page's single animated moment: a short press on first render, as if
the stamp had just come down. Skipped entirely under
`prefers-reduced-motion: reduce`.

Why a postmark: the notice arrived by post, the date is the thing the post
started, and a stamp is the one object in this world that means "a date was
fixed on a day". It is a metaphor the reader already owns.

## Everything else stays quiet

- Left-aligned text, generous spacing, one column of content.
- No card grid, no gradients, no shadows beyond the one under the stamp.
- No emoji, no all-caps labels, no eyebrow labels above headings, no
  middle-dot metadata strings, no arrows appended to buttons.
- Section headings are plain and say what is under them: "In short",
  "What they want", "Your options".

## Palette

Every pair below was checked for contrast against the background it sits on.

| Token | Value | Use | Contrast on paper |
|---|---|---|---|
| `--paper` | `#F3F5F2` | page background (cool, not cream) | — |
| `--ink` | `#1D2A4D` | headings, body, the stamp | 12.6:1 |
| `--ink-soft` | `#4A5470` | secondary text, captions | 7.3:1 |
| `--stamp` | `#8C1D2C` | overdue, urgent, conflicts | 7.5:1 |
| `--confirmed` | `#2D6A4B` | receipts that were found | 5.3:1 |
| `--highlighter` | `#F4D67A` | background of a confirmed quote | ink on it: 9.8:1 |
| `--rule` | `#D7DBD5` | hairlines and borders | non-text |

The three status colours are each paired with a shape as well: a tick for
confirmed, a filled circle for a conflict, a hollow circle for unclear, a
question mark for not found. A verdict is legible with the stylesheet off.

## Type

System fonts only. No web font, so nothing is fetched from another origin and
the CSP needs no exception.

```
"Segoe UI", "Nirmala UI", "Noto Sans", "Noto Sans Devanagari",
"Kohinoor Devanagari", system-ui, sans-serif
```

Scale: 16 / 20 / 25 / 31 / 39 px. Body line height 1.6, raised to 1.75 for
Hindi, which needs the room for its matras. Measure capped at 70ch. Dates and
amounts use tabular numerals so a column of them lines up.

## Copy

Sentence case. Active verbs. The same name for an action everywhere: the
button says **Read my notice**, so the progress message says **Reading your
notice…** and the heading that follows says **Your notice**.

Errors say what happened and what to do about it. They do not apologise, and
they do not blame the reader: "That PDF looks like a scan, so there is no text
to read. Paste the text instead." is the shape.

Nothing on the page tells the reader what to decide. Options are described,
never ranked. The word "should" does not appear in any generated or static
string about the reader's choices.

## Layout

### Intake

```
┌──────────────────────────────────────────────────────────────┐
│ Mohlat                                     English | हिन्दी    │
├──────────────────────────────────────────────────────────────┤
│ Understand your legal notice and the date you need to act by │
│                                                              │
│ Your notice                        What happens next          │
│ ( ) Upload a file (•) Paste text   1 We read the notice       │
│ [ textarea                     ]   2 We work out your date    │
│ When did you receive it? [date]    3 You see your options     │
│ Explain in [English] Detail [Simple]                          │
│ [ Read my notice ]                 Nothing is stored.         │
│ Try a sample: [Cheque] [Bank loan] [Notice to vacate]        │
├──────────────────────────────────────────────────────────────┤
│ Information, not legal advice. Free legal aid: 15100          │
└──────────────────────────────────────────────────────────────┘
```

The "What happens next" column is three numbered lines, not a card. It exists
to tell a worried reader that this is three steps and then it is over.

### Report

```
┌──────────────┬───────────────────────────────────────────────┐
│ On this page │   ╭───────────╮                               │
│ Your date    │  (  Act by    )  12 days left                 │
│ In short     │  (  16 Mar 26 )  How we worked this out ▸      │
│ What they want╰───────────╯                                  │
│ The law      │ In short …                                    │
│ Your options │ What they want … [Found in your notice]       │
│ Cross-check  │ …                                             │
│ Ask          │                                               │
│ Legal aid    │                                               │
│ Briefing     │                                               │
└──────────────┴───────────────────────────────────────────────┘
```

Section order, top to bottom:

1. The respond-by stamp, or a clear "No deadline found in this notice".
2. An urgent banner, if screening found a summons, hearing or auction.
3. A notice that the document contains text aimed at an AI, if it does.
4. In short.
5. What they want.
6. Dates in this notice.
7. What the law says: the rule card with its source links and review date,
   or "No rule in our rulebook matched; we used the period in the notice."
8. Your options.
9. Check against your agreement.
10. Ask about your documents.
11. Free legal help.
12. Briefing sheet.
13. Your notice: the masked source text.

On narrow screens "On this page" sits above the report in normal flow rather
than becoming a drawer, because a drawer is one more thing to work out.

## Receipts

Every fact taken from the document carries its receipt inline:

- Found: a tick, the words "Found in your notice", and a link that opens the
  source panel, scrolls to the highlighted line and moves focus to it.
- Not found: "Not found word for word in your notice. Check this yourself."

The highlight is a `<mark>` with the highlighter background. A reader can
always get from a claim to the words it came from in one click.

## Accessibility decisions made here, not retrofitted

- Landmarks: `header`, `nav`, `main`, `footer`. Exactly one `h1`. No skipped
  heading levels.
- A skip link to `main` as the first focusable element.
- Every control has a real `<label>`; hints are tied with `aria-describedby`.
- A failed submit renders an error summary at the top of the form listing each
  problem as a link to its field, and moves focus to the summary.
- Progress is announced through an `aria-live="polite"` region.
- When the report arrives, focus moves to its first heading.
- Focus outline is 3px with a 2px offset, visible on every background.
- Targets are at least 24px, and 44px for the primary buttons.
- Hindi content is wrapped with `lang="hi"`, and `<html lang>` changes on
  switch so a screen reader changes voice.
- No horizontal scroll at 320px; usable at 400% zoom.
- A print stylesheet reduces the page to the briefing sheet.

## What this plan deliberately avoids

Checked against the way an AI tends to design a page by default:

- No hero section with a gradient and a centred headline.
- No three-column feature grid with icons.
- No card for every piece of information.
- No purple-to-blue gradient, no glassmorphism, no drop shadows everywhere.
- No emoji as iconography.
- No dark mode toggle nobody asked for.
- No animation beyond the single stamp press.
- No "Powered by AI" badge.

The stamp is the only ornament, and it earns its place by being the answer to
the question the reader came with.
