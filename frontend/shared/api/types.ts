export type ItemType = 'protein' | 'vegetable' | 'carb';
export type Locale = 'en' | 'nl';

export interface Nutrition {
  source: string;
  status: 'ok' | 'not_found' | 'error' | string;
  kcal: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  fiber_g: number | null;
  user_confirmed: boolean;
}

export interface Item {
  id: number;
  name: string;
  type: ItemType;
  portion_grams: number | null;
  fat_source: boolean;
  track_stock: boolean;
  is_complete_meal: boolean;
  category_ids: number[];
  nutrition: Nutrition | null;
  in_stock?: boolean | null;
  replaces_count?: number;
}

export interface ItemInput {
  name: string;
  type: ItemType;
  portion_grams: number | null;
  fat_source: boolean;
  track_stock: boolean;
  is_complete_meal: boolean;
  category_ids: number[];
}

export interface NutritionInput {
  source: 'manual' | 'open_food_facts' | 'usda';
  external_id?: string;
  matched_name?: string;
  kcal: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  fiber_g: number | null;
}

export interface NutritionCandidate {
  source: 'open_food_facts' | 'usda';
  external_id: string;
  matched_name: string;
  score: number;
  kcal: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  fiber_g: number | null;
}

export interface NutritionLookup {
  item_id: number;
  candidates: NutritionCandidate[];
  failed_sources: string[];
}

export interface Category {
  id: number;
  name: string;
  is_starter: boolean;
  min_per_7_days: number;
  item_count: number;
  item_ids: number[];
}

export interface CategoryInput {
  name: string;
  min_per_7_days?: number;
  item_ids?: number[];
}

export interface Rule {
  id: number;
  kind: 'blacklist' | 'whitelist';
  scope: 'combination' | 'item';
  category_ids: number[];
  item_id: number | null;
  enabled: boolean;
}

export interface RuleInput {
  kind: Rule['kind'];
  scope: Rule['scope'];
  category_ids: number[];
  item_id?: number;
  enabled: boolean;
}

export interface RuleCheck {
  feasible: boolean;
  exhausted: boolean;
  affected_days: string[];
  locked_conflicts: string[];
}

export interface DinnerItem {
  id: number;
  name: string;
  type: ItemType;
  is_complete_meal: boolean;
}

export interface Dinner {
  id: number | null;
  items: DinnerItem[];
}

export interface MenuDay {
  date: string;
  status: 'planned' | 'pinned' | 'eaten' | 'empty';
  dinner: Dinner | null;
  kcal: number | null;
  balance: 'ok' | 'off_target' | 'unknown';
  replaced_reason: string | null;
  warnings: string[];
}

export interface WarningRecord {
  id: number;
  code: string;
  subject: { type: string; id: string };
  payload: Record<string, unknown>;
  created_at: string | null;
}

export interface BalanceTargets {
  vegetables: number;
  protein: number;
  carbs: number;
  tolerance: number;
}

export interface Settings {
  window_days: number;
  household_size: number;
  repeat_gap_days: number;
  balance_targets: BalanceTargets;
  language: 'auto' | Locale;
}

export interface SettingsInput {
  window_days?: number;
  household_size?: number;
  repeat_gap_days?: number;
  balance_targets?: BalanceTargets;
  language?: 'auto' | Locale;
  usda_api_key?: string;
}

export interface Template {
  protein: number;
  vegetable: number;
  carb: number;
}

export interface StarterPack {
  language: Locale;
  language_name: string;
  ingredient_count: number;
  meal_count: number;
  ingredients: string[];
  meals: string[];
  ingredient_categories: string[];
  meal_categories: string[];
}

export interface OnboardingStatus {
  required: boolean;
  packs: Record<Locale, StarterPack>;
}

export interface OnboardingInput {
  language: Locale;
  seed_ingredients: boolean;
  seed_meals: boolean;
  window_days: number;
  household_size: number;
  repeat_gap_days: number;
  balance_targets: BalanceTargets;
  template: Template;
  fish_min_per_7_days: number;
  vegetarian_min_per_7_days: number;
}

export interface ImportPreview {
  added: Record<string, number>;
  skipped: Record<string, number>;
  settings_available: boolean;
}
