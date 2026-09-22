// @ts-nocheck
/** The postmark must say its state in words, not only in colour. */

import { beforeAll, describe, expect, it } from 'vitest';

import * as i18n from '../../web/js/i18n.js';
import { daysPhrase, isUrgent, renderStamp } from '../../web/js/stamp.js';
import { useLanguage } from './helpers.js';

beforeAll(async () => {
  await useLanguage(i18n, 'en');
});

const deadline = (overrides) => ({
  respond_by: '2026-10-01',
  days_left: 9,
  status: 'UPCOMING',
  ...overrides,
});

describe('the postmark', () => {
  it('states the days remaining in words', () => {
    const node = renderStamp(deadline());
    expect(node.textContent).toContain('9 days left');
  });

  it('says overdue in words, not only in colour', () => {
    const node = renderStamp(deadline({ status: 'OVERDUE', days_left: -4 }));
    expect(node.textContent).toContain('Overdue by 4 days');
    expect(node.className).toContain('is-urgent');
  });

  it('says due today in words', () => {
    const node = renderStamp(deadline({ status: 'DUE_TODAY', days_left: 0 }));
    expect(node.textContent).toContain('Due today');
  });

  it('uses the singular for one day', () => {
    expect(daysPhrase('UPCOMING', 1)).toBe('1 day left');
    expect(daysPhrase('OVERDUE', -1)).toBe('Overdue by 1 day');
  });

  it('carries a label a screen reader can read on its own', () => {
    const node = renderStamp(deadline());
    expect(node.getAttribute('role')).toBe('img');
    expect(node.getAttribute('aria-label')).toContain('Act by');
    expect(node.getAttribute('aria-label')).toContain('9 days left');
  });

  it('marks a date three days away or less as urgent', () => {
    expect(isUrgent('UPCOMING', 4)).toBe(false);
    expect(isUrgent('UPCOMING', 3)).toBe(true);
    expect(isUrgent('DUE_TODAY', 0)).toBe(true);
    expect(isUrgent('OVERDUE', -1)).toBe(true);
  });

  it('never relies on the class alone for an urgent state', () => {
    const node = renderStamp(deadline({ status: 'UPCOMING', days_left: 2 }));
    expect(node.className).toContain('is-urgent');
    expect(node.textContent).toContain('2 days left');
  });

  it('shows a plain state when there is no date', () => {
    const node = renderStamp(deadline({ respond_by: null, days_left: null, status: 'UNKNOWN' }));
    expect(node.textContent).toContain('No date found');
    expect(node.className).toContain('stamp-none');
  });

  it('carries a machine-readable date', () => {
    const node = renderStamp(deadline());
    const time = node.querySelector('time');
    expect(time?.getAttribute('datetime')).toBe('2026-10-01');
  });
});
