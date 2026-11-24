import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { api } from '@shared/api/instance.js';
import type { Dinner, MenuDay, WarningRecord } from '@shared/api/types';
import { I18nService } from '@app/core/services/i18n.service';
import { MessageService } from '@app/core/services/message.service';

@Component({
  selector: 'mp-menu',
  standalone: true,
  imports: [CommonModule, MatButtonModule, MatCardModule, MatChipsModule, MatProgressSpinnerModule],
  template: `
    <section>
      <mat-card>
        <mat-card-header>
          <mat-card-title>{{ i18n.t('menu.title') }}</mat-card-title>
          <mat-card-subtitle>{{ i18n.t('menu.subtitle', { days: windowDays() }) }}</mat-card-subtitle>
        </mat-card-header>
        <mat-card-actions>
          <button mat-flat-button type="button" [disabled]="busy() === 'replan'" (click)="replan()">
            {{ i18n.t('menu.replan') }}
          </button>
        </mat-card-actions>
      </mat-card>

      @for (warning of warnings(); track warning.id) {
        <mat-card>
          <mat-card-content>
            {{ warningText(warning) }}
            <button mat-button type="button" (click)="resolveWarning(warning)">
              {{ i18n.t('warnings.resolve') }}
            </button>
          </mat-card-content>
        </mat-card>
      }

      @if (loading()) {
        <mat-card><mat-card-content><mat-spinner diameter="32" /></mat-card-content></mat-card>
      } @else if (days().length === 0) {
        <mat-card><mat-card-content>{{ i18n.t('menu.empty') }}</mat-card-content></mat-card>
      } @else {
        @for (day of days(); track day.date) {
          <mat-card>
            <mat-card-header>
              <mat-card-title>{{ formatDate(day.date) }}</mat-card-title>
              <mat-card-subtitle>
                {{ i18n.t('menu.status.' + day.status) }} · {{ i18n.t('menu.balance.' + day.balance) }}
              </mat-card-subtitle>
            </mat-card-header>
            <mat-card-content>
              @if (day.dinner?.items?.length) {
                <mat-chip-set aria-label="{{ i18n.t('menu.title') }}">
                  @for (item of day.dinner!.items; track item.id) {
                    <mat-chip>
                      {{ item.name }} ·
                      {{ item.is_complete_meal ? i18n.t('items.completeMeal') : i18n.t('type.' + item.type) }}
                    </mat-chip>
                  }
                </mat-chip-set>
              } @else {
                <p>{{ i18n.t('menu.noDinner') }}</p>
              }
              <p>{{ day.kcal === null ? i18n.t('menu.kcalUnknown') : i18n.t('menu.kcal', { kcal: day.kcal }) }}</p>
              @if (day.replaced_reason) { <p>{{ i18n.t('menu.replacedHint') }}</p> }
            </mat-card-content>
            <mat-card-actions>
              <button
                mat-button
                type="button"
                [disabled]="!day.dinner || day.status === 'eaten' || busy() === day.date"
                (click)="togglePin(day)"
              >
                {{ day.status === 'pinned' ? i18n.t('menu.unpin') : i18n.t('menu.pin') }}
              </button>
              <button
                mat-button
                type="button"
                [disabled]="day.status === 'eaten' || busy() === day.date"
                (click)="toggleSuggestions(day)"
              >
                {{ day.dinner ? i18n.t('menu.swap') : i18n.t('menu.edit') }}
              </button>
              <button
                mat-button
                type="button"
                [disabled]="!day.dinner || day.status === 'eaten' || busy() === day.date"
                (click)="logEaten(day)"
              >
                {{ i18n.t('menu.logEaten') }}
              </button>
            </mat-card-actions>
            @if (suggestFor() === day.date) {
              <mat-card-content>
                <h3>{{ i18n.t('menu.chooseDinner', { date: formatDate(day.date) }) }}</h3>
                @if (suggestions().length === 0) {
                  <p>{{ i18n.t('menu.noSuggestions') }}</p>
                }
                @for (dinner of suggestions(); track dinnerKey(dinner)) {
                  <p>
                    {{ dinnerNames(dinner) }}
                    <button mat-button type="button" (click)="chooseSuggestion(day, dinner)">
                      {{ i18n.t('menu.useDinner') }}
                    </button>
                  </p>
                }
              </mat-card-content>
            }
          </mat-card>
        }
      }
    </section>
  `,
})
export class MenuComponent implements OnInit {
  readonly i18n = inject(I18nService);
  private readonly messages = inject(MessageService);
  readonly loading = signal(true);
  readonly busy = signal<string | null>(null);
  readonly days = signal<MenuDay[]>([]);
  readonly warnings = signal<WarningRecord[]>([]);
  readonly suggestions = signal<Dinner[]>([]);
  readonly suggestFor = signal<string | null>(null);
  readonly windowDays = signal(14);

  ngOnInit(): void {
    void this.load();
  }

  async load(): Promise<void> {
    this.loading.set(true);
    try {
      const settings = await api.settings.get();
      this.windowDays.set(settings.window_days);
      const start = this.localIsoDate();
      const end = this.addDays(start, settings.window_days - 1);
      const [days, warnings] = await Promise.all([
        api.menu.list(start, end),
        api.warnings.list(),
      ]);
      this.days.set(days);
      this.warnings.set(warnings);
    } catch (error) {
      this.messages.error(error);
    } finally {
      this.loading.set(false);
    }
  }

  async togglePin(day: MenuDay): Promise<void> {
    await this.mutate(day.date, () => api.menu.update(day.date, { pinned: day.status !== 'pinned' }), 'menu.updated');
  }

  async logEaten(day: MenuDay): Promise<void> {
    await this.mutate(day.date, () => api.menu.eaten(day.date), 'menu.eatenLogged');
  }

  async toggleSuggestions(day: MenuDay): Promise<void> {
    if (this.suggestFor() === day.date) {
      this.suggestFor.set(null);
      return;
    }
    this.suggestFor.set(day.date);
    this.suggestions.set([]);
    try {
      this.suggestions.set(await api.menu.swapSuggestions(day.date));
    } catch (error) {
      this.messages.error(error);
    }
  }

  async chooseSuggestion(day: MenuDay, dinner: Dinner): Promise<void> {
    await this.mutate(day.date, () => api.menu.swap(day.date, dinner.items.map((item) => item.id)), 'menu.updated');
    this.suggestFor.set(null);
  }

  async resolveWarning(warning: WarningRecord): Promise<void> {
    try {
      await api.warnings.resolve(warning.id);
      this.warnings.update((warnings) => warnings.filter((item) => item.id !== warning.id));
    } catch (error) {
      this.messages.error(error);
    }
  }

  async replan(): Promise<void> {
    this.busy.set('replan');
    try {
      await api.menu.replan();
      this.messages.success(this.i18n.t('menu.replanned'));
      await this.load();
    } catch (error) {
      this.messages.error(error);
    } finally {
      this.busy.set(null);
    }
  }

  warningText(warning: WarningRecord): string {
    const key = `warning.${warning.code}`;
    const translated = this.i18n.t(key);
    return translated === key ? this.i18n.t('warning.unknown', { code: warning.code }) : translated;
  }

  formatDate(dateText: string): string {
    const [year, month, day] = dateText.split('-').map(Number);
    return new Intl.DateTimeFormat(this.i18n.locale(), {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
    }).format(new Date(year, month - 1, day));
  }

  dinnerKey(dinner: Dinner): string {
    return dinner.items.map((item) => item.id).join('-');
  }

  dinnerNames(dinner: Dinner): string {
    return dinner.items.map((item) => item.name).join(' · ');
  }

  private async mutate(date: string, action: () => Promise<unknown>, messageKey: string): Promise<void> {
    this.busy.set(date);
    try {
      await action();
      this.messages.success(this.i18n.t(messageKey));
      await this.load();
    } catch (error) {
      this.messages.error(error);
    } finally {
      this.busy.set(null);
    }
  }

  private localIsoDate(): string {
    const date = new Date();
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  }

  private addDays(dateText: string, days: number): string {
    const [year, month, day] = dateText.split('-').map(Number);
    const date = new Date(year, month - 1, day + days);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  }
}
