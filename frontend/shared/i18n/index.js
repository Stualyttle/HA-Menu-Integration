/**
 * Translation lookup for the panel and cards.
 *
 * Dictionaries are flat objects keyed by dotted names (e.g. "tabs.menu").
 * A missing key falls back to English, and then to the key itself.
 */
import en from './en.json';
import nl from './nl.json';

export const DICTIONARIES = { en, nl };
export const SUPPORTED_LOCALES = Object.keys(DICTIONARIES);
export const FALLBACK_LOCALE = 'en';

/**
 * Map a language setting or browser tag to a supported locale.
 * "auto", empty, or unknown values resolve to the fallback.
 * @param {string|null|undefined} language e.g. "nl", "nl-NL", "auto"
 * @returns {string}
 */
export function resolveLocale(language) {
  if (!language || typeof language !== 'string') return FALLBACK_LOCALE;
  const base = language.toLowerCase().split(/[-_]/)[0];
  return SUPPORTED_LOCALES.includes(base) ? base : FALLBACK_LOCALE;
}

/**
 * @param {string} locale
 * @param {Record<string, Record<string, string>>} [dictionaries]
 * @returns {(key: string, params?: Record<string, string|number>) => string}
 */
export function createTranslator(locale, dictionaries = DICTIONARIES) {
  const primary = dictionaries[resolveLocale(locale)] ?? {};
  const fallback = dictionaries[FALLBACK_LOCALE] ?? {};

  return function t(key, params = {}) {
    const template = Object.prototype.hasOwnProperty.call(primary, key)
      ? primary[key]
      : Object.prototype.hasOwnProperty.call(fallback, key)
        ? fallback[key]
        : key;
    return template.replace(/\{(\w+)\}/g, (match, name) =>
      Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : match,
    );
  };
}
