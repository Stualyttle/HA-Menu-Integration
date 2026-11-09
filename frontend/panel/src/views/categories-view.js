/**
 * Categories tab: categories with their minimum number of dinners per 7 days.
 * Minimums are saved per row; the list reloads when items change (version bump).
 */
import {
  MpView,
  confirmAction,
  html,
  icon,
  listOf,
  reportError,
  toast,
  t,
} from '../../../shared/components/common.js';
import { api } from '../../../shared/api/instance.js';

export class MpCategoriesView extends MpView {
  static properties = {
    version: { type: Number },
    categories: { state: true },
    loading: { state: true },
    newName: { state: true },
    newMinimum: { state: true },
  };

  constructor() {
    super();
    this.version = 0;
    this.categories = [];
    this.loading = true;
    this.newName = '';
    this.newMinimum = 0;
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  updated(changed) {
    if (changed.has('version') && changed.get('version') !== undefined) {
      this.load();
    }
  }

  async load() {
    this.loading = true;
    try {
      this.categories = listOf(await api.categories.list(), 'categories');
    } catch (err) {
      reportError(this, err);
    } finally {
      this.loading = false;
    }
  }

  async saveMinimum(category, value) {
    const minimum = Math.max(0, Number.parseInt(value, 10) || 0);
    try {
      await api.categories.update(category.id, { min_per_7_days: minimum });
      toast(this, t('categories.minimumSaved'));
      await this.load();
    } catch (err) {
      reportError(this, err);
    }
  }

  async remove(category) {
    if (!(await confirmAction(this, t('categories.confirmDelete')))) return;
    try {
      await api.categories.remove(category.id);
      toast(this, t('categories.deleted'));
      await this.load();
    } catch (err) {
      reportError(this, err);
    }
  }

  async add(e) {
    e.preventDefault();
    const name = this.newName.trim();
    if (!name) return;
    try {
      await api.categories.create({ name, min_per_7_days: this.newMinimum });
      this.newName = '';
      this.newMinimum = 0;
      toast(this, t('categories.saved'));
      await this.load();
    } catch (err) {
      reportError(this, err);
    }
  }

  renderRow(category) {
    return html`<tr data-id=${category.id}>
      <td>
        ${category.name}
        ${category.starter ? html`<span class="badge">${t('categories.starter')}</span>` : ''}
      </td>
      <td>
        <md-outlined-text-field
          type="number"
          min="0"
          label="${t('categories.col.minimum')}"
          .value=${String(category.min_per_7_days ?? 0)}
          @change=${(e) => this.saveMinimum(category, e.target.value)}
        ></md-outlined-text-field>
      </td>
      <td class="muted">${t('categories.itemCount', { count: category.item_count ?? 0 })}</td>
      <td class="actions">
        <md-icon-button aria-label="${t('common.delete')}: ${category.name}" @click=${() => this.remove(category)}>
          ${icon('delete')}
        </md-icon-button>
      </td>
    </tr>`;
  }

  renderTable() {
    if (this.loading) {
      return html`<div class="loading" role="status"><md-circular-progress indeterminate></md-circular-progress>${t('common.loading')}</div>`;
    }
    if (!this.categories.length) return html`<p class="muted">${t('categories.empty')}</p>`;
    return html`<table class="plain">
      <thead>
        <tr>
          <th>${t('categories.col.name')}</th>
          <th>${t('categories.col.minimum')}</th>
          <th>${t('categories.col.items')}</th>
          <th></th>
        </tr>
      </thead>
      <tbody>${this.categories.map((c) => this.renderRow(c))}</tbody>
    </table>`;
  }

  render() {
    return html`<div class="page">
      <div class="page-head">
        <h2>${t('categories.title')}</h2>
      </div>
      <div class="card stack">
        ${this.renderTable()}
        <form class="row" @submit=${(e) => this.add(e)}>
          <md-outlined-text-field
            class="grow"
            label="${t('categories.name')}"
            .value=${this.newName}
            @input=${(e) => (this.newName = e.target.value)}
          ></md-outlined-text-field>
          <md-outlined-text-field
            type="number"
            min="0"
            label="${t('categories.minimum')}"
            .value=${String(this.newMinimum)}
            @input=${(e) => (this.newMinimum = Number.parseInt(e.target.value, 10) || 0)}
          ></md-outlined-text-field>
          <md-filled-button type="submit">${icon('plus')} ${t('categories.add')}</md-filled-button>
        </form>
      </div>
    </div>`;
  }
}

customElements.define('mp-categories-view', MpCategoriesView);
