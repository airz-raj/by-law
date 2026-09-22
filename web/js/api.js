// @ts-check
/**
 * The one place that talks to the server. Problem responses become an
 * ApiError carrying the problem type, so callers branch on a stable code
 * rather than on a message.
 */

const TIMEOUT_MS = 45000;
const BASE = '/api/v1';

/** An error carrying the server's problem type and detail. */
export class ApiError extends Error {
  /**
   * @param {string} type
   * @param {string} detail
   * @param {number} status
   */
  constructor(type, detail, status) {
    super(detail);
    this.name = 'ApiError';
    this.type = type;
    this.detail = detail;
    this.status = status;
  }
}

/**
 * Perform one request with a timeout.
 * @param {string} path
 * @param {RequestInit} init
 * @returns {Promise<any>}
 */
async function request(path, init) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  let response;
  try {
    response = await fetch(`${BASE}${path}`, { ...init, signal: controller.signal });
  } catch (cause) {
    throw new ApiError('mohlat:network', 'network_error', 0);
  } finally {
    clearTimeout(timer);
  }

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const type = body && typeof body.type === 'string' ? body.type : 'mohlat:internal';
    const detail = body && typeof body.detail === 'string' ? body.detail : '';
    throw new ApiError(type, detail, response.status);
  }
  return body;
}

/**
 * Read a notice.
 * @param {FormData} form
 * @returns {Promise<any>}
 */
export function decodeNotice(form) {
  return request('/notices/decode', { method: 'POST', body: form });
}

/**
 * Check a notice against the agreement behind it.
 * @param {FormData} form
 * @returns {Promise<any>}
 */
export function crossCheck(form) {
  return request('/notices/cross-check', { method: 'POST', body: form });
}

/**
 * Ask a question about the loaded documents.
 * @param {{question: string, documents: {label: string, text: string}[], language: string}} body
 * @returns {Promise<any>}
 */
export function askQuestion(body) {
  return request('/questions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/**
 * Check the Section 12 criteria.
 * @param {Record<string, boolean | string>} body
 * @returns {Promise<any>}
 */
export function checkLegalAid(body) {
  return request('/legal-aid/check', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/**
 * Fetch a sample document.
 * @param {string} name
 * @returns {Promise<string>}
 */
export async function loadSample(name) {
  const response = await fetch(`/samples/${name}.txt`);
  if (!response.ok) throw new ApiError('mohlat:sample', 'sample_unavailable', response.status);
  return response.text();
}
