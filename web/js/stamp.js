// @ts-check
/**
 * The postmark. It is the page's one bold element, and its state is
 * carried by text as well as colour, so it survives greyscale, colour
 * blindness and a screen reader.
 */

import { el } from './dom.js';
import { formatDateShort, t } from './i18n.js';

/** Days remaining at or below which the stamp turns maroon. */
export const URGENT_THRESHOLD_DAYS = 3;

/**
 * The sentence under the date, for a given status.
 * @param {string} status
 * @param {number | null} daysLeft
 * @returns {string}
 */
export function daysPhrase(status, daysLeft) {
  if (status === 'DUE_TODAY') return t('stamp_due_today');
  if (status === 'OVERDUE') {
    const days = Math.abs(daysLeft ?? 0);
    return days === 1 ? t('stamp_overdue_one') : t('stamp_overdue', { days });
  }
  if (status === 'UPCOMING') {
    const days = daysLeft ?? 0;
    return days === 1 ? t('stamp_one_day_left') : t('stamp_days_left', { days });
  }
  return t('stamp_no_date');
}

/**
 * Whether this deadline should be drawn in the urgent colour.
 * @param {string} status
 * @param {number | null} daysLeft
 * @returns {boolean}
 */
export function isUrgent(status, daysLeft) {
  if (status === 'OVERDUE' || status === 'DUE_TODAY') return true;
  return status === 'UPCOMING' && (daysLeft ?? 0) <= URGENT_THRESHOLD_DAYS;
}

/**
 * Build the stamp for a deadline.
 * @param {{respond_by: string | null, days_left: number | null, status: string}} deadline
 * @returns {HTMLElement}
 */
export function renderStamp(deadline) {
  if (!deadline.respond_by) {
    return el(
      'p',
      { class: 'stamp stamp-none', role: 'img', 'aria-label': t('stamp_no_date') },
      el('span', { class: 'stamp-caption' }, t('stamp_no_date')),
    );
  }

  const phrase = daysPhrase(deadline.status, deadline.days_left);
  const readable = `${t('stamp_act_by')} ${formatDateShort(deadline.respond_by)}. ${phrase}`;
  const classes = isUrgent(deadline.status, deadline.days_left) ? 'stamp is-urgent' : 'stamp';

  return el(
    'p',
    { class: classes, role: 'img', 'aria-label': readable },
    el('span', { class: 'stamp-caption' }, t('stamp_act_by')),
    el(
      'time',
      { class: 'stamp-date', datetime: deadline.respond_by },
      formatDateShort(deadline.respond_by),
    ),
    el('span', { class: 'stamp-days' }, phrase),
  );
}
