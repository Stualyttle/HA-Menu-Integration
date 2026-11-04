/**
 * Items tab: searchable list of foods with type, portion, stock tracking and nutrition status.
 * Editing and creating happen in the item dialog, opened through mp-edit-item.
 */
import { MpView, html, icon, listOf, reportError, t, typeLabel, editItem } from '../../../shared/components/common.js';
import { api } from '../../../shared/api/instance.js';

const TYPES = ['protein', 'vegetable', 'carb'];
const SEARCH_DEBOUNCE_MS = 300;

export class MpItemsView extends MpView {
  static properties = {
    version: { type: Number },
    items: { state: true },
    loading: { state: true },
    query: { state: true },
    type: { state: true },
    nutrition: { state: true },
  };

  constructor() {
    super();
    this.version = 0;
    this.items = [];
    this.loading = true;
    this.query = '';
    this.type = '';
    this.nutrition = '';
    this.searchTimer = null;
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  disconnectedCallback() {
    clearTimeout(this.searchTimer);
    super.disconnectedCallback();
  }

  updated(changed) {
    if (changed.has('version') && changed.get('version') !== undefined) {
      this.load();
    }
  }

  filters() {
    const filters = {};
    if (this.query.trim()) filters.q = this.query.trim();
    if (this.type) filters.type = this.type;
    if (this.nutrition === 'verified') filters.verified = 'true';
    if (this.nutrition === 'unverified') filters.verified = 'false';
    return filters;
  }

  async load() {
    this.loading = true;
    try {
      this.items = listOf(await api.items.list(this.filters()), 'items');
    } catch (err) {
      reportError(this, err);
    } finally {
      this.loading = false;
    }
  }

  onSearch(e) {
    this.query = e.target.value;
    clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => this.load(), SEARCH_DEBOUNCE_MS);
  }

  onType(e) {
    this.type = e.target.value;
    this.load();
  }

  onNutrition(e) {
    this.nutrition = e.target.value;
    this.load();
  }

  renderItem(item) {
    const verified = item.nutrition?.status === 'verified';
    const portion = item.portion_grams
      ? t('items.portion', { grams: item.portion_grams })
      : t('items.noPortion');
    return html`<tr data-id=${item.id}>
      <td>${item.name}</td>
      <td><span class="chip-type">${typeLabel(item.type)}</span></td>
      <td class="muted">${portion}</td>
      <td>
        <span class="badge ${verified ? 'verified' : 'unverified'}">
          ${verified ? t('items.verified') : t('items.unverified')}
        </span>
      </td>
      <td>${item.track_stock ? html`<span class="badge ok">${t('items.tracksStock')}</span>` : ''}</td>
      <td class="actions">
        <md-icon-button aria-label="${t('common.edit')}: ${item.name}" @click=${() => editItem(this, item.id)}>
          ${icon('pencil')}
        </md-icon-button>
      </td>
    </tr>`;
  }

  renderTable() {
    if (this.loading) {
      return html`<div class="loading" role="status"><md-circular-progress indeterminate></md-circular-progress>${t('common.loading')}</div>`;
    }
    if (!this.items.length) return html`<p class="muted">${t('items.empty')}</p>`;
    return html`<table class="plain">
      <tbody>${this.items.map((item) => this.renderItem(item))}</tbody>
    </table>`;
  }

  render() {
    return html`<div class="page">
      <div class="page-head">
        <h2>${t('items.title')}</h2>
        <md-filled-button @click=${() => editItem(this, null)}>${icon('plus')} ${t('items.add')}</md-filled-button>
      </div>
      <div class="card stack">
        <div class="row">
          <md-outlined-text-field
            class="grow"
            label="${t('items.search')}"
            .value=${this.query}
            @input=${(e) => this.onSearch(e)}
          ></md-outlined-text-field>
          <md-outlined-select label="${t('items.filter.type')}" .value=${this.type} @change=${(e) => this.onType(e)}>
            <md-select-option value="" ?selected=${!this.type}><div slot="headline">${t('items.filter.any')}</div></md-select-option>
            ${TYPES.map(
              (type) => html`<md-select-option value=${type} ?selected=${this.type === type}>
                <div slot="headline">${typeLabel(type)}</div>
              </md-select-option>`,
            )}
          </md-outlined-select>
          <md-outlined-select label="${t('items.filter.nutrition')}" .value=${this.nutrition} @change=${(e) => this.onNutrition(e)}>
            <md-select-option value="" ?selected=${!this.nutrition}><div slot="headline">${t('items.filter.any')}</div></md-select-option>
            <md-select-option value="verified" ?selected=${this.nutrition === 'verified'}><div slot="headline">${t('items.filter.verified')}</div></md-select-option>
            <md-select-option value="unverified" ?selected=${this.nutrition === 'unverified'}><div slot="headline">${t('items.filter.unverified')}</div></md-select-option>
          </md-outlined-select>
        </div>
        ${this.renderTable()}
      </div>
    </div>`;
  }
}

customElements.define('mp-items-view', MpItemsView);
