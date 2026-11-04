import { ApiError } from './client.js';

/**
 * Turn any thrown value into a translated, user-facing message.
 * Known server codes map to i18n keys; anything else falls back by HTTP status.
 * @param {unknown} err
 * @param {(key: string, params?: Record<string, string|number>) => string} t
 * @returns {string}
 */
export function errorMessage(err, t) {
  if (!(err instanceof ApiError)) return t('error.generic');
  if (err.code === 'network_error') return t('error.network_error');
  if (err.status > 0) {
    const key = `error.status.${err.status}`;
    const text = t(key);
    if (text !== key) return text;
  }
  return err.message || t('error.generic');
}

/** Dates are local ISO YYYY-MM-DD strings, as the API expects. */
export function isoDate(date = new Date()) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

/** Add whole days to an ISO date string without timezone drift. */
export function addDays(iso, days) {
  const [y, m, d] = iso.split('-').map(Number);
  return isoDate(new Date(y, m - 1, d + days));
}

/** Short weekday and day-month label for a day row, e.g. "Tue 4 Nov". */
export function formatDay(iso, locale) {
  const [y, m, d] = iso.split('-').map(Number);
  return new Intl.DateTimeFormat(locale, { weekday: 'short', day: 'numeric', month: 'short' }).format(
    new Date(y, m - 1, d),
  );
}
