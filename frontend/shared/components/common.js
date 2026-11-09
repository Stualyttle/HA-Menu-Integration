/**
 * Shared view helpers: base class (light DOM so the panel styles apply),
 * inline icons, list normalisation, and toast/error events.
 */
import { LitElement, html, svg } from 'lit';
import { ICON_PATHS } from './icons.js';
import { t } from '../i18n/current.js';
import { errorMessage } from '../api/errors.js';

/** Base class for panel views. Renders into light DOM so global panel styles apply. */
export class MpView extends LitElement {
  createRenderRoot() {
    return this;
  }
}

/** Inline Material Symbols icon by name from ICON_PATHS. */
export function icon(name) {
  const d = ICON_PATHS[name];
  if (!d) return '';
  return html`<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${svg`<path d="${d}"/>`}</svg>`;
}

/** Accepts either a bare array or a wrapper object such as {items: [...]}. */
export function listOf(payload, ...keys) {
  if (Array.isArray(payload)) return payload;
  if (payload && typeof payload === 'object') {
    for (const key of keys) {
      if (Array.isArray(payload[key])) return payload[key];
    }
  }
  return [];
}

/** Emits a toast for the app shell to show. */
export function toast(host, message, kind = 'info') {
  host.dispatchEvent(new CustomEvent('mp-toast', { detail: { message, kind }, bubbles: true, composed: true }));
}

/** Emits a toast with the localised message for an API or network error. */
export function reportError(host, err) {
  toast(host, errorMessage(err, t), 'error');
}

/** Tells the app shell an item changed so list views reload. */
export function itemsChanged(host) {
  host.dispatchEvent(new CustomEvent('mp-items-changed', { bubbles: true, composed: true }));
}

/** Localised label for an item type (protein, vegetable, carb). */
export function typeLabel(type) {
  return t(`type.${type}`);
}

/** Asks the app shell to open the item dialog (id null means a new item). */
export function editItem(host, id = null) {
  host.dispatchEvent(new CustomEvent('mp-edit-item', { detail: { id }, bubbles: true, composed: true }));
}

/** Requests a localized confirmation from the app shell. */
export function confirmAction(host, message) {
  return new Promise((resolve) => {
    host.dispatchEvent(
      new CustomEvent('mp-confirm', {
        detail: { message, resolve },
        bubbles: true,
        composed: true,
      }),
    );
  });
}

export { html, t };
