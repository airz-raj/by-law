// @ts-check
/**
 * Receipts: the visible link between a claim and the words it came from.
 *
 * A confirmed quote gets a tick, the words "Found in your notice" and a
 * control that reveals the source and moves focus to the highlighted
 * line. An unconfirmed one says plainly that it could not be found.
 */

import { el } from './dom.js';
import { t } from './i18n.js';

/** The shape the source-view module registers so a receipt can reveal a quote. */
/** @type {((start: number, end: number) => void) | null} */
let revealer = null;

/**
 * Register the function a receipt calls to reveal a quote in the source.
 * @param {(start: number, end: number) => void} reveal
 * @returns {void}
 */
export function onReveal(reveal) {
  revealer = reveal;
}

/**
 * Build the receipt marker for one quote.
 * @param {{found: boolean, start: number | null, end: number | null, reason: string | null}} receipt
 * @returns {HTMLElement}
 */
export function renderReceipt(receipt) {
  if (!receipt.found) {
    const message = receipt.reason === 'TOO_SHORT' ? t('receipt_short') : t('receipt_missing');
    return el(
      'span',
      { class: 'receipt receipt-missing' },
      el('span', { class: 'receipt-mark', 'aria-hidden': 'true' }, '?'),
      el('span', {}, message),
    );
  }

  const marker = el(
    'span',
    { class: 'receipt receipt-found' },
    el('span', { class: 'receipt-mark', 'aria-hidden': 'true' }, '✓'),
    el('span', {}, t('receipt_found')),
  );

  if (receipt.start !== null && receipt.end !== null) {
    const button = el('button', { type: 'button', class: 'receipt-link' }, t('receipt_show'));
    button.addEventListener('click', () => {
      if (revealer) revealer(/** @type {number} */ (receipt.start), /** @type {number} */ (receipt.end));
    });
    marker.appendChild(button);
  }
  return marker;
}
