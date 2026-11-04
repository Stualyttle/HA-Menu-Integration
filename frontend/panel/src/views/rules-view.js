/**
 * Rules tab: blacklist and whitelist cards plus a combination builder.
 * The builder runs a feasibility check (no save) as categories are picked.
 */
import { MpView, html, icon, listOf, reportError, toast, t } from '../../../shared/components/common.js';
import { api } from '../../../shared/api/instance.js';

export class MpRulesView extends MpView {
  static properties = {
    version: { type: Number },
    rules: { state: true },
    categories: { state: true },
    loading: { state: true },
    kind: { state: true },
    selected: { state: true },
    check: { state: true },
  };

  constructor() {
    super();
    this.version = 0;
    this.rules = [];
    this.categories = [];
    this.loading = true;
    this.kind = 'blacklist';
    this.selected = [];
    this.check = null;
    this.checkSeq = 0;
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
      const [rules, categories] = await Promise.all([api.rules.list(), api.categories.list()]);
      this.rules = listOf(rules, 'rules');
      this.categories = listOf(categories, 'categories');
    } catch (err) {
      reportError(this, err);
    } finally {
      this.loading = false;
    }
  }

  categoryName(id) {
    return this.categories.find((c) => c.id === id)?.name ?? String(id);
  }

  ruleLabel(rule) {
    if (rule.scope === 'item') return `${t('rules.kind.item')} #${rule.item_id}`;
    return (rule.category_ids || []).map((id) => this.categoryName(id)).join(' + ');
  }

  listNames(ids) {
    return ids.map((id) => this.categoryName(id)).join(', ');
  }

  bodyFor(kind, ids) {
    return { kind, scope: 'combination', category_ids: ids, enabled: true };
  }

  async runCheck(kind, ids) {
    const seq = ++this.checkSeq;
    if (ids.length < 2) {
      this.check = null;
      return;
    }
    try {
      const result = await api.rules.check(this.bodyFor(kind, ids));
      if (seq === this.checkSeq) this.check = result;
    } catch (err) {
      if (seq === this.checkSeq) this.check = { feasible: true, error: err };
    }
  }

  toggleCategory(id, checked) {
    const set = new Set(this.selected);
    if (checked) set.add(id);
    else set.delete(id);
    this.selected = [...set];
    this.runCheck(this.kind, this.selected);
  }

  changeKind(kind) {
    this.kind = kind;
    this.runCheck(kind, this.selected);
  }

  get blocked() {
    return this.check && this.check.feasible === false;
  }

  async add() {
    if (this.selected.length < 2 || this.blocked) return;
    try {
      await api.rules.create(this.bodyFor(this.kind, this.selected));
      toast(this, t('rules.added'));
      this.selected = [];
      this.check = null;
      await this.load();
    } catch (err) {
      reportError(this, err);
    }
  }

  async remove(rule) {
    if (!window.confirm(t('rules.confirmDelete'))) return;
    try {
      await api.rules.remove(rule.id);
      toast(this, t('rules.deleted'));
      await this.load();
    } catch (err) {
      reportError(this, err);
    }
  }

  renderCard(kind) {
    const list = this.rules.filter((r) => r.kind === kind);
    const title = kind === 'blacklist' ? t('rules.blacklist') : t('rules.whitelist');
    const hint = kind === 'blacklist' ? t('rules.blacklistHint') : t('rules.whitelistHint');
    return html`
      <section class="card" aria-labelledby="rules-${kind}">
        <h3 id="rules-${kind}">${title}</h3>
        <p class="muted">${hint}</p>
        ${list.length === 0
          ? html`<p class="muted">${t('rules.none')}</p>`
          : html`<ul class="plain-list">
              ${list.map(
                (rule) => html`<li class="row">
                  <span class="grow">${this.ruleLabel(rule)}</span>
                  <span class="chip-type">${t(`rules.kind.${rule.scope}`)}</span>
                  <md-icon-button aria-label="${t('rules.delete')}" @click=${() => this.remove(rule)}>
                    ${icon('delete')}
                  </md-icon-button>
                </li>`,
              )}
            </ul>`}
      </section>
    `;
  }

  renderPreview() {
    if (this.selected.length < 2) return html`<p class="muted">${t('rules.pickTwo')}</p>`;
    const names = this.listNames(this.selected);
    const key = this.kind === 'blacklist' ? 'rules.previewBlacklist' : 'rules.previewWhitelist';
    return html`<p>${t(key, { names })}</p>`;
  }

  render() {
    if (this.loading && this.rules.length === 0) {
      return html`<div class="loading"><md-circular-progress indeterminate></md-circular-progress></div>`;
    }
    return html`
      <div class="page-head">
        <h2>${t('rules.title')}</h2>
      </div>
      ${this.blocked
        ? html`<div class="banner error" role="alert">
            <strong>${t('rules.infeasibleTitle')}</strong>
            <span>${t('rules.infeasibleBody')}</span>
            <span>${t('rules.infeasibleSave', { days: this.check.affected_days ?? 0 })}</span>
          </div>`
        : ''}
      <div class="grid-2">
        ${this.renderCard('blacklist')} ${this.renderCard('whitelist')}
      </div>
      <section class="card">
        <h3>${t('rules.builderTitle')}</h3>
        <div class="stack">
          <span class="field-label" id="builder-categories">${t('rules.builderCategories')}</span>
          <div class="chips" role="group" aria-labelledby="builder-categories">
            ${this.categories.map(
              (c) => html`<md-filter-chip
                label="${c.name}"
                ?selected=${this.selected.includes(c.id)}
                @click=${() => this.toggleCategory(c.id, !this.selected.includes(c.id))}
              ></md-filter-chip>`,
            )}
          </div>
          <md-outlined-select
            label="${t('rules.builderKind')}"
            .value=${this.kind}
            @change=${(e) => this.changeKind(e.target.value)}
          >
            <md-select-option value="blacklist"><div slot="headline">${t('rules.kindBlacklist')}</div></md-select-option>
            <md-select-option value="whitelist"><div slot="headline">${t('rules.kindWhitelist')}</div></md-select-option>
          </md-outlined-select>
          <div class="preview" aria-live="polite">${this.renderPreview()}</div>
          <div class="row">
            <span class="grow"></span>
            <md-filled-button
              ?disabled=${this.selected.length < 2 || this.blocked}
              @click=${() => this.add()}
            >${t('rules.add')}</md-filled-button>
          </div>
        </div>
      </section>
    `;
  }
}

customElements.define('mp-rules-view', MpRulesView);
