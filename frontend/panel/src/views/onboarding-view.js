import { MpView, html, reportError, t } from '../../../shared/components/common.js';
import { api } from '../../../shared/api/instance.js';
import { resolveLocale } from '../../../shared/i18n/index.js';
import { setLocale } from '../../../shared/i18n/current.js';

const STEPS = ['language', 'starter', 'preferences'];
const TARGET_KEYS = ['vegetables', 'protein', 'carbs', 'tolerance'];
const SLOT_KEYS = ['protein', 'vegetable', 'carb'];

export class MpOnboardingView extends MpView {
  static properties = {
    settings: { attribute: false },
    setup: { attribute: false },
    template: { attribute: false },
    step: { state: true },
    form: { state: true },
    dinnerTemplate: { state: true },
    saving: { state: true },
    initialized: { state: true },
  };

  constructor() {
    super();
    this.settings = null;
    this.setup = null;
    this.template = null;
    this.step = 0;
    this.form = null;
    this.dinnerTemplate = null;
    this.saving = false;
    this.initialized = false;
  }

  updated() {
    if (this.initialized || !this.settings || !this.setup || !this.template) return;
    const language = ['en', 'nl'].includes(this.settings.language)
      ? this.settings.language
      : resolveLocale(navigator.language);
    this.form = {
      language,
      seed_ingredients: true,
      seed_meals: true,
      window_days: Number(this.settings.window_days ?? 14),
      household_size: Number(this.settings.household_size ?? 2),
      repeat_gap_days: Number(this.settings.repeat_gap_days ?? 14),
      balance_targets: { ...this.settings.balance_targets },
      fish_min_per_7_days: 1,
      vegetarian_min_per_7_days: 2,
    };
    this.dinnerTemplate = {
      protein: Number(this.template.protein ?? 1),
      vegetable: Number(this.template.vegetable ?? 1),
      carb: Number(this.template.carb ?? 1),
    };
    this.initialized = true;
    this.applyLanguage(language);
  }

  applyLanguage(language) {
    setLocale(language);
    document.documentElement.lang = language;
    document.title = t('app.title');
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
    this.dinnerTemplate = { ...this.dinnerTemplate, [key]: value };
  }

  setSeed(key, value) {
    const next = { ...this.form, [key]: value };
    if (!next.seed_ingredients && !next.seed_meals) {
      next.fish_min_per_7_days = 0;
      next.vegetarian_min_per_7_days = 0;
    }
    this.form = next;
  }

  changeLanguage(language) {
    this.setField('language', language);
    this.applyLanguage(language);
  }

  get pack() {
    return this.setup?.packs?.[this.form?.language] ?? { ingredients: [], meals: [] };
  }

  hasStarterContent() {
    return this.form.seed_ingredients || this.form.seed_meals;
  }

  nextStep() {
    if (this.step < STEPS.length - 1) this.step += 1;
  }

  previousStep() {
    if (this.step > 0) this.step -= 1;
  }

  async finish() {
    if (this.saving) return;
    this.saving = true;
    try {
      const payload = {
        ...this.form,
        fish_min_per_7_days: this.hasStarterContent() ? this.form.fish_min_per_7_days : 0,
        vegetarian_min_per_7_days: this.hasStarterContent()
          ? this.form.vegetarian_min_per_7_days
          : 0,
        balance_targets: this.form.balance_targets,
        template: this.dinnerTemplate,
      };
      const result = await api.onboarding.complete(payload);
      if (result.seeded.ingredients || result.seeded.meals) {
        try {
          await api.menu.replan();
        } catch (err) {
          reportError(this, err);
        }
      }
      this.dispatchEvent(new CustomEvent('setup-complete', { bubbles: true, composed: true }));
    } catch (err) {
      reportError(this, err);
    } finally {
      this.saving = false;
    }
  }

  renderLanguageStep() {
    return html`<section class="onboarding-panel stack">
      <p class="eyebrow">${t('onboarding.stepLabel', { current: 1, total: STEPS.length })}</p>
      <h2>${t('onboarding.language.title')}</h2>
      <p class="muted">${t('onboarding.language.help')}</p>
      <md-outlined-select
        label=${t('settings.language')}
        .value=${this.form.language}
        @change=${(event) => this.changeLanguage(event.target.value)}
      >
        <md-select-option value="nl" ?selected=${this.form.language === 'nl'}>
          <div slot="headline">${t('settings.language.nl')}</div>
        </md-select-option>
        <md-select-option value="en" ?selected=${this.form.language === 'en'}>
          <div slot="headline">${t('settings.language.en')}</div>
        </md-select-option>
      </md-outlined-select>
      <div class="onboarding-note">${t('onboarding.language.persist')}</div>
    </section>`;
  }

  renderPackOption(key, enabled, titleKey, helpKey, names, categories, count) {
    return html`<section class="seed-option">
      <label class="seed-option-heading">
        <md-checkbox .checked=${enabled} @change=${(event) => this.setSeed(key, event.target.checked)}></md-checkbox>
        <span class="seed-option-copy">
          <strong>${t(titleKey)}</strong>
          <small>${t(helpKey)}</small>
        </span>
        <span class="seed-count">${count}</span>
      </label>
      ${enabled
        ? html`<details class="seed-preview">
            <summary>${t('onboarding.starter.preview')}</summary>
            <p><strong>${t('onboarding.starter.previewItems')}</strong> ${names.join(' · ')}</p>
            <p><strong>${t('onboarding.starter.previewCategories')}</strong> ${categories.join(' · ')}</p>
          </details>`
        : ''}
    </section>`;
  }

  renderStarterStep() {
    const pack = this.pack;
    const languageName = t(`onboarding.contentLanguage.${this.form.language}`);
    return html`<section class="onboarding-panel stack">
      <p class="eyebrow">${t('onboarding.stepLabel', { current: 2, total: STEPS.length })}</p>
      <h2>${t('onboarding.starter.title')}</h2>
      <p class="muted">${t('onboarding.starter.help', { language: languageName })}</p>
      <div class="seed-options">
        ${this.renderPackOption(
          'seed_ingredients',
          this.form.seed_ingredients,
          'onboarding.starter.ingredients',
          'onboarding.starter.ingredientsHelp',
          pack.ingredients ?? [],
          pack.ingredient_categories ?? [],
          pack.ingredient_count ?? 0,
        )}
        ${this.renderPackOption(
          'seed_meals',
          this.form.seed_meals,
          'onboarding.starter.meals',
          'onboarding.starter.mealsHelp',
          pack.meals ?? [],
          pack.meal_categories ?? [],
          pack.meal_count ?? 0,
        )}
      </div>
      <p class="onboarding-note">
        ${this.hasStarterContent()
          ? t('onboarding.starter.selected', {
              ingredients: this.form.seed_ingredients ? pack.ingredient_count : 0,
              meals: this.form.seed_meals ? pack.meal_count : 0,
              language: languageName,
            })
          : t('onboarding.starter.emptySelection')}
      </p>
      <md-text-button @click=${() => {
        this.setSeed('seed_ingredients', false);
        this.setSeed('seed_meals', false);
      }}>${t('onboarding.starter.noSeed')}</md-text-button>
    </section>`;
  }

  renderNumberField(label, value, min, max, change, help = '') {
    return html`<md-outlined-text-field
      label=${label}
      type="number"
      min=${min}
      max=${max}
      .value=${String(value)}
      supporting-text=${help}
      @change=${(event) => change(Number(event.target.value))}
    ></md-outlined-text-field>`;
  }

  renderPreferencesStep() {
    const targets = this.form.balance_targets;
    const targetSum = TARGET_KEYS.slice(0, 3).reduce((sum, key) => sum + Number(targets[key]), 0);
    const hasContent = this.hasStarterContent();
    return html`<section class="onboarding-panel stack">
      <p class="eyebrow">${t('onboarding.stepLabel', { current: 3, total: STEPS.length })}</p>
      <h2>${t('onboarding.preferences.title')}</h2>
      <p class="muted">${t('onboarding.preferences.help')}</p>

      <section class="onboarding-group stack">
        <h3>${t('settings.window.title')}</h3>
        <label class="field-label" for="onboarding-window">${t('settings.window.value', { days: this.form.window_days })}</label>
        <md-slider
          id="onboarding-window"
          min="7"
          max="60"
          labeled
          .value=${String(this.form.window_days)}
          @change=${(event) => this.setField('window_days', Number(event.target.value))}
        ></md-slider>
        <div class="grid-2">
          ${this.renderNumberField(
            t('settings.household.size'),
            this.form.household_size,
            1,
            10,
            (value) => this.setField('household_size', value),
          )}
          ${this.renderNumberField(
            t('settings.household.gap'),
            this.form.repeat_gap_days,
            0,
            60,
            (value) => this.setField('repeat_gap_days', value),
          )}
        </div>
      </section>

      <section class="onboarding-group stack">
        <h3>${t('onboarding.preferences.diet')}</h3>
        ${hasContent
          ? html`<div class="grid-2">
              ${this.renderNumberField(
                t('onboarding.preferences.fish'),
                this.form.fish_min_per_7_days,
                0,
                7,
                (value) => this.setField('fish_min_per_7_days', value),
                t('onboarding.preferences.perWeek'),
              )}
              ${this.renderNumberField(
                t('onboarding.preferences.vegetarian'),
                this.form.vegetarian_min_per_7_days,
                0,
                7,
                (value) => this.setField('vegetarian_min_per_7_days', value),
                t('onboarding.preferences.perWeek'),
              )}
            </div>`
          : html`<p class="muted">${t('onboarding.preferences.noSeedHelp')}</p>`}
      </section>

      <section class="onboarding-group stack">
        <h3>${t('settings.template.title')}</h3>
        <div class="grid-2">
          ${SLOT_KEYS.map((key) =>
            this.renderNumberField(
              t(`settings.template.${key}`),
              this.dinnerTemplate[key],
              0,
              2,
              (value) => this.setSlot(key, value),
            ),
          )}
        </div>
      </section>

      <section class="onboarding-group stack">
        <h3>${t('settings.balance.title')}</h3>
        <div class="grid-2">
          ${TARGET_KEYS.map((key) =>
            this.renderNumberField(
              t(`settings.balance.${key}`),
              targets[key],
              0,
              100,
              (value) => this.setTarget(key, value),
            ),
          )}
        </div>
        <p class=${targetSum === 100 ? 'muted' : 'validation-message'}>
          ${targetSum === 100
            ? t('settings.balance.help')
            : t('onboarding.preferences.targetSum', { sum: targetSum })}
        </p>
      </section>
    </section>`;
  }

  render() {
    if (!this.initialized) {
      return html`<div class="loading" role="status"><md-circular-progress indeterminate></md-circular-progress>${t('common.loading')}</div>`;
    }
    const validTargets =
      TARGET_KEYS.slice(0, 3).reduce((sum, key) => sum + Number(this.form.balance_targets[key]), 0) === 100;
    const validTemplate = SLOT_KEYS.some((key) => Number(this.dinnerTemplate[key]) > 0);
    return html`<main class="onboarding-shell">
      <header class="onboarding-brand">
        <div class="brand-mark" aria-hidden="true">MP</div>
        <div><strong>${t('app.title')}</strong><span>${t('onboarding.brandSubtitle')}</span></div>
        <div class="onboarding-progress" aria-label="${t('onboarding.stepLabel', {
          current: this.step + 1,
          total: STEPS.length,
        })}">
          ${STEPS.map((_, index) => html`<span class=${index <= this.step ? 'active' : ''}></span>`)}
        </div>
      </header>
      ${this.step === 0
        ? this.renderLanguageStep()
        : this.step === 1
          ? this.renderStarterStep()
          : this.renderPreferencesStep()}
      <footer class="onboarding-actions">
        ${this.step > 0
          ? html`<md-text-button @click=${() => this.previousStep()}>${t('common.back')}</md-text-button>`
          : html`<span></span>`}
        ${this.step < STEPS.length - 1
          ? html`<md-filled-button @click=${() => this.nextStep()}>${t('common.continue')}</md-filled-button>`
          : html`<md-filled-button
              ?disabled=${this.saving || !validTargets || !validTemplate}
              @click=${() => this.finish()}
            >${this.saving ? t('common.saving') : t('onboarding.finish')}</md-filled-button>`}
      </footer>
    </main>`;
  }
}

customElements.define('mp-onboarding-view', MpOnboardingView);
