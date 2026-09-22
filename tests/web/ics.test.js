// @ts-nocheck
/** The calendar file must be one a calendar will actually accept. */

import { describe, expect, it } from 'vitest';

import { ALARM_DAYS_BEFORE, buildCalendar, compactDate, escapeText, nextDay } from '../../web/js/ics.js';

const calendar = buildCalendar({
  date: '2026-10-01',
  title: 'Respond to legal notice',
  description: 'Deadline worked out by Mohlat. Information, not legal advice.',
  stamp: '20260922T000000Z',
});

describe('the calendar export', () => {
  it('is a calendar', () => {
    expect(calendar.startsWith('BEGIN:VCALENDAR')).toBe(true);
    expect(calendar.trimEnd().endsWith('END:VCALENDAR')).toBe(true);
    expect(calendar).toContain('VERSION:2.0');
  });

  it('separates every line with CRLF', () => {
    const lines = calendar.split('\r\n');
    expect(lines.length).toBeGreaterThan(10);
    expect(calendar).not.toMatch(/[^\r]\n/);
  });

  it('is an all-day event on the respond-by date', () => {
    expect(calendar).toContain('DTSTART;VALUE=DATE:20261001');
    expect(calendar).toContain('DTEND;VALUE=DATE:20261002');
  });

  it('carries an alarm two days before', () => {
    expect(calendar).toContain('BEGIN:VALARM');
    expect(calendar).toContain(`TRIGGER:-P${ALARM_DAYS_BEFORE}D`);
    expect(calendar).toContain('ACTION:DISPLAY');
    expect(calendar).toContain('END:VALARM');
  });

  it('has a unique identifier', () => {
    expect(calendar).toMatch(/UID:mohlat-20261001-/);
  });

  it('escapes commas, semicolons and newlines in text', () => {
    // Written with String.raw so the expectation cannot carry the same
    // broken escape the implementation once had: '\;' is not an escape
    // sequence in JavaScript, it is just ';'.
    expect(escapeText('a, b; c\nd')).toBe(String.raw`a\, b\; c\n` + 'd');
    expect(escapeText('back\\slash')).toBe(String.raw`back\\slash`);
  });

  it('escaping a semicolon actually changes the string', () => {
    expect(escapeText('a;b')).not.toBe('a;b');
    expect(escapeText('a;b')).toBe(String.raw`a\;b`);
  });

  it('escapes every semicolon in a property value', () => {
    const risky = buildCalendar({
      date: '2026-10-01',
      title: 'Pay; reply; or dispute',
      description: 'x',
      stamp: '20260922T000000Z',
    });
    const summary = risky.split('\r\n').find((line) => line.startsWith('SUMMARY:'));
    expect(summary).toBe(String.raw`SUMMARY:Pay\; reply\; or dispute`);
  });

  it('escapes the description it was given', () => {
    expect(calendar).toContain('Information\\, not legal advice.');
  });

  it('rolls the end date over a month boundary', () => {
    expect(nextDay('2026-10-31')).toBe('2026-11-01');
    expect(nextDay('2028-02-28')).toBe('2028-02-29');
    expect(nextDay('2026-12-31')).toBe('2027-01-01');
  });

  it('compacts dates', () => {
    expect(compactDate('2026-10-01')).toBe('20261001');
  });
});
