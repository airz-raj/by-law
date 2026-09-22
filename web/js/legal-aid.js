// @ts-check
/**
 * The Section 12 check. The answer is a rule, not a model call, so this
 * section works even when the model is down.
 */

import { checkLegalAid } from './api.js';
import { el, fragment, replace } from './dom.js';
import { t } from './i18n.js';

/** The Section 12 categories, in the order the Act lists them. */
export const CATEGORIES = [
  'sc_st',
  'trafficking_begar',
  'woman_or_child',
  'disability',
  'undeserved_want',
  'industrial_workman',
  'custody',
];

/** The three answers to the income question. */
export const INCOME_ANSWERS = ['yes', 'no', 'unsure'];

/**
 * Build the form and the area its answer lands in.
 * @returns {HTMLElement}
 */
export function renderLegalAid() {
  const output = el('div', { id: 'legal-aid-output', role: 'status', 'aria-live': 'polite' });

  const checkboxes = CATEGORIES.map((name) =>
    el(
      'span',
      { class: 'radio' },
      el('input', { type: 'checkbox', id: `aid-${name}`, name }),
      el('label', { for: `aid-${name}` }, t(`legal_aid_${name}`)),
    ),
  );

  const incomeOptions = INCOME_ANSWERS.map((value) =>
    el(
      'span',
      { class: 'radio' },
      el('input', {
        type: 'radio',
        id: `aid-income-${value}`,
        name: 'income_below_state_limit',
        value,
        checked: value === 'unsure',
      }),
      el('label', { for: `aid-income-${value}` }, t(`legal_aid_income_${value}`)),
    ),
  );

  const form = /** @type {HTMLFormElement} */ (
    el(
      'form',
      { id: 'legal-aid-form' },
      el(
        'fieldset',
        { class: 'field' },
        el('legend', {}, t('legal_aid_intro')),
        ...checkboxes.map((box) => el('div', {}, box)),
      ),
      el(
        'fieldset',
        { class: 'field' },
        el('legend', {}, t('legal_aid_income')),
        el('div', { class: 'radio-row' }, ...incomeOptions),
      ),
      el('button', { type: 'submit', class: 'button' }, t('legal_aid_submit')),
    )
  );

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    /** @type {Record<string, boolean | string>} */
    const body = { income_below_state_limit: String(data.get('income_below_state_limit') ?? 'unsure') };
    CATEGORIES.forEach((name) => {
      body[name] = data.get(name) !== null;
    });
    try {
      const result = await checkLegalAid(body);
      replace(output, renderEligibility(result));
    } catch {
      replace(output, el('p', { class: 'provisional-note' }, t('error_generic')));
    }
  });

  return el('div', {}, form, output);
}

/**
 * Render the answer to a Section 12 check.
 * @param {{likely_eligible: boolean, matched: string[], next_steps: string[]}} result
 * @returns {DocumentFragment}
 */
export function renderEligibility(result) {
  return fragment(
    el('h3', {}, result.likely_eligible ? t('legal_aid_eligible') : t('legal_aid_not_eligible')),
    result.matched.length
      ? fragment(
          el('p', { class: 'item-label' }, t('legal_aid_matched')),
          el('ul', {}, ...result.matched.map((code) => el('li', {}, t(`clause_${code}`)))),
        )
      : null,
    el('ul', { class: 'checklist' }, ...result.next_steps.map((code) => el('li', {}, t(`aid_${code}`)))),
  );
}
