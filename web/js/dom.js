// @ts-check
/**
 * Element construction. Text is only ever set through textContent, and
 * attributes only through setAttribute against an allow-list, so nothing
 * that arrives from the server can become markup.
 *
 * No file in web/js may use innerHTML, outerHTML, insertAdjacentHTML or
 * document.write. A test greps for them.
 */

/** Attributes any element may carry. */
const GLOBAL_ATTRIBUTES = new Set([
  'class',
  'id',
  'lang',
  'dir',
  'title',
  'role',
  'tabindex',
  'hidden',
  'href',
  'rel',
  'target',
  'type',
  'name',
  'value',
  'for',
  'rows',
  'cols',
  'min',
  'max',
  'step',
  'accept',
  'placeholder',
  'disabled',
  'checked',
  'selected',
  'required',
  'multiple',
  'colspan',
  'rowspan',
  'datetime',
  'download',
]);

/** Prefixes for attribute families that are always allowed. */
const ALLOWED_PREFIXES = ['aria-', 'data-'];

/**
 * Whether an attribute may be set on a generated element.
 * @param {string} name
 * @returns {boolean}
 */
export function isAllowedAttribute(name) {
  const lower = name.toLowerCase();
  if (lower.startsWith('on')) return false;
  if (ALLOWED_PREFIXES.some((prefix) => lower.startsWith(prefix))) return true;
  return GLOBAL_ATTRIBUTES.has(lower);
}

/**
 * Whether a URL may be used in an href.
 * Only https and same-document fragments; never javascript: or data:.
 * @param {string} value
 * @returns {boolean}
 */
export function isSafeHref(value) {
  return value.startsWith('https://') || value.startsWith('#') || value.startsWith('/');
}

/**
 * Anything that may be appended: a primitive, a node, nothing, or a list
 * of those. The list case is typed one level deep; deeper nesting still
 * works at runtime because append flattens recursively.
 * @typedef {string | number | boolean | Node | null | undefined} Leaf
 * @typedef {Leaf | Leaf[] | Leaf[][]} Child
 */

/**
 * Append one child to a parent, flattening arrays and turning primitives
 * into text nodes.
 * @param {Node} parent
 * @param {Child} child
 * @returns {void}
 */
function append(parent, child) {
  if (child === null || child === undefined || child === false) return;
  if (Array.isArray(child)) {
    child.forEach((one) => append(parent, one));
    return;
  }
  if (child instanceof Node) {
    parent.appendChild(child);
    return;
  }
  parent.appendChild(document.createTextNode(String(child)));
}

/**
 * Build an element.
 * @param {string} tag
 * @param {Record<string, string | number | boolean | null | undefined>} [attributes]
 * @param {...Child} children
 * @returns {HTMLElement}
 */
export function el(tag, attributes = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (value === null || value === undefined || value === false) continue;
    if (!isAllowedAttribute(name)) continue;
    if (name === 'href' && !isSafeHref(String(value))) continue;
    node.setAttribute(name, value === true ? '' : String(value));
  }
  children.forEach((child) => append(node, child));
  return node;
}

/**
 * Build a document fragment from children.
 * @param {...Child} children
 * @returns {DocumentFragment}
 */
export function fragment(...children) {
  const node = document.createDocumentFragment();
  children.forEach((child) => append(node, child));
  return node;
}

/**
 * Replace everything inside a node.
 * @param {Element} node
 * @param {...Child} children
 * @returns {void}
 */
export function replace(node, ...children) {
  node.replaceChildren();
  children.forEach((child) => append(node, child));
}

/**
 * Find one element, or throw if the page does not have it.
 * @template {Element} T
 * @param {string} selector
 * @returns {T}
 */
export function need(selector) {
  const found = /** @type {T | null} */ (document.querySelector(selector));
  if (found === null) throw new Error(`the page is missing ${selector}`);
  return found;
}

/**
 * Find one element, or return null.
 * @template {Element} T
 * @param {string} selector
 * @returns {T | null}
 */
export function find(selector) {
  return /** @type {T | null} */ (document.querySelector(selector));
}
