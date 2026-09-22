// @ts-check
/**
 * Questions answered from the loaded documents alone.
 *
 * When the server says the documents do not support an answer, this shows
 * the standard sentence rather than whatever the model wrote.
 */

import { askQuestion } from './api.js';
import { el, fragment, replace } from './dom.js';
import { language, t } from './i18n.js';

/**
 * Build the question section.
 * @param {() => {label: string, text: string}[]} documents
 * @param {(message: string) => void} announce
 * @returns {HTMLElement}
 */
export function renderAsk(documents, announce) {
  const output = el('div', { id: 'ask-output', role: 'status', 'aria-live': 'polite' });

  const input = /** @type {HTMLInputElement} */ (
    el('input', { type: 'text', id: 'question', name: 'question',
      'aria-describedby': 'question-hint', maxlength: '500' })
  );

  const submit = /** @type {HTMLButtonElement} */ (
    el('button', { type: 'submit', class: 'button' }, t('ask_submit'))
  );

  const form = /** @type {HTMLFormElement} */ (
    el(
      'form',
      { id: 'ask-form' },
      el('p', { class: 'quiet' }, t('ask_intro')),
      el(
        'div',
        { class: 'field' },
        el('label', { for: 'question' }, t('ask_label')),
        el('p', { class: 'hint', id: 'question-hint' }, t('ask_hint')),
        input,
      ),
      submit,
    )
  );

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (input.value.trim().length < 3) {
      input.focus();
      return;
    }
    submit.disabled = true;
    announce(t('progress_asking'));
    try {
      const answer = await askQuestion({
        question: input.value.trim(),
        documents: documents(),
        language: language(),
      });
      replace(output, renderAnswer(answer));
    } catch {
      replace(output, el('p', { class: 'provisional-note' }, t('error_generic')));
    } finally {
      submit.disabled = false;
      announce('');
    }
  });

  return el('div', {}, form, output);
}

/**
 * Render one answer.
 * @param {{answer: string, supported: boolean, receipts: {quote: string, found: boolean}[]}} answer
 * @returns {DocumentFragment}
 */
export function renderAnswer(answer) {
  if (!answer.supported) {
    return fragment(el('p', { class: 'answer' }, t('ask_unsupported')));
  }
  const confirmed = answer.receipts.filter((receipt) => receipt.found);
  return fragment(
    el('p', { class: 'answer' }, answer.answer),
    confirmed.length
      ? fragment(
          el('p', { class: 'quiet' }, t('ask_supported_note')),
          el(
            'ul',
            {},
            ...confirmed.map((receipt) => el('li', {}, el('q', {}, receipt.quote))),
          ),
        )
      : null,
  );
}
