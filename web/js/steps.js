// @ts-check
/**
 * Turning deadline step codes into sentences.
 *
 * The server never sends a user-facing sentence: it sends a code and its
 * parameters, and the wording lives in the language files.
 */

import { formatDate, t } from './i18n.js';

/** Parameters that name a date and should be formatted as one. */
const DATE_PARAMS = new Set(['date', 'rule_date', 'notice_date']);

/**
 * Render one explanation step as a sentence.
 * @param {{code: string, params: Record<string, string | number>}} step
 * @returns {string}
 */
export function stepSentence(step) {
  /** @type {Record<string, string | number>} */
  const params = {};
  for (const [name, value] of Object.entries(step.params ?? {})) {
    params[name] = DATE_PARAMS.has(name) ? formatDate(String(value)) : value;
  }
  return t(`step_${step.code}`, params);
}

/**
 * Render every step as sentences.
 * @param {{code: string, params: Record<string, string | number>}[]} steps
 * @returns {string[]}
 */
export function stepSentences(steps) {
  return steps.map(stepSentence);
}
