/**
 * Menu tab: warnings banner, the day list for the window, and per-day actions.
 */
import { MpView, html, icon, listOf, reportError, toast, t } from '../../../shared/components/common.js';
import { api } from '../../../shared/api/instance.js';
import { addDays, formatDay, isoDate } from '../../../shared/api/errors.js';

const DEFAULT_WINDOW_DAYS = 14;

export class MpMenuView extends MpView {
  static properties = {
    version: { type: Number },
    days: { state: true },
    warnings: { state: true },
    loading: { state: true },
    busy: { state: true },
    suggestFor: { state: true },
    suggestions: { state: true },
    windowDays: { state: true },
  };

  constructor() {
    super();
    this.version = 0;
    this.days = [];
    this.warnings = [];
    this.loading = true;
    this.busy = null;
    this.suggestFor = null;
    this.suggestions = [];
    this.windowDays = DEFAULT_WINDOW_DAYS;
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
      const settings = await api.settings.get().catch(() => null);
      if (settings?.window_days) this.windowDays = settings.window_days;
      const today = isoDate();
      const [menu, warnings] = await Promise.all([
        api.menu.list(today, addDays(today, this.windowDays - 1)),
        api.warnings.list(),
      ]);
      this.days = listOf(menu, 'days', 'menu');
      this.warnings = listOf(warnings, 'warnings', 'items');
    } catch (err) {
      reportError(this, err);
    } finally {
      this.loading = false;
    }
  }

  async mutate(date, action, successMessage) {
    this.busy = date;
    try {
      await action();
      if (successMessage) toast(this, successMessage);
      await this.load();
    } catch (err) {
      reportError(this, err);
    } finally {
      this.busy = null;
    }
  }

  togglePin(day) {
    const pinned = day.status !== 'pinned';
    return this.mutate(day.date, () => api.menu.update(day.date, { pinned }), t('menu.updated'));
  }

  logEaten(day) {
    return this.mutate(day.date, () => api.menu.eaten(day.date), t('menu.eatenLogged'));
  }

  /**
   * Edit and Choose both open the swap suggestions for the day. The API has
   * no list of all dinners, so suggestions are the only source of choices.
   */
  async toggleSuggestions(day) {
    if (this.suggestFor === day.date) {
      this.suggestFor = null;
      return;
    }
    this.suggestFor = day.date;
    this.suggestions = [];
    try {
      this.suggestions = listOf(await api.menu.swapSuggestions(day.date), 'suggestions', 'dinners');
    } catch (err) {
      reportError(this, err);
    }
  }

  chooseSuggestion(day, dinnerId) {
    this.suggestFor = null;
    return this.mutate(day.date, () => api.menu.swap(day.date, dinnerId), t('menu.updated'));
  }

  async resolveWarning(warning) {
    try {
      await api.warnings.resolve(warning.id);
      this.warnings = this.warnings.filter((w) => w.id !== warning.id);
    } catch (err) {
      reportError(this, err);
    }
  }

  async replan() {
    this.busy = 'replan';
    try {
      await api.menu.replan();
      toast(this, t('menu.replanned'));
      await this.load();
    } catch (err) {
      reportError(this, err);
    } finally {
      this.busy = null;
    }
  }

  renderWarnings() {
    if (!this.warnings.length) return '';
    return html`<section class="banner" role="status" aria-label="${t('warnings.title')}">
      ${icon('alert')}
      <div class="grow">
        <strong>${t('warnings.title')}</strong>
        <ul>
          ${this.warnings.map((w) => {
            const key = `warning.${w.code}`;
            const text = t(key);
            const message = text === key ? t('warning.unknown', { code: w.code }) : text;
            return html`<li class="row">
              <span class="grow">${message}</span>
              <md-text-button @click=${() => this.resolveWarning(w)}>${t('warnings.resolve')}</md-text-button>
            </li>`;
          })}
        </ul>
      </div>
    </section>`;
  }

  renderDinner(day) {
    if (!day.dinner) return html`<span class="muted">${t('menu.noDinner')}</span>`;
    return html`<div class="dinner">
      ${(day.dinner.items ?? []).map(
        (item) => html`<span class="chip-type">${item.name} · ${t(`type.${item.type}`)}</span>`,
      )}
    </div>`;
  }

  renderSuggestions(day) {
    if (this.suggestFor !== day.date) return '';
    if (!this.suggestions.length) {
      return html`<div class="card stack" aria-live="polite">
        <p class="muted">${t('menu.noSuggestions')}</p>
      </div>`;
    }
    return html`<div class="card stack" role="group" aria-label="${t('menu.chooseDinner', { date: day.date })}">
      <h3>${t('menu.chooseDinner', { date: formatDay(day.date, this.locale()) })}</h3>
      ${this.suggestions.map(
        (dinner) => html`<div class="row">
          <span class="grow">${(dinner.items ?? []).map((i) => i.name).join(', ')}</span>
          ${dinner.kcal != null ? html`<span class="muted">${t('menu.kcal', { kcal: dinner.kcal })}</span>` : ''}
          <md-outlined-button @click=${() => this.chooseSuggestion(day, dinner.id)}>
            ${t('menu.useDinner')}
          </md-outlined-button>
        </div>`,
      )}
    </div>`;
  }

  locale() {
    return document.documentElement.lang || 'en';
  }

  renderDay(day) {
    const isToday = day.date === isoDate();
    const isEmpty = day.status === 'empty' || !day.dinner;
    const isEaten = day.status === 'eaten';
    const isPinned = day.status === 'pinned';
    const busy = this.busy === day.date;
    const balance = day.balance ?? 'unknown';
    const kcalText = day.kcal != null ? t('menu.kcal', { kcal: day.kcal }) : t('menu.kcalUnknown');
    const editLabel = isEmpty
      ? t('menu.chooseDinner', { date: day.date })
      : t('menu.dinnerFor', { date: day.date });
    const swapLabel = isEmpty
      ? t('menu.chooseDinner', { date: day.date })
      : t('menu.swapFor', { date: day.date });

    return html`<article class="day ${isToday ? 'today' : ''}" data-date=${day.date}>
      <div class="when">${formatDay(day.date, this.locale())}</div>
      <div class="stack">
        ${this.renderDinner(day)}
        <div class="row">
          <span class="badge ${day.status}">${t(`menu.status.${day.status}`)}</span>
          <span class="badge ${balance}">${t(`menu.balance.${balance}`)}</span>
          <span class="muted">${kcalText}</span>
          ${day.replaced_reason ? html`<span class="muted">${t('menu.replacedHint')}</span>` : ''}
        </div>
      </div>
      <div class="actions">
        <md-icon-button
          toggle
          aria-label="${t('menu.pin')}: ${day.date}"
          aria-pressed=${isPinned ? 'true' : 'false'}
          ?disabled=${isEmpty || busy || isEaten}
          @click=${() => this.togglePin(day)}
        >${icon('pin')}</md-icon-button>
        <md-icon-button
          aria-label=${editLabel}
          ?disabled=${isEaten || busy}
          @click=${() => this.toggleSuggestions(day)}
        >${icon('pencil')}</md-icon-button>
        <md-icon-button
          aria-label=${swapLabel}
          ?disabled=${isEaten || busy || isEmpty}
          @click=${() => this.toggleSuggestions(day)}
        >${icon('swap')}</md-icon-button>
        <md-icon-button
          toggle
          aria-label="${t('menu.logEaten')}: ${day.date}"
          aria-pressed=${isEaten ? 'true' : 'false'}
          ?disabled=${isEmpty || busy || isEaten}
          @click=${() => this.logEaten(day)}
        >${icon('check')}</md-icon-button>
      </div>
      ${this.renderSuggestions(day)}
    </article>`;
  }

  render() {
    return html`<div class="page">
      <div class="page-head">
        <div>
          <h2>${t('menu.title')}</h2>
          <p class="muted">${t('menu.subtitle', { days: this.windowDays })}</p>
        </div>
        <md-outlined-button ?disabled=${this.busy === 'replan'} @click=${() => this.replan()}>
          ${icon('refresh')} ${t('menu.replan')}
        </md-outlined-button>
      </div>
      ${this.renderWarnings()}
      ${this.loading
        ? html`<div class="loading" role="status"><md-circular-progress indeterminate></md-circular-progress>${t('common.loading')}</div>`
        : this.days.length
          ? this.days.map((day) => this.renderDay(day))
          : html`<p class="muted">${t('menu.empty')}</p>`}
    </div>`;
  }
}

customElements.define('mp-menu-view', MpMenuView);
