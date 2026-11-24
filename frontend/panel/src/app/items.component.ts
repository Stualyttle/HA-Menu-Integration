import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { api } from '../../../shared/api/instance.js';
import type { Item, ItemType } from '../../../shared/api/types';
import { I18nService } from './i18n.service';
import { ItemEditorComponent } from './item-editor.component';
import { MessageService } from './message.service';

type NutritionFilter = '' | 'verified' | 'unverified';

@Component({
  selector: 'mp-items',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatCardModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressSpinnerModule,
    MatSelectModule,
  ],
  template: `
    <h1>{{ i18n.t('items.title') }}</h1>
    <mat-card>
      <mat-card-content>
        <mat-form-field appearance="outline">
          <mat-label>{{ i18n.t('items.search') }}</mat-label>
          <input matInput [(ngModel)]="query" (ngModelChange)="onSearchChange()" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>{{ i18n.t('items.filter.type') }}</mat-label>
          <mat-select [(ngModel)]="typeFilter" (selectionChange)="load()">
            <mat-option value="">{{ i18n.t('items.filter.any') }}</mat-option>
            <mat-option value="protein">{{ i18n.t('type.protein') }}</mat-option>
            <mat-option value="vegetable">{{ i18n.t('type.vegetable') }}</mat-option>
            <mat-option value="carb">{{ i18n.t('type.carb') }}</mat-option>
          </mat-select>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>{{ i18n.t('items.filter.nutrition') }}</mat-label>
          <mat-select [(ngModel)]="nutritionFilter" (selectionChange)="load()">
            <mat-option value="">{{ i18n.t('items.filter.any') }}</mat-option>
            <mat-option value="verified">{{ i18n.t('items.filter.verified') }}</mat-option>
            <mat-option value="unverified">{{ i18n.t('items.filter.unverified') }}</mat-option>
          </mat-select>
        </mat-form-field>
        <button mat-flat-button type="button" (click)="openEditor(null)">
          {{ i18n.t('items.add') }}
        </button>
      </mat-card-content>
    </mat-card>

    @if (loading()) {
      <mat-card><mat-card-content><mat-spinner diameter="32" /></mat-card-content></mat-card>
    } @else if (items().length === 0) {
      <mat-card><mat-card-content>{{ i18n.t('items.empty') }}</mat-card-content></mat-card>
    } @else {
      @for (item of items(); track item.id) {
        <mat-card>
          <mat-card-header>
            <mat-card-title>{{ item.name }}</mat-card-title>
            <mat-card-subtitle>
              @if (item.is_complete_meal) {
                {{ i18n.t('items.completeMeal') }}
              } @else {
                {{ typeLabel(item.type) }}
              }
              ·
              {{ item.portion_grams ? i18n.t('items.portion', { grams: item.portion_grams }) : i18n.t('items.noPortion') }}
            </mat-card-subtitle>
          </mat-card-header>
          <mat-card-content>
            <p>
              {{ isVerified(item) ? i18n.t('items.verified') : i18n.t('items.unverified') }}
              @if (item.track_stock) { · {{ i18n.t('items.tracksStock') }} }
            </p>
          </mat-card-content>
          <mat-card-actions>
            <button mat-button type="button" (click)="openEditor(item.id)">
              {{ i18n.t('common.edit') }}
            </button>
          </mat-card-actions>
        </mat-card>
      }
    }
  `,
})
export class ItemsComponent implements OnDestroy, OnInit {
  readonly i18n = inject(I18nService);
  private readonly dialog = inject(MatDialog);
  private readonly messages = inject(MessageService);
  readonly items = signal<Item[]>([]);
  readonly loading = signal(true);
  query = '';
  typeFilter: '' | ItemType = '';
  nutritionFilter: NutritionFilter = '';
  private searchTimer: ReturnType<typeof setTimeout> | null = null;

  ngOnInit(): void {
    void this.load();
  }

  ngOnDestroy(): void {
    if (this.searchTimer) clearTimeout(this.searchTimer);
  }

  typeLabel(type: ItemType): string {
    return this.i18n.t(`type.${type}`);
  }

  isVerified(item: Item): boolean {
    return (
      item.nutrition?.status === 'ok' &&
      (item.nutrition.source === 'manual' || item.nutrition.user_confirmed)
    );
  }

  onSearchChange(): void {
    if (this.searchTimer) clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => void this.load(), 300);
  }

  async load(): Promise<void> {
    this.loading.set(true);
    const filters: Record<string, string> = {};
    if (this.query.trim()) filters['q'] = this.query.trim();
    if (this.typeFilter) filters['type'] = this.typeFilter;
    if (this.nutritionFilter === 'verified') filters['verified'] = 'true';
    if (this.nutritionFilter === 'unverified') filters['verified'] = 'false';
    try {
      this.items.set(await api.items.list(filters));
    } catch (error) {
      this.messages.error(error);
    } finally {
      this.loading.set(false);
    }
  }

  openEditor(itemId: number | null): void {
    this.dialog
      .open(ItemEditorComponent, {
        data: itemId,
        width: '760px',
        maxWidth: '95vw',
        maxHeight: '90vh',
      })
      .afterClosed()
      .subscribe((changed: boolean | undefined) => {
        if (changed) void this.load();
      });
  }
}
