/**
 * Stock tab: per item, answer whether it is in stock. Answering "no" previews
 * how many dinners in the window would be replaced before anything is saved.
 */
import { MpView, html, listOf, reportError, toast, t } from '../../../shared/components/common.js';
import { api } from '../../../shared/api/instance.js';

export class MpStockView extends MpView {
  static properties = {
    items: { state: true },
    loading: { state: true },
    pendingNo: { state: true },
  };

  constructor() {
    super();
    this.items = [];
    this.loading = true;
    /** { item, replacesCount } while the user confirms a "no" answer. */
    this.pendingNo = null;
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  async load() {
    this.loading = true;
    try {
      this.items = listOf(await api.stock.list(true), 'stock', 'items');
    } catch (err) {
      reportError(this, err);
    } finally {
      this.loading = false;
    }
  }

  async answer(item, inStock) {
    if (inStock === false) {
      await this.previewNo(item);
      return;
    }
    await this.save(item, true);
  }

  async previewNo(item) {
    try {
      const preview = await api.stock.preview(item.id, false);
      this.pendingNo = { item, replacesCount: preview?.replaces_count ?? 0 };
    } catch (err) {
      reportError(this, err);
    }
  }

  async confirmNo() {
    const pending = this.pendingNo;
    if (!pending) return;
    this.pendingNo = null;
    await this.save(pending.item, false);
  }

  async save(item, inStock) {
    try {
      await api.stock.set(item.id, inStock);
      toast(this, t('stock.updated'));
      await this.load();
    } catch (err) {
      reportError(this, err);
    }
  }

  renderConfirm() {
    const { item, replacesCount } = this.pendingNo;
    return html`<div class="banner" role="alertdialog" aria-labelledby="stock-confirm-title">
      <div class="grow">
        <strong id="stock-confirm-title">${item.name}</strong>
        <div>${t('stock.replacesDetail', { count: replacesCount })}</div>
      </div>
      <md-text-button @click=${() => (this.pendingNo = null)}>${t('common.cancel')}</md-text-button>
      <md-filled-button @click=${() => this.confirmNo()}>${t('stock.saveNo')}</md-filled-button>
    </div>`;
  }

  renderRow(item) {
    const answer = item.in_stock;
    const yesPressed = answer === true;
    const noPressed = answer === false;
    return html`<li class="stock-row" data-id=${item.id}>
      <div class="grow">
        <div>${item.name}</div>
        <div class="muted">
          ${answer === null || answer === undefined
            ? html`<span class="badge">${t('stock.unanswered')}</span>`
            : ''}
          ${item.replaces_count ? t('stock.replaces', { count: item.replaces_count }) : ''}
        </div>
      </div>
      <div class="row" role="group" aria-label="${item.name}">
        <md-filled-button
          aria-pressed=${yesPressed ? 'true' : 'false'}
          @click=${() => this.answer(item, true)}
        >${t('common.yes')}</md-filled-button>
        <md-outlined-button
          aria-pressed=${noPressed ? 'true' : 'false'}
          @click=${() => this.answer(item, false)}
        >${t('common.no')}</md-outlined-button>
      </div>
    </li>`;
  }

  renderList() {
    if (this.loading) {
      return html`<div class="loading" role="status"><md-circular-progress indeterminate></md-circular-progress>${t('common.loading')}</div>`;
    }
    if (!this.items.length) return html`<p class="muted">${t('stock.empty')}</p>`;
    return html`<ul class="plain-list">${this.items.map((item) => this.renderRow(item))}</ul>`;
  }

  render() {
    return html`<div class="page">
      <div class="page-head">
        <h2>${t('stock.title')}</h2>
        <span class="muted">${t('stock.subtitle')}</span>
      </div>
      <p class="muted">${t('stock.help')}</p>
      <div class="card stack">
        ${this.pendingNo ? this.renderConfirm() : ''}
        ${this.renderList()}
      </div>
    </div>`;
  }
}

customElements.define('mp-stock-view', MpStockView);
