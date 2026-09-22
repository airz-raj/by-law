// @ts-nocheck
/** Shared setup for the browser tests: the page shell and the strings. */

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

export const ROOT = resolve(import.meta.dirname, '..', '..');

/** Read a file from the repository. */
export function readRepoFile(...parts) {
  return readFileSync(resolve(ROOT, ...parts), 'utf8');
}

/** Load a language file as an object. */
export function readStrings(code) {
  return JSON.parse(readRepoFile('web', 'i18n', `${code}.json`));
}

/** Load a recorded model answer. */
export function readFixture(name) {
  return JSON.parse(readRepoFile('tests', 'fixtures', 'llm', `${name}.json`));
}

/**
 * Make the i18n module serve a language without fetching it.
 * jsdom has no fetch, so the module's loader is fed directly.
 */
export async function useLanguage(i18n, code = 'en') {
  const strings = readStrings(code);
  globalThis.fetch = async () => ({ ok: true, json: async () => strings });
  await i18n.use(code);
  return strings;
}

/** Put the real index.html into the jsdom document. */
export function loadPage() {
  const html = readRepoFile('web', 'index.html');
  const body = html.split('<body>')[1].split('</body>')[0];
  document.documentElement.lang = 'en';
  document.body.innerHTML = body;
  return document;
}

/** A decode report built from the committed fixtures, as the API returns it. */
export function buildReport(overrides = {}) {
  const extraction = readFixture('decode_cheque');
  const notice = { text: 'Pay Rs. 48,500 within fifteen days of receipt of this notice.', redactions: { PAN: 1 } };
  const receipt = (quote, found = true, start = 0, end = 10) => ({
    quote,
    found,
    start: found ? start : null,
    end: found ? end : null,
    reason: found ? null : 'NOT_FOUND',
  });
  return {
    request_id: 'test-request-id',
    disclaimer: 'Information, not legal advice.',
    notice,
    classification: {
      label: 'in.ni_act.s138_demand',
      reason: 'MATCHED',
      matched_terms: ['cheque', 'section 138'],
      rule: {
        id: 'in.ni_act.s138_demand',
        title: 'Demand notice for a dishonoured cheque',
        clock_starts: 'receipt',
        period_days: 15,
        what_you_must_do: 'Pay within 15 days.',
        what_can_happen_next: 'A complaint may follow.',
        your_rights: ['Section 138 covers enforceable debts.'],
        caveats: ['Check the 30-day limit.'],
        sources: [{ label: 'NI Act, 1881', url: 'https://www.indiacode.nic.in/handle/123456789/2189' }],
        last_reviewed: '2026-09-22',
      },
    },
    summary: extraction.summary,
    sender_role: extraction.sender_role,
    recipient_role: extraction.recipient_role,
    demands: [{ what: 'Pay the cheque amount', amount_text: 'Rs. 48,500/-', receipt: receipt('Pay Rs. 48,500 within fifteen days', true, 0, 33) }],
    cited_references: [{ reference: 'Section 138', receipt: receipt('within fifteen days of receipt', true, 18, 48) }],
    dates: [{ kind: 'NOTICE_DATE', label: 'Date on the notice', value: '2026-09-14', receipt: receipt('fifteen days of receipt', false) }],
    deadline: {
      respond_by: '2026-10-01',
      days_left: 9,
      status: 'UPCOMING',
      basis: 'RULEBOOK',
      provisional: false,
      steps: [
        { code: 'CLOCK_STARTS_RECEIPT', params: { date: '2026-09-16' } },
        { code: 'PERIOD_DAYS', params: { days: 15 } },
        { code: 'RESPOND_BY', params: { date: '2026-10-01' } },
        { code: 'NO_HOLIDAY_ADJUSTMENT', params: {} },
      ],
    },
    options: extraction.options,
    documents_to_gather: extraction.documents_to_gather,
    questions_for_lawyer: extraction.questions_for_lawyer,
    plain_terms: extraction.plain_terms,
    screening: { ai_directed: [], urgent: [] },
    ...overrides,
  };
}
