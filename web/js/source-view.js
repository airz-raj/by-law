// @ts-check
/**
 * The masked source text, with confirmed quotes highlighted.
 *
 * The panel is built once from the text the server returned, split at the
 * offsets of every confirmed quote. Revealing a quote opens the panel,
 * scrolls to the mark and moves focus to it, so a keyboard reader ends up
 * where a mouse reader would be looking.
 */

import { el, fragment, replace } from './dom.js';
import { onReveal } from './receipts.js';
import { t } from './i18n.js';

/** @typedef {{start: number, end: number}} Span */

/** @type {HTMLElement | null} */
let panel = null;

/** @type {HTMLDetailsElement | null} */
let disclosure = null;

/**
 * Merge overlapping spans and drop any that fall outside the text.
 * @param {Span[]} spans
 * @param {number} length
 * @returns {Span[]}
 */
export function normaliseSpans(spans, length) {
  const valid = spans
    .filter((span) => span.start >= 0 && span.end > span.start && span.end <= length)
    .sort((a, b) => a.start - b.start);

  /** @type {Span[]} */
  const merged = [];
  for (const span of valid) {
    const last = merged[merged.length - 1];
    if (last && span.start <= last.end) {
      last.end = Math.max(last.end, span.end);
    } else {
      merged.push({ start: span.start, end: span.end });
    }
  }
  return merged;
}

/**
 * Build the highlighted text as a fragment.
 * @param {string} text
 * @param {Span[]} spans
 * @returns {DocumentFragment}
 */
export function renderHighlighted(text, spans) {
  const merged = normaliseSpans(spans, text.length);
  const parts = [];
  let cursor = 0;
  merged.forEach((span, index) => {
    if (span.start > cursor) parts.push(text.slice(cursor, span.start));
    parts.push(
      el(
        'mark',
        { id: `quote-${index}`, tabindex: '-1', 'data-start': String(span.start) },
        text.slice(span.start, span.end),
      ),
    );
    cursor = span.end;
  });
  if (cursor < text.length) parts.push(text.slice(cursor));
  return fragment(...parts);
}

/**
 * Build the source section.
 * @param {{text: string, redactions: Record<string, number>}} notice
 * @param {Span[]} spans
 * @returns {HTMLElement}
 */
export function renderSource(notice, spans) {
  panel = el('div', { class: 'source-panel', id: 'source-panel' });
  replace(panel, renderHighlighted(notice.text, spans));

  const counts = Object.entries(notice.redactions)
    .map(([kind, count]) => `${count} ${t(`redaction_${kind}`)}`)
    .join(', ');

  disclosure = /** @type {HTMLDetailsElement} */ (
    el(
      'details',
      { id: 'source-disclosure' },
      el('summary', {}, t('section_source')),
      el('p', { class: 'hint' }, t('source_intro')),
      counts ? el('p', { class: 'hint' }, t('source_redactions', { counts })) : null,
      panel,
    )
  );

  onReveal(reveal);
  return disclosure;
}

/**
 * Open the source and move focus to the quote at these offsets.
 * @param {number} start
 * @param {number} end
 * @returns {void}
 */
export function reveal(start, end) {
  if (!panel || !disclosure) return;
  disclosure.open = true;
  const marks = Array.from(panel.querySelectorAll('mark'));
  const target =
    marks.find((mark) => Number(mark.getAttribute('data-start')) === start) ??
    marks.find((mark) => {
      const markStart = Number(mark.getAttribute('data-start'));
      return markStart <= start && start < markStart + (mark.textContent ?? '').length;
    });
  if (!target) return;
  target.scrollIntoView({ block: 'center', behavior: 'auto' });
  target.focus();
  void end;
}
