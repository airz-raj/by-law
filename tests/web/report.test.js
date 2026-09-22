// @ts-nocheck
/** Rendering the report: escaping, receipts, and accessibility. */

import axe from 'axe-core';
import { beforeAll, beforeEach, describe, expect, it } from 'vitest';

import * as i18n from '../../web/js/i18n.js';
import { renderBanners, renderDeadline, renderLaw, renderOptions, renderReport } from '../../web/js/report.js';
import { buildReport, loadPage, useLanguage } from './helpers.js';

beforeAll(async () => {
  await useLanguage(i18n, 'en');
});

/** Render a report into a container and return it. */
function render(overrides = {}) {
  const host = document.createElement('div');
  host.appendChild(renderReport(buildReport(overrides)));
  return host;
}

describe('the report', () => {
  it('renders every section', () => {
    const host = render();
    for (const id of ['deadline', 'summary', 'demands', 'dates', 'law', 'options']) {
      expect(host.querySelector(`#section-${id}`), id).not.toBeNull();
    }
  });

  it('shows the respond-by date and the days remaining', () => {
    const host = render();
    const deadline = host.querySelector('#section-deadline');
    expect(deadline.textContent).toContain('9 days left');
  });

  it('shows the working as sentences, not codes', () => {
    const host = render();
    const steps = host.querySelectorAll('#section-deadline .steps li');
    expect(steps.length).toBeGreaterThan(2);
    const text = [...steps].map((li) => li.textContent).join(' ');
    expect(text).not.toContain('CLOCK_STARTS_RECEIPT');
    expect(text).toContain('The law allows 15 days');
    expect(text).toContain('public or court holidays');
  });

  it('treats a summary containing markup as text', () => {
    const hostile = '<img src=x onerror=alert(1)> and <script>alert(2)</script>';
    const host = render({ summary: hostile });
    expect(host.querySelector('img')).toBeNull();
    expect(host.querySelector('script')).toBeNull();
    expect(host.textContent).toContain('<img src=x onerror=alert(1)>');
  });

  it('treats a demand containing markup as text', () => {
    const report = buildReport();
    report.demands[0].what = '<button onclick="alert(1)">Pay</button>';
    const host = document.createElement('div');
    host.appendChild(renderReport(report));
    expect(host.querySelector('button[onclick]')).toBeNull();
  });

  it('marks a confirmed quote as found', () => {
    const host = render();
    expect(host.querySelector('#section-demands').textContent).toContain('Found in your notice');
  });

  it('says plainly when a quote could not be found', () => {
    const host = render();
    expect(host.querySelector('#section-dates').textContent).toContain(
      'Not found word for word in your notice',
    );
  });

  it('highlights confirmed quotes in the source panel', () => {
    const host = render();
    const marks = host.querySelectorAll('.source-panel mark');
    expect(marks.length).toBeGreaterThan(0);
  });

  it('says which identifiers were masked', () => {
    const host = render();
    expect(host.querySelector('#source-disclosure').textContent).toContain('PAN numbers');
  });

  it('shows the rule card with its source link and review date', () => {
    const host = document.createElement('div');
    host.appendChild(renderLaw(buildReport()));
    const link = host.querySelector('a[href]');
    expect(link.getAttribute('href')).toContain('indiacode.nic.in');
    expect(host.textContent).toContain('Last reviewed');
  });

  it('says plainly when no rule matched', () => {
    const report = buildReport();
    report.classification.rule = null;
    const host = document.createElement('div');
    host.appendChild(renderLaw(report));
    expect(host.textContent).toContain('No rule in our rulebook matched');
  });

  it('describes options without ranking them', () => {
    const host = document.createElement('div');
    host.appendChild(renderOptions(buildReport()));
    expect(host.textContent).toContain('described, not ranked');
    expect(host.textContent.toLowerCase()).not.toContain('we recommend');
    expect(host.textContent).not.toMatch(/\bbest option\b/i);
  });

  it('shows the urgent banner only when screening raised something', () => {
    const quiet = document.createElement('div');
    quiet.appendChild(renderBanners({ ai_directed: [], urgent: [] }));
    expect(quiet.querySelector('.banner')).toBeNull();

    const loud = document.createElement('div');
    loud.appendChild(renderBanners({ ai_directed: [], urgent: ['AUCTION'] }));
    expect(loud.querySelector('.banner-urgent')).not.toBeNull();
    expect(loud.textContent).toContain('auction');
  });

  it('warns when the document contains text addressed to an AI', () => {
    const host = document.createElement('div');
    host.appendChild(renderBanners({ ai_directed: ['ADDRESSED_TO_AI'], urgent: [] }));
    expect(host.textContent).toContain('addressed to an AI');
  });

  it('marks a provisional deadline as provisional', () => {
    const report = buildReport();
    report.deadline.provisional = true;
    const host = document.createElement('div');
    host.appendChild(renderDeadline(report));
    expect(host.querySelector('.provisional-note')).not.toBeNull();
  });

  it('says plainly when no deadline was found', () => {
    const report = buildReport();
    report.deadline = { respond_by: null, days_left: null, status: 'UNKNOWN', basis: 'UNKNOWN', provisional: false, steps: [] };
    const host = document.createElement('div');
    host.appendChild(renderDeadline(report));
    expect(host.textContent).toContain('No deadline found in this notice');
  });
});

describe('the report in Hindi', () => {
  it('renders Devanagari headings', async () => {
    await useLanguage(i18n, 'hi');
    const host = render();
    expect(host.querySelector('#heading-deadline').textContent).toMatch(/[ऀ-ॿ]/);
    await useLanguage(i18n, 'en');
  });
});

describe('accessibility', () => {
  beforeEach(() => {
    loadPage();
  });

  it('has no axe violations in the report state', async () => {
    const target = document.querySelector('#report-body');
    target.appendChild(renderReport(buildReport()));
    document.querySelector('#report').hidden = false;
    document.querySelector('#intake').hidden = true;

    const results = await axe.run(document.body, {
      // jsdom has no layout, so it cannot compute rendered colour.
      rules: { 'color-contrast': { enabled: false } },
    });
    expect(results.violations.map((violation) => violation.id)).toEqual([]);
  });

  it('gives the page exactly one h1', () => {
    expect(document.querySelectorAll('h1').length).toBe(1);
  });

  it('skips no heading levels in the report', () => {
    const target = document.querySelector('#report-body');
    target.appendChild(renderReport(buildReport()));
    const levels = [...document.querySelectorAll('h1, h2, h3')].map((node) =>
      Number(node.tagName.slice(1)),
    );
    let previous = levels[0];
    for (const level of levels) {
      expect(level - previous).toBeLessThanOrEqual(1);
      previous = level;
    }
  });
});
