import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { api } from '@shared/api/instance.js';
import type { Item } from '@shared/api/types';
import { I18nService } from '@app/core/services/i18n.service';
import { MessageService } from '@app/core/services/message.service';

interface PendingStockAnswer {
  item: Item;
  replacesCount: number;
}

@Component({
  selector: 'mp-stock',
  standalone: true,
  imports: [CommonModule, MatButtonModule, MatCardModule, MatProgressSpinnerModule],
  template: `
    <mat-card>
      <mat-card-header>
        <mat-card-title>{{ i18n.t('stock.title') }}</mat-card-title>
        <mat-card-subtitle>{{ i18n.t('stock.subtitle') }}</mat-card-subtitle>
      </mat-card-header>
      <mat-card-content>{{ i18n.t('stock.help') }}</mat-card-content>
    </mat-card>
    @if (pendingNo(); as pending) {
      <mat-card>
        <mat-card-header>
          <mat-card-title>{{ pending.item.name }}</mat-card-title>
        </mat-card-header>
        <mat-card-content>
          {{ i18n.t('stock.replacesDetail', { count: pending.replacesCount }) }}
        </mat-card-content>
        <mat-card-actions>
          <button mat-button type="button" (click)="pendingNo.set(null)">
            {{ i18n.t('common.cancel') }}
          </button>
          <button mat-flat-button type="button" (click)="confirmNo()">
            {{ i18n.t('stock.saveNo') }}
          </button>
        </mat-card-actions>
      </mat-card>
    }
    @if (loading()) {
      <mat-card><mat-card-content><mat-spinner diameter="32" /></mat-card-content></mat-card>
    } @else if (items().length === 0) {
      <mat-card><mat-card-content>{{ i18n.t('stock.empty') }}</mat-card-content></mat-card>
    } @else {
      @for (item of items(); track item.id) {
        <mat-card>
          <mat-card-header>
            <mat-card-title>{{ item.name }}</mat-card-title>
            <mat-card-subtitle>
              @if (item.in_stock === null || item.in_stock === undefined) {
                {{ i18n.t('stock.unanswered') }}
              } @else if (item.replaces_count) {
                {{ i18n.t('stock.replaces', { count: item.replaces_count }) }}
              }
            </mat-card-subtitle>
          </mat-card-header>
          <mat-card-actions>
            <button mat-flat-button type="button" [attr.aria-pressed]="item.in_stock === true" (click)="answer(item, true)">
              {{ i18n.t('common.yes') }}
            </button>
            <button mat-button type="button" [attr.aria-pressed]="item.in_stock === false" (click)="answer(item, false)">
              {{ i18n.t('common.no') }}
            </button>
          </mat-card-actions>
        </mat-card>
      }
    }
  `,
})
export class StockComponent implements OnInit {
  readonly i18n = inject(I18nService);
  private readonly messages = inject(MessageService);
  readonly loading = signal(true);
  readonly items = signal<Item[]>([]);
  readonly pendingNo = signal<PendingStockAnswer | null>(null);

  ngOnInit(): void {
    void this.load();
  }

  async load(): Promise<void> {
    this.loading.set(true);
    try {
      this.items.set(await api.stock.list(true));
    } catch (error) {
      this.messages.error(error);
    } finally {
      this.loading.set(false);
    }
  }

  async answer(item: Item, inStock: boolean): Promise<void> {
    if (inStock) {
      await this.save(item, true);
      return;
    }
    try {
      const preview = await api.stock.preview(item.id, false);
      this.pendingNo.set({ item, replacesCount: preview.replaces_count });
    } catch (error) {
      this.messages.error(error);
    }
  }

  async confirmNo(): Promise<void> {
    const pending = this.pendingNo();
    if (!pending) return;
    this.pendingNo.set(null);
    await this.save(pending.item, false);
  }

  private async save(item: Item, inStock: boolean): Promise<void> {
    try {
      await api.stock.set(item.id, inStock);
      this.messages.success(this.i18n.t('stock.updated'));
      await this.load();
    } catch (error) {
      this.messages.error(error);
    }
  }
}
