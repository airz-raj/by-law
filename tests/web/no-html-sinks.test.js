// @ts-nocheck
/** No browser module may write markup from a string. */

import { readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import { ROOT } from './helpers.js';

const JS_DIR = resolve(ROOT, 'web', 'js');

const BANNED = [
  'innerHTML',
  'outerHTML',
  'insertAdjacentHTML',
  'document.write',
  'eval(',
  'new Function(',
  'setAttribute("on',
];

/** Strip comments, so a rule written down in a docstring is not a violation. */
function code(source) {
  return source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
}

const files = readdirSync(JS_DIR).filter((name) => name.endsWith('.js'));

describe('browser modules', () => {
  it('there are modules to check', () => {
    expect(files.length).toBeGreaterThan(10);
  });

  it.each(files)('%s writes no markup from a string', (name) => {
    const source = code(readFileSync(resolve(JS_DIR, name), 'utf8'));
    for (const sink of BANNED) {
      expect(source, `${name} uses ${sink}`).not.toContain(sink);
    }
  });

  it.each(files)('%s leaves no debug statements', (name) => {
    const source = code(readFileSync(resolve(JS_DIR, name), 'utf8'));
    expect(source).not.toContain('console.log');
    expect(source).not.toContain('debugger');
  });
});
