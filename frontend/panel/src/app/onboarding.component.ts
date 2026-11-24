import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, output, signal } from '@angular/core';
import { FormControl, FormGroup, NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { MatSliderModule } from '@angular/material/slider';
import { MatStepperModule } from '@angular/material/stepper';
import { api } from '../../../shared/api/instance.js';
import type {
  BalanceTargets,
  Locale,
  OnboardingInput,
  OnboardingStatus,
  Settings,
  Template,
} from '../../../shared/api/types';
import { I18nService } from './i18n.service';
import { MessageService } from './message.service';

type OnboardingForm = FormGroup<{
  language: FormControl<Locale>;
  seed_ingredients: FormControl<boolean>;
  seed_meals: FormControl<boolean>;
  window_days: FormControl<number>;
  household_size: FormControl<number>;
  repeat_gap_days: FormControl<number>;
  vegetables: FormControl<number>;
  protein: FormControl<number>;
  carbs: FormControl<number>;
  tolerance: FormControl<number>;
  fish_min_per_7_days: FormControl<number>;
  vegetarian_min_per_7_days: FormControl<number>;
  protein_slots: FormControl<number>;
  vegetable_slots: FormControl<number>;
  carb_slots: FormControl<number>;
}>;

@Component({
  selector: 'mp-onboarding',
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatCardModule,
    MatCheckboxModule,
    MatExpansionModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressSpinnerModule,
    MatSelectModule,
    MatSliderModule,
    MatStepperModule,
    ReactiveFormsModule,
  ],
  template: `
    @if (loading()) {
      <mat-card>
        <mat-card-content><mat-spinner diameter="32" /> {{ i18n.t('common.loading') }}</mat-card-content>
      </mat-card>
    } @else if (loadError()) {
      <mat-card>
        <mat-card-header><mat-card-title>{{ i18n.t('app.loadFailed') }}</mat-card-title></mat-card-header>
        <mat-card-actions>
          <button mat-flat-button type="button" (click)="load()">{{ i18n.t('app.retry') }}</button>
        </mat-card-actions>
      </mat-card>
    } @else if (pack()) {
      <form [formGroup]="form">
        <mat-card>
          <mat-card-header>
            <mat-card-title>{{ i18n.t('app.title') }}</mat-card-title>
            <mat-card-subtitle>{{ i18n.t('onboarding.brandSubtitle') }}</mat-card-subtitle>
          </mat-card-header>
          <mat-card-content>
            <mat-horizontal-stepper [linear]="false">
              <mat-step>
                <ng-template matStepLabel>{{ i18n.t('onboarding.language.title') }}</ng-template>
                <h2>{{ i18n.t('onboarding.language.title') }}</h2>
                <p>{{ i18n.t('onboarding.language.help') }}</p>
                <mat-form-field appearance="outline">
                  <mat-label>{{ i18n.t('settings.language') }}</mat-label>
                  <mat-select formControlName="language" (selectionChange)="applyLocale($event.value)">
                    <mat-option value="en">{{ i18n.t('settings.language.en') }}</mat-option>
                    <mat-option value="nl">{{ i18n.t('settings.language.nl') }}</mat-option>
                  </mat-select>
                </mat-form-field>
                <p>{{ i18n.t('onboarding.language.persist') }}</p>
                <button mat-flat-button type="button" matStepperNext>
                  {{ i18n.t('common.continue') }}
                </button>
              </mat-step>

              <mat-step>
                <ng-template matStepLabel>{{ i18n.t('onboarding.starter.title') }}</ng-template>
                <h2>{{ i18n.t('onboarding.starter.title') }}</h2>
                <p>
                  {{ i18n.t('onboarding.starter.help', {
                    language: i18n.t('onboarding.contentLanguage.' + form.controls.language.value)
                  }) }}
                </p>
                <mat-checkbox formControlName="seed_ingredients">
                  {{ i18n.t('onboarding.starter.ingredients') }} ({{ pack()!.ingredient_count }})
                </mat-checkbox>
                <p>{{ i18n.t('onboarding.starter.ingredientsHelp') }}</p>
                @if (form.controls.seed_ingredients.value) {
                  <mat-expansion-panel>
                    <mat-expansion-panel-header>
                      <mat-panel-title>{{ i18n.t('onboarding.starter.preview') }}</mat-panel-title>
                    </mat-expansion-panel-header>
                    <p>{{ pack()!.ingredients.join(' · ') }}</p>
                    <p>{{ pack()!.ingredient_categories.join(' · ') }}</p>
                  </mat-expansion-panel>
                }
                <mat-checkbox formControlName="seed_meals">
                  {{ i18n.t('onboarding.starter.meals') }} ({{ pack()!.meal_count }})
                </mat-checkbox>
                <p>{{ i18n.t('onboarding.starter.mealsHelp') }}</p>
                @if (form.controls.seed_meals.value) {
                  <mat-expansion-panel>
                    <mat-expansion-panel-header>
                      <mat-panel-title>{{ i18n.t('onboarding.starter.preview') }}</mat-panel-title>
                    </mat-expansion-panel-header>
                    <p>{{ pack()!.meals.join(' · ') }}</p>
                    <p>{{ pack()!.meal_categories.join(' · ') }}</p>
                  </mat-expansion-panel>
                }
                @if (!hasStarterContent()) {
                  <p>{{ i18n.t('onboarding.starter.emptySelection') }}</p>
                }
                <button mat-button type="button" (click)="startEmpty()">
                  {{ i18n.t('onboarding.starter.noSeed') }}
                </button>
                <button mat-button type="button" matStepperPrevious>
                  {{ i18n.t('common.back') }}
                </button>
                <button mat-flat-button type="button" matStepperNext>
                  {{ i18n.t('common.continue') }}
                </button>
              </mat-step>

              <mat-step>
                <ng-template matStepLabel>{{ i18n.t('onboarding.preferences.title') }}</ng-template>
                <h2>{{ i18n.t('onboarding.preferences.title') }}</h2>
                <p>{{ i18n.t('onboarding.preferences.help') }}</p>
                <mat-form-field appearance="outline">
                  <mat-label>{{ i18n.t('settings.window.label') }}</mat-label>
                  <input matInput type="number" min="7" max="60" formControlName="window_days" />
                </mat-form-field>
                <mat-slider min="7" max="60" step="1" discrete>
                  <input matSliderThumb formControlName="window_days" />
                </mat-slider>

                <mat-form-field appearance="outline">
                  <mat-label>{{ i18n.t('settings.household.size') }}</mat-label>
                  <input matInput type="number" min="1" max="10" formControlName="household_size" />
                </mat-form-field>
                <mat-form-field appearance="outline">
                  <mat-label>{{ i18n.t('settings.household.gap') }}</mat-label>
                  <input matInput type="number" min="0" max="60" formControlName="repeat_gap_days" />
                </mat-form-field>

                @if (hasStarterContent()) {
                  <mat-form-field appearance="outline">
                    <mat-label>{{ i18n.t('onboarding.preferences.fish') }}</mat-label>
                    <input matInput type="number" min="0" max="7" formControlName="fish_min_per_7_days" />
                  </mat-form-field>
                  <mat-form-field appearance="outline">
                    <mat-label>{{ i18n.t('onboarding.preferences.vegetarian') }}</mat-label>
                    <input matInput type="number" min="0" max="7" formControlName="vegetarian_min_per_7_days" />
                  </mat-form-field>
                } @else {
                  <p>{{ i18n.t('onboarding.preferences.noSeedHelp') }}</p>
                }

                <h3>{{ i18n.t('settings.template.title') }}</h3>
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

                <h3>{{ i18n.t('settings.balance.title') }}</h3>
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
                <button mat-button type="button" matStepperPrevious>
                  {{ i18n.t('common.back') }}
                </button>
                <button
                  mat-flat-button
                  type="button"
                  [disabled]="saving() || form.invalid || targetSum() !== 100 || !templateValid()"
                  (click)="finish()"
                >
                  {{ saving() ? i18n.t('common.saving') : i18n.t('onboarding.finish') }}
                </button>
              </mat-step>
            </mat-horizontal-stepper>
          </mat-card-content>
        </mat-card>
      </form>
    }
  `,
})
export class OnboardingComponent implements OnInit {
  readonly completed = output<void>();
  readonly i18n = inject(I18nService);
  private readonly messages = inject(MessageService);
  private readonly fb = inject(NonNullableFormBuilder);
  readonly loading = signal(true);
  readonly loadError = signal(false);
  readonly saving = signal(false);
  readonly setup = signal<OnboardingStatus | null>(null);
  readonly form: OnboardingForm = this.fb.group({
    language: this.fb.control<Locale>('en'),
    seed_ingredients: this.fb.control(true),
    seed_meals: this.fb.control(true),
    window_days: this.fb.control(14, [Validators.min(7), Validators.max(60)]),
    household_size: this.fb.control(2, [Validators.min(1), Validators.max(10)]),
    repeat_gap_days: this.fb.control(14, [Validators.min(0), Validators.max(60)]),
    vegetables: this.fb.control(50, [Validators.min(0), Validators.max(100)]),
    protein: this.fb.control(25, [Validators.min(0), Validators.max(100)]),
    carbs: this.fb.control(25, [Validators.min(0), Validators.max(100)]),
    tolerance: this.fb.control(10, [Validators.min(0), Validators.max(100)]),
    fish_min_per_7_days: this.fb.control(1, [Validators.min(0), Validators.max(7)]),
    vegetarian_min_per_7_days: this.fb.control(2, [Validators.min(0), Validators.max(7)]),
    protein_slots: this.fb.control(1, [Validators.min(0), Validators.max(2)]),
    vegetable_slots: this.fb.control(1, [Validators.min(0), Validators.max(2)]),
    carb_slots: this.fb.control(1, [Validators.min(0), Validators.max(2)]),
  });

  ngOnInit(): void {
    void this.load();
  }

  pack() {
    return this.setup()?.packs[this.form.controls.language.value];
  }

  hasStarterContent(): boolean {
    const value = this.form.getRawValue();
    return value.seed_ingredients || value.seed_meals;
  }

  targetSum(): number {
    const value = this.form.getRawValue();
    return value.vegetables + value.protein + value.carbs;
  }

  templateValid(): boolean {
    const value = this.form.getRawValue();
    return value.protein_slots + value.vegetable_slots + value.carb_slots > 0;
  }

  applyLocale(locale: Locale): void {
    this.i18n.setLocale(locale);
  }

  startEmpty(): void {
    this.form.patchValue({
      seed_ingredients: false,
      seed_meals: false,
      fish_min_per_7_days: 0,
      vegetarian_min_per_7_days: 0,
    });
  }

  async finish(): Promise<void> {
    if (this.saving() || this.form.invalid || this.targetSum() !== 100 || !this.templateValid()) {
      this.form.markAllAsTouched();
      return;
    }
    this.saving.set(true);
    const value = this.form.getRawValue();
    const payload: OnboardingInput = {
      language: value.language,
      seed_ingredients: value.seed_ingredients,
      seed_meals: value.seed_meals,
      window_days: value.window_days,
      household_size: value.household_size,
      repeat_gap_days: value.repeat_gap_days,
      balance_targets: this.targets(value),
      template: {
        protein: value.protein_slots,
        vegetable: value.vegetable_slots,
        carb: value.carb_slots,
      },
      fish_min_per_7_days: this.hasStarterContent() ? value.fish_min_per_7_days : 0,
      vegetarian_min_per_7_days: this.hasStarterContent() ? value.vegetarian_min_per_7_days : 0,
    };
    try {
      const result = await api.onboarding.complete(payload);
      if (result.seeded.ingredients || result.seeded.meals) await api.menu.replan();
      this.completed.emit();
    } catch (error) {
      this.messages.error(error);
    } finally {
      this.saving.set(false);
    }
  }

  async load(): Promise<void> {
    this.loading.set(true);
    try {
      const [settings, template, setup] = await Promise.all([
        api.settings.get(),
        api.template.get(),
        api.onboarding.get(),
      ]);
      this.loadError.set(false);
      this.setup.set(setup);
      const language = this.initialLanguage(settings);
      this.i18n.setLocale(language);
      this.form.reset(this.formValue(settings, template, language));
    } catch (error) {
      this.loadError.set(true);
      this.messages.error(error);
    } finally {
      this.loading.set(false);
    }
  }

  private initialLanguage(settings: Settings): Locale {
    if (settings.language === 'en' || settings.language === 'nl') return settings.language;
    return navigator.language.toLowerCase().startsWith('nl') ? 'nl' : 'en';
  }

  private formValue(
    settings: Settings,
    template: Template,
    language: Locale,
  ): ReturnType<OnboardingForm['getRawValue']> {
    const targets = settings.balance_targets;
    return {
      language,
      seed_ingredients: true,
      seed_meals: true,
      window_days: settings.window_days,
      household_size: settings.household_size,
      repeat_gap_days: settings.repeat_gap_days,
      vegetables: targets.vegetables,
      protein: targets.protein,
      carbs: targets.carbs,
      tolerance: targets.tolerance,
      fish_min_per_7_days: 1,
      vegetarian_min_per_7_days: 2,
      protein_slots: template.protein,
      vegetable_slots: template.vegetable,
      carb_slots: template.carb,
    };
  }

  private targets(value: ReturnType<OnboardingForm['getRawValue']>): BalanceTargets {
    return {
      vegetables: value.vegetables,
      protein: value.protein,
      carbs: value.carbs,
      tolerance: value.tolerance,
    };
  }
}
