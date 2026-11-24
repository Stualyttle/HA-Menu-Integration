import { MpView, html, listOf, reportError, t } from '../../../shared/components/common.js';
import { api } from '../../../shared/api/instance.js';
import { formatDay, isoDate } from '../../../shared/api/errors.js';

export class MpDashboardView extends MpView {
  static properties = {
    version: { type: Number },
    days: { state: true },
    warnings: { state: true },
    stock: { state: true },
    items: { state: true },
    loading: { state: true },
  };

  constructor() {
    super();
    this.version = 0;
    this.days = [];
    this.warnings = [];
    this.stock = [];
    this.items = [];
    this.loading = true;
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  updated(changed) {
    if (changed.has('version') && changed.get('version') !== undefined) this.load();
  }

  async load() {
    this.loading = true;
    try {
      const [menu, warnings, stock, items] = await Promise.all([
        api.menu.list(),
        api.warnings.list(),
        api.stock.list(),
        api.items.list(),
      ]);
      this.days = listOf(menu, 'days', 'menu');
      this.warnings = listOf(warnings, 'warnings', 'items');
      this.stock = listOf(stock, 'items');
      this.items = listOf(items, 'items');
    } catch (err) {
      reportError(this, err);
    } finally {
      this.loading = false;
    }
  }

  navigate(tab) {
    window.location.hash = tab;
  }

  renderDinner(day) {
    if (!day?.dinner?.items?.length) return html`<p class="muted">${t('menu.noDinner')}</p>`;
    return html`<div class="dinner-summary">
      ${day.dinner.items.map((item) => html`<span class="dinner-item">${item.name}</span>`)}
    </div>`;
  }

  render() {
    if (this.loading) {
      return html`<div class="loading" role="status"><md-circular-progress indeterminate></md-circular-progress>${t('common.loading')}</div>`;
    }

    const today = this.days.find((day) => day.date === isoDate());
    const upcoming = this.days.filter((day) => day.date !== isoDate()).slice(0, 5);
    const outOfStock = this.stock.filter((item) => item.in_stock === false).length;
    const locale = document.documentElement.lang || 'en';

    return html`<div class="page dashboard-page">
      <header class="dashboard-welcome">
        <div>
          <p class="eyebrow">${t('dashboard.eyebrow')}</p>
          <h2>${t('dashboard.title')}</h2>
          <p class="muted">${t('dashboard.subtitle')}</p>
        </div>
        <md-filled-button @click=${() => this.navigate('menu')}>${t('dashboard.openMenu')}</md-filled-button>
      </header>

      <section class="summary-grid" aria-label="${t('dashboard.summary')}">
        <article class="summary-card summary-primary">
          <span class="summary-label">${t('dashboard.today')}</span>
          <strong>${today ? formatDay(today.date, locale) : t('dashboard.notPlanned')}</strong>
          ${this.renderDinner(today)}
          ${today?.status ? html`<span class="badge ${today.status}">${t(`menu.status.${today.status}`)}</span>` : ''}
        </article>
        <article class="summary-card">
          <span class="summary-label">${t('dashboard.menuDays')}</span>
          <strong>${this.days.length}</strong>
          <span class="muted">${t('dashboard.menuDaysHelp')}</span>
        </article>
        <article class="summary-card">
          <span class="summary-label">${t('dashboard.stockAlerts')}</span>
          <strong>${outOfStock}</strong>
          <span class="muted">${t('dashboard.stockAlertsHelp')}</span>
        </article>
        <article class="summary-card">
          <span class="summary-label">${t('dashboard.warnings')}</span>
          <strong>${this.warnings.length}</strong>
          <span class="muted">${t('dashboard.warningsHelp')}</span>
        </article>
      </section>

      <section class="dashboard-columns">
        <article class="card dashboard-card">
          <div class="section-heading">
            <div>
              <p class="eyebrow">${t('dashboard.previewEyebrow')}</p>
              <h3>${t('dashboard.upcoming')}</h3>
            </div>
            <md-text-button @click=${() => this.navigate('menu')}>${t('dashboard.viewAll')}</md-text-button>
          </div>
          ${upcoming.length
            ? html`<ul class="upcoming-list">
                ${upcoming.map(
                  (day) => html`<li>
                    <span class="upcoming-date">${formatDay(day.date, locale)}</span>
                    <span class="upcoming-dinner">${day.dinner?.items?.map((item) => item.name).join(' · ') || t('menu.noDinner')}</span>
                    <span class="badge ${day.status}">${t(`menu.status.${day.status}`)}</span>
                  </li>`,
                )}
              </ul>`
            : html`<p class="muted">${t('menu.empty')}</p>`}
        </article>
        <article class="card dashboard-card">
          <p class="eyebrow">${t('dashboard.manageEyebrow')}</p>
          <h3>${t('dashboard.quickActions')}</h3>
          <div class="quick-actions">
            <button class="quick-action" @click=${() => this.navigate('items')}>
              <span class="quick-action-number">${this.items.length}</span>
              <span><strong>${t('dashboard.items')}</strong><small>${t('dashboard.itemsHelp')}</small></span>
            </button>
            <button class="quick-action" @click=${() => this.navigate('stock')}>
              <span class="quick-action-number">${this.stock.length}</span>
              <span><strong>${t('tabs.stock')}</strong><small>${t('dashboard.stockHelp')}</small></span>
            </button>
            <button class="quick-action" @click=${() => this.navigate('settings')}>
              <span class="quick-action-number">›</span>
              <span><strong>${t('tabs.settings')}</strong><small>${t('dashboard.settingsHelp')}</small></span>
            </button>
          </div>
        </article>
      </section>
    </div>`;
  }
}

customElements.define('mp-dashboard-view', MpDashboardView);
