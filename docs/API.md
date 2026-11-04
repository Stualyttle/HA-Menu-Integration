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
- 422 is reserved for the planned rules check (see below). No route raises it yet.
- List endpoints return a bare JSON array, not a wrapper object.
- Language: responses carry no UI text except `message`. Warning and status codes are stable identifiers, translated by the client.

Status column: **Implemented** means the route exists in `addon/app/api/` and has tests. **Planned** means the route is not implemented yet. The panel (`frontend/shared/api/client.js`) calls some planned routes, so those calls fail until they land.

## Health and sync

| Method | Path | Purpose | Response | Status |
|---|---|---|---|---|
| GET | `/api/health` | Liveness and version | `{status: "ok", version}` | Implemented |
| POST | `/api/sync` | Integration sends HA language and time zone each poll | `{language, time_zone, timezone_mismatch: bool}` | Planned |

## Menu

Planned. No menu router exists yet.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/menu?from=&to=` | Days in the window (default today plus `window_days - 1`) |
| GET | `/api/menu/today` | Today's day with dinner components, kcal (or `null`), balance (`ok`, `off_target`, `unknown`), status |
| PUT | `/api/menu/{date}` | Pin, unpin, or set a dinner (future days only) |
| POST | `/api/menu/{date}/eaten` | Mark eaten (never changes stock) |
| GET | `/api/menu/{date}/swap` | Three suggestions that satisfy all hard rules |
| POST | `/api/menu/{date}/swap` | Apply a suggestion (`dinner_id`) |

Day object: `{date, status: planned|pinned|eaten|empty, dinner: {id, items: [{id, name, type}]} | null, kcal, balance, replaced_reason, warnings: [code]}`.

## Items, categories, rules

| Method | Path | Purpose | Status |
|---|---|---|---|
| GET / POST | `/api/items` | List (filters: `type`, `category_id`, `verified`, `track_stock`, `q`) / create (`ItemIn`) | Implemented |
| GET / PUT / DELETE | `/api/items/{id}` | Read / update / delete | Implemented |
| POST | `/api/items/{id}/nutrition/lookup` | Start an Open Food Facts or USDA lookup | Planned |
| PUT | `/api/items/{id}/nutrition` | Manual entry or confirm a match | Planned |
| GET / POST | `/api/categories` | List / create (`CategoryIn`: `name`, `min_per_7_days` 0–7, `item_ids`) | Implemented |
| GET / PUT / DELETE | `/api/categories/{id}` | Read / update / delete | Implemented |
| GET / POST | `/api/rules` | List / create (`RuleIn`: `kind: blacklist|whitelist`, `scope: combination|item`, `category_ids`, `item_id`, `enabled`) | Implemented |
| PUT / DELETE | `/api/rules/{id}` | Update / delete | Implemented |
| POST | `/api/rules/check` | Feasibility check without saving; returns `{feasible, affected_days}` | Planned |

Item object (`ItemOut`): `{id, name, type: protein|vegetable|carb, portion_grams, fat_source, track_stock, category_ids, nutrition: {source, status, kcal, protein_g, carbs_g, fat_g, fiber_g, user_confirmed} | null}`.

Category object (`CategoryOut`): `{id, name, is_starter, min_per_7_days, item_count, item_ids}`.

Rule object (`RuleOut`): `{id, kind, scope, category_ids, item_id, enabled}`.

## Stock

| Method | Path | Purpose | Status |
|---|---|---|---|
| GET | `/api/stock?unanswered_first=true` | Items with `track_stock` set, with `in_stock` (`true|false|null`) and `replaces_count` | Implemented |
| PUT | `/api/stock/{item_id}` | Body `{in_stock: bool|null}`. Response: `{item_id, in_stock, replaced_dates, restored_dates, shopping}` | Implemented (side effects are placeholders until the menu engine is wired) |
| POST | `/api/stock/{item_id}/preview` | `{in_stock: bool}` returns `{item_id, in_stock, replaces_count}` before saving | Implemented |

## Settings and template

| Method | Path | Purpose | Status |
|---|---|---|---|
| GET / PUT | `/api/settings` | Read `SettingsOut`: `window_days`, `household_size`, `repeat_gap_days`, `balance_targets`, `language`. Update takes `SettingsIn` (all fields optional). `usda_api_key` is write-only and never returned. | Implemented |
| GET / PUT | `/api/template` | Body `{protein, vegetable, carb}`, each 0–2. An all-zero template returns 400. | Implemented |

`balance_targets` is `{vegetables, protein, carbs, tolerance}`, each 0–100. The three targets must sum to 100 (checked in the domain layer).

## Import and export

Planned. No io router exists yet. The domain-level export and import code is in `addon/app/io/`.

| Method | Path | Purpose | Status |
|---|---|---|---|
| GET | `/api/export` | Export file (`schema_version: 1`, names not IDs, secrets excluded) | Planned |
| POST | `/api/import/preview` | Validate and return `{added, skipped, settings_available}` | Planned |
| POST | `/api/import` | Merge; body includes `include_settings`, `include_history` | Planned |

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

Websocket commands (`menu_planner/...`) and services (`menu_planner.log_eaten`, `menu_planner.set_stock`, `menu_planner.swap_today`) are defined in PLAN section 10 and implemented by agent D. They proxy to the add-on endpoints above and do not add behaviour.
