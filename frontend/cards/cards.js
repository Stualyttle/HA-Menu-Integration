import { LitElement, css, html } from 'lit';
import { cardStrings, dinnerItems, itemId } from './card-utils.js';

const STRINGS = {
  en: {
    today: "Today's dinner",
    stock: 'Stock check',
    window: 'Menu window',
    loading: 'Loading…',
    empty: 'No dinner planned for this day.',
    eaten: 'Log as eaten',
    logged: 'Eaten',
    swap: 'Swap dinner',
    apply: 'Choose this dinner',
    cancel: 'Cancel',
    noSuggestions: 'No valid alternatives are available.',
    stockQuestion: 'Do you have this item?',
    yes: 'Yes',
    no: 'No',
    confirmNo: 'Confirm no',
    replaces: 'May replace {count} dinners',
    emptyStock: 'No stock items to check.',
    kcal: '{value} kcal',
    balance: { ok: 'Balanced', off_target: 'Off target', unknown: 'Balance unknown' },
    statuses: { planned: 'Planned', pinned: 'Pinned', eaten: 'Eaten', empty: 'Empty' },
    errors: 'Could not load Menu Planner.',
  },
  nl: {
    today: 'Diner van vandaag',
    stock: 'Voorraad controleren',
    window: 'Menuvenster',
    loading: 'Laden…',
    empty: 'Er is geen diner gepland voor deze dag.',
    eaten: 'Markeer als gegeten',
    logged: 'Gegeten',
    swap: 'Diner wisselen',
    apply: 'Kies dit diner',
    cancel: 'Annuleren',
    noSuggestions: 'Er zijn geen geldige alternatieven.',
    stockQuestion: 'Heb je dit ingrediënt?',
    yes: 'Ja',
    no: 'Nee',
    confirmNo: 'Nee bevestigen',
    replaces: 'Vervangt mogelijk {count} diners',
    emptyStock: 'Geen voorraaditems om te controleren.',
    kcal: '{value} kcal',
    balance: { ok: 'In balans', off_target: 'Buiten doel', unknown: 'Balans onbekend' },
    statuses: { planned: 'Gepland', pinned: 'Vastgezet', eaten: 'Gegeten', empty: 'Leeg' },
    errors: 'Menu Planner kon niet worden geladen.',
  },
};

const baseStyles = css`
  :host {
    display: block;
    color: var(--primary-text-color, #212121);
    font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
  }
  ha-card {
    overflow: hidden;
    border-radius: var(--ha-card-border-radius, 12px);
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 16px 16px 0;
    font-size: 16px;
    font-weight: 500;
  }
  main { padding: 8px 16px 16px; }
  .muted, .meta { color: var(--secondary-text-color, #727272); }
  .meta { font-size: 12px; }
  .row, .actions, .metrics {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .row { justify-content: space-between; }
  .actions { flex-wrap: wrap; margin-top: 12px; }
  .metrics { flex-wrap: wrap; margin-top: 12px; }
  .chip {
    display: inline-flex;
    align-items: center;
    min-height: 26px;
    padding: 3px 10px;
    border-radius: 14px;
    background: var(--secondary-background-color, #f5f5f5);
    color: var(--secondary-text-color, #727272);
    font-size: 12px;
  }
  .warning { color: var(--error-color, #db4437); }
  button {
    min-height: 36px;
    border: 0;
    border-radius: 18px;
    padding: 0 14px;
    background: transparent;
    color: var(--primary-color, #03a9f4);
    font: inherit;
    font-weight: 500;
    cursor: pointer;
  }
  button.primary {
    background: var(--primary-color, #03a9f4);
    color: var(--text-primary-color, #fff);
  }
  button:disabled { opacity: 0.55; cursor: default; }
  ul { list-style: none; padding: 0; margin: 0; }
  li { padding: 10px 0; border-bottom: 1px solid var(--divider-color, #e0e0e0); }
  li:last-child { border-bottom: 0; }
  details { border-bottom: 1px solid var(--divider-color, #e0e0e0); }
  summary { cursor: pointer; list-style: none; padding: 10px 0; }
  summary::-webkit-details-marker { display: none; }
  .components { margin: 0 0 10px 14px; padding-left: 12px; border-left: 2px solid var(--divider-color, #e0e0e0); }
  .components li { padding: 3px 0; border: 0; }
  .error { color: var(--error-color, #db4437); }
`;

class MenuPlannerCard extends LitElement {
  static properties = {
    hass: { attribute: false },
    config: { attribute: false },
    data: { state: true },
    loading: { state: true },
    error: { state: true },
    suggestions: { state: true },
    preview: { state: true },
  };

  static styles = baseStyles;

  constructor() {
    super();
    this.data = null;
    this.loading = true;
    this.error = '';
    this._refreshTimer = null;
  }

  setConfig(config) {
    this.config = { ...config };
  }

  get _t() {
    return STRINGS[cardStrings(this.hass?.locale?.language)];
  }

  get _title() {
    return this.config?.title || this._t[this.constructor.titleKey];
  }

  connectedCallback() {
    super.connectedCallback();
    this._refreshTimer = window.setInterval(() => this._load(), 60_000);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    window.clearInterval(this._refreshTimer);
  }

  updated(changed) {
    if (changed.has('hass') && this.hass && !this._loaded) {
      this._load();
    }
  }

  async _ws(message) {
    if (!this.hass) throw new Error('Home Assistant connection is unavailable');
    return this.hass.callWS(message);
  }

  async _load() {
    if (!this.hass || this._loadingRequest) return;
    this._loadingRequest = true;
    this.loading = true;
    this.error = '';
    try {
      this.data = await this._fetchData();
      this._loaded = true;
    } catch (error) {
      this.error = error?.message || this._t.errors;
    } finally {
      this.loading = false;
      this._loadingRequest = false;
    }
  }

  async _fetchData() {
    return null;
  }

  async _act(action, reload = true) {
    this.error = '';
    try {
      await action();
      if (reload) await this._load();
    } catch (error) {
      this.error = error?.message || this._t.errors;
    }
  }

  _header(meta = '') {
    return html`<header><span>${this._title}</span>${meta ? html`<span class="meta">${meta}</span>` : ''}</header>`;
  }

  _error() {
    return this.error ? html`<p class="error" role="alert">${this.error}</p>` : '';
  }

  static getStubConfig() {
    return { type: `custom:${this.elementName}`, preview: true };
  }

  static getConfigForm() {
    return { schema: this.formSchema };
  }

  static getConfigElement() {
    const editor = document.createElement('menu-planner-card-editor');
    editor.schema = this.formSchema;
    return editor;
  }
}

class MenuPlannerTodayCard extends MenuPlannerCard {
  static titleKey = 'today';
  static elementName = 'menu-planner-today-card';
  static formSchema = [
    { name: 'title', selector: { text: {} } },
    { name: 'show_kcal', selector: { boolean: {} } },
    { name: 'show_balance', selector: { boolean: {} } },
  ];

  static styles = [baseStyles, css`.dinner-title { font-size: 20px; font-weight: 500; }`];

  async _fetchData() {
    return this._ws({ type: 'menu_planner/today' });
  }

  async _showSuggestions() {
    const day = this.data?.date;
    if (!day) return;
    await this._act(async () => {
      this.suggestions = await this._ws({ type: 'menu_planner/swap/suggestions', date: day });
    }, false);
  }

  async _applySwap(dinner) {
    const day = this.data?.date;
    const item_ids = dinnerItems(dinner).map(itemId).filter(Number.isInteger);
    if (!day || !item_ids.length) return;
    await this._act(async () => {
      await this._ws({ type: 'menu_planner/swap/apply', date: day, item_ids });
      this.suggestions = null;
    });
  }

  render() {
    const dinner = this.data?.dinner;
    const items = dinnerItems(dinner);
    const date = this.data?.date;
    const eaten = this.data?.status === 'eaten';
    const suggestions = Array.isArray(this.suggestions)
      ? this.suggestions
      : this.suggestions?.suggestions ?? [];
    return html`
      <ha-card>
        ${this._header(date || '')}
        <main>
          ${this.loading && !this.data
            ? html`<p class="muted">${this._t.loading}</p>`
            : dinner
              ? html`
                  <div class="dinner-title">${items.map((item) => item.name).join(' · ')}</div>
                  ${this.config?.show_kcal !== false || this.config?.show_balance !== false
                    ? html`<div class="metrics">
                        ${this.config?.show_kcal !== false
                          ? html`<span class="chip">${this.data.kcal == null
                              ? '—'
                              : this._t.kcal.replace('{value}', this.data.kcal)}</span>`
                          : ''}
                        ${this.config?.show_balance !== false
                          ? html`<span class="chip">${this._t.balance[this.data.balance] || this._t.balance.unknown}</span>`
                          : ''}
                      </div>`
                    : ''}
                  ${this.data.warnings?.length
                    ? html`<p class="warning">${this.data.warnings.join(', ')}</p>`
                    : ''}
                  <div class="actions">
                    <button class="primary" ?disabled=${eaten} @click=${() =>
                      this._act(() => this._ws({ type: 'menu_planner/eaten', date }))}>
                      ${eaten ? this._t.logged : this._t.eaten}
                    </button>
                    <button ?disabled=${eaten} @click=${() => this._showSuggestions()}>${this._t.swap}</button>
                  </div>
                  ${suggestions.length
                    ? html`<ul aria-label=${this._t.swap}>
                        ${suggestions.map((suggestion) => html`
                          <li class="row">
                            <span>${dinnerItems(suggestion).map((item) => item.name).join(' · ')}</span>
                            <button @click=${() => this._applySwap(suggestion)}>${this._t.apply}</button>
                          </li>
                        `)}
                      </ul>`
                    : this.suggestions
                      ? html`<p class="muted">${this._t.noSuggestions}</p>`
                      : ''}
                `
              : html`<p class="muted">${this._t.empty}</p>`}
          ${this._error()}
        </main>
      </ha-card>
    `;
  }

  getCardSize() {
    return this.suggestions ? 5 : 3;
  }

  getGridOptions() {
    return { columns: 6, rows: this.getCardSize(), min_columns: 3, min_rows: 2 };
  }
}

class MenuPlannerStockCard extends MenuPlannerCard {
  static titleKey = 'stock';
  static elementName = 'menu-planner-stock-card';
  static formSchema = [
    { name: 'title', selector: { text: {} } },
    { name: 'unanswered_only', selector: { boolean: {} } },
    { name: 'show_impact', selector: { boolean: {} } },
    { name: 'item_count', selector: { number: { min: 1, max: 20, step: 1 } } },
  ];

  static styles = [baseStyles, css`.stock-name { font-weight: 500; } .stock-actions { display: flex; gap: 2px; }`];

  async _fetchData() {
    const result = await this._ws({
      type: 'menu_planner/stock',
      unanswered_first: true,
    });
    const rows = Array.isArray(result) ? result : result?.items ?? [];
    return rows.filter((row) => !this.config?.unanswered_only || row.in_stock == null)
      .slice(0, Number(this.config?.item_count) || 5);
  }

  async _answer(row, inStock) {
    const id = itemId(row);
    if (!Number.isInteger(id)) return;
    await this._act(async () => {
      await this._ws({ type: 'menu_planner/stock/set', item_id: id, in_stock: inStock });
      this.preview = null;
    });
  }

  async _previewNo(row) {
    const id = itemId(row);
    if (!Number.isInteger(id)) return;
    await this._act(async () => {
      this.preview = {
        id,
        result: await this._ws({
          type: 'menu_planner/stock/preview',
          item_id: id,
          in_stock: false,
        }),
      };
    }, false);
  }

  render() {
    const rows = this.data ?? [];
    return html`
      <ha-card>
        ${this._header()}
        <main>
          ${this.loading && !this.data
            ? html`<p class="muted">${this._t.loading}</p>`
            : rows.length
              ? html`<ul>
                  ${rows.map((row) => {
                    const id = itemId(row);
                    const preview = this.preview?.id === id ? this.preview.result : null;
                    return html`<li>
                      <div class="row">
                        <span class="stock-name">${row.name}</span>
                        <div class="stock-actions">
                          <button aria-label="${this._t.yes}: ${row.name}" @click=${() => this._answer(row, true)}>${this._t.yes}</button>
                          <button aria-label="${this._t.no}: ${row.name}" @click=${() => this.config?.show_impact === false
                            ? this._answer(row, false)
                            : this._previewNo(row)}>${this._t.no}</button>
                        </div>
                      </div>
                      ${preview
                        ? html`<div class="row">
                            <span class="meta">${this._t.replaces.replace('{count}', preview.replaces_count)}</span>
                            <button @click=${() => this._answer(row, false)}>${this._t.confirmNo}</button>
                          </div>`
                        : row.in_stock == null && row.replaces_count
                          ? html`<div class="meta">${this._t.replaces.replace('{count}', row.replaces_count)}</div>`
                          : ''}
                    </li>`;
                  })}
                </ul>`
              : html`<p class="muted">${this._t.emptyStock}</p>`}
          ${this._error()}
        </main>
      </ha-card>
    `;
  }

  getCardSize() {
    return Math.max(2, Math.min(7, (this.data?.length ?? 3) + 1));
  }

  getGridOptions() {
    return { columns: 6, rows: this.getCardSize(), min_columns: 3, min_rows: 2 };
  }
}

class MenuPlannerWindowCard extends MenuPlannerCard {
  static titleKey = 'window';
  static elementName = 'menu-planner-window-card';
  static formSchema = [
    { name: 'title', selector: { text: {} } },
    { name: 'day_count', selector: { number: { min: 1, max: 60, step: 1 } } },
  ];

  async _fetchData() {
    const result = await this._ws({ type: 'menu_planner/window' });
    const days = Array.isArray(result) ? result : result?.days ?? [];
    return days.slice(0, Number(this.config?.day_count) || 14);
  }

  render() {
    const days = this.data ?? [];
    return html`
      <ha-card>
        ${this._header(days.length ? `${days.length} days` : '')}
        <main>
          ${this.loading && !this.data
            ? html`<p class="muted">${this._t.loading}</p>`
            : html`<ul>
                ${days.map((day) => html`
                  <li>
                    <details>
                      <summary>
                        <div class="row">
                          <span>${day.date}</span>
                          <span class="chip">${this._t.statuses[day.status] || day.status}</span>
                        </div>
                        <div class="meta">${dinnerItems(day.dinner).map((item) => item.name).join(' · ') || this._t.empty}</div>
                      </summary>
                      ${day.dinner?.items?.length
                        ? html`<ul class="components">
                            ${day.dinner.items.map((item) => html`<li>${item.name} <span class="meta">· ${item.type}</span></li>`)}
                          </ul>`
                        : ''}
                    </details>
                  </li>
                `)}
              </ul>`}
          ${this._error()}
        </main>
      </ha-card>
    `;
  }

  getCardSize() {
    return Math.min(12, (this.data?.length ?? 5) + 1);
  }

  getGridOptions() {
    return { columns: 12, rows: this.getCardSize(), min_columns: 4, min_rows: 3 };
  }
}

class MenuPlannerCardEditor extends LitElement {
  static properties = {
    hass: { attribute: false },
    schema: { attribute: false },
    data: { state: true },
  };

  static styles = css`:host { display: block; }`;

  constructor() {
    super();
    this.data = {};
  }

  setConfig(config) {
    this.data = { ...config };
  }

  _valueChanged(event) {
    this.data = event.detail.value;
    this.dispatchEvent(new CustomEvent('config-changed', {
      detail: { config: this.data },
      bubbles: true,
      composed: true,
    }));
  }

  render() {
    return html`<ha-form
      .hass=${this.hass}
      .data=${this.data}
      .schema=${this.schema || []}
      .computeLabel=${(schema) => schema.name}
      @value-changed=${this._valueChanged}
    ></ha-form>`;
  }
}

customElements.define('menu-planner-card-editor', MenuPlannerCardEditor);
customElements.define(MenuPlannerTodayCard.elementName, MenuPlannerTodayCard);
customElements.define(MenuPlannerStockCard.elementName, MenuPlannerStockCard);
customElements.define(MenuPlannerWindowCard.elementName, MenuPlannerWindowCard);

window.customCards = window.customCards || [];
window.customCards.push(
  { type: MenuPlannerTodayCard.elementName, name: 'Menu Planner: Today', description: 'Today’s planned dinner and swap actions.', preview: true },
  { type: MenuPlannerStockCard.elementName, name: 'Menu Planner: Stock', description: 'Confirm whether tracked ingredients are in stock.', preview: true },
  { type: MenuPlannerWindowCard.elementName, name: 'Menu Planner: Window', description: 'Browse the planned menu window.', preview: true },
);
