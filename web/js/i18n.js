// @ts-check
/**
 * Translation. The server sends codes and parameters; every user-facing
 * sentence is built here, so adding a language means adding a JSON file
 * and nothing else.
 */

/** @typedef {Record<string, string>} Strings */

/** @type {Record<string, Strings>} */
const loaded = {};

/** @type {string} */
let current = 'en';

/**
 * The language currently in use.
 * @returns {string}
 */
export function language() {
  return current;
}

/**
 * Load a language file and make it current.
 * @param {string} code
 * @returns {Promise<void>}
 */
export async function use(code) {
  if (!loaded[code]) {
    const response = await fetch(`/i18n/${code}.json`, { headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error(`could not load the ${code} strings`);
    loaded[code] = await response.json();
  }
  current = code;
  document.documentElement.lang = code;
}

/**
 * Translate a key, filling {placeholders} from params.
 * An unknown key returns the key itself, so a missing string is visible
 * rather than silently blank.
 * @param {string} key
 * @param {Record<string, string | number>} [params]
 * @returns {string}
 */
export function t(key, params = {}) {
  const strings = loaded[current] ?? {};
  const template = strings[key];
  if (template === undefined) return key;
  return template.replace(/\{(\w+)\}/g, (whole, name) => {
    const value = params[name];
    return value === undefined ? whole : String(value);
  });
}

/**
 * Whether a key exists in the current language.
 * @param {string} key
 * @returns {boolean}
 */
export function has(key) {
  return Object.prototype.hasOwnProperty.call(loaded[current] ?? {}, key);
}

/**
 * Apply the current language to every element carrying data-i18n.
 * @param {ParentNode} [root]
 * @returns {void}
 */
export function applyTo(root = document) {
  root.querySelectorAll('[data-i18n]').forEach((node) => {
    const key = node.getAttribute('data-i18n');
    if (key) node.textContent = t(key);
  });
}

/**
 * Format an ISO date for reading, in the current language.
 * @param {string | null} iso
 * @returns {string}
 */
export function formatDate(iso) {
  if (!iso) return '';
  const parsed = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return iso;
  const locale = current === 'hi' ? 'hi-IN' : 'en-IN';
  return parsed.toLocaleDateString(locale, { day: 'numeric', month: 'long', year: 'numeric' });
}

/**
 * Format an ISO date compactly, for the stamp.
 * @param {string | null} iso
 * @returns {string}
 */
export function formatDateShort(iso) {
  if (!iso) return '';
  const parsed = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return iso;
  const locale = current === 'hi' ? 'hi-IN' : 'en-IN';
  return parsed.toLocaleDateString(locale, { day: 'numeric', month: 'short', year: '2-digit' });
}
