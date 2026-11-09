/**
 * Item dialog: create or edit an item, its categories, flags, and nutrition
 * (lookup, match confirmation, manual entry). Hosted once by the app shell.
 *
 * md-dialog fires `closed` on itself without bubbling, so this element
 * re-dispatches it on the host for the app shell to listen to.
 */
import {
  MpView,
  confirmAction,
  html,
  icon,
  itemsChanged,
  listOf,
  reportError,
  toast,
  typeLabel,
  t,
} from '../../../shared/components/common.js';
import { api } from '../../../shared/api/instance.js';

const TYPES = ['protein', 'vegetable', 'carb'];
const NUTRITION_FIELDS = [
  { key: 'kcal', label: 'item.nutrition.kcal' },
  { key: 'protein_g', label: 'item.nutrition.protein' },
  { key: 'carbs_g', label: 'item.nutrition.carbs' },
  { key: 'fat_g', label: 'item.nutrition.fat' },
  { key: 'fiber_g', label: 'item.nutrition.fiber' },
];
const DEFAULT_PORTION_GRAMS = '300';

function emptyForm() {
  return {
    name: '',
    type: 'protein',
    portion_grams: DEFAULT_PORTION_GRAMS,
    fat_source: false,
    track_stock: false,
    is_complete_meal: false,
    category_ids: [],
  };
}

function formFromItem(item) {
  return {
    name: item.name ?? '',
    type: item.type ?? 'protein',
    portion_grams: item.portion_grams == null ? '' : String(item.portion_grams),
    fat_source: Boolean(item.fat_source),
    track_stock: Boolean(item.track_stock),
    is_complete_meal: Boolean(item.is_complete_meal),
    category_ids: [...(item.category_ids ?? [])],
  };
}

function valuesFrom(nutrition) {
  const values = {};
  for (const { key } of NUTRITION_FIELDS) {
    values[key] = nutrition?.[key] == null ? '' : String(nutrition[key]);
  }
  return values;
}

function nutritionFromItem(nutrition) {
  return {
    values: valuesFrom(nutrition),
    status: nutrition?.status ?? 'none',
    source: nutrition?.source ?? null,
    confirmed: Boolean(nutrition?.user_confirmed),
    dirty: false,
  };
}

function toNumber(value) {
  if (value === '' || value == null) return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function nutritionPayload(values) {
  const payload = {};
  for (const { key } of NUTRITION_FIELDS) payload[key] = toNumber(values[key]);
  return payload;
}

export class MpItemDialog extends MpView {
  static properties = {
    open: { type: Boolean },
    itemId: { attribute: false },
    item: { state: true },
    categories: { state: true },
    form: { state: true },
    nutrition: { state: true },
    nameError: { state: true },
    busy: { state: true },
  };

  constructor() {
    super();
    this.open = false;
    this.itemId = null;
    this.item = null;
    this.categories = [];
    this.form = emptyForm();
    this.nutrition = nutritionFromItem(null);
    this.nameError = false;
    this.busy = null;
  }

  updated(changed) {
    if (changed.has('open') && this.open) this.start();
  }

  async start() {
    this.nameError = false;
    this.busy = null;
    this.item = null;
    this.form = emptyForm();
    this.nutrition = nutritionFromItem(null);
    this.busy = 'load';
    try {
      const [categories, item] = await Promise.all([
        api.categories.list(),
        this.itemId ? api.items.get(this.itemId) : null,
      ]);
      this.categories = listOf(categories, 'categories', 'items');
      if (item) this.applyItem(item);
    } catch (err) {
      reportError(this, err);
    } finally {
      this.busy = null;
    }
  }

  applyItem(item) {
    this.item = item;
    this.form = formFromItem(item);
    this.nutrition = nutritionFromItem(item.nutrition);
  }

  async reloadItem() {
    if (!this.itemId) return;
    this.applyItem(await api.items.get(this.itemId));
  }

  setField(key, value) {
    this.form = { ...this.form, [key]: value };
  }

  toggleCategory(id) {
    const ids = this.form.category_ids;
    const next = ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id];
    this.setField('category_ids', next);
  }

  setNutritionValue(key, value) {
    this.nutrition = {
      ...this.nutrition,
      values: { ...this.nutrition.values, [key]: value },
      dirty: true,
    };
  }

  close() {
    this.querySelector('md-dialog')?.close();
  }

  payload() {
    return {
      name: this.form.name.trim(),
      type: this.form.type,
      portion_grams: toNumber(this.form.portion_grams),
      fat_source: this.form.fat_source,
      track_stock: this.form.track_stock,
      is_complete_meal: this.form.is_complete_meal,
      category_ids: this.form.category_ids,
    };
  }

  async save() {
    const payload = this.payload();
    if (!payload.name) {
      this.nameError = true;
      return;
    }
    this.nameError = false;
    this.busy = 'save';
    try {
      let id = this.itemId;
      if (id) {
        await api.items.update(id, payload);
      } else {
        const created = await api.items.create(payload);
        id = created?.id;
      }
      if (this.nutrition.dirty && id) {
        await api.items.setNutrition(id, {
          ...nutritionPayload(this.nutrition.values),
          source: 'manual',
          user_confirmed: false,
        });
      }
      toast(this, t('item.saved'), 'info');
      itemsChanged(this);
      this.close();
    } catch (err) {
      reportError(this, err);
    } finally {
      this.busy = null;
    }
  }

  async remove() {
    if (!this.itemId || !(await confirmAction(this, t('item.confirmDelete')))) return;
    this.busy = 'delete';
    try {
      await api.items.remove(this.itemId);
      toast(this, t('item.deleted'), 'info');
      itemsChanged(this);
      this.close();
    } catch (err) {
      reportError(this, err);
    } finally {
      this.busy = null;
    }
  }

  async lookup() {
    if (!this.itemId) return;
    this.busy = 'lookup';
    try {
      await api.items.lookupNutrition(this.itemId);
      toast(this, t('item.nutrition.lookupStarted'), 'info');
      await this.reloadItem();
    } catch (err) {
      reportError(this, err);
    } finally {
      this.busy = null;
    }
  }

  async confirmMatch() {
    if (!this.itemId) return;
    this.busy = 'confirm';
    try {
      await api.items.setNutrition(this.itemId, {
        ...nutritionPayload(this.nutrition.values),
        source: this.nutrition.source,
        user_confirmed: true,
      });
      toast(this, t('item.nutrition.confirmed'), 'info');
      itemsChanged(this);
      await this.reloadItem();
    } catch (err) {
      reportError(this, err);
    } finally {
      this.busy = null;
    }
  }

  renderNutritionBadge() {
    const { status, source, confirmed } = this.nutrition;
    if (confirmed) {
      return html`<span class="badge verified">${icon('check')}${t('item.nutrition.verified', { source: source ?? '' })}</span>`;
    }
    if (status === 'candidate') {
      return html`<span class="badge warn">${icon('alert')}${t('item.nutrition.candidate')}</span>`;
    }
    if (status === 'failed') {
      return html`<span class="badge warn">${icon('alert')}${t('item.nutrition.failed')}</span>`;
    }
    return html`<span class="badge unverified">${t('item.nutrition.unverified')}</span>`;
  }

  renderNutrition() {
    const busy = this.busy;
    return html`
      <section class="stack" aria-labelledby="item-nutrition-title">
        <div class="row">
          <h3 id="item-nutrition-title" class="grow">${t('item.nutrition.title')}</h3>
          ${this.renderNutritionBadge()}
        </div>
        ${this.nutrition.status === 'candidate' && !this.nutrition.confirmed
          ? html`
              <div class="banner" role="status">
                <div class="grow">
                  <strong>${t('item.nutrition.matchTitle')}</strong>
                  <p class="muted">${t('item.nutrition.matchHelp')}</p>
                </div>
                <md-filled-button ?disabled=${busy === 'confirm'} @click=${() => this.confirmMatch()}>
                  ${t('item.nutrition.confirm')}
                </md-filled-button>
              </div>`
          : ''}
        <div class="grid-2">
          ${NUTRITION_FIELDS.map(
            ({ key, label }) => html`
              <md-outlined-text-field
                type="number"
                min="0"
                step="any"
                label=${t(label)}
                .value=${this.nutrition.values[key]}
                @input=${(e) => this.setNutritionValue(key, e.target.value)}
              ></md-outlined-text-field>`,
          )}
        </div>
        <div class="row">
          <p class="muted grow">${this.itemId ? t('item.nutrition.manualHelp') : ''}</p>
          <md-outlined-button ?disabled=${!this.itemId || busy === 'lookup'} @click=${() => this.lookup()}>
            ${t('item.nutrition.lookup')}
          </md-outlined-button>
        </div>
      </section>`;
  }

  render() {
    const busy = this.busy;
    const editing = Boolean(this.itemId);
    const title = t(editing ? 'item.title.edit' : 'item.title.add');
    return html`
      <md-dialog class="item-dialog" aria-label=${title} ?open=${this.open} @closed=${(e) => this.onClosed(e)}>
        <div slot="headline">${title}</div>
        <div slot="content" class="dialog-body">
          <md-outlined-text-field
            label=${t('item.name')}
            required
            .value=${this.form.name}
            ?error=${this.nameError}
            errorText=${this.nameError ? t('item.nameRequired') : ''}
            @input=${(e) => this.setField('name', e.target.value)}
          ></md-outlined-text-field>

          <fieldset class="stack">
            <legend class="field-label">${t('item.flags')}</legend>
            <label class="switch-row">
              <md-switch
                ?selected=${this.form.is_complete_meal}
                @change=${(e) => {
                  const isCompleteMeal = e.target.selected;
                  this.form = {
                    ...this.form,
                    is_complete_meal: isCompleteMeal,
                    type: isCompleteMeal ? 'carb' : this.form.type,
                  };
                }}
              ></md-switch>
              <span><strong>${t('item.completeMeal')}</strong><br /><span class="muted">${t('item.completeMealHelp')}</span></span>
            </label>
          </fieldset>

          ${this.form.is_complete_meal
            ? ''
            : html`<fieldset class="stack">
                <legend class="field-label">${t('item.type')}</legend>
                <div class="chips">
                  ${TYPES.map(
                    (type) => html`
                      <label class="row">
                        <md-radio
                          name="item-type"
                          value=${type}
                          ?checked=${this.form.type === type}
                          @change=${() => this.setField('type', type)}
                        ></md-radio>
                        ${typeLabel(type)}
                      </label>`,
                  )}
                </div>
              </fieldset>`}

          <fieldset class="stack">
            <legend class="field-label">${t('item.categories')}</legend>
            <div class="chips">
              ${this.categories.map(
                (cat) => html`
                  <md-filter-chip
                    label=${cat.name}
                    ?selected=${this.form.category_ids.includes(cat.id)}
                    @click=${() => this.toggleCategory(cat.id)}
                  ></md-filter-chip>`,
              )}
            </div>
          </fieldset>

          <md-outlined-text-field
            type="number"
            min="0"
            label=${t('item.portion')}
            supportingText=${t('item.portionHelp')}
            .value=${this.form.portion_grams}
            @input=${(e) => this.setField('portion_grams', e.target.value)}
          ></md-outlined-text-field>

          <fieldset class="stack">
            <label class="switch-row">
              <md-switch
                ?selected=${this.form.fat_source}
                @change=${(e) => this.setField('fat_source', e.target.selected)}
              ></md-switch>
              <span><strong>${t('item.fatSource')}</strong><br /><span class="muted">${t('item.fatSourceHelp')}</span></span>
            </label>
            <label class="switch-row">
              <md-switch
                ?selected=${this.form.track_stock}
                @change=${(e) => this.setField('track_stock', e.target.selected)}
              ></md-switch>
              <span><strong>${t('item.trackStock')}</strong><br /><span class="muted">${t('item.trackStockHelp')}</span></span>
            </label>
          </fieldset>

          ${this.renderNutrition()}
        </div>
        <div slot="actions" class="row">
          ${editing
            ? html`<md-text-button class="danger" ?disabled=${busy !== null} @click=${() => this.remove()}>
                ${t('item.delete')}
              </md-text-button>`
            : ''}
          <span class="grow"></span>
          <md-text-button ?disabled=${busy === 'save'} @click=${() => this.close()}>${t('common.cancel')}</md-text-button>
          <md-filled-button ?disabled=${busy !== null} @click=${() => this.save()}>${t('common.save')}</md-filled-button>
        </div>
      </md-dialog>`;
  }

  onClosed(e) {
    e.stopPropagation();
    this.dispatchEvent(new Event('closed'));
  }
}

customElements.define('mp-item-dialog', MpItemDialog);
