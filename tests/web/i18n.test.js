// @ts-nocheck
/** The two languages must stay in step, and placeholders must match. */

import { describe, expect, it } from 'vitest';

import { readStrings } from './helpers.js';

const en = readStrings('en');
const hi = readStrings('hi');

/** The {placeholders} a template uses. */
function placeholders(template) {
  return new Set([...template.matchAll(/\{(\w+)\}/g)].map((match) => match[1]));
}

describe('language files', () => {
  it('have identical key sets', () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(hi).sort());
  });

  it('have no empty strings', () => {
    for (const [key, value] of Object.entries({ ...en, ...hi })) {
      expect(value.trim(), key).not.toBe('');
    }
  });

  it.each(Object.keys(en))('%s uses the same placeholders in both languages', (key) => {
    expect([...placeholders(hi[key])].sort()).toEqual([...placeholders(en[key])].sort());
  });

  it('translates every deadline step code', () => {
    const codes = [
      'RULE_MATCHED', 'CLOCK_STARTS_RECEIPT', 'CLOCK_STARTS_NOTICE_DATE', 'PERIOD_DAYS',
      'EXCLUDE_FIRST_DAY', 'RESPOND_BY', 'DAYS_LEFT', 'RECEIPT_DATE_MISSING',
      'NOTICE_ASKS_SOONER', 'PLAN_FOR_EARLIER', 'STATED_PERIOD_USED', 'STATED_DATE_USED',
      'NO_DEADLINE_FOUND', 'NO_HOLIDAY_ADJUSTMENT', 'OVERDUE_WARNING', 'DUE_TODAY_WARNING',
    ];
    for (const code of codes) {
      expect(en[`step_${code}`], code).toBeTruthy();
      expect(hi[`step_${code}`], code).toBeTruthy();
    }
  });

  it('translates every option kind and Section 12 clause', () => {
    for (const kind of ['COMPLY', 'REPLY_IN_WRITING', 'NEGOTIATE', 'DISPUTE_WITH_HELP', 'FREE_LEGAL_AID']) {
      expect(en[`option_${kind}`]).toBeTruthy();
      expect(hi[`option_${kind}`]).toBeTruthy();
    }
    for (const clause of ['SC_ST', 'TRAFFICKING_BEGAR', 'WOMAN_OR_CHILD', 'DISABILITY',
      'UNDESERVED_WANT', 'INDUSTRIAL_WORKMAN', 'CUSTODY', 'INCOME_BELOW_LIMIT']) {
      expect(en[`clause_${clause}`]).toBeTruthy();
      expect(hi[`clause_${clause}`]).toBeTruthy();
    }
  });

  it('writes Hindi in Devanagari, not transliterated English', () => {
    const devanagari = /[ऀ-ॿ]/;
    const sample = ['intake_heading', 'submit', 'section_deadline', 'stamp_act_by'];
    for (const key of sample) {
      expect(devanagari.test(hi[key]), key).toBe(true);
    }
  });

  it('never tells the reader what they should decide', () => {
    for (const [key, value] of Object.entries(en)) {
      expect(value.toLowerCase(), key).not.toMatch(/\byou should\b/);
      expect(value.toLowerCase(), key).not.toMatch(/\bwe recommend\b/);
    }
  });
});
