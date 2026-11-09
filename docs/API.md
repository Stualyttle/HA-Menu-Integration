# Menu Planner: API contract

Frozen interface between the add-on, the integration, and the frontend. Parallel agents (PLAN section 14) must not change it without a Log entry in [WORKFILE.md](WORKFILE.md) and an update here.

## Transport

| Listener | Port | Auth | Used by |
|---|---|---|---|
| Internal | 8098 (not published) | Header `X-Menu-Planner-Token` | Integration |
| Ingress | 8099 | None (Supervisor restricts to the ingress proxy) | Add-on panel |

- Base path: `/api`. All bodies are JSON (`application/json`, UTF-8).
- Dates are ISO 8601 `YYYY-MM-DD` in the local time zone sent by the integration on each sync (`time_zone`, IANA name).
- Errors: `{"error": {"code": "<snake_case>", "message": "<human text>", "details": {}}}` with HTTP 400 (request or config validation, including an all-zero template), 404, 409 (conflict, e.g. duplicate name, or a day that cannot be edited, or a rejected swap), 500.
- Auth failure (401) is the exception to the envelope: `{"detail": "invalid or missing token"}` (internal listener only).
- 422 is not used. Request validation failures return 400 (`validation_error`); `POST /api/rules/check` returns 200 with `feasible: false` instead of an error.
- List endpoints return a bare JSON array, not a wrapper object.
- Language: responses carry no UI text except `message`. Warning and status codes are stable identifiers, translated by the client.

Status column: **Implemented** means the route exists in `addon/app/api/` and has tests. The panel (`frontend/shared/api/client.js`) uses these same routes; it does not substitute local mock results.

## Health and sync

| Method | Path | Purpose | Response | Status |
|---|---|---|---|---|
| GET | `/api/health` | Liveness and version | `{status: "ok", version}` | Implemented |
| POST | `/api/sync` | Integration sends HA language and time zone each poll. Body `{language, time_zone}` | `{language, time_zone, timezone_mismatch: bool}` | Implemented |

## Menu

| Method | Path | Purpose | Status |
|---|---|---|---|
| GET | `/api/menu?from=&to=` | Bare array of days in the window (default today plus `window_days - 1`) | Implemented |
| GET | `/api/menu/today` | Today's day (single object, not an array) | Implemented |
| POST | `/api/menu/replan` | Regenerate planned days (pinned, eaten, and past days are kept). Returns the window as a bare array | Implemented |
| PUT | `/api/menu/{date}` | Body `{pinned: bool}` (exactly one of `pinned` or `dinner_id`). `pinned` pins or unpins (future days only). `dinner_id` applies a swap (see below) | Implemented |
| POST | `/api/menu/{date}/eaten` | Mark eaten (never changes stock). Not allowed for future dates | Implemented |
| GET | `/api/menu/{date}/swap` | Bare array of up to three `DinnerOut` suggestions that satisfy all hard rules. Today (until eaten) and future days in the window | Implemented |
| POST | `/api/menu/{date}/swap` | Body `{item_ids: [int, ...]}` for a suggestion, or `{dinner_id}` for a persisted dinner. Applies and persists only the selected dinner. Today (until eaten) and future days in the window. Returns the day | Implemented |

Day object (`MenuDayOut`): `{date, status: planned|pinned|eaten|empty, dinner: {id, items: [{id, name, type}]} | null, kcal, balance, replaced_reason}`. `kcal` is `null` when a component lacks verified nutrition. `balance` is `ok`, `off_target`, or `unknown`. Swap suggestions return the same dinner shape; `id` is `null` for a generated dinner that is not yet stored. Use its item IDs in the `item_ids` request body rather than treating that null ID as a database reference.

Generated candidate dinners are transient while reading or checking rules. A planner write stores only the candidate dinners selected for the resulting plan. Fetching swap suggestions does not write candidates; applying a suggestion identifies it by its item IDs and persists it as part of the swap.

Errors: a date outside the window or a past date in a swap or PUT returns 409 (`day_not_editable`). An eaten day cannot be pinned or swapped. A dinner that fails hard rules returns 409 (`swap_rejected`).

## Items, categories, rules

| Method | Path | Purpose | Status |
|---|---|---|---|
| GET / POST | `/api/items` | List (filters: `type`, `category_id`, `verified`, `track_stock`, `q`) / create (`ItemIn`) | Implemented |
| GET / PUT / DELETE | `/api/items/{id}` | Read / update / delete | Implemented |
| GET | `/api/items/{id}/nutrition/lookup` | Open Food Facts and USDA lookup (synchronous). Returns `{item_id, candidates: [{source, external_id, matched_name, score, kcal, protein_g, carbs_g, fat_g, fiber_g}], failed_sources: [source]}` | Implemented |
| PUT | `/api/items/{id}/nutrition` | Body `{source: manual|open_food_facts|usda, external_id?, matched_name?, kcal?, protein_g?, carbs_g?, fat_g?, fiber_g?}`. Manual entry or confirm a candidate. Returns `NutritionOut` | Implemented |
| POST | `/api/items/nutrition/retry` | Immediately retries lookup for every item with an open `nutrition_failed` warning. Returns `{retried_item_ids}` | Implemented |
| GET / POST | `/api/categories` | List / create (`CategoryIn`: `name`, `min_per_7_days` 0–7, `item_ids`) | Implemented |
| GET / PUT / DELETE | `/api/categories/{id}` | Read / update / delete | Implemented |
| GET / POST | `/api/rules` | List / create (`RuleIn`: `kind: blacklist|whitelist`, `scope: combination|item`, `category_ids`, `item_id`, `enabled`) | Implemented |
| PUT / DELETE | `/api/rules/{id}` | Update / delete | Implemented |
| POST | `/api/rules/check` | Feasibility check without saving. Body `{rule: RuleIn, rule_id?: int}`. Returns `{feasible, exhausted, affected_days, locked_conflicts}` | Implemented |

Item object (`ItemOut`): `{id, name, type: protein|vegetable|carb, portion_grams, fat_source, track_stock, category_ids, nutrition: {source, status, kcal, protein_g, carbs_g, fat_g, fiber_g, user_confirmed} | null}`.

Category object (`CategoryOut`): `{id, name, is_starter, min_per_7_days, item_count, item_ids}`.

Rule object (`RuleOut`): `{id, kind, scope, category_ids, item_id, enabled}`.

## Stock

| Method | Path | Purpose | Status |
|---|---|---|---|
| GET | `/api/stock?unanswered_first=true` | Items with `track_stock` set, with `in_stock` (`true|false|null`) and `replaces_count` | Implemented |
| PUT | `/api/stock/{item_id}` | Body `{in_stock: bool|null}`. Response: `{item_id, in_stock, replaced_dates, restored_dates, shopping}`. Replaced and restored dates reflect the real engine diff. `shopping` is a placeholder (shopping list is deferred, PLAN section 11) | Implemented
| POST | `/api/stock/{item_id}/preview` | `{in_stock: bool}` returns `{item_id, in_stock, replaces_count}` before saving | Implemented |

## Settings and template

| Method | Path | Purpose | Status |
|---|---|---|---|
| GET / PUT | `/api/settings` | Read `SettingsOut`: `window_days`, `household_size`, `repeat_gap_days`, `balance_targets`, `language`. Update takes `SettingsIn` (all fields optional). `usda_api_key` is write-only and never returned. | Implemented |
| GET / PUT | `/api/template` | Body `{protein, vegetable, carb}`, each 0–2. An all-zero template returns 400. | Implemented |

`balance_targets` is `{vegetables, protein, carbs, tolerance}`, each 0–100. The three targets must sum to 100 (checked in the domain layer).

## Import and export

| Method | Path | Purpose | Status |
|---|---|---|---|
| GET | `/api/export` | Export file (`schema_version: 1`, names not IDs, secrets excluded) | Implemented |
| POST | `/api/import/preview` | Body is the export document. Validates and returns `{added, skipped, settings_available}`. Writes nothing | Implemented |
| POST | `/api/import` | Body `{document, include_settings: bool, include_history: bool}`. Merges and returns `{added, skipped, settings_available}`. `include_history: true` returns 400 (history is not part of export v1) | Implemented |

## Warnings

| Method | Path | Purpose | Status |
|---|---|---|---|
| GET | `/api/warnings` | Unresolved warnings (bare array) | Implemented |
| POST | `/api/warnings/{id}/resolve` | Mark resolved. Returns 204. | Implemented |

Warning object (`WarningOut`): `{id, code, subject: {type: date|item|category, id: string}, payload, created_at}`.

Warning codes (stable):

| Code | Meaning |
|---|---|
| `replaced_dinner` | A dinner was replaced by a stock change |
| `missed_minimum` | A category minimum is not met in a rolling 7-day span |
| `repeat_gap_unavoidable` | The repeat gap could not be honoured |
| `empty_day` | No valid dinner exists for a day |
| `minimum_infeasible` | A minimum cannot be met with the current items and rules |
| `nutrition_failed` | A nutrition lookup failed; the item stays unverified |
| `timezone_mismatch` | The add-on time zone differs from the HA time zone |

## Integration contract (not HTTP)

The integration serves the built Lovelace bundle at `/menu_planner/menu-planner-cards.js` and registers it with Home Assistant's frontend automatically. The cards use websocket commands; they do not call the add-on directly.

| Websocket command | Request fields | Add-on operation |
|---|---|---|
| `menu_planner/today` | none | `GET /api/menu/today` |
| `menu_planner/window` | optional `from`, `to` | `GET /api/menu` |
| `menu_planner/stock` | optional `unanswered_first` (default `true`) | `GET /api/stock` |
| `menu_planner/stock/set` | `item_id`, optional `in_stock` | `PUT /api/stock/{item_id}` |
| `menu_planner/stock/preview` | `item_id`, `in_stock` | `POST /api/stock/{item_id}/preview` |
| `menu_planner/eaten` | `date` | `POST /api/menu/{date}/eaten` |
| `menu_planner/swap/suggestions` | `date` | `GET /api/menu/{date}/swap` |
| `menu_planner/swap/apply` | `date` and exactly one of `dinner_id` or `item_ids` | `POST /api/menu/{date}/swap` |

Services (`menu_planner.log_eaten`, `menu_planner.set_stock`, `menu_planner.swap_today`) remain available to automations. They proxy to the add-on and refresh the integration coordinator after writes.
