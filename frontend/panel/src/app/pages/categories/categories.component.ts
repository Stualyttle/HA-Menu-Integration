import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormControl, FormGroup, NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatDialog } from '@angular/material/dialog';
import { firstValueFrom } from 'rxjs';
import { api } from '@shared/api/instance.js';
import type { Category, CategoryInput } from '@shared/api/types';
import { ConfirmationDialogComponent } from '@app/components/dialogs/confirmation-dialog.component';
import { I18nService } from '@app/core/services/i18n.service';
import { MessageService } from '@app/core/services/message.service';

@Component({
  selector: 'mp-categories',
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressSpinnerModule,
    ReactiveFormsModule,
  ],
  template: `
    <h1>{{ i18n.t('categories.title') }}</h1>
    @if (loading()) {
      <mat-card><mat-card-content><mat-spinner diameter="32" /></mat-card-content></mat-card>
    } @else if (categories().length === 0) {
      <mat-card><mat-card-content>{{ i18n.t('categories.empty') }}</mat-card-content></mat-card>
    } @else {
      @for (category of categories(); track category.id) {
        <mat-card>
          <mat-card-header>
            <mat-card-title>{{ category.name }}</mat-card-title>
            <mat-card-subtitle>
              {{ i18n.t('categories.itemCount', { count: category.item_count }) }}
              @if (category.is_starter) { · {{ i18n.t('categories.starter') }} }
            </mat-card-subtitle>
          </mat-card-header>
          <mat-card-content>
            <mat-form-field appearance="outline">
              <mat-label>{{ i18n.t('categories.col.minimum') }}</mat-label>
              <input matInput type="number" min="0" max="7" [formControl]="minimumControl(category.id)" />
            </mat-form-field>
          </mat-card-content>
          <mat-card-actions>
            <button mat-button type="button" (click)="saveMinimum(category)">
              {{ i18n.t('common.save') }}
            </button>
            <button mat-button type="button" (click)="remove(category)">
              {{ i18n.t('common.delete') }}
            </button>
          </mat-card-actions>
        </mat-card>
      }
    }

    <mat-card>
      <mat-card-header><mat-card-title>{{ i18n.t('categories.add') }}</mat-card-title></mat-card-header>
      <mat-card-content>
        <form [formGroup]="form" (ngSubmit)="add()">
          <mat-form-field appearance="outline">
            <mat-label>{{ i18n.t('categories.name') }}</mat-label>
            <input matInput formControlName="name" required />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>{{ i18n.t('categories.minimum') }}</mat-label>
            <input matInput type="number" min="0" max="7" formControlName="min_per_7_days" />
          </mat-form-field>
          <button mat-flat-button type="submit" [disabled]="form.invalid || saving()">
            {{ i18n.t('categories.add') }}
          </button>
        </form>
      </mat-card-content>
    </mat-card>
  `,
})
export class CategoriesComponent implements OnInit {
  readonly i18n = inject(I18nService);
  private readonly messages = inject(MessageService);
  private readonly dialog = inject(MatDialog);
  private readonly fb = inject(NonNullableFormBuilder);
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly categories = signal<Category[]>([]);
  readonly minimums = new Map<number, FormControl<number>>();
  readonly form: FormGroup<{
    name: FormControl<string>;
    min_per_7_days: FormControl<number>;
  }> = this.fb.group({
    name: this.fb.control('', { validators: [Validators.required, Validators.maxLength(100)] }),
    min_per_7_days: this.fb.control(0, { validators: [Validators.min(0), Validators.max(7)] }),
  });

  ngOnInit(): void {
    void this.load();
  }

  async load(): Promise<void> {
    this.loading.set(true);
    try {
      const categories = await api.categories.list();
      this.categories.set(categories);
      this.minimums.clear();
      for (const category of categories) {
        this.minimums.set(
          category.id,
          new FormControl(category.min_per_7_days ?? 0, {
            nonNullable: true,
            validators: [Validators.min(0), Validators.max(7)],
          }),
        );
      }
    } catch (error) {
      this.messages.error(error);
    } finally {
      this.loading.set(false);
    }
  }

  minimumControl(id: number): FormControl<number> {
    const control = this.minimums.get(id);
    if (!control) throw new Error(`Missing minimum control for category ${id}`);
    return control;
  }

  async saveMinimum(category: Category): Promise<void> {
    const control = this.minimumControl(category.id);
    if (control.invalid) {
      control.markAsTouched();
      return;
    }
    await this.perform(() =>
      api.categories.update(category.id, {
        name: category.name,
        min_per_7_days: control.value,
        item_ids: category.item_ids,
      }),
    );
    this.messages.success(this.i18n.t('categories.minimumSaved'));
    await this.load();
  }

  async add(): Promise<void> {
    if (this.form.invalid || this.saving()) {
      this.form.markAllAsTouched();
      return;
    }
    const value = this.form.getRawValue();
    const payload: CategoryInput = { name: value.name.trim(), min_per_7_days: value.min_per_7_days };
    const success = await this.perform(() => api.categories.create(payload));
    if (success) {
      this.form.reset({ name: '', min_per_7_days: 0 });
      this.messages.success(this.i18n.t('categories.saved'));
      await this.load();
    }
  }

  async remove(category: Category): Promise<void> {
    const confirmed = await firstValueFrom(
      this.dialog
        .open(ConfirmationDialogComponent, {
          data: {
            title: this.i18n.t('common.confirmDelete'),
            message: this.i18n.t('categories.confirmDelete'),
            confirmLabel: this.i18n.t('common.delete'),
          },
        })
        .afterClosed(),
    );
    if (confirmed !== true) return;
    const success = await this.perform(() => api.categories.remove(category.id));
    if (success) {
      this.messages.success(this.i18n.t('categories.deleted'));
      await this.load();
    }
  }

  private async perform(action: () => Promise<unknown>): Promise<boolean> {
    this.saving.set(true);
    try {
      await action();
      return true;
    } catch (error) {
      this.messages.error(error);
      return false;
    } finally {
      this.saving.set(false);
    }
  }
}
