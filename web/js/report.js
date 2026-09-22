// @ts-check
/**
 * The report. Data in, DocumentFragment out: nothing here reads the page
 * or attaches to it, so every section can be rendered in a test.
 */

import { el, fragment } from './dom.js';
import { formatDate, t } from './i18n.js';
import { renderReceipt } from './receipts.js';
import { renderSource } from './source-view.js';
import { renderStamp } from './stamp.js';
import { stepSentences } from './steps.js';

/** The sections that always appear, in order, with their heading keys. */
export const SECTIONS = [
  ['deadline', 'section_deadline'],
  ['summary', 'section_summary'],
  ['demands', 'section_demands'],
  ['dates', 'section_dates'],
  ['law', 'section_law'],
  ['options', 'section_options'],
  ['crosscheck', 'section_crosscheck'],
  ['ask', 'section_ask'],
  ['legal-aid', 'section_legal_aid'],
  ['briefing', 'section_briefing'],
];

/**
 * Wrap content in a titled section.
 * @param {string} id
 * @param {string} headingKey
 * @param {...(Node | null)} content
 * @returns {HTMLElement}
 */
export function section(id, headingKey, ...content) {
  return el(
    'section',
    { class: 'report-section', id: `section-${id}`, 'aria-labelledby': `heading-${id}` },
    el('h2', { id: `heading-${id}` }, t(headingKey)),
    ...content.filter((node) => node !== null),
  );
}

/**
 * The respond-by block: the stamp, the basis, and the working.
 * @param {any} report
 * @returns {HTMLElement}
 */
export function renderDeadline(report) {
  const deadline = report.deadline;
  const sentences = stepSentences(deadline.steps ?? []);

  const summary = el(
    'div',
    { class: 'stamp-summary' },
    deadline.respond_by
      ? el('p', {}, t(`basis_${deadline.basis}`))
      : el(
          'div',
          {},
          el('h3', {}, t('no_deadline_heading')),
          el('p', {}, t('no_deadline_body')),
        ),
    deadline.provisional ? el('p', { class: 'provisional-note' }, t('provisional_note')) : null,
  );

  const working = el(
    'details',
    {},
    el('summary', {}, t('working_heading')),
    el('ol', { class: 'steps' }, ...sentences.map((line) => el('li', {}, line))),
  );

  return section(
    'deadline',
    'section_deadline',
    el('div', { class: 'stamp-block' }, renderStamp(deadline), summary),
    working,
  );
}

/**
 * Banners for screening signals, if any were raised.
 * @param {{ai_directed: string[], urgent: string[]}} screening
 * @returns {DocumentFragment}
 */
export function renderBanners(screening) {
  const parts = [];
  if (screening.urgent.length > 0) {
    parts.push(
      el(
        'div',
        { class: 'banner banner-urgent', role: 'note' },
        el('h2', {}, t('urgent_heading')),
        el('p', {}, screening.urgent.map((code) => t(`urgent_${code}`)).join(', ')),
        el('p', {}, t('urgent_body')),
      ),
    );
  }
  if (screening.ai_directed.length > 0) {
    parts.push(
      el(
        'div',
        { class: 'banner', role: 'note' },
        el('h2', {}, t('ai_heading')),
        el('p', {}, screening.ai_directed.map((code) => t(`ai_${code}`)).join(', ')),
        el('p', {}, t('ai_body')),
      ),
    );
  }
  return fragment(...parts);
}

/**
 * The plain-language summary, with a read-aloud control where supported.
 * @param {any} report
 * @param {(text: string, button: HTMLButtonElement) => void} [speak]
 * @returns {HTMLElement}
 */
export function renderSummary(report, speak) {
  const body = el('p', {}, report.summary);
  const roles = el(
    'dl',
    { class: 'definition-list' },
    el('dt', {}, t('sender_role')),
    el('dd', {}, report.sender_role),
    el('dt', {}, t('recipient_role')),
    el('dd', {}, report.recipient_role),
  );

  let control = null;
  if (speak) {
    const button = /** @type {HTMLButtonElement} */ (
      el('button', { type: 'button', class: 'button button-quiet' }, t('read_aloud'))
    );
    button.addEventListener('click', () => speak(report.summary, button));
    control = button;
  }

  return section('summary', 'section_summary', body, roles, control);
}

/**
 * What the notice demands, and what it relies on.
 * @param {any} report
 * @returns {HTMLElement}
 */
export function renderDemands(report) {
  const demands =
    report.demands.length === 0
      ? [el('p', { class: 'quiet' }, t('demands_none'))]
      : report.demands.map((/** @type {any} */ demand) =>
          el(
            'div',
            { class: 'item' },
            el(
              'p',
              {},
              el('span', { class: 'item-label' }, demand.what),
              demand.amount_text ? ' — ' : null,
              demand.amount_text ? el('span', { class: 'amount' }, demand.amount_text) : null,
            ),
            renderReceipt(demand.receipt),
          ),
        );

  const references =
    report.cited_references.length === 0
      ? null
      : fragment(
          el('h3', {}, t('references_heading')),
          ...report.cited_references.map((/** @type {any} */ reference) =>
            el(
              'div',
              { class: 'item' },
              el('p', {}, reference.reference),
              renderReceipt(reference.receipt),
            ),
          ),
        );

  const terms =
    report.plain_terms.length === 0
      ? null
      : fragment(
          el('h3', {}, t('plain_terms_heading')),
          el(
            'dl',
            { class: 'definition-list' },
            ...report.plain_terms.flatMap((/** @type {any} */ term) => [
              el('dt', {}, term.term),
              el('dd', {}, term.meaning),
            ]),
          ),
        );

  return section('demands', 'section_demands', ...demands, references, terms);
}

/**
 * Every date the notice mentions.
 * @param {any} report
 * @returns {HTMLElement}
 */
export function renderDates(report) {
  const items = report.dates.map((/** @type {any} */ mention) =>
    el(
      'div',
      { class: 'item' },
      el(
        'p',
        {},
        el('span', { class: 'item-label' }, mention.label),
        mention.value ? ' — ' : null,
        mention.value
          ? el('time', { datetime: mention.value, class: 'numeric' }, formatDate(mention.value))
          : null,
      ),
      renderReceipt(mention.receipt),
    ),
  );
  return section('dates', 'section_dates', ...items);
}

/**
 * The rule card, or a plain statement that no rule matched.
 * @param {any} report
 * @returns {HTMLElement}
 */
export function renderLaw(report) {
  const rule = report.classification.rule;
  if (!rule) {
    return section('law', 'section_law', el('p', {}, t('classification_no_rule')));
  }

  const clockKey =
    rule.clock_starts === 'receipt' ? 'rule_clock_receipt' : 'rule_clock_notice_date';

  const list = (/** @type {string[]} */ items) =>
    items.length === 0
      ? null
      : el('ul', {}, ...items.map((/** @type {string} */ line) => el('li', {}, line)));

  const card = el(
    'div',
    { class: 'rule-card' },
    el('h3', {}, rule.title),
    el('p', { class: 'quiet' }, `${t('rule_period', { days: rule.period_days })} · ${t(clockKey)}`),
    el('h3', {}, t('rule_must_do')),
    el('p', {}, rule.what_you_must_do),
    el('h3', {}, t('rule_next')),
    el('p', {}, rule.what_can_happen_next),
    rule.your_rights.length ? el('h3', {}, t('rule_rights')) : null,
    list(rule.your_rights),
    rule.caveats.length ? el('h3', {}, t('rule_caveats')) : null,
    list(rule.caveats),
    el(
      'p',
      { class: 'rule-sources' },
      `${t('rule_sources')}: `,
      ...rule.sources.map((/** @type {any} */ source) =>
        el('a', { href: source.url, rel: 'noopener noreferrer', target: '_blank' }, source.label),
      ),
    ),
    el('p', { class: 'rule-sources' }, t('rule_reviewed', { date: formatDate(rule.last_reviewed) })),
  );

  const matched =
    report.classification.matched_terms.length > 0
      ? el(
          'p',
          { class: 'quiet' },
          t('classification_matched_terms', {
            terms: report.classification.matched_terms.join(', '),
          }),
        )
      : null;

  return section('law', 'section_law', card, matched);
}

/**
 * The options, described and never ranked.
 * @param {any} report
 * @returns {HTMLElement}
 */
export function renderOptions(report) {
  const items = report.options.map((/** @type {any} */ option) =>
    el(
      'div',
      { class: 'item' },
      el('h3', {}, t(`option_${option.kind}`)),
      el('p', {}, el('span', { class: 'item-label' }, `${t('option_involves')}: `), option.what_it_involves),
      option.prepare.length
        ? fragment(
            el('p', { class: 'item-label' }, t('option_prepare')),
            el('ul', { class: 'checklist' }, ...option.prepare.map((/** @type {string} */ line) => el('li', {}, line))),
          )
        : null,
      el('p', {}, el('span', { class: 'item-label' }, `${t('option_if_ignored')}: `), option.if_ignored),
    ),
  );
  return section('options', 'section_options', el('p', { class: 'quiet' }, t('options_note')), ...items);
}

/**
 * Collect the offsets of every confirmed quote, for the source panel.
 * @param {any} report
 * @returns {{start: number, end: number}[]}
 */
export function confirmedSpans(report) {
  /** @type {{start: number, end: number}[]} */
  const spans = [];
  const collect = (/** @type {any} */ receipt) => {
    if (receipt && receipt.found && receipt.start !== null && receipt.end !== null) {
      spans.push({ start: receipt.start, end: receipt.end });
    }
  };
  report.demands.forEach((/** @type {any} */ d) => collect(d.receipt));
  report.cited_references.forEach((/** @type {any} */ r) => collect(r.receipt));
  report.dates.forEach((/** @type {any} */ d) => collect(d.receipt));
  return spans;
}

/**
 * Build the whole report.
 * @param {any} report
 * @param {{speak?: (text: string, button: HTMLButtonElement) => void}} [hooks]
 * @returns {DocumentFragment}
 */
export function renderReport(report, hooks = {}) {
  return fragment(
    renderBanners(report.screening),
    renderDeadline(report),
    renderSummary(report, hooks.speak),
    renderDemands(report),
    renderDates(report),
    renderLaw(report),
    renderOptions(report),
    renderSource(report.notice, confirmedSpans(report)),
  );
}
