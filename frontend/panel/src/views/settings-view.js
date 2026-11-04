/**
 * Settings tab: menu window, household, repeat gap, balance targets, dinner
 * template, language, and the write-only USDA key. Retry failed lookups lives here too.
 */
import { MpView, html, reportError, toast, t } from '../../../shared/components/common.js';
import { api } from '../../../shared/api/instance.js';

const WINDOW_MIN = 7;
const WINDOW_MAX = 60;
const SLOT_MAX = 2;
const LANGUAGES = ['auto', 'en', 'nl'];
const RELOAD_DELAY_MS = 1200;

function numberOr(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export class MpSettingsView extends MpView {
  static properties = {
    form: { state: true },
    template: { state: true },
    usdaKey: { state: true },
    loading: { state: true },
    saving: { state: true },
  };

  constructor() {
    super();
    this.form = null;
    this.template = { protein: 0, vegetable: 0, carb: 0 };
    /** Typed into the write-only field; never pre-filled from the server. */
    this.usdaKey = '';
    this.loading = true;
    this.saving = false;
    this.loadedLanguage = null;
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  async load() {
    this.loading = true;
    try {
      const [settings, template] = await Promise.all([api.settings.get(), api.template.get()]);
      this.form = {
        window_days: numberOr(settings.window_days, 14),
        household_size: numberOr(settings.household_size, 2),
        repeat_gap_days: numberOr(settings.repeat_gap_days, 14),
        language: settings.language ?? 'auto',
        balance_targets: {
          vegetables: numberOr(settings.balance_targets?.vegetables, 50),
          protein: numberOr(settings.balance_targets?.protein, 25),
          carbs: numberOr(settings.balance_targets?.carbs, 25),
          tolerance: numberOr(settings.balance_targets?.tolerance, 10),
        },
      };
      this.loadedLanguage = this.form.language;
      this.template = {
        protein: numberOr(template?.protein, 1),
        vegetable: numberOr(template?.vegetable, 1),
        carb: numberOr(template?.carb, 1),
      };
    } catch (err) {
      reportError(this, err);
    } finally {
      this.loading = false;
    }
  }

  setField(key, value) {
    this.form = { ...this.form, [key]: value };
  }

  setTarget(key, value) {
    this.form = {
      ...this.form,
      balance_targets: { ...this.form.balance_targets, [key]: value },
    };
  }

  setSlot(key, value) {
    this.template = { ...this.template, [key]: value };
  }

  buildSettingsPayload() {
    const payload = {
      window_days: this.form.window_days,
      household_size: this.form.household_size,
      repeat_gap_days: this.form.repeat_gap_days,
      language: this.form.language,
      balance_targets: this.form.balance_targets,
    };
    if (this.usdaKey.trim()) payload.usda_api_key = this.usdaKey.trim();
    return payload;
  }

  async save() {
    if (!this.form || this.saving) return;
    this.saving = true;
    try {
      await Promise.all([
        api.settings.update(this.buildSettingsPayload()),
        api.template.update({ ...this.template }),
      ]);
      this.usdaKey = '';
      toast(this, t('settings.saved'));
      if (this.form.language !== this.loadedLanguage) {
        toast(this, t('settings.reloadForLanguage'));
        setTimeout(() => window.location.reload(), RELOAD_DELAY_MS);
      }
    } catch (err) {
      reportError(this, err);
    } finally {
      this.saving = false;
    }
  }

  async retryLookups() {
    try {
      await api.settings.retryLookups();
      toast(this, t('settings.retryStarted'));
    } catch (err) {
      reportError(this, err);
    }
  }

  renderWindow() {
    const days = this.form.window_days;
    return html`<section class="card stack">
      <h3>${t('settings.window.title')}</h3>
      <label class="field-label" for="window-slider">${t('settings.window.label')}: ${t('settings.window.value', { days })}</label>
      <md-slider
        id="window-slider"
        min=${WINDOW_MIN}
        max=${WINDOW_MAX}
        value=${days}
        labeled
        @change=${(e) => this.setField('window_days', Number(e.target.value))}
      ></md-slider>
      <p class="muted">${t('settings.window.help')}</p>
    </section>`;
  }

  renderHousehold() {
    return html`<section class="card stack">
      <h3>${t('settings.household.title')}</h3>
      <div class="grid-2">
        <md-outlined-text-field
          label=${t('settings.household.size')}
          type="number"
          min="1"
          max="10"
          .value=${String(this.form.household_size)}
          supporting-text=${t('settings.household.sizeHelp')}
          @change=${(e) => this.setField('household_size', Number(e.target.value))}
        ></md-outlined-text-field>
        <md-outlined-text-field
          label=${t('settings.household.gap')}
          type="number"
          min="0"
          max="60"
          .value=${String(this.form.repeat_gap_days)}
          supporting-text=${t('settings.household.gapHelp')}
          @change=${(e) => this.setField('repeat_gap_days', Number(e.target.value))}
        ></md-outlined-text-field>
      </div>
    </section>`;
  }

  renderBalance() {
    const targets = this.form.balance_targets;
    const field = (key, label) => html`<md-outlined-text-field
      label=${label}
      type="number"
      min="0"
      max="100"
      .value=${String(targets[key])}
      @change=${(e) => this.setTarget(key, Number(e.target.value))}
    ></md-outlined-text-field>`;
    return html`<section class="card stack">
      <h3>${t('settings.balance.title')}</h3>
      <div class="grid-2">
        ${field('vegetables', t('settings.balance.vegetables'))}
        ${field('protein', t('settings.balance.protein'))}
        ${field('carbs', t('settings.balance.carbs'))}
        ${field('tolerance', t('settings.balance.tolerance'))}
      </div>
      <p class="muted">${t('settings.balance.help')}</p>
    </section>`;
  }

  renderTemplate() {
    const slot = (key, label) => html`<md-outlined-text-field
      label=${label}
      type="number"
      min="0"
      max=${SLOT_MAX}
      .value=${String(this.template[key])}
      @change=${(e) => this.setSlot(key, Number(e.target.value))}
    ></md-outlined-text-field>`;
    return html`<section class="card stack">
      <h3>${t('settings.template.title')}</h3>
      <div class="grid-2">
        ${slot('protein', t('settings.template.protein'))}
        ${slot('vegetable', t('settings.template.vegetable'))}
        ${slot('carb', t('settings.template.carb'))}
      </div>
      <p class="muted">${t('settings.template.help')}</p>
    </section>`;
  }

  renderGeneral() {
    return html`<section class="card stack">
      <h3>${t('settings.general.title')}</h3>
      <md-outlined-select
        label=${t('settings.language')}
        .value=${this.form.language}
        @change=${(e) => this.setField('language', e.target.value)}
      >
        ${LANGUAGES.map(
          (code) => html`<md-select-option value=${code} ?selected=${this.form.language === code}>
            <div slot="headline">${t(`settings.language.${code}`)}</div>
          </md-select-option>`,
        )}
      </md-outlined-select>
      <md-outlined-text-field
        label=${t('settings.usda')}
        type="password"
        autocomplete="off"
        placeholder=${t('settings.usda.placeholder')}
        .value=${this.usdaKey}
        supporting-text=${t('settings.usda.help')}
        @input=${(e) => (this.usdaKey = e.target.value)}
      ></md-outlined-text-field>
      <div class="row">
        <md-outlined-button @click=${() => this.retryLookups()}>${t('settings.retry')}</md-outlined-button>
      </div>
    </section>`;
  }

  render() {
    if (this.loading) {
      return html`<div class="loading" role="status"><md-circular-progress indeterminate></md-circular-progress>${t('common.loading')}</div>`;
    }
    if (!this.form) return html`<p class="muted">${t('error.generic')}</p>`;
    return html`<div class="page">
      <div class="page-head">
        <h2>${t('settings.title')}</h2>
        <md-filled-button ?disabled=${this.saving} @click=${() => this.save()}>${t('common.save')}</md-filled-button>
      </div>
      ${this.renderWindow()}
      ${this.renderHousehold()}
      ${this.renderBalance()}
      ${this.renderTemplate()}
      ${this.renderGeneral()}
    </div>`;
  }
}

customElements.define('mp-settings-view', MpSettingsView);
