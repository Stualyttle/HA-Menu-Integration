import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormControl, FormGroup, NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialog, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatRadioModule } from '@angular/material/radio';
import { MatSelectModule } from '@angular/material/select';
import { firstValueFrom } from 'rxjs';
import { api } from '../../../shared/api/instance.js';
import type {
  Category,
  Item,
  ItemInput,
  ItemType,
  Nutrition,
  NutritionCandidate,
  NutritionInput,
  NutritionLookup,
} from '../../../shared/api/types';
import { ConfirmationDialogComponent } from './confirmation-dialog.component';
import type { ConfirmationDialogData } from './confirmation-dialog.component';
import { I18nService } from './i18n.service';
import { MessageService } from './message.service';

type EditorForm = FormGroup<{
  name: FormControl<string>;
  type: FormControl<ItemType>;
  portion_grams: FormControl<string>;
  fat_source: FormControl<boolean>;
  track_stock: FormControl<boolean>;
  is_complete_meal: FormControl<boolean>;
  category_ids: FormControl<number[]>;
}>;

type NutritionForm = FormGroup<{
  kcal: FormControl<string>;
  protein_g: FormControl<string>;
  carbs_g: FormControl<string>;
  fat_g: FormControl<string>;
  fiber_g: FormControl<string>;
}>;

const NUTRIENTS = ['kcal', 'protein_g', 'carbs_g', 'fat_g', 'fiber_g'] as const;
type Nutrient = (typeof NUTRIENTS)[number];

@Component({
  selector: 'mp-item-editor',
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatCheckboxModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressSpinnerModule,
    MatRadioModule,
    MatSelectModule,
    ReactiveFormsModule,
  ],
  template: `
    <h2 mat-dialog-title>{{ i18n.t(itemId ? 'item.title.edit' : 'item.title.add') }}</h2>
    @if (loading()) {
      <mat-dialog-content><mat-spinner diameter="32" /></mat-dialog-content>
    } @else {
      <form [formGroup]="form" (ngSubmit)="save()">
        <mat-dialog-content>
          <mat-form-field appearance="outline">
            <mat-label>{{ i18n.t('item.name') }}</mat-label>
            <input matInput formControlName="name" required />
            @if (form.controls.name.touched && form.controls.name.invalid) {
              <mat-error>{{ i18n.t('item.nameRequired') }}</mat-error>
            }
          </mat-form-field>

          <mat-checkbox formControlName="is_complete_meal">
            {{ i18n.t('item.completeMeal') }}
          </mat-checkbox>
          <p>{{ i18n.t('item.completeMealHelp') }}</p>
          @if (!form.controls.is_complete_meal.value) {
            <mat-form-field appearance="outline">
              <mat-label>{{ i18n.t('item.type') }}</mat-label>
              <mat-select formControlName="type">
                <mat-option value="protein">{{ i18n.t('type.protein') }}</mat-option>
                <mat-option value="vegetable">{{ i18n.t('type.vegetable') }}</mat-option>
                <mat-option value="carb">{{ i18n.t('type.carb') }}</mat-option>
              </mat-select>
            </mat-form-field>
          }

          <h3>{{ i18n.t('item.categories') }}</h3>
          @if (categories().length === 0) {
            <p>{{ i18n.t('categories.empty') }}</p>
          } @else {
            @for (category of categories(); track category.id) {
              <mat-checkbox
                [checked]="form.controls.category_ids.value.includes(category.id)"
                (change)="toggleCategory(category.id, $event.checked)"
              >
                {{ category.name }}
              </mat-checkbox>
            }
          }

          <mat-form-field appearance="outline">
            <mat-label>{{ i18n.t('item.portion') }}</mat-label>
            <input matInput type="number" min="0" step="any" formControlName="portion_grams" />
            <mat-hint>{{ i18n.t('item.portionHelp') }}</mat-hint>
          </mat-form-field>
          <mat-checkbox formControlName="fat_source">{{ i18n.t('item.fatSource') }}</mat-checkbox>
          <p>{{ i18n.t('item.fatSourceHelp') }}</p>
          <mat-checkbox formControlName="track_stock">{{ i18n.t('item.trackStock') }}</mat-checkbox>
          <p>{{ i18n.t('item.trackStockHelp') }}</p>

          <h3>{{ i18n.t('item.nutrition.title') }}</h3>
          @if (candidates().length > 0) {
            <p role="status">{{ i18n.t('item.nutrition.matchHelp') }}</p>
            <mat-form-field appearance="outline">
              <mat-label>{{ i18n.t('item.nutrition.matchTitle') }}</mat-label>
              <mat-select
                [value]="selectedCandidateKey()"
                (selectionChange)="selectCandidate($event.value)"
              >
                @for (candidate of candidates(); track candidateKey(candidate)) {
                  <mat-option [value]="candidateKey(candidate)">
                    {{ candidate.matched_name }} · {{ candidate.source }}
                  </mat-option>
                }
              </mat-select>
            </mat-form-field>
            <button
              mat-button
              type="button"
              [disabled]="busy() || !selectedCandidate()"
              (click)="confirmMatch()"
            >
              {{ i18n.t('item.nutrition.confirm') }}
            </button>
          } @else if (nutritionStatus() === 'failed') {
            <p role="status">{{ i18n.t('item.nutrition.failed') }}</p>
          } @else if (nutrition()?.user_confirmed) {
            <p role="status">{{ i18n.t('item.nutrition.verified', { source: nutrition()?.source ?? '' }) }}</p>
          } @else {
            <p>{{ i18n.t('item.nutrition.unverified') }}</p>
          }
          <div [formGroup]="nutritionForm">
            @for (nutrient of nutrients; track nutrient) {
              <mat-form-field appearance="outline">
                <mat-label>{{ i18n.t(nutrientLabel(nutrient)) }}</mat-label>
                <input
                  matInput
                  type="number"
                  min="0"
                  step="any"
                  [formControlName]="nutrient"
                  (input)="nutritionDirty.set(true)"
                />
              </mat-form-field>
            }
          </div>
          @if (!nutritionValid()) {
            <p role="alert">{{ i18n.t('item.nutrition.requiredFields') }}</p>
          }
          <p>{{ i18n.t('item.nutrition.manualHelp') }}</p>
          @if (itemId) {
            <button mat-button type="button" [disabled]="busy()" (click)="lookupNutrition()">
              {{ busy() === 'lookup' ? i18n.t('common.loading') : i18n.t('item.nutrition.lookup') }}
            </button>
          }
        </mat-dialog-content>
        <mat-dialog-actions align="end">
          @if (itemId) {
            <button mat-button type="button" color="warn" [disabled]="busy()" (click)="remove()">
              {{ i18n.t('item.delete') }}
            </button>
          }
          <button mat-button type="button" [disabled]="busy()" (click)="dialogRef.close(false)">
            {{ i18n.t('common.cancel') }}
          </button>
          <button mat-flat-button type="submit" [disabled]="busy() || form.invalid">
            {{ busy() === 'save' ? i18n.t('common.saving') : i18n.t('common.save') }}
          </button>
        </mat-dialog-actions>
      </form>
    }
  `,
})
export class ItemEditorComponent implements OnInit {
  readonly itemId = inject<number | null>(MAT_DIALOG_DATA);
  readonly i18n = inject(I18nService);
  readonly dialogRef = inject(MatDialogRef<ItemEditorComponent, boolean>);
  private readonly dialog = inject(MatDialog);
  private readonly messages = inject(MessageService);
  private readonly fb = inject(NonNullableFormBuilder);
  readonly loading = signal(true);
  readonly busy = signal<'save' | 'delete' | 'lookup' | 'confirm' | null>(null);
  readonly categories = signal<Category[]>([]);
  readonly nutrition = signal<Nutrition | null>(null);
  readonly nutritionStatus = signal<string>('none');
  readonly candidates = signal<NutritionCandidate[]>([]);
  readonly selectedCandidate = signal<NutritionCandidate | null>(null);
  readonly selectedCandidateKey = signal('');
  readonly nutritionDirty = signal(false);
  readonly nutrients = NUTRIENTS;
  readonly form: EditorForm = this.fb.group({
    name: this.fb.control('', Validators.required),
    type: this.fb.control<ItemType>('protein'),
    portion_grams: this.fb.control('300'),
    fat_source: this.fb.control(false),
    track_stock: this.fb.control(false),
    is_complete_meal: this.fb.control(false),
    category_ids: this.fb.control<number[]>([]),
  });
  readonly nutritionForm: NutritionForm = this.fb.group({
    kcal: this.fb.control(''),
    protein_g: this.fb.control(''),
    carbs_g: this.fb.control(''),
    fat_g: this.fb.control(''),
    fiber_g: this.fb.control(''),
  });

  ngOnInit(): void {
    void this.load();
  }

  nutrientLabel(field: Nutrient): string {
    const labels: Record<Nutrient, string> = {
      kcal: 'item.nutrition.kcal',
      protein_g: 'item.nutrition.protein',
      carbs_g: 'item.nutrition.carbs',
      fat_g: 'item.nutrition.fat',
      fiber_g: 'item.nutrition.fiber',
    };
    return labels[field];
  }

  candidateKey(candidate: NutritionCandidate): string {
    return `${candidate.source}:${candidate.external_id}`;
  }

  selectCandidate(key: string): void {
    const candidate = this.candidates().find((entry) => this.candidateKey(entry) === key);
    this.selectedCandidate.set(candidate ?? null);
    this.selectedCandidateKey.set(candidate ? key : '');
    if (!candidate) return;
    this.nutritionForm.patchValue({
      kcal: this.nutritionValue(candidate.kcal),
      protein_g: this.nutritionValue(candidate.protein_g),
      carbs_g: this.nutritionValue(candidate.carbs_g),
      fat_g: this.nutritionValue(candidate.fat_g),
      fiber_g: this.nutritionValue(candidate.fiber_g),
    });
    this.nutritionDirty.set(false);
  }

  toggleCategory(categoryId: number, checked: boolean): void {
    const selected = this.form.controls.category_ids.value;
    this.form.controls.category_ids.setValue(
      checked ? [...selected, categoryId] : selected.filter((id) => id !== categoryId),
    );
  }

  async save(): Promise<void> {
    if (this.busy() || this.form.invalid || !this.nutritionValid()) {
      this.form.markAllAsTouched();
      return;
    }
    const value = this.form.getRawValue();
    const payload: ItemInput = {
      name: value.name.trim(),
      type: value.is_complete_meal ? 'carb' : value.type,
      portion_grams: this.toNumber(value.portion_grams),
      fat_source: value.fat_source,
      track_stock: value.track_stock,
      is_complete_meal: value.is_complete_meal,
      category_ids: value.category_ids,
    };
    if (!payload.name) {
      this.form.controls.name.setErrors({ required: true });
      this.form.controls.name.markAsTouched();
      return;
    }
    this.busy.set('save');
    try {
      const saved = this.itemId
        ? await api.items.update(this.itemId, payload)
        : await api.items.create(payload);
      if (this.nutritionDirty()) {
        await api.items.setNutrition(saved.id, this.nutritionPayload('manual'));
      }
      this.messages.success(this.i18n.t('item.saved'));
      this.dialogRef.close(true);
    } catch (error) {
      this.messages.error(error);
    } finally {
      this.busy.set(null);
    }
  }

  async remove(): Promise<void> {
    if (!this.itemId || this.busy()) return;
    const data: ConfirmationDialogData = {
      title: this.i18n.t('common.confirmDelete'),
      message: this.i18n.t('item.confirmDelete'),
      confirmLabel: this.i18n.t('common.delete'),
    };
    const confirmed = await firstValueFrom(
      this.dialog
        .open(ConfirmationDialogComponent, { data, width: '420px', maxWidth: '90vw' })
        .afterClosed(),
    );
    if (!confirmed) return;
    this.busy.set('delete');
    try {
      await api.items.remove(this.itemId);
      this.messages.success(this.i18n.t('item.deleted'));
      this.dialogRef.close(true);
    } catch (error) {
      this.messages.error(error);
    } finally {
      this.busy.set(null);
    }
  }

  async lookupNutrition(): Promise<void> {
    if (!this.itemId || this.busy()) return;
    this.busy.set('lookup');
    try {
      const result: NutritionLookup = await api.items.lookupNutrition(this.itemId);
      this.candidates.set(result.candidates);
      this.selectedCandidate.set(null);
      this.selectedCandidateKey.set('');
      this.nutritionStatus.set(
        result.candidates.length ? 'candidate' : result.failed_sources.length ? 'failed' : 'none',
      );
      this.messages.success(this.i18n.t('item.nutrition.lookupStarted'));
    } catch (error) {
      this.messages.error(error);
    } finally {
      this.busy.set(null);
    }
  }

  async confirmMatch(): Promise<void> {
    if (!this.itemId || this.busy()) return;
    this.busy.set('confirm');
    try {
      const candidate = this.selectedCandidate();
      if (!candidate) return;
      await api.items.setNutrition(this.itemId, this.nutritionPayload(candidate.source, candidate));
      await this.reloadItem();
      this.candidates.set([]);
      this.selectedCandidate.set(null);
      this.selectedCandidateKey.set('');
      this.messages.success(this.i18n.t('item.nutrition.confirmed'));
    } catch (error) {
      this.messages.error(error);
    } finally {
      this.busy.set(null);
    }
  }

  private async load(): Promise<void> {
    this.loading.set(true);
    try {
      const [categories, item] = await Promise.all([
        api.categories.list(),
        this.itemId ? api.items.get(this.itemId) : Promise.resolve(null),
      ]);
      this.categories.set(categories);
      if (item) this.applyItem(item);
    } catch (error) {
      this.messages.error(error);
      this.dialogRef.close(false);
    } finally {
      this.loading.set(false);
    }
  }

  private async reloadItem(): Promise<void> {
    if (!this.itemId) return;
    this.applyItem(await api.items.get(this.itemId));
  }

  private applyItem(item: Item): void {
    this.form.reset({
      name: item.name,
      type: item.type,
      portion_grams: item.portion_grams == null ? '' : String(item.portion_grams),
      fat_source: item.fat_source,
      track_stock: item.track_stock,
      is_complete_meal: item.is_complete_meal,
      category_ids: [...item.category_ids],
    });
    this.nutrition.set(item.nutrition);
    const status = item.nutrition?.status;
    this.nutritionStatus.set(status === 'error' || status === 'not_found' ? 'failed' : status ?? 'none');
    this.candidates.set([]);
    this.selectedCandidate.set(null);
    this.selectedCandidateKey.set('');
    this.nutritionForm.reset({
      kcal: this.nutritionValue(item.nutrition?.kcal),
      protein_g: this.nutritionValue(item.nutrition?.protein_g),
      carbs_g: this.nutritionValue(item.nutrition?.carbs_g),
      fat_g: this.nutritionValue(item.nutrition?.fat_g),
      fiber_g: this.nutritionValue(item.nutrition?.fiber_g),
    });
    this.nutritionDirty.set(false);
  }

  private nutritionValue(value: number | null | undefined): string {
    return value == null ? '' : String(value);
  }

  nutritionValid(): boolean {
    if (!this.nutritionDirty()) return true;
    const values = this.nutritionForm.getRawValue();
    return [values.kcal, values.protein_g, values.carbs_g, values.fat_g].every(
      (value) => this.toNumber(value) !== null,
    );
  }

  private toNumber(value: string): number | null {
    if (!value.trim()) return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
  }

  private nutritionPayload(
    source: NutritionInput['source'],
    candidate?: NutritionCandidate,
  ): NutritionInput {
    const values = this.nutritionForm.getRawValue();
    return {
      source,
      ...(candidate
        ? {
            external_id: candidate.external_id,
            matched_name: candidate.matched_name,
          }
        : {}),
      kcal: this.toNumber(values.kcal),
      protein_g: this.toNumber(values.protein_g),
      carbs_g: this.toNumber(values.carbs_g),
      fat_g: this.toNumber(values.fat_g),
      fiber_g: this.toNumber(values.fiber_g),
    };
  }
}
