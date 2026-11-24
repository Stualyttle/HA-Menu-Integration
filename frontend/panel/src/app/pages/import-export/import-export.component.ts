import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { api } from '@shared/api/instance.js';
import type { ImportPreview } from '@shared/api/types';
import { I18nService } from '@app/core/services/i18n.service';
import { MessageService } from '@app/core/services/message.service';

@Component({
  selector: 'mp-import-export',
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatCardModule,
    MatCheckboxModule,
    MatInputModule,
    MatProgressSpinnerModule,
  ],
  template: `
    <h1>{{ i18n.t('tabs.importExport') }}</h1>
    <mat-card>
      <mat-card-header>
        <mat-card-title>{{ i18n.t('io.export.title') }}</mat-card-title>
        <mat-card-subtitle>{{ i18n.t('io.export.help') }}</mat-card-subtitle>
      </mat-card-header>
      <mat-card-actions>
        <button mat-flat-button type="button" [disabled]="busy()" (click)="exportJson()">
          {{ i18n.t('io.export.button') }}
        </button>
      </mat-card-actions>
    </mat-card>

    <mat-card>
      <mat-card-header>
        <mat-card-title>{{ i18n.t('io.import.title') }}</mat-card-title>
        <mat-card-subtitle>{{ i18n.t('io.import.help') }}</mat-card-subtitle>
      </mat-card-header>
      <mat-card-content>
        <label for="import-file">{{ i18n.t('io.import.file') }}</label>
        <input id="import-file" type="file" accept="application/json,.json" (change)="onFileChosen($event)" />
        @if (fileName()) { <p>{{ fileName() }}</p> }
      </mat-card-content>
    </mat-card>

    @if (busy()) {
      <mat-card><mat-card-content><mat-spinner diameter="32" /></mat-card-content></mat-card>
    }
    @if (preview(); as summary) {
      <mat-card>
        <mat-card-header><mat-card-title>{{ i18n.t('io.preview.title') }}</mat-card-title></mat-card-header>
        <mat-card-content>
          <p>{{ i18n.t('io.preview.added') }}: {{ total(summary.added) }}</p>
          <p>{{ i18n.t('io.preview.skipped') }}: {{ total(summary.skipped) }}</p>
          @if (total(summary.added) === 0 && total(summary.skipped) === 0 && !summary.settings_available) {
            <p>{{ i18n.t('io.preview.none') }}</p>
          }
          @if (summary.settings_available) {
            <mat-checkbox [checked]="includeSettings()" (change)="includeSettings.set($event.checked)">
              {{ i18n.t('io.preview.settings') }}
            </mat-checkbox>
          }
        </mat-card-content>
        <mat-card-actions>
          <button mat-button type="button" [disabled]="busy()" (click)="cancelPreview()">
            {{ i18n.t('io.preview.cancel') }}
          </button>
          <button
            mat-flat-button
            type="button"
            [disabled]="busy() || (total(summary.added) === 0 && !includeSettings())"
            (click)="importNow()"
          >
            {{ i18n.t('io.preview.import', { count: total(summary.added) }) }}
          </button>
        </mat-card-actions>
      </mat-card>
    }
  `,
})
export class ImportExportComponent {
  readonly i18n = inject(I18nService);
  private readonly messages = inject(MessageService);
  readonly busy = signal(false);
  readonly fileName = signal('');
  readonly preview = signal<ImportPreview | null>(null);
  readonly includeSettings = signal(false);
  private document: Record<string, unknown> | null = null;
  private fileInput: HTMLInputElement | null = null;

  async exportJson(): Promise<void> {
    this.busy.set(true);
    try {
      const data = await api.exportData();
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
      const link = document.createElement('a');
      link.href = url;
      link.download = `menu-planner-export-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      this.messages.error(error);
    } finally {
      this.busy.set(false);
    }
  }

  async onFileChosen(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    this.fileInput = input;
    const file = input.files?.[0];
    this.preview.set(null);
    this.document = null;
    this.fileName.set(file?.name ?? '');
    if (!file) return;
    try {
      const parsed: unknown = JSON.parse(await file.text());
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        this.messages.error(new Error(this.i18n.t('io.import.invalidFile')));
        return;
      }
      this.document = parsed as Record<string, unknown>;
      await this.loadPreview();
    } catch (error) {
      if (error instanceof SyntaxError) {
        this.messages.error(new Error(this.i18n.t('io.import.invalidFile')));
        return;
      }
      this.messages.error(error);
    }
  }

  async importNow(): Promise<void> {
    const document = this.document;
    if (!document || this.busy()) return;
    this.busy.set(true);
    try {
      await api.importData(document, {
        include_settings: this.includeSettings(),
      });
      this.messages.success(this.i18n.t('io.imported'));
      this.cancelPreview();
    } catch (error) {
      this.messages.error(error);
    } finally {
      this.busy.set(false);
    }
  }

  total(values: Record<string, number>): number {
    return Object.values(values).reduce((sum, value) => sum + Number(value || 0), 0);
  }

  cancelPreview(): void {
    this.preview.set(null);
    this.document = null;
    this.fileName.set('');
    this.includeSettings.set(false);
    if (this.fileInput) this.fileInput.value = '';
  }

  private async loadPreview(): Promise<void> {
    const document = this.document;
    if (!document) return;
    this.busy.set(true);
    try {
      this.preview.set(await api.importPreview(document));
    } catch (error) {
      this.preview.set(null);
      this.messages.error(error);
    } finally {
      this.busy.set(false);
    }
  }
}
