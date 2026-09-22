// @ts-check
/**
 * The intake form: validation, the error summary, and the progress
 * message.
 *
 * A failed submit renders a summary at the top listing each problem as a
 * link to its field, and moves focus to the summary, so a keyboard or
 * screen-reader user is told what is wrong without hunting for it.
 */

import { el, replace } from './dom.js';
import { t } from './i18n.js';

/** @typedef {{field: string, messageKey: string}} Problem */

/**
 * Validate the intake form.
 * @param {{source: string, text: string, hasFile: boolean, receiptDate: string, today: string}} values
 * @returns {Problem[]}
 */
export function validate(values) {
  /** @type {Problem[]} */
  const problems = [];

  if (values.source === 'file') {
    if (!values.hasFile) problems.push({ field: 'notice-file', messageKey: 'error_no_file' });
  } else if (values.text.trim().length === 0) {
    problems.push({ field: 'notice-text', messageKey: 'error_no_document' });
  }

  if (values.receiptDate && values.receiptDate > values.today) {
    problems.push({ field: 'receipt-date', messageKey: 'error_future_date' });
  }

  return problems;
}

/**
 * Show the problems, or clear the summary when there are none.
 * @param {HTMLElement} summary
 * @param {HTMLElement} list
 * @param {Problem[]} problems
 * @returns {void}
 */
export function showProblems(summary, list, problems) {
  document.querySelectorAll('.field.is-invalid').forEach((field) => {
    field.classList.remove('is-invalid');
  });
  document.querySelectorAll('.field-error').forEach((node) => node.remove());

  if (problems.length === 0) {
    summary.hidden = true;
    replace(list);
    return;
  }

  replace(
    list,
    ...problems.map((problem) =>
      el('li', {}, el('a', { href: `#${problem.field}` }, t(problem.messageKey))),
    ),
  );
  summary.hidden = false;

  problems.forEach((problem) => {
    const input = document.getElementById(problem.field);
    const field = input?.closest('.field');
    if (field) {
      field.classList.add('is-invalid');
      field.appendChild(el('p', { class: 'field-error' }, t(problem.messageKey)));
    }
  });

  summary.focus();
}

/**
 * Build the form body to send.
 * @param {{source: string, text: string, file: File | null, receiptDate: string, language: string, readingLevel: string}} values
 * @returns {FormData}
 */
export function buildRequest(values) {
  const body = new FormData();
  if (values.source === 'file' && values.file) {
    body.set('file', values.file);
  } else {
    body.set('text', values.text);
  }
  if (values.receiptDate) body.set('receipt_date', values.receiptDate);
  body.set('language', values.language);
  body.set('reading_level', values.readingLevel);
  return body;
}

/**
 * Turn a problem type from the server into the message to show.
 * The server's own detail is preferred, because it is written for a
 * reader; the generic string is the fallback.
 * @param {{type: string, detail: string}} error
 * @returns {string}
 */
export function messageForError(error) {
  if (error.detail && error.type !== 'mohlat:internal') return error.detail;
  return t('error_generic');
}
