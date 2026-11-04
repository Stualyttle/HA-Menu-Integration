# Menu Planner: API contract

Frozen interface between the add-on, the integration, and the frontend. Parallel agents (PLAN section 14) must not change it without a Log entry in [WORKFILE.md](WORKFILE.md) and an update here.

## Transport

| Listener | Port | Auth | Used by |
|---|---|---|---|
| Internal | 8098 (not published) | Header `X-Menu-Planner-Token` | Integration |
| Ingress | 8099 | None (Supervisor restricts to the ingress proxy) | Add-on panel |

- Base path: `/api`. All bodies are JSON (`application/json`, UTF-8).
- Dates are ISO 8601 `YYYY-MM-DD` in the local time zone sent by the integration on each sync (`time_zone`, IANA name).
- Errors: `{"error": {"code": "<snake_case>", "message": "<human text>", "details": {}}}` with HTTP 400 (validation), 401 (token), 404, 409 (conflict, e.g. duplicate name), 422 (infeasible rule), 500.
- Language: responses carry no UI text except `message`. Warning and status codes are stable identifiers, translated by the client.

## Health and sync

| Method | Path | Purpose | Response |
|---|---|---|---|
| GET | `/api/health` | Liveness and version | `{status: "ok", version}` |
| POST | `/api/sync` | Integration sends HA language and time zone each poll | `{language, time_zone, timezone_mismatch: bool}` |

## Menu

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

| Method | Path | Purpose |
|---|---|---|
| GET / POST | `/api/items` | List (filters: `type`, `category_id`, `verified`, `track_stock`, `q`) / create |
| GET / PUT / DELETE | `/api/items/{id}` | Read / update / delete |
| POST | `/api/items/{id}/nutrition/lookup` | Start an Open Food Facts or USDA lookup |
| PUT | `/api/items/{id}/nutrition` | Manual entry or confirm a match |
| GET / POST | `/api/categories` | List (with `min_per_7_days`, `item_count`) / create |
| GET / PUT / DELETE | `/api/categories/{id}` | Read / update / delete |
| GET / POST | `/api/rules` | List / create (`kind: blacklist|whitelist`, `scope: combination|item`, `category_ids`, `item_id`, `enabled`) |
| PUT / DELETE | `/api/rules/{id}` | Update / delete |
| POST | `/api/rules/check` | Feasibility check without saving; returns `{feasible, affected_days}` |

Item object: `{id, name, type: protein|vegetable|carb, portion_grams, fat_source, track_stock, category_ids, nutrition: {source, status, kcal, protein_g, carbs_g, fat_g, fiber_g, user_confirmed} | null}`.

## Stock

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/stock?unanswered_first=true` | Distinct items in the window with `in_stock` (`true|false|null`) and `replaces_count` |
| PUT | `/api/stock/{item_id}` | Set `in_stock`. Response includes `replaced_dates`, `restored_dates`, `shopping` changes |
| POST | `/api/stock/{item_id}/preview` | `{in_stock: false}` returns `replaces_count` before saving |

## Settings, import, export

| Method | Path | Purpose |
|---|---|---|
| GET / PUT | `/api/settings` | Read / update: `window_days` (7–60), `household_size`, `repeat_gap_days`, `balance_targets`, `language` (`auto|en|nl`), `usda_api_key` (write-only, never returned) |
| GET / PUT | `/api/template` | Slot counts per type (0–2 each) |
| GET | `/api/export` | Export file (`schema_version: 1`, names not IDs, secrets excluded) |
| POST | `/api/import/preview` | Validate and return `{added, skipped, settings_available}` |
| POST | `/api/import` | Merge; body includes `include_settings`, `include_history` |

## Warnings

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/warnings` | Unresolved warnings |
| POST | `/api/warnings/{id}/resolve` | Mark resolved |

Warning object: `{id, code, subject: {type: date|item|category, id}, payload, created_at}`.

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
