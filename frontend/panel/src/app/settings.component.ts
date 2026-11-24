import { Component, OnInit, inject, signal } from '@angular/core';
import { FormControl, FormGroup, NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { api } from '../../../shared/api/instance.js';
import type { BalanceTargets, Category, Settings, Template } from '../../../shared/api/types';
import { I18nService } from './i18n.service';
import { MessageService } from './message.service';

type PreferenceKey = 'fish' | 'vegetarian';
type SettingsForm = FormGroup<{
  window_days: FormControl<number>;
  household_size: FormControl<number>;
  repeat_gap_days: FormControl<number>;
  language: FormControl<'en' | 'nl'>;
  vegetables: FormControl<number>;
  protein: FormControl<number>;
  carbs: FormControl<number>;
  tolerance: FormControl<number>;
  protein_slots: FormControl<number>;
  vegetable_slots: FormControl<number>;
  carb_slots: FormControl<number>;
  fish_min: FormControl<number>;
  vegetarian_min: FormControl<number>;
  usda_api_key: FormControl<string>;
}>;

const PREFERENCE_CATEGORY_NAMES: Record<PreferenceKey, string[]> = {
  fish: ['fish', 'vis'],
  vegetarian: ['vegetarian', 'vegetarisch'],
};

@Component({
  selector: 'mp-settings',
  standalone: true,
  imports: [
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressSpinnerModule,
    MatSelectModule,
    ReactiveFormsModule,
  ],
  template: `
    <h1>{{ i18n.t('settings.title') }}</h1>
    @if (loading()) {
      <mat-card><mat-card-content><mat-spinner diameter="32" /></mat-card-content></mat-card>
    } @else {
      <form [formGroup]="form" (ngSubmit)="save()">
        <mat-card>
          <mat-card-header><mat-card-title>{{ i18n.t('settings.window.title') }}</mat-card-title></mat-card-header>
          <mat-card-content>
            <mat-form-field appearance="outline">
              <mat-label>{{ i18n.t('settings.window.label') }}</mat-label>
              <input matInput type="number" min="7" max="60" formControlName="window_days" />
              <mat-hint>{{ i18n.t('settings.window.help') }}</mat-hint>
            </mat-form-field>
          </mat-card-content>
        </mat-card>

        <mat-card>
          <mat-card-header><mat-card-title>{{ i18n.t('settings.household.title') }}</mat-card-title></mat-card-header>
          <mat-card-content>
            <mat-form-field appearance="outline">
              <mat-label>{{ i18n.t('settings.household.size') }}</mat-label>
              <input matInput type="number" min="1" max="10" formControlName="household_size" />
              <mat-hint>{{ i18n.t('settings.household.sizeHelp') }}</mat-hint>
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>{{ i18n.t('settings.household.gap') }}</mat-label>
              <input matInput type="number" min="0" max="60" formControlName="repeat_gap_days" />
              <mat-hint>{{ i18n.t('settings.household.gapHelp') }}</mat-hint>
            </mat-form-field>
          </mat-card-content>
        </mat-card>

        <mat-card>
          <mat-card-header><mat-card-title>{{ i18n.t('onboarding.preferences.diet') }}</mat-card-title></mat-card-header>
          <mat-card-content>
            <p>{{ i18n.t('settings.preferences.help') }}</p>
            @if (preferenceCategories.fish) {
              <mat-form-field appearance="outline">
                <mat-label>{{ i18n.t('onboarding.preferences.fish') }}</mat-label>
                <input matInput type="number" min="0" max="7" formControlName="fish_min" />
                <mat-hint>{{ i18n.t('onboarding.preferences.perWeek') }}</mat-hint>
              </mat-form-field>
            }
            @if (preferenceCategories.vegetarian) {
              <mat-form-field appearance="outline">
                <mat-label>{{ i18n.t('onboarding.preferences.vegetarian') }}</mat-label>
                <input matInput type="number" min="0" max="7" formControlName="vegetarian_min" />
                <mat-hint>{{ i18n.t('onboarding.preferences.perWeek') }}</mat-hint>
              </mat-form-field>
            }
            @if (!preferenceCategories.fish && !preferenceCategories.vegetarian) {
              <p>{{ i18n.t('settings.preferences.noCategories') }}</p>
            }
          </mat-card-content>
        </mat-card>

        <mat-card>
          <mat-card-header><mat-card-title>{{ i18n.t('settings.balance.title') }}</mat-card-title></mat-card-header>
          <mat-card-content>
            <mat-form-field appearance="outline">
              <mat-label>{{ i18n.t('settings.balance.vegetables') }}</mat-label>
              <input matInput type="number" min="0" max="100" formControlName="vegetables" />
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>{{ i18n.t('settings.balance.protein') }}</mat-label>
              <input matInput type="number" min="0" max="100" formControlName="protein" />
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>{{ i18n.t('settings.balance.carbs') }}</mat-label>
              <input matInput type="number" min="0" max="100" formControlName="carbs" />
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>{{ i18n.t('settings.balance.tolerance') }}</mat-label>
              <input matInput type="number" min="0" max="100" formControlName="tolerance" />
            </mat-form-field>
            <p>{{ i18n.t('settings.balance.help') }}</p>
            @if (targetSum() !== 100) {
              <p role="alert">{{ i18n.t('onboarding.preferences.targetSum', { sum: targetSum() }) }}</p>
            }
          </mat-card-content>
        </mat-card>

        <mat-card>
          <mat-card-header><mat-card-title>{{ i18n.t('settings.template.title') }}</mat-card-title></mat-card-header>
          <mat-card-content>
            <mat-form-field appearance="outline">
              <mat-label>{{ i18n.t('settings.template.protein') }}</mat-label>
              <input matInput type="number" min="0" max="2" formControlName="protein_slots" />
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>{{ i18n.t('settings.template.vegetable') }}</mat-label>
              <input matInput type="number" min="0" max="2" formControlName="vegetable_slots" />
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>{{ i18n.t('settings.template.carb') }}</mat-label>
              <input matInput type="number" min="0" max="2" formControlName="carb_slots" />
            </mat-form-field>
            <p>{{ i18n.t('settings.template.help') }}</p>
          </mat-card-content>
        </mat-card>

        <mat-card>
          <mat-card-header><mat-card-title>{{ i18n.t('settings.general.title') }}</mat-card-title></mat-card-header>
          <mat-card-content>
            <mat-form-field appearance="outline">
              <mat-label>{{ i18n.t('settings.language') }}</mat-label>
              <mat-select formControlName="language">
                <mat-option value="en">{{ i18n.t('settings.language.en') }}</mat-option>
                <mat-option value="nl">{{ i18n.t('settings.language.nl') }}</mat-option>
              </mat-select>
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>{{ i18n.t('settings.usda') }}</mat-label>
              <input
                matInput
                type="password"
                autocomplete="new-password"
                placeholder="{{ i18n.t('settings.usda.placeholder') }}"
                formControlName="usda_api_key"
              />
              <mat-hint>{{ i18n.t('settings.usda.help') }}</mat-hint>
            </mat-form-field>
          </mat-card-content>
          <mat-card-actions>
            <button mat-button type="button" [disabled]="saving()" (click)="retryLookups()">
              {{ i18n.t('settings.retry') }}
            </button>
          </mat-card-actions>
        </mat-card>

        <button mat-flat-button type="submit" [disabled]="saving() || form.invalid || targetSum() !== 100 || !templateValid()">
          {{ saving() ? i18n.t('common.saving') : i18n.t('common.save') }}
        </button>
      </form>
    }
  `,
})
export class SettingsComponent implements OnInit {
  readonly i18n = inject(I18nService);
  private readonly messages = inject(MessageService);
  private readonly fb = inject(NonNullableFormBuilder);
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly preferenceCategories: Partial<Record<PreferenceKey, Category>> = {};
  readonly form: SettingsForm = this.fb.group({
    window_days: this.fb.control(14, [Validators.min(7), Validators.max(60)]),
    household_size: this.fb.control(2, [Validators.min(1), Validators.max(10)]),
    repeat_gap_days: this.fb.control(14, [Validators.min(0), Validators.max(60)]),
    language: this.fb.control<'en' | 'nl'>('en'),
    vegetables: this.fb.control(50, [Validators.min(0), Validators.max(100)]),
    protein: this.fb.control(25, [Validators.min(0), Validators.max(100)]),
    carbs: this.fb.control(25, [Validators.min(0), Validators.max(100)]),
    tolerance: this.fb.control(10, [Validators.min(0), Validators.max(100)]),
    protein_slots: this.fb.control(1, [Validators.min(0), Validators.max(2)]),
    vegetable_slots: this.fb.control(1, [Validators.min(0), Validators.max(2)]),
    carb_slots: this.fb.control(1, [Validators.min(0), Validators.max(2)]),
    fish_min: this.fb.control(0, [Validators.min(0), Validators.max(7)]),
    vegetarian_min: this.fb.control(0, [Validators.min(0), Validators.max(7)]),
    usda_api_key: this.fb.control(''),
  });
  private loadedLanguage: 'en' | 'nl' = 'en';

  ngOnInit(): void {
    void this.load();
  }

  targetSum(): number {
    const value = this.form.getRawValue();
    return value.vegetables + value.protein + value.carbs;
  }

  templateValid(): boolean {
    const value = this.form.getRawValue();
    return value.protein_slots + value.vegetable_slots + value.carb_slots > 0;
  }

  async load(): Promise<void> {
    this.loading.set(true);
    try {
      const [settings, template, categories] = await Promise.all([
        api.settings.get(),
        api.template.get(),
        api.categories.list(),
      ]);
      const language = settings.language === 'nl' ? 'nl' : 'en';
      this.loadedLanguage = language;
      this.i18n.setLocale(language);
      this.loadPreferenceCategories(categories);
      this.form.reset(this.settingsFormValue(settings, template));
    } catch (error) {
      this.messages.error(error);
    } finally {
      this.loading.set(false);
    }
  }

  async save(): Promise<void> {
    if (this.form.invalid || this.targetSum() !== 100 || !this.templateValid() || this.saving()) {
      this.form.markAllAsTouched();
      return;
    }
    this.saving.set(true);
    const value = this.form.getRawValue();
    const settingsPayload: Settings = {
      window_days: value.window_days,
      household_size: value.household_size,
      repeat_gap_days: value.repeat_gap_days,
      language: value.language,
      balance_targets: this.targetsFrom(value),
    };
    const template: Template = {
      protein: value.protein_slots,
      vegetable: value.vegetable_slots,
      carb: value.carb_slots,
    };
    try {
      const updates = (Object.keys(PREFERENCE_CATEGORY_NAMES) as PreferenceKey[])
        .map((key) => {
          const category = this.preferenceCategories[key];
          if (!category) return null;
          return api.categories.update(category.id, {
            name: category.name,
            item_ids: category.item_ids,
            min_per_7_days: key === 'fish' ? value.fish_min : value.vegetarian_min,
          });
        })
        .filter((request): request is Promise<Category> => request !== null);
      await Promise.all([
        api.settings.update({
          ...settingsPayload,
          ...(value.usda_api_key.trim() ? { usda_api_key: value.usda_api_key.trim() } : {}),
        }),
        api.template.update(template),
        ...updates,
      ]);
      if (updates.length) await api.menu.replan();
      this.i18n.setLocale(value.language);
      this.messages.success(this.i18n.t('settings.saved'));
      this.form.controls.usda_api_key.setValue('');
      this.loadedLanguage = value.language;
      await this.load();
    } catch (error) {
      this.messages.error(error);
    } finally {
      this.saving.set(false);
    }
  }

  async retryLookups(): Promise<void> {
    try {
      await api.settings.retryLookups();
      this.messages.success(this.i18n.t('settings.retryCompleted'));
    } catch (error) {
      this.messages.error(error);
    }
  }

  private settingsFormValue(settings: Settings, template: Template): ReturnType<SettingsForm['getRawValue']> {
    return {
      window_days: settings.window_days,
      household_size: settings.household_size,
      repeat_gap_days: settings.repeat_gap_days,
      language: settings.language === 'nl' ? 'nl' : 'en',
      vegetables: settings.balance_targets.vegetables,
      protein: settings.balance_targets.protein,
      carbs: settings.balance_targets.carbs,
      tolerance: settings.balance_targets.tolerance,
      protein_slots: template.protein,
      vegetable_slots: template.vegetable,
      carb_slots: template.carb,
      fish_min: this.preferenceCategories.fish?.min_per_7_days ?? 0,
      vegetarian_min: this.preferenceCategories.vegetarian?.min_per_7_days ?? 0,
      usda_api_key: '',
    };
  }

  private targetsFrom(value: ReturnType<SettingsForm['getRawValue']>): BalanceTargets {
    return {
      vegetables: value.vegetables,
      protein: value.protein,
      carbs: value.carbs,
      tolerance: value.tolerance,
    };
  }

  private loadPreferenceCategories(categories: Category[]): void {
    for (const key of Object.keys(PREFERENCE_CATEGORY_NAMES) as PreferenceKey[]) {
      const names = PREFERENCE_CATEGORY_NAMES[key];
      this.preferenceCategories[key] =
        categories.find((category) => names.includes(category.name.toLowerCase())) ?? undefined;
    }
  }
}
