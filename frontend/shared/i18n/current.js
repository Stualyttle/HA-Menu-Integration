/**
 * Current translator, set once by the app shell after settings are loaded.
 * Views call t(key, params) directly; the panel reloads when the language changes.
 */
import { createTranslator } from './index.js';

let translator = createTranslator('en');

/** @param {string} locale a supported locale, or any value (resolved to English if unknown) */
export function setLocale(locale) {
  translator = createTranslator(locale);
}

/** @type {(key: string, params?: Record<string, string|number>) => string} */
export function t(key, params) {
  return translator(key, params);
}
