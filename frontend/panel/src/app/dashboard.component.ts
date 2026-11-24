import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { RouterLink } from '@angular/router';
import { api } from '../../../shared/api/instance.js';
import type { Item, MenuDay, WarningRecord } from '../../../shared/api/types';
import { I18nService } from './i18n.service';
import { MessageService } from './message.service';

interface QuickLink {
  path: string;
  label: string;
  help: string;
  count?: number;
}

@Component({
  selector: 'mp-dashboard',
  standalone: true,
  imports: [CommonModule, MatButtonModule, MatCardModule, MatChipsModule, MatProgressSpinnerModule, RouterLink],
  template: `
    <section>
      <mat-card>
        <mat-card-header>
          <mat-card-title>{{ i18n.t('dashboard.title') }}</mat-card-title>
          <mat-card-subtitle>{{ i18n.t('dashboard.subtitle') }}</mat-card-subtitle>
        </mat-card-header>
        <mat-card-actions>
          <a mat-flat-button routerLink="/menu">{{ i18n.t('dashboard.openMenu') }}</a>
        </mat-card-actions>
      </mat-card>

      @if (loading()) {
        <mat-card>
          <mat-card-content>
            <mat-spinner diameter="32" />
            {{ i18n.t('common.loading') }}
          </mat-card-content>
        </mat-card>
      } @else {
        <mat-card>
          <mat-card-header>
            <mat-card-title>{{ i18n.t('dashboard.today') }}</mat-card-title>
          </mat-card-header>
          <mat-card-content>
            @if (today()) {
              <h2>{{ formatDate(today()!.date) }}</h2>
              @if (today()!.dinner?.items?.length) {
                <mat-chip-set aria-label="{{ i18n.t('dashboard.today') }}">
                  @for (item of today()!.dinner!.items; track item.id) {
                    <mat-chip>{{ item.name }}</mat-chip>
                  }
                </mat-chip-set>
              } @else {
                <p>{{ i18n.t('menu.noDinner') }}</p>
              }
              <p>{{ i18n.t('menu.status.' + today()!.status) }}</p>
            } @else {
              <p>{{ i18n.t('dashboard.notPlanned') }}</p>
            }
          </mat-card-content>
        </mat-card>

        <mat-card>
          <mat-card-header>
            <mat-card-title>{{ i18n.t('dashboard.summary') }}</mat-card-title>
          </mat-card-header>
          <mat-card-content>
            <p>{{ i18n.t('dashboard.menuDays') }}: {{ days().length }}</p>
            <p>{{ i18n.t('dashboard.stockAlerts') }}: {{ outOfStockCount() }}</p>
            <p>{{ i18n.t('dashboard.warnings') }}: {{ warnings().length }}</p>
          </mat-card-content>
        </mat-card>

        <mat-card>
          <mat-card-header>
            <mat-card-title>{{ i18n.t('dashboard.upcoming') }}</mat-card-title>
          </mat-card-header>
          <mat-card-content>
            @if (upcoming().length) {
              @for (day of upcoming(); track day.date) {
                <p>
                  <strong>{{ formatDate(day.date) }}</strong> —
                  {{ dinnerNames(day) || i18n.t('menu.noDinner') }}
                  ({{ i18n.t('menu.status.' + day.status) }})
                </p>
              }
            } @else {
              <p>{{ i18n.t('menu.empty') }}</p>
            }
          </mat-card-content>
          <mat-card-actions>
            <a mat-button routerLink="/menu">{{ i18n.t('dashboard.viewAll') }}</a>
          </mat-card-actions>
        </mat-card>

        <mat-card>
          <mat-card-header>
            <mat-card-title>{{ i18n.t('dashboard.quickActions') }}</mat-card-title>
          </mat-card-header>
          <mat-card-content>
            @for (link of quickLinks(); track link.path) {
              <p>
                <a mat-button [routerLink]="link.path" target="_blank" rel="noopener noreferrer">
                  {{ i18n.t(link.label) }}
                  @if (link.count !== undefined) { ({{ link.count }}) }
                </a>
                {{ i18n.t(link.help) }}
              </p>
            }
          </mat-card-content>
        </mat-card>
      }
    </section>
  `,
})
export class DashboardComponent implements OnInit {
  readonly i18n = inject(I18nService);
  private readonly messages = inject(MessageService);
  readonly loading = signal(true);
  readonly days = signal<MenuDay[]>([]);
  readonly warnings = signal<WarningRecord[]>([]);
  readonly stock = signal<Item[]>([]);
  readonly items = signal<Item[]>([]);
  readonly today = signal<MenuDay | undefined>(undefined);
  readonly outOfStockCount = signal(0);
  readonly upcoming = signal<MenuDay[]>([]);
  readonly quickLinks = signal<QuickLink[]>([]);

  ngOnInit(): void {
    void this.load();
  }

  async load(): Promise<void> {
    this.loading.set(true);
    try {
      const [days, warnings, stock, items] = await Promise.all([
        api.menu.list(),
        api.warnings.list(),
        api.stock.list(),
        api.items.list(),
      ]);
      const today = days.find((day) => day.date === this.localIsoDate());
      this.days.set(days);
      this.warnings.set(warnings);
      this.stock.set(stock);
      this.items.set(items);
      this.today.set(today);
      this.outOfStockCount.set(stock.filter((item) => item.in_stock === false).length);
      this.upcoming.set(days.filter((day) => day.date !== this.localIsoDate()).slice(0, 5));
      this.quickLinks.set([
        { path: '/menu', label: 'tabs.menu', help: 'dashboard.menuHelp' },
        { path: '/items', label: 'dashboard.items', help: 'dashboard.itemsHelp', count: items.length },
        { path: '/categories', label: 'tabs.categories', help: 'dashboard.categoriesHelp' },
        { path: '/rules', label: 'tabs.rules', help: 'dashboard.rulesHelp' },
        { path: '/stock', label: 'tabs.stock', help: 'dashboard.stockHelp', count: stock.length },
        { path: '/settings', label: 'tabs.settings', help: 'dashboard.settingsHelp' },
        { path: '/import-export', label: 'tabs.importExport', help: 'dashboard.importExportHelp' },
      ]);
    } catch (error) {
      this.messages.error(error);
    } finally {
      this.loading.set(false);
    }
  }

  formatDate(dateText: string): string {
    const [year, month, day] = dateText.split('-').map(Number);
    return new Intl.DateTimeFormat(this.i18n.locale(), {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
    }).format(new Date(year, month - 1, day));
  }

  dinnerNames(day: MenuDay): string {
    return day.dinner?.items.map((item) => item.name).join(' · ') ?? '';
  }

  private localIsoDate(): string {
    const date = new Date();
    return [
      date.getFullYear(),
      String(date.getMonth() + 1).padStart(2, '0'),
      String(date.getDate()).padStart(2, '0'),
    ].join('-').replace(/^(\d{4})(\d{2})(\d{2})$/, '$1-$2-$3');
  }
}
