/**
 * Import / export tab. Export downloads the schema-version-1 JSON. Import reads a
 * file, shows a preview with skipped entries, and merges after confirmation.
 * Settings and menu history are opt-in (unticked by default).
 */
import { MpView, html, itemsChanged, reportError, toast, t } from '../../../shared/components/common.js';
import { api } from '../../../shared/api/instance.js';

const SKIP_KEYS = new Set(['item', 'category', 'rule', 'minimum']);

function countOf(value) {
  if (Array.isArray(value)) return value.length;
  return Number(value) || 0;
}

function skipMessage(entry) {
  const kind = SKIP_KEYS.has(entry?.kind) ? entry.kind : 'other';
  const key = `io.skip.${kind}`;
  return kind === 'other'
    ? t(key, { kind: entry?.kind ?? '', name: entry?.name ?? '' })
    : t(key, { name: entry?.name ?? '' });
}

export class MpImportExportView extends MpView {
  static properties = {
    fileName: { state: true },
    exportFile: { state: true },
    preview: { state: true },
    includeSettings: { state: true },
    includeHistory: { state: true },
    busy: { state: true },
  };

  constructor() {
    super();
    this.fileName = '';
    /** Parsed export JSON chosen by the user, sent for preview and import. */
    this.exportFile = null;
    this.preview = null;
    this.includeSettings = false;
    this.includeHistory = false;
    this.busy = false;
  }

  async exportJson() {
    this.busy = true;
    try {
      const data = await api.exportData();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `menu-planner-export-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.append(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      reportError(this, err);
    } finally {
      this.busy = false;
    }
  }

  async onFileChosen(event) {
    const file = event.target.files?.[0];
    this.preview = null;
    this.exportFile = null;
    this.fileName = file?.name ?? '';
    if (!file) return;
    let parsed;
    try {
      parsed = JSON.parse(await file.text());
    } catch {
      toast(this, t('io.import.invalidFile'), 'error');
      return;
    }
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      toast(this, t('io.import.invalidFile'), 'error');
      return;
    }
    this.exportFile = parsed;
    await this.loadPreview();
  }

  async loadPreview() {
    this.busy = true;
    try {
      this.preview = await api.importPreview(this.exportFile);
    } catch (err) {
      this.preview = null;
      reportError(this, err);
    } finally {
      this.busy = false;
    }
  }

  cancelPreview() {
    this.preview = null;
    this.exportFile = null;
    this.fileName = '';
    this.includeSettings = false;
    this.includeHistory = false;
    const input = this.querySelector('input[type="file"]');
    if (input) input.value = '';
  }

  async importNow() {
    if (!this.exportFile || this.busy) return;
    this.busy = true;
    try {
      await api.importData({
        ...this.exportFile,
        include_settings: this.includeSettings,
        include_history: this.includeHistory,
      });
      toast(this, t('io.imported'));
      itemsChanged(this);
      this.cancelPreview();
    } catch (err) {
      reportError(this, err);
    } finally {
      this.busy = false;
    }
  }

  renderPreview() {
    const added = countOf(this.preview.added);
    const skipped = Array.isArray(this.preview.skipped) ? this.preview.skipped : [];
    const skippedCount = countOf(this.preview.skipped);
    const settingsAvailable = Boolean(this.preview.settings_available);
    const nothing = added === 0 && skippedCount === 0 && !settingsAvailable;
    return html`<section class="card stack" aria-labelledby="preview-title">
      <h3 id="preview-title">${t('io.preview.title')}</h3>
      ${nothing ? html`<p class="muted">${t('io.preview.none')}</p>` : ''}
      <div class="row">
        <span class="badge ok">${t('io.preview.added')}: ${added}</span>
        <span class="badge">${t('io.preview.skipped')}: ${skippedCount}</span>
      </div>
      ${skipped.length
        ? html`<ul class="plain-list" aria-label="${t('io.preview.skippedList')}">
            ${skipped.map((entry) => html`<li class="muted">${skipMessage(entry)}</li>`)}
          </ul>`
        : ''}
      <fieldset class="stack">
        <legend>${t('io.preview.also')}</legend>
        ${settingsAvailable
          ? html`<label class="switch-row">
              <md-checkbox
                ?checked=${this.includeSettings}
                @change=${(e) => (this.includeSettings = e.target.checked)}
              ></md-checkbox>
              <span>${t('io.preview.settings')}</span>
            </label>`
          : ''}
        <label class="switch-row">
          <md-checkbox
            ?checked=${this.includeHistory}
            @change=${(e) => (this.includeHistory = e.target.checked)}
          ></md-checkbox>
          <span>${t('io.preview.history')}</span>
        </label>
      </fieldset>
      <div class="row">
        <md-text-button ?disabled=${this.busy} @click=${() => this.cancelPreview()}>${t('io.preview.cancel')}</md-text-button>
        <md-filled-button ?disabled=${this.busy || nothing} @click=${() => this.importNow()}>
          ${t('io.preview.import', { count: added })}
        </md-filled-button>
      </div>
    </section>`;
  }

  render() {
    return html`<div class="page">
      <div class="page-head">
        <h2>${t('tabs.importExport')}</h2>
      </div>
      <section class="card stack">
        <h3>${t('io.export.title')}</h3>
        <p class="muted">${t('io.export.help')}</p>
        <div class="row">
          <md-filled-button ?disabled=${this.busy} @click=${() => this.exportJson()}>${t('io.export.button')}</md-filled-button>
        </div>
      </section>
      <section class="card stack">
        <h3>${t('io.import.title')}</h3>
        <p class="muted">${t('io.import.help')}</p>
        <div class="row">
          <label class="field-label" for="import-file">${t('io.import.file')}</label>
          <input id="import-file" type="file" accept="application/json,.json" @change=${(e) => this.onFileChosen(e)} />
          <span class="muted">${this.fileName || t('io.import.noFile')}</span>
        </div>
      </section>
      ${this.preview ? this.renderPreview() : ''}
    </div>`;
  }
}

customElements.define('mp-import-export-view', MpImportExportView);
