// @ts-check
/**
 * Checking the notice against the agreement it relies on.
 *
 * Each claim shows the words from both documents, and a verdict carried by
 * text and a shape as well as colour. A verdict the server downgraded says
 * so, rather than quietly appearing as "unclear".
 */

import { crossCheck, loadSample } from './api.js';
import { el, fragment, replace } from './dom.js';
import { language, t } from './i18n.js';
import { messageForError } from './intake.js';

/** The mark drawn beside each verdict, so colour is never the only signal. */
const VERDICT_MARKS = {
  CONSISTENT: '✓',
  CONFLICTS: '●',
  NOT_IN_AGREEMENT: '○',
  UNCLEAR: '?',
};

/** The sample agreement offered alongside the vacate notice. */
export const SAMPLE_AGREEMENT = 'rent-agreement';

/**
 * Build the cross-check section.
 * @param {() => string} noticeText  the masked notice from the report
 * @param {(message: string) => void} announce
 * @returns {HTMLElement}
 */
export function renderCrossCheck(noticeText, announce) {
  const output = el('div', { id: 'crosscheck-output' });

  const textarea = /** @type {HTMLTextAreaElement} */ (
    el('textarea', { id: 'agreement-text', name: 'agreement_text', rows: '8',
      'aria-describedby': 'agreement-hint' })
  );

  const fileInput = /** @type {HTMLInputElement} */ (
    el('input', {
      type: 'file',
      id: 'agreement-file',
      name: 'file',
      accept: '.txt,.pdf,text/plain,application/pdf',
      'aria-describedby': 'agreement-hint',
    })
  );

  const fileLabel = el('label', { for: 'agreement-file' }, t('crosscheck_file_label'));

  const sampleButton = /** @type {HTMLButtonElement} */ (
    el('button', { type: 'button', class: 'button button-quiet' }, t('crosscheck_sample'))
  );
  sampleButton.addEventListener('click', async () => {
    textarea.value = await loadSample(SAMPLE_AGREEMENT);
    textarea.focus();
  });

  const submit = /** @type {HTMLButtonElement} */ (
    el('button', { type: 'submit', class: 'button' }, t('crosscheck_submit'))
  );

  const form = /** @type {HTMLFormElement} */ (
    el(
      'form',
      { id: 'crosscheck-form' },
      el('p', { class: 'quiet' }, t('crosscheck_intro')),
      el(
        'div',
        { class: 'field' },
        el('label', { for: 'agreement-text' }, t('crosscheck_label')),
        el('p', { class: 'hint', id: 'agreement-hint' }, t('crosscheck_hint')),
        textarea,
      ),
      el('div', { class: 'field' }, fileLabel, fileInput),
      el('div', { class: 'button-row' }, submit, sampleButton),
    )
  );

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const body = new FormData();
    body.set('notice_text', noticeText());
    body.set('language', language());
    if (fileInput.files && fileInput.files.length > 0) {
      body.set('file', fileInput.files[0]);
    } else {
      body.set('agreement_text', textarea.value);
    }

    submit.disabled = true;
    announce(t('progress_cross_checking'));
    try {
      const result = await crossCheck(body);
      replace(output, renderClaims(result));
      announce('');
    } catch (error) {
      replace(output, el('p', { class: 'provisional-note' }, messageForError(error)));
      announce('');
    } finally {
      submit.disabled = false;
    }
  });

  return el('div', {}, form, output);
}

/**
 * Render the claims a cross-check returned.
 * @param {{agreement_summary: string, claims: any[]}} result
 * @returns {DocumentFragment}
 */
export function renderClaims(result) {
  if (result.claims.length === 0) {
    return fragment(el('p', { class: 'quiet' }, t('crosscheck_none')));
  }
  return fragment(
    el('h3', {}, t('crosscheck_summary')),
    el('p', {}, result.agreement_summary),
    el('h3', {}, t('crosscheck_claims')),
    ...result.claims.map(renderClaim),
  );
}

/**
 * Render one checked claim.
 * @param {any} claim
 * @returns {HTMLElement}
 */
export function renderClaim(claim) {
  const mark = VERDICT_MARKS[/** @type {keyof typeof VERDICT_MARKS} */ (claim.verdict)] ?? '?';
  return el(
    'div',
    { class: 'item' },
    el('p', { class: 'item-label' }, claim.claim),
    el(
      'p',
      { class: `verdict verdict-${String(claim.verdict).toLowerCase()}` },
      el('span', { 'aria-hidden': 'true' }, mark),
      el('span', {}, t(`verdict_${claim.verdict}`)),
    ),
    claim.downgraded_from ? el('p', { class: 'quiet' }, t('verdict_downgraded')) : null,
    claim.downgraded_from ? null : el('p', {}, claim.explanation),
    el(
      'blockquote',
      {},
      el('p', { class: 'quiet' }, t('crosscheck_notice_says')),
      el('p', {}, claim.notice_receipt.quote),
    ),
    claim.agreement_receipt
      ? el(
          'blockquote',
          {},
          el('p', { class: 'quiet' }, t('crosscheck_agreement_says')),
          el('p', {}, claim.agreement_receipt.quote),
        )
      : null,
  );
}
