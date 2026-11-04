import { describe, it, expect } from 'vitest';
import { createTranslator, resolveLocale, DICTIONARIES, FALLBACK_LOCALE } from '../i18n/index.js';

describe('resolveLocale', () => {
  it('accepts supported base tags, including regional variants', () => {
    expect(resolveLocale('nl')).toBe('nl');
    expect(resolveLocale('nl-NL')).toBe('nl');
    expect(resolveLocale('en_GB')).toBe('en');
  });

  it('falls back to English for auto, unknown, or missing values', () => {
    expect(resolveLocale('auto')).toBe(FALLBACK_LOCALE);
    expect(resolveLocale('de')).toBe(FALLBACK_LOCALE);
    expect(resolveLocale('')).toBe(FALLBACK_LOCALE);
    expect(resolveLocale(null)).toBe(FALLBACK_LOCALE);
    expect(resolveLocale(undefined)).toBe(FALLBACK_LOCALE);
  });
});

describe('createTranslator', () => {
  const dictionaries = {
    en: { 'greet': 'Hello {name}', 'only.en': 'English only' },
    nl: { 'greet': 'Hallo {name}' },
  };

  it('uses the requested locale when the key exists', () => {
    const t = createTranslator('nl', dictionaries);
    expect(t('greet', { name: 'Anna' })).toBe('Hallo Anna');
  });

  it('falls back to English when the key is missing in the locale', () => {
    const t = createTranslator('nl', dictionaries);
    expect(t('only.en')).toBe('English only');
  });

  it('returns the key itself when no dictionary has it', () => {
    const t = createTranslator('en', dictionaries);
    expect(t('missing.key')).toBe('missing.key');
  });

  it('leaves unknown placeholders in place', () => {
    const t = createTranslator('en', dictionaries);
    expect(t('greet')).toBe('Hello {name}');
  });

  it('uses English when the locale is auto', () => {
    const t = createTranslator('auto', dictionaries);
    expect(t('greet', { name: 'Bo' })).toBe('Hello Bo');
  });
});

describe('bundled dictionaries', () => {
  it('have identical key sets in English and Dutch', () => {
    const en = Object.keys(DICTIONARIES.en).sort();
    const nl = Object.keys(DICTIONARIES.nl).sort();
    expect(nl).toEqual(en);
  });

  it('have no empty values', () => {
    for (const [locale, dict] of Object.entries(DICTIONARIES)) {
      for (const [key, value] of Object.entries(dict)) {
        expect(value, `${locale}:${key}`).toBeTruthy();
      }
    }
  });
});
