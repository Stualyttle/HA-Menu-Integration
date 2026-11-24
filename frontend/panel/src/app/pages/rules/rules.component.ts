import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { MatDialog } from '@angular/material/dialog';
import { firstValueFrom } from 'rxjs';
import { api } from '@shared/api/instance.js';
import type { Category, Rule, RuleCheck, RuleInput } from '@shared/api/types';
import { ConfirmationDialogComponent } from '@app/components/dialogs/confirmation-dialog.component';
import { I18nService } from '@app/core/services/i18n.service';
import { MessageService } from '@app/core/services/message.service';

@Component({
  selector: 'mp-rules',
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatCardModule,
    MatCheckboxModule,
    MatFormFieldModule,
    MatProgressSpinnerModule,
    MatSelectModule,
  ],
  template: `
    <h1>{{ i18n.t('rules.title') }}</h1>
    @if (loading()) {
      <mat-card><mat-card-content><mat-spinner diameter="32" /></mat-card-content></mat-card>
    } @else {
      @for (kind of kinds; track kind) {
        <mat-card>
          <mat-card-header>
            <mat-card-title>{{ i18n.t(kind === 'blacklist' ? 'rules.blacklist' : 'rules.whitelist') }}</mat-card-title>
            <mat-card-subtitle>
              {{ i18n.t(kind === 'blacklist' ? 'rules.blacklistHint' : 'rules.whitelistHint') }}
            </mat-card-subtitle>
          </mat-card-header>
          <mat-card-content>
            @if (rulesFor(kind).length === 0) {
              <p>{{ i18n.t('rules.none') }}</p>
            } @else {
              @for (rule of rulesFor(kind); track rule.id) {
                <p>
                  {{ ruleLabel(rule) }} · {{ i18n.t('rules.kind.' + rule.scope) }}
                  <button mat-button type="button" (click)="remove(rule)">
                    {{ i18n.t('rules.delete') }}
                  </button>
                </p>
              }
            }
          </mat-card-content>
        </mat-card>
      }

      <mat-card>
        <mat-card-header>
          <mat-card-title>{{ i18n.t('rules.builderTitle') }}</mat-card-title>
        </mat-card-header>
        <mat-card-content>
          <p>{{ i18n.t('rules.builderCategories') }}</p>
          @for (category of categories(); track category.id) {
            <mat-checkbox
              [checked]="selected().includes(category.id)"
              (change)="toggleCategory(category.id, $event.checked)"
            >
              {{ category.name }}
            </mat-checkbox>
          }
          <mat-form-field appearance="outline">
            <mat-label>{{ i18n.t('rules.builderKind') }}</mat-label>
            <mat-select [value]="kind()" (selectionChange)="changeKind($event.value)">
              <mat-option value="blacklist">{{ i18n.t('rules.kindBlacklist') }}</mat-option>
              <mat-option value="whitelist">{{ i18n.t('rules.kindWhitelist') }}</mat-option>
            </mat-select>
          </mat-form-field>
          @if (selected().length < 2) {
            <p>{{ i18n.t('rules.pickTwo') }}</p>
          } @else {
            <p>
              {{ i18n.t(kind() === 'blacklist' ? 'rules.previewBlacklist' : 'rules.previewWhitelist', {
                names: selectedNames()
              }) }}
            </p>
          }
          @if (check()?.feasible === false) {
            <mat-card>
              <mat-card-content>
                <strong>{{ i18n.t('rules.infeasibleTitle') }}</strong>
                {{ i18n.t('rules.infeasibleBody') }}
                {{ i18n.t('rules.infeasibleSave', { days: check()?.affected_days?.length ?? 0 }) }}
              </mat-card-content>
            </mat-card>
          }
        </mat-card-content>
        <mat-card-actions>
          <button
            mat-flat-button
            type="button"
            [disabled]="selected().length < 2 || check()?.feasible === false || saving()"
            (click)="add()"
          >
            {{ i18n.t('rules.add') }}
          </button>
        </mat-card-actions>
      </mat-card>
    }
  `,
})
export class RulesComponent implements OnInit {
  readonly i18n = inject(I18nService);
  private readonly messages = inject(MessageService);
  private readonly dialog = inject(MatDialog);
  readonly kinds: RuleInput['kind'][] = ['blacklist', 'whitelist'];
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly rules = signal<Rule[]>([]);
  readonly categories = signal<Category[]>([]);
  readonly kind = signal<RuleInput['kind']>('blacklist');
  readonly selected = signal<number[]>([]);
  readonly check = signal<RuleCheck | null>(null);
  private checkSequence = 0;

  ngOnInit(): void {
    void this.load();
  }

  async load(): Promise<void> {
    this.loading.set(true);
    try {
      const [rules, categories] = await Promise.all([api.rules.list(), api.categories.list()]);
      this.rules.set(rules);
      this.categories.set(categories);
    } catch (error) {
      this.messages.error(error);
    } finally {
      this.loading.set(false);
    }
  }

  rulesFor(kind: RuleInput['kind']): Rule[] {
    return this.rules().filter((rule) => rule.kind === kind);
  }

  ruleLabel(rule: Rule): string {
    if (rule.scope === 'item') return `${this.i18n.t('rules.kind.item')} #${rule.item_id ?? ''}`;
    return (rule.category_ids ?? []).map((id) => this.categoryName(id)).join(' + ');
  }

  selectedNames(): string {
    return this.selected().map((id) => this.categoryName(id)).join(', ');
  }

  toggleCategory(id: number, checked: boolean): void {
    const next = new Set(this.selected());
    if (checked) next.add(id);
    else next.delete(id);
    const selected = [...next];
    this.selected.set(selected);
    void this.runCheck(this.kind(), selected);
  }

  changeKind(kind: RuleInput['kind']): void {
    this.kind.set(kind);
    void this.runCheck(kind, this.selected());
  }

  async add(): Promise<void> {
    const ids = this.selected();
    if (ids.length < 2 || this.check()?.feasible === false) return;
    this.saving.set(true);
    try {
      await api.rules.create(this.ruleBody(this.kind(), ids));
      this.messages.success(this.i18n.t('rules.added'));
      this.selected.set([]);
      this.check.set(null);
      await this.load();
    } catch (error) {
      this.messages.error(error);
    } finally {
      this.saving.set(false);
    }
  }

  async remove(rule: Rule): Promise<void> {
    const confirmed = await firstValueFrom(
      this.dialog
        .open(ConfirmationDialogComponent, {
          data: {
            title: this.i18n.t('common.confirmDelete'),
            message: this.i18n.t('rules.confirmDelete'),
            confirmLabel: this.i18n.t('common.delete'),
          },
        })
        .afterClosed(),
    );
    if (confirmed !== true) return;
    try {
      await api.rules.remove(rule.id);
      this.messages.success(this.i18n.t('rules.deleted'));
      await this.load();
    } catch (error) {
      this.messages.error(error);
    }
  }

  private async runCheck(kind: RuleInput['kind'], ids: number[]): Promise<void> {
    const sequence = ++this.checkSequence;
    if (ids.length < 2) {
      this.check.set(null);
      return;
    }
    try {
      const result = await api.rules.check(this.ruleBody(kind, ids));
      if (sequence === this.checkSequence) this.check.set(result);
    } catch (error) {
      if (sequence === this.checkSequence) this.messages.error(error);
    }
  }

  private ruleBody(kind: RuleInput['kind'], ids: number[]): RuleInput {
    return { kind, scope: 'combination', category_ids: ids, enabled: true };
  }

  private categoryName(id: number): string {
    return this.categories().find((category) => category.id === id)?.name ?? String(id);
  }
}
