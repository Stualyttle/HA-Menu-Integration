import type {
  BalanceTargets,
  Category,
  CategoryInput,
  Dinner,
  ImportPreview,
  Item,
  ItemInput,
  MenuDay,
  NutritionInput,
  NutritionLookup,
  OnboardingInput,
  OnboardingStatus,
  Rule,
  RuleCheck,
  RuleInput,
  Settings,
  SettingsInput,
  Template,
  WarningRecord,
} from './types.js';

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;
}

export interface ApiClient {
  health(): Promise<{ status: string; version: string }>;
  sync(payload: { language: string; time_zone: string }): Promise<unknown>;
  menu: {
    list(from?: string, to?: string): Promise<MenuDay[]>;
    today(): Promise<MenuDay>;
    update(date: string, payload: { pinned?: boolean; dinner_id?: number }): Promise<MenuDay>;
    eaten(date: string): Promise<MenuDay>;
    swapSuggestions(date: string): Promise<Dinner[]>;
    swap(date: string, itemIds: number[]): Promise<MenuDay>;
    replan(): Promise<MenuDay[]>;
  };
  items: {
    list(filters?: Record<string, string | number | boolean | null | undefined>): Promise<Item[]>;
    get(itemId: number): Promise<Item>;
    create(payload: Partial<ItemInput>): Promise<Item>;
    update(itemId: number, payload: Partial<ItemInput>): Promise<Item>;
    remove(itemId: number): Promise<null>;
    lookupNutrition(itemId: number): Promise<NutritionLookup>;
    setNutrition(itemId: number, payload: NutritionInput): Promise<unknown>;
  };
  categories: {
    list(): Promise<Category[]>;
    get(categoryId: number): Promise<Category>;
    create(payload: CategoryInput): Promise<Category>;
    update(categoryId: number, payload: CategoryInput): Promise<Category>;
    remove(categoryId: number): Promise<null>;
  };
  rules: {
    list(): Promise<Rule[]>;
    create(payload: RuleInput): Promise<Rule>;
    update(ruleId: number, payload: Partial<RuleInput>): Promise<Rule>;
    remove(ruleId: number): Promise<null>;
    check(rule: RuleInput, ruleId?: number): Promise<RuleCheck>;
  };
  stock: {
    list(unansweredFirst?: boolean): Promise<Item[]>;
    set(itemId: number, inStock: boolean | null): Promise<unknown>;
    preview(itemId: number, inStock: boolean): Promise<{ item_id: number; in_stock: boolean; replaces_count: number }>;
  };
  settings: {
    get(): Promise<Settings>;
    update(payload: SettingsInput): Promise<Settings>;
    retryLookups(): Promise<{ retried_item_ids: number[] }>;
  };
  onboarding: {
    get(): Promise<OnboardingStatus>;
    complete(payload: OnboardingInput): Promise<{
      required: false;
      language: string;
      seeded: { ingredients: number; meals: number };
    }>;
  };
  template: {
    get(): Promise<Template>;
    update(payload: Template): Promise<Template>;
  };
  exportData(): Promise<Record<string, unknown>>;
  importPreview(document: Record<string, unknown>): Promise<ImportPreview>;
  importData(document: Record<string, unknown>, options?: {
    include_settings?: boolean;
    include_history?: boolean;
  }): Promise<ImportPreview>;
  warnings: {
    list(): Promise<WarningRecord[]>;
    resolve(warningId: number): Promise<null>;
  };
}

export function createApiClient(options?: {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
}): ApiClient;
