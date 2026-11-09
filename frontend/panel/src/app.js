/**
 * App shell: loads settings, sets the locale, renders the tab navigation,
 * hosts the single item dialog and the toasts, and routes by URL hash.
 */
import { html, nothing } from 'lit';
import { MpView, icon } from '../../shared/components/common.js';
import { api } from '../../shared/api/instance.js';
import { errorMessage } from '../../shared/api/errors.js';
import { resolveLocale } from '../../shared/i18n/index.js';
import { setLocale, t } from '../../shared/i18n/current.js';
import './views/menu-view.js';
import './views/items-view.js';
import './views/item-dialog.js';
import './views/categories-view.js';
import './views/rules-view.js';
import './views/stock-view.js';
import './views/settings-view.js';
import './views/import-export-view.js';

const TABS = [
  { id: 'menu', label: 'tabs.menu', icon: 'calendar' },
  { id: 'items', label: 'tabs.items', icon: 'items' },
  { id: 'categories', label: 'tabs.categories', icon: 'tag' },
  { id: 'rules', label: 'tabs.rules', icon: 'shield' },
  { id: 'stock', label: 'tabs.stock', icon: 'package' },
  { id: 'settings', label: 'tabs.settings', icon: 'cog' },
  { id: 'import-export', label: 'tabs.importExport', icon: 'download' },
];

const TOAST_MS = 4000;
const TAB_KEYS = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 };

/** Panel language: an explicit setting wins; "auto" follows the browser language. */
export function localeFromSettings(settings) {
  const language = settings?.language;
  return resolveLocale(!language || language === 'auto' ? navigator.language : language);
}

export class MpApp extends MpView {
  static properties = {
    status: { state: true },
    errorText: { state: true },
    tab: { state: true },
    toasts: { state: true },
    dialogOpen: { state: true },
    editItemId: { state: true },
    itemsVersion: { state: true },
    confirmation: { state: true },
  };

  constructor() {
    super();
    this.status = 'loading';
    this.errorText = '';
    this.tab = 'menu';
    this.toasts = [];
    this.dialogOpen = false;
    this.confirmation = null;
    /** null means a new item; a string id means edit that item. */
    this.editItemId = null;
    /** Bumped after an item changes so list views reload. */
    this.itemsVersion = 0;
  }

  connectedCallback() {
    super.connectedCallback();
    this.addEventListener('mp-toast', this.onToast);
    this.addEventListener('mp-edit-item', this.onEditItem);
    this.addEventListener('mp-items-changed', this.onItemsChanged);
    this.addEventListener('mp-confirm', this.onConfirmRequest);
    window.addEventListener('hashchange', this.onHashChange);
    this.onHashChange();
    this.load();
  }

  disconnectedCallback() {
    this.removeEventListener('mp-toast', this.onToast);
    this.removeEventListener('mp-edit-item', this.onEditItem);
    this.removeEventListener('mp-items-changed', this.onItemsChanged);
    this.removeEventListener('mp-confirm', this.onConfirmRequest);
    window.removeEventListener('hashchange', this.onHashChange);
    super.disconnectedCallback();
  }

  async load() {
    this.status = 'loading';
    try {
      const settings = await api.settings.get();
      const locale = localeFromSettings(settings);
      setLocale(locale);
      document.documentElement.lang = locale;
      document.title = t('app.title');
      this.status = 'ready';
    } catch (err) {
      setLocale('en');
      this.errorText = errorMessage(err, t);
      this.status = 'error';
    }
  }

  onHashChange = () => {
    const name = window.location.hash.replace(/^#/, '');
    if (name === 'edit-item') {
      this.editItemId = null;
      this.dialogOpen = true;
      return;
    }
    if (TABS.some((item) => item.id === name)) this.tab = name;
  };

  onToast = (event) => {
    const { message, kind } = event.detail;
    const id = `${Date.now()}-${Math.random()}`;
    this.toasts = [...this.toasts, { id, message, kind }];
    setTimeout(() => {
      this.toasts = this.toasts.filter((item) => item.id !== id);
    }, TOAST_MS);
  };

  onEditItem = (event) => {
    this.editItemId = event.detail?.id ?? null;
    this.dialogOpen = true;
  };

  onItemsChanged = () => {
    this.itemsVersion += 1;
  };

  onConfirmRequest = (event) => {
    event.stopPropagation();
    const request = event.detail;
    if (typeof request?.resolve !== 'function') return;
    if (this.confirmation) {
      request.resolve(false);
      return;
    }
    this.confirmation = request;
  };

  finishConfirmation(confirmed) {
    const dialog = this.querySelector('md-dialog.confirm-dialog');
    if (dialog?.open) dialog.close();
    const resolve = this.confirmation?.resolve;
    this.confirmation = null;
    resolve?.(confirmed);
  }

  onDialogClosed() {
    this.dialogOpen = false;
  }

  selectTab(id) {
    this.tab = id;
    if (window.location.hash !== `#${id}`) history.replaceState(null, '', `#${id}`);
  }

  onTabKey(event) {
    if (!(event.key in TAB_KEYS)) return;
    event.preventDefault();
    const index = TABS.findIndex((item) => item.id === this.tab);
    const next = TABS[(index + TAB_KEYS[event.key] + TABS.length) % TABS.length];
    this.selectTab(next.id);
    this.querySelector(`[data-tab="${next.id}"]`)?.focus();
  }

  renderView() {
    switch (this.tab) {
      case 'items':
        return html`<mp-items-view .version=${this.itemsVersion}></mp-items-view>`;
      case 'categories':
        return html`<mp-categories-view .version=${this.itemsVersion}></mp-categories-view>`;
      case 'rules':
        return html`<mp-rules-view></mp-rules-view>`;
      case 'stock':
        return html`<mp-stock-view></mp-stock-view>`;
      case 'settings':
        return html`<mp-settings-view></mp-settings-view>`;
      case 'import-export':
        return html`<mp-import-export-view></mp-import-export-view>`;
      default:
        return html`<mp-menu-view .version=${this.itemsVersion}></mp-menu-view>`;
    }
  }

  renderTabs() {
    return html`<nav class="sidebar" aria-label="${t('app.navLabel')}">
      <div class="tabs" role="tablist" aria-orientation="vertical" @keydown=${(e) => this.onTabKey(e)}>
        ${TABS.map(
          (item) => html`<button
            class="tab"
            role="tab"
            data-tab=${item.id}
            aria-selected=${this.tab === item.id ? 'true' : 'false'}
            tabindex=${this.tab === item.id ? '0' : '-1'}
            @click=${() => this.selectTab(item.id)}
          >${icon(item.icon)}<span>${t(item.label)}</span></button>`,
        )}
      </div>
    </nav>`;
  }

  renderToasts() {
    return html`<div class="toast-stack" aria-live="polite">
      ${this.toasts.map(
        (item) => html`<div class="toast ${item.kind === 'error' ? 'error' : ''}" role="status">${item.message}</div>`,
      )}
    </div>`;
  }

  render() {
    if (this.status === 'loading') {
      return html`<div class="loading" role="status"><md-circular-progress indeterminate></md-circular-progress>${t('app.loading')}</div>`;
    }
    if (this.status === 'error') {
      return html`<div class="main"><div class="banner error" role="alert">
        <div class="grow">${this.errorText || t('app.loadFailed')}</div>
        <md-text-button @click=${() => this.load()}>${t('app.retry')}</md-text-button>
      </div></div>`;
    }
    return html`
      <div class="shell">
        ${this.renderTabs()}
        <main class="main">${this.renderView()}</main>
      </div>
      <mp-item-dialog
        .open=${this.dialogOpen}
        .itemId=${this.editItemId}
        @closed=${() => this.onDialogClosed()}
      ></mp-item-dialog>
      ${this.confirmation
        ? html`<md-dialog
            class="confirm-dialog"
            aria-label=${t('common.confirmDelete')}
            open
            @closed=${() => this.finishConfirmation(false)}
          >
            <div slot="headline">${t('common.confirmDelete')}</div>
            <div slot="content"><p>${this.confirmation.message}</p></div>
            <div slot="actions" class="row">
              <md-text-button @click=${() => this.finishConfirmation(false)}>${t('common.cancel')}</md-text-button>
              <md-filled-button class="confirm-danger" @click=${() => this.finishConfirmation(true)}>
                ${t('common.delete')}
              </md-filled-button>
            </div>
          </md-dialog>`
        : nothing}
      ${this.toasts.length ? this.renderToasts() : nothing}
    `;
  }
}

customElements.define('mp-app', MpApp);
