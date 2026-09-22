// @ts-check
/**
 * Wiring. Every other module is pure: this is the only file that reads the
 * page, attaches listeners and moves focus.
 */

import { ApiError, decodeNotice, loadSample } from './api.js';
import { renderAsk } from './ask.js';
import { renderBriefing } from './briefing.js';
import { renderCrossCheck } from './crosscheck.js';
import { el, need, replace } from './dom.js';
import { applyTo, language, t, use } from './i18n.js';
import { renderLegalAid } from './legal-aid.js';
import { renderReport, section } from './report.js';
import { buildRequest, messageForError, showProblems, validate } from './intake.js';
import { isAvailable, speak, stop } from './speech.js';

/** Sections added below the generated report, in order. */
const EXTRA_SECTIONS = [
  ['crosscheck', 'section_crosscheck'],
  ['ask', 'section_ask'],
  ['legal-aid', 'section_legal_aid'],
  ['briefing', 'section_briefing'],
];

/** @type {{report: any, receiptDate: string} | null} */
let current = null;

/** Today, as the browser sees it, for the future-date check. */
function today() {
  return new Date().toISOString().slice(0, 10);
}

/**
 * Announce progress to the live region.
 * @param {string} message
 */
function announce(message) {
  need('#progress').textContent = message;
}

/**
 * Read the intake form.
 * @returns {{source: string, text: string, file: File | null, hasFile: boolean, receiptDate: string, language: string, readingLevel: string, today: string}}
 */
function readForm() {
  const fileInput = /** @type {HTMLInputElement} */ (need('#notice-file'));
  const file = fileInput.files && fileInput.files.length > 0 ? fileInput.files[0] : null;
  const checked = /** @type {HTMLInputElement | null} */ (
    document.querySelector('input[name="source"]:checked')
  );
  return {
    source: checked ? checked.value : 'paste',
    text: /** @type {HTMLTextAreaElement} */ (need('#notice-text')).value,
    file,
    hasFile: file !== null,
    receiptDate: /** @type {HTMLInputElement} */ (need('#receipt-date')).value,
    language: /** @type {HTMLSelectElement} */ (need('#language-select')).value,
    readingLevel: /** @type {HTMLSelectElement} */ (need('#reading-level')).value,
    today: today(),
  };
}

/** Build the contents list from the sections that were rendered. */
function buildContents() {
  const list = need('#contents-list');
  const headings = Array.from(document.querySelectorAll('.report-section > h2'));
  replace(
    list,
    ...headings.map((heading) => {
      const parent = /** @type {HTMLElement} */ (heading.parentElement);
      return el('li', {}, el('a', { href: `#${parent.id}` }, heading.textContent ?? ''));
    }),
  );
}

/**
 * Show the report for a decoded notice.
 * @param {any} report
 * @param {string} receiptDate
 */
function showReport(report, receiptDate) {
  current = { report, receiptDate };
  const body = need('#report-body');

  const noticeText = () => report.notice.text;
  const documents = () => [{ label: 'notice', text: report.notice.text }];

  replace(
    body,
    renderReport(report, isAvailable() ? { speak } : {}),
    section('crosscheck', 'section_crosscheck', renderCrossCheck(noticeText, announce)),
    section('ask', 'section_ask', renderAsk(documents, announce)),
    section('legal-aid', 'section_legal_aid', renderLegalAid()),
    section('briefing', 'section_briefing', renderBriefing(report, receiptDate)),
  );

  const briefing = document.getElementById('section-briefing');
  if (briefing) briefing.classList.add('print-me');

  /** @type {HTMLElement} */ (need('#intake')).hidden = true;
  const reportSection = /** @type {HTMLElement} */ (need('#report'));
  reportSection.hidden = false;
  buildContents();

  const first = /** @type {HTMLElement | null} */ (document.querySelector('.report-section h2'));
  if (first) {
    first.tabIndex = -1;
    first.focus();
  }
  announce(t('progress_done'));
  void EXTRA_SECTIONS;
}

/** Return to intake and forget everything held in memory. */
function startAgain() {
  stop();
  current = null;
  replace(need('#report-body'));
  replace(need('#contents-list'));
  /** @type {HTMLElement} */ (need('#report')).hidden = true;
  /** @type {HTMLElement} */ (need('#intake')).hidden = false;
  announce('');
  /** @type {HTMLTextAreaElement} */ (need('#notice-text')).value = '';
  /** @type {HTMLInputElement} */ (need('#notice-file')).value = '';
  /** @type {HTMLElement} */ (need('#intake-heading')).focus();
}

/** Submit the intake form. */
/**
 * @param {Event} event
 * @returns {Promise<void>}
 */
async function submit(event) {
  event.preventDefault();
  const values = readForm();
  const problems = validate(values);
  showProblems(need('#error-summary'), need('#error-summary-list'), problems);
  if (problems.length > 0) return;

  const button = /** @type {HTMLButtonElement} */ (need('#submit-button'));
  button.disabled = true;
  button.textContent = t('submit_working');
  announce(t('progress_reading'));

  try {
    const report = await decodeNotice(buildRequest(values));
    showReport(report, values.receiptDate);
  } catch (error) {
    const message =
      error instanceof ApiError ? messageForError(error) : t('error_generic');
    showProblems(need('#error-summary'), need('#error-summary-list'), []);
    replace(
      need('#error-summary-list'),
      el('li', {}, message),
    );
    const summary = /** @type {HTMLElement} */ (need('#error-summary'));
    summary.hidden = false;
    summary.focus();
    announce('');
  } finally {
    button.disabled = false;
    button.textContent = t('submit');
  }
}

/** Switch between pasting and uploading. */
function onSourceChange() {
  const checked = /** @type {HTMLInputElement | null} */ (
    document.querySelector('input[name="source"]:checked')
  );
  const isFile = checked?.value === 'file';
  /** @type {HTMLElement} */ (need('#paste-field')).hidden = isFile;
  /** @type {HTMLElement} */ (need('#file-field')).hidden = !isFile;
}

/**
 * Change the interface language and re-render whatever is on screen.
 * @param {string} code
 */
async function switchLanguage(code) {
  stop();
  await use(code);
  applyTo(document);
  document.querySelectorAll('.language-button').forEach((button) => {
    const isCurrent = button.getAttribute('data-language') === code;
    button.classList.toggle('is-current', isCurrent);
    button.setAttribute('aria-pressed', String(isCurrent));
  });
  /** @type {HTMLSelectElement} */ (need('#language-select')).value = code;
  if (current) showReport(current.report, current.receiptDate);
}

/** Attach every listener. */
function wire() {
  need('#intake-form').addEventListener('submit', submit);
  need('#start-again').addEventListener('click', startAgain);

  document.querySelectorAll('input[name="source"]').forEach((input) => {
    input.addEventListener('change', onSourceChange);
  });

  document.querySelectorAll('[data-sample]').forEach((button) => {
    button.addEventListener('click', async () => {
      const name = button.getAttribute('data-sample');
      if (!name) return;
      /** @type {HTMLInputElement} */ (need('#source-paste')).checked = true;
      onSourceChange();
      const textarea = /** @type {HTMLTextAreaElement} */ (need('#notice-text'));
      textarea.value = await loadSample(name);
      textarea.focus();
    });
  });

  document.querySelectorAll('.language-button').forEach((button) => {
    button.addEventListener('click', () => {
      const code = button.getAttribute('data-language');
      if (code) void switchLanguage(code);
    });
  });

  need('#language-select').addEventListener('change', (event) => {
    const value = /** @type {HTMLSelectElement} */ (event.target).value;
    void switchLanguage(value);
  });
}

/** Start the page. */
async function start() {
  await use(document.documentElement.lang || 'en');
  applyTo(document);
  onSourceChange();
  wire();
  void language;
}

void start();
