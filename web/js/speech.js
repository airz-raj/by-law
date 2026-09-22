// @ts-check
/**
 * Read aloud, where the browser offers it. The control is not rendered at
 * all when speechSynthesis is missing, rather than rendered and broken.
 */

import { language, t } from './i18n.js';

/**
 * Whether this browser can speak.
 * @returns {boolean}
 */
export function isAvailable() {
  return typeof window !== 'undefined' && 'speechSynthesis' in window;
}

/**
 * Speak some text, or stop if it is already speaking.
 * @param {string} text
 * @param {HTMLButtonElement} button
 * @returns {void}
 */
export function speak(text, button) {
  if (!isAvailable()) return;
  const synth = window.speechSynthesis;

  if (synth.speaking) {
    synth.cancel();
    button.textContent = t('read_aloud');
    return;
  }

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = language() === 'hi' ? 'hi-IN' : 'en-IN';
  utterance.rate = 0.95;
  utterance.addEventListener('end', () => {
    button.textContent = t('read_aloud');
  });
  button.textContent = t('stop_reading');
  synth.speak(utterance);
}

/**
 * Stop anything being spoken.
 * @returns {void}
 */
export function stop() {
  if (isAvailable() && window.speechSynthesis.speaking) window.speechSynthesis.cancel();
}
