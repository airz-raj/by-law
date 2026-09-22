// @ts-nocheck
/** The intake form: validation, the error summary and where focus goes. */

import axe from 'axe-core';
import { beforeAll, beforeEach, describe, expect, it } from 'vitest';

import * as i18n from '../../web/js/i18n.js';
import { buildRequest, messageForError, showProblems, validate } from '../../web/js/intake.js';
import { loadPage, useLanguage } from './helpers.js';

beforeAll(async () => {
  await useLanguage(i18n, 'en');
});

const values = (overrides = {}) => ({
  source: 'paste',
  text: 'A long enough notice to send.',
  hasFile: false,
  receiptDate: '',
  today: '2026-09-22',
  ...overrides,
});

describe('validation', () => {
  it('accepts pasted text', () => {
    expect(validate(values())).toEqual([]);
  });

  it('refuses an empty paste', () => {
    const problems = validate(values({ text: '   ' }));
    expect(problems).toEqual([{ field: 'notice-text', messageKey: 'error_no_document' }]);
  });

  it('refuses the file option with no file chosen', () => {
    const problems = validate(values({ source: 'file', hasFile: false }));
    expect(problems).toEqual([{ field: 'notice-file', messageKey: 'error_no_file' }]);
  });

  it('accepts the file option with a file chosen', () => {
    expect(validate(values({ source: 'file', hasFile: true, text: '' }))).toEqual([]);
  });

  it('refuses a receipt date in the future', () => {
    const problems = validate(values({ receiptDate: '2026-09-23' }));
    expect(problems).toContainEqual({ field: 'receipt-date', messageKey: 'error_future_date' });
  });

  it('accepts today as a receipt date', () => {
    expect(validate(values({ receiptDate: '2026-09-22' }))).toEqual([]);
  });

  it('reports several problems at once', () => {
    const problems = validate(values({ text: '', receiptDate: '2027-01-01' }));
    expect(problems.length).toBe(2);
  });
});

describe('the request body', () => {
  it('sends pasted text', () => {
    const body = buildRequest({ source: 'paste', text: 'notice body', file: null, receiptDate: '2026-09-16', language: 'en', readingLevel: 'simple' });
    expect(body.get('text')).toBe('notice body');
    expect(body.get('receipt_date')).toBe('2026-09-16');
    expect(body.get('file')).toBeNull();
  });

  it('sends a file instead of text when one was chosen', () => {
    const file = new File(['notice body'], 'notice.txt', { type: 'text/plain' });
    const body = buildRequest({ source: 'file', text: '', file, receiptDate: '', language: 'hi', readingLevel: 'detailed' });
    expect(body.get('file')).toBe(file);
    expect(body.get('text')).toBeNull();
    expect(body.get('language')).toBe('hi');
    expect(body.get('reading_level')).toBe('detailed');
  });

  it('omits the receipt date when it was not given', () => {
    const body = buildRequest({ source: 'paste', text: 'x', file: null, receiptDate: '', language: 'en', readingLevel: 'simple' });
    expect(body.get('receipt_date')).toBeNull();
  });
});

describe('error messages', () => {
  it('prefers the sentence the server wrote for a reader', () => {
    const message = messageForError({ type: 'mohlat:scanned-pdf', detail: 'That PDF looks like a scan.' });
    expect(message).toBe('That PDF looks like a scan.');
  });

  it('falls back to a generic sentence for an internal failure', () => {
    const message = messageForError({ type: 'mohlat:internal', detail: 'NullPointerException at app/foo' });
    expect(message).toBe('Something went wrong. Try again in a moment.');
  });
});

describe('the error summary', () => {
  beforeEach(() => {
    loadPage();
  });

  it('lists each problem as a link to its field, and takes focus', () => {
    const summary = document.querySelector('#error-summary');
    const list = document.querySelector('#error-summary-list');
    showProblems(summary, list, validate(values({ text: '' })));

    expect(summary.hidden).toBe(false);
    const link = list.querySelector('a');
    expect(link.getAttribute('href')).toBe('#notice-text');
    expect(link.textContent).toBe('Paste the text of your notice, or choose a file.');
    expect(document.activeElement).toBe(summary);
  });

  it('marks the field itself as invalid', () => {
    const summary = document.querySelector('#error-summary');
    const list = document.querySelector('#error-summary-list');
    showProblems(summary, list, validate(values({ text: '' })));
    expect(document.querySelector('#paste-field').classList.contains('is-invalid')).toBe(true);
    expect(document.querySelector('#paste-field .field-error')).not.toBeNull();
  });

  it('clears itself once the problems are fixed', () => {
    const summary = document.querySelector('#error-summary');
    const list = document.querySelector('#error-summary-list');
    showProblems(summary, list, validate(values({ text: '' })));
    showProblems(summary, list, []);
    expect(summary.hidden).toBe(true);
    expect(list.children.length).toBe(0);
    expect(document.querySelector('.field.is-invalid')).toBeNull();
  });

  it('announces itself as an alert', () => {
    expect(document.querySelector('#error-summary').getAttribute('role')).toBe('alert');
  });
});

describe('accessibility of the intake state', () => {
  beforeEach(() => {
    loadPage();
  });

  it('has no axe violations', async () => {
    const results = await axe.run(document.body, {
      // jsdom has no layout, so it cannot compute rendered colour.
      rules: { 'color-contrast': { enabled: false } },
    });
    expect(results.violations.map((violation) => violation.id)).toEqual([]);
  });

  it('has no axe violations with the error summary showing', async () => {
    const summary = document.querySelector('#error-summary');
    const list = document.querySelector('#error-summary-list');
    showProblems(summary, list, validate(values({ text: '', receiptDate: '2027-01-01' })));
    const results = await axe.run(document.body, {
      rules: { 'color-contrast': { enabled: false } },
    });
    expect(results.violations.map((violation) => violation.id)).toEqual([]);
  });

  it('labels every control', () => {
    const controls = document.querySelectorAll('input, select, textarea');
    expect(controls.length).toBeGreaterThan(5);
    controls.forEach((control) => {
      const labelled =
        document.querySelector(`label[for="${control.id}"]`) !== null ||
        control.getAttribute('aria-label') !== null;
      expect(labelled, control.id || control.name).toBe(true);
    });
  });

  it('starts with a skip link to the main landmark', () => {
    const first = document.querySelector('a.skip-link');
    expect(first.getAttribute('href')).toBe('#main');
    expect(document.querySelector('main').id).toBe('main');
  });

  it('announces progress politely', () => {
    const progress = document.querySelector('#progress');
    expect(progress.getAttribute('aria-live')).toBe('polite');
    expect(progress.getAttribute('role')).toBe('status');
  });
});
