// @ts-check
/**
 * The briefing sheet: one page to take to a lawyer or a legal services
 * authority. It prints on its own, and the deadline can be added to a
 * calendar without leaving the page.
 */

import { el } from './dom.js';
import { buildCalendar, downloadCalendar } from './ics.js';
import { formatDate, t } from './i18n.js';

/**
 * Build the briefing sheet.
 * @param {any} report
 * @param {string | null} receiptDate
 * @returns {HTMLElement}
 */
export function renderBriefing(report, receiptDate) {
  const sheet = el(
    'div',
    { class: 'briefing' },
    el('h3', {}, t('briefing_heading')),
    el('p', { class: 'quiet' }, report.disclaimer),
    el('h3', {}, t('briefing_facts')),
    el(
      'dl',
      { class: 'definition-list' },
      el('dt', {}, t('briefing_notice_type')),
      el('dd', {}, noticeType(report)),
      el('dt', {}, t('sender_role')),
      el('dd', {}, report.sender_role),
      el('dt', {}, t('recipient_role')),
      el('dd', {}, report.recipient_role),
      ...amountRows(report),
    ),
    el('h3', {}, t('briefing_dates')),
    el(
      'dl',
      { class: 'definition-list' },
      el('dt', {}, t('briefing_received')),
      el('dd', {}, receiptDate ? formatDate(receiptDate) : '—'),
      el('dt', {}, t('briefing_respond_by')),
      el('dd', {}, report.deadline.respond_by ? formatDate(report.deadline.respond_by) : '—'),
    ),
    el('h3', {}, t('briefing_documents')),
    el(
      'ul',
      { class: 'checklist' },
      ...report.documents_to_gather.map((/** @type {string} */ line) => el('li', {}, line)),
    ),
    el('h3', {}, t('briefing_questions')),
    el(
      'ol',
      { class: 'checklist' },
      ...report.questions_for_lawyer.map((/** @type {string} */ line) => el('li', {}, line)),
    ),
  );

  const printButton = /** @type {HTMLButtonElement} */ (
    el('button', { type: 'button', class: 'button' }, t('briefing_print'))
  );
  printButton.addEventListener('click', () => window.print());

  const controls = [printButton];

  if (report.deadline.respond_by) {
    const calendarButton = /** @type {HTMLButtonElement} */ (
      el('button', { type: 'button', class: 'button button-quiet' }, t('briefing_calendar'))
    );
    calendarButton.addEventListener('click', () => {
      downloadCalendar(
        buildCalendar({
          date: report.deadline.respond_by,
          title: t('calendar_title'),
          description: t('calendar_description'),
        }),
      );
    });
    controls.push(calendarButton);
  }

  return el(
    'div',
    {},
    el('p', { class: 'quiet' }, t('briefing_intro')),
    el('div', { class: 'button-row' }, ...controls),
    sheet,
  );
}

/**
 * What to call this notice on the sheet.
 *
 * The rule's title when one matched, and otherwise the label the model
 * gave, which is the only description there is.
 * @param {any} report
 * @returns {string}
 */
function noticeType(report) {
  if (report.classification.rule) return report.classification.rule.title;
  const label = report.classification.label;
  return label && label !== 'other' ? label : t('briefing_notice_unmatched');
}

/**
 * The amount rows, when the notice demands one.
 * @param {any} report
 * @returns {(HTMLElement)[]}
 */
function amountRows(report) {
  const withAmount = report.demands.find((/** @type {any} */ d) => d.amount_text);
  if (!withAmount) return [];
  return [el('dt', {}, t('briefing_amount')), el('dd', { class: 'amount' }, withAmount.amount_text)];
}

