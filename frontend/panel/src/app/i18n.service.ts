import { Injectable, signal } from '@angular/core';
import en from '../../../shared/i18n/en.json';
import nl from '../../../shared/i18n/nl.json';
import type { Locale } from '../../../shared/api/types';

type Dictionary = Record<string, string>;
type TranslationParams = Record<string, string | number>;
const dictionaries: Record<Locale, Dictionary> = { en, nl };

@Injectable({ providedIn: 'root' })
export class I18nService {
  readonly locale = signal<Locale>('en');

  setLocale(value: string | null | undefined): void {
    const language = value?.toLowerCase().split(/[-_]/)[0];
    this.locale.set(language === 'nl' ? 'nl' : 'en');
    document.documentElement.lang = this.locale();
    document.title = this.t('app.title');
  }

  t(key: string, params: TranslationParams = {}): string {
    const template = dictionaries[this.locale()][key] ?? dictionaries.en[key] ?? key;
    return template.replace(/\{(\w+)\}/g, (match, name: string) =>
      Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : match,
    );
  }
}
