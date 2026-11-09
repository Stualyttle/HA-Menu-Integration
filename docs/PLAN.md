# Menu Planner: Implementation Plan

Working name: **Menu Planner** (integration domain `menu_planner`, add-on slug `menu_planner`).
Progress tracking: `docs/WORKFILE.md`. Mockups: `docs/mockups/`.
Last updated: 2026-11-04.

Items marked **(proposal)** are implementation choices not yet confirmed by the user. Items marked **(assumed)** are interpretations to check in review (see section 15).

## 1. Goal

A Home Assistant integration (HACS) plus an add-on that:

1. Plans a healthy dinner for every day in a rolling window (default 14 days: today plus 13). Days roll forward at local midnight.
2. Tracks yes/no stock per item and re-plans dinners that use a missing item.
3. Shows three Lovelace cards: today's dinner, stock check, and the window menu.
4. Gives the add-on dashboard full control: items, categories, black and white lists, category minimums, settings, and JSON import/export.
5. Looks and behaves like native Home Assistant (HA theme variables, Material 3 style).

## 2. Scope

In v1:

- Dinners only: a dinner is a set of items. The template gives per-type counts from 0 to 2 (protein, vegetable, carb) and is editable. A dinner is valid when its per-type counts equal the template, and it cannot be empty.
- Items with categories, portions, nutrition (verified or unverified), and stock tracking.
- Hard blacklist; soft whitelist; soft category minimums; repeat gap; plate balance.
- English and Dutch UI (follows HA language, English fallback).
- Nutrition lookup with manual fallback, starter content, JSON export and import.

Out of scope (v1): breakfast and lunch, allergies and diets, stock quantities, ingredient lists and recipes per item, multiple user accounts or per-user permissions, cloud sync, grocery prices.

## 3. Glossary

| Term | Meaning |
|---|---|
| Add-on | The server app (FastAPI + SQLite) with the full dashboard. User-facing text says "Add-on". |
| Integration | The HA component (`custom_components/menu_planner`): card data, sensors, services, notifications. |
| Item | A food with one type: protein, vegetable, or carb. Ordinary items are dinner components; an item can instead be marked as a complete meal and planned standalone. Stock is per item, not a recipe ingredient. |
| Category | A label on items (for example fish, Asian). An item can have several. |
| Dinner | A set of items (no duplicate sets). A component dinner meets the template counts per type (protein, vegetable, carb; 0 to 2 each). A complete-meal item is a valid one-item dinner and cannot be combined with components. Its categories are the union of its items' categories. |
| Window | The days shown and planned: today plus N-1 days. N defaults to 14, range 7 to 60. |
| Hard rule | Never violated. If no dinner fits, the day is left empty. |
| Soft rule | Scored. Violated only when nothing better fits, with a warning. |
| Unverified | An item whose nutrition facts are not confirmed yet. It can still be planned. |

## 4. Architecture

### 4.1 Components

- **Add-on** (`addon/`): Python 3.12, FastAPI, SQLite in `/data`. Owns all data, the generator, nutrition lookup, and import/export. Serves the panel through Ingress.
- **Integration** (`custom_components/menu_planner/`): config flow (discovery), coordinator (polls the add-on), sensors, websocket commands for the cards, services for automations, persistent notifications, shopping-list sync, card bundle serving.
- **Frontend** (`frontend/`): Lit + Material Web (Material 3), with HA theme variables (decided). Two Vite bundles: `panel` (add-on UI) and `cards` (Lovelace).

### 4.2 Data-flow rules

- The add-on is the only store of menu data.
- Cards call only the integration (websocket commands and services). They never call the add-on directly.
- The panel calls only its own add-on API through Ingress.
- The integration calls the add-on API over the internal network with the token.
- The add-on never calls HA Core. It returns warning codes and shopping needs; the integration creates notifications and shopping-list items.

### 4.3 Connection (discovery)

- `addon/config.yaml` has `discovery: [menu_planner]`.
- On start, the add-on posts to `http://supervisor/discovery` with `service: menu_planner` and `config: {host: "$(hostname)", port: <internal port>, token: <token>}`.
- The integration implements `async_step_hassio(discovery_info: HassioServiceInfo)`: it stores `discovery_info.config`, shows one confirm step, and creates the entry. There is no manual host entry.
- A repeat discovery updates the existing entry in place instead of creating a second one. The flow calls `self._abort_if_unique_id_configured(updates={...})`, the HA core pattern (see `homeassistant/components/goalzero/config_flow.py`).
- The hostname is never hard-coded. Repository installs prefix an 8-character hash (for example `a1b2c3d4-menu-planner`).
- Discovery needs no `hassio_api`: `/discovery` is in the default-allowed Supervisor set (HA contributor communication guide).
- Phase 1 must still verify that Core can reach the internal port without `ports:` (implied by the AdGuard example, not stated), and the lifecycle (whether the app re-sends on each start, and removal on uninstall).

### 4.4 Security

- Internal listener: a container port that is not listed under `ports:`. Serves `/api/*` only. Requires header `X-Menu-Planner-Token`.
- Token: random, generated on first start, stored in `/data`, sent in discovery, never logged, compared in constant time.
- Ingress listener (`ingress_port`, default 8099): serves the panel and `/api/*` without a token. The Supervisor restricts this port to the ingress proxy.
- No `homeassistant_api`, `full_access`, `docker_api`, `host_pid`, or `hassio_api`. Discovery does not need `hassio_api`. Protection mode stays on.
- No per-user permissions in v1.

### 4.5 Languages and time zone

- Cards use `hass.language`. The panel uses the language the integration syncs (`hass.config.language`), with English fallback.
- Translations: `frontend/shared/i18n/en.json` and `nl.json` for the panel and cards; HA `translations/` for the integration.
- The add-on returns warning codes, not text. Text is translated in the frontends and the integration.
- The add-on learns HA's time zone from the integration's sync. The `TZ` environment variable is the fallback before the first sync. A mismatch between the two shows a warning in the panel.

## 5. Data model

SQLite, schema versioned with `PRAGMA user_version`.

| Table | Key columns |
|---|---|
| `items` | id, name (unique, case-insensitive), type (protein / vegetable / carb), portion_grams (per household, nullable), fat_source (bool), track_stock (bool), is_complete_meal (bool; schema v2), created_at, updated_at |
| `nutrition` | item_id (PK), source (open_food_facts / usda / manual), external_id, matched_name, kcal, protein_g, carbs_g, fat_g, fiber_g (per 100 g), user_confirmed (bool), status (ok / not_found / error), fetched_at |
| `categories` | id, name (unique, case-insensitive), is_starter |
| `item_categories` | item_id, category_id |
| `category_minimums` | category_id, min_per_7_days |
| `rules` | id, kind (blacklist / whitelist), scope (combination / item), category_ids (set), item_id (nullable), enabled |
| `template_slots` | slot_type (protein / vegetable / carb), count (0 to 2) |
| `dinners` | id, items_key (sorted item ids, comma-joined, unique) |
| `dinner_items` | dinner_id, item_id (PK together; cascades on delete of either side) |
| `menu_days` | date (PK), dinner_id (nullable), status (planned / pinned / eaten / empty), replaced_reason (nullable), updated_at |
| `stock` | item_id (PK), in_stock (bool; NULL = unanswered), updated_at |
| `shopping_items` | item_id, added_at, removed_at |
| `warnings` | id, code, subject (date / item / category), payload_json, created_at, resolved_at |
| `settings` | key (PK), value_json |

Settings keys: `window_days` (7 to 60, default 14), `household_size` (default 2), `repeat_gap_days` (default 14), `balance_targets` (vegetables 50, protein 25, carbs 25, tolerance 10), `language` (auto / en / nl), `usda_api_key` (secret, excluded from export), `time_zone` (read-only, from `TZ`).

## 6. Planning rules and generator

### 6.1 Hard rules

- An item with `in_stock = false` is never planned.
- A blacklisted item is never planned.
- A dinner is invalid when its categories (the union over its items) contain every category of an enabled blacklist combination (assumed).
- Template slot counts are always met.
- A complete meal is a standalone exception to template counts; it cannot be combined with other items and obeys item, combination, and stock rules.
- Pinned and eaten days are fixed. Past days are history and never change.

### 6.2 Soft rules and priority

Conflicts resolve in this order, highest first:

1. Category minimums: evaluated for every 7-day span that overlaps the window. Past eaten or planned days count.
2. Repeat gap: an item may not reappear within `repeat_gap_days` of its last appearance (default 14). At the default, an item appears at most once per 14-day span.
3. Whitelist combinations: a preference.
4. Balance (plate, section 6.9).

### 6.3 Scoring (proposal, verified by unit tests)

- Each valid candidate gets a penalty. The lowest penalty wins.
- Minimum shortfall: a large penalty per missing dinner in any 7-day span. Candidates containing a short category get a bonus.
- Repeat gap: a penalty for each item used within the gap.
- Whitelist match: a bonus.
- Balance: a penalty for distance from the targets; a bonus for `fat_source` items. Complete meals do not contribute to component gram balance, which is reported as unknown.
- Ties are broken by a seeded random generator (seed = date plus replan revision). Results look random but are reproducible in tests.

### 6.4 Filling and re-planning

- Greedy, day by day in date order. Each open day takes the lowest-penalty valid dinner.
- Re-plan triggers: window roll-forward (new last day), stock change, edits to blacklist, whitelist, minimums, repeat gap, items, or template, and manual swap. Only future, non-pinned days change.
- A later stock "yes" re-plans only the days replaced for that item's "no".
- Feasibility check on rule save: validate that minimums can be met by the available items (bounded search) and warn when they cannot. One dinner can count toward several categories, so a simple sum is not enough.

### 6.5 Window and roll-over

- Window = today + (N-1) days, with N = `window_days`.
- At local midnight the window shifts, the new last day is generated, and yesterday becomes history.
- Missed roll-overs (add-on stopped) catch up on startup (assumed).
- A future day can be pinned, edited (choose another dinner), or swapped. Past days are read-only.

### 6.6 Stock flow

- Stock is tracked per item. Unanswered means in stock (assumed).
- Answer **no**:
  - `in_stock = false`.
  - Every planned dinner in the window that uses the item is replaced (`replaced_reason = stock`).
  - Days that enter the window while the item is "no" avoid it.
  - The item is added to the shopping list (HA list via the integration, plus the add-on copy).
  - A warning is created for any day left empty.
- Answer **yes**:
  - `in_stock = true`.
  - The shopping-list item is removed automatically (HA and add-on).
  - Days replaced because of that "no" are re-planned. Other days are untouched.
- Logging a dinner as eaten does not change stock.
- The stock card asks once per distinct item in the window.

### 6.7 Empty days and warnings

- If no valid dinner exists, the day becomes `empty` and a warning is created. The generator retries when rules or stock change.
- Warning codes: `replaced_dinner`, `missed_minimum`, `repeat_gap_unavoidable`, `empty_day`, `minimum_infeasible`, `nutrition_failed`, `timezone_mismatch`.
- The panel lists all warnings. The integration mirrors them as persistent notifications (created once, dismissed on resolve) and exposes them on the cards and sensors.

### 6.8 Swap

- Suggests three valid dinners for the day, satisfying all hard rules including stock and blacklist (assumed). Choosing one replaces the day.
- The swapped-in dinner counts like a planned one for minimums and repeat gap.

### 6.9 Balance (healthy plate)

- Basis: Voedingscentrum healthy plate. The user approved these defaults. The official page could not be fetched during planning, so re-verify the wording and numbers against the source before release.
- Targets per dinner (editable settings):
  - Vegetables and fruit: 50%.
  - Protein: 25%.
  - Carbs: 25%.
  - Tolerance: 10 percentage points before a penalty applies **(proposal)**.
  - Fat: items have a `fat_source` flag (oily fish, nuts, seeds, avocado, oils) that gives a bonus. No numeric fat target in v1 **(proposal)**.
- Shares are computed from portion weights (grams per household). Without portion weights, balance does not rank dinners.
- A dinner with any unverified component is not balance-scored. It is shown as "balance unknown" (assumed).
- Balance is soft. It never blocks a dinner.

## 7. Nutrition

- Lookup order: Open Food Facts (no key), then USDA FoodData Central (optional user API key), then manual entry.
- Per item: kcal, protein, carbs, fat, and fiber per 100 g, plus source and matched product name.
- On failure (no match, network error, rate limit), the item stays unverified, manual entry is offered, and retries run later with backoff.
- Successful lookups are cached permanently and refreshed only on request.
- An automatic match becomes verified only after the user confirms the matched product **(proposal)**. This guards against wrong products, especially for fresh produce.
- kcal per dinner is shown only when all components are verified; otherwise "unknown" (assumed). kcal is never scored.
- Household size (default 2) scales portions for kcal and grams.

## 8. Import and export

- Export: one JSON file with `schema_version: 1`. It contains items, categories, minimums, rules, template, and settings (secrets excluded). References use names, not IDs. The optional `is_complete_meal` item field defaults to false when importing older exports.
- Import: validate the schema version and structure, show a preview (added and skipped counts), then merge.
- Merge: items and categories match by name, case-insensitive. Existing ones are skipped (not updated). New ones are added. Rules and minimums are skipped when an equivalent one exists.
- Settings and history are imported only when ticked in the preview **(proposal)**.

## 9. Add-on panel

Sidebar panel via Ingress (`panel_title: Menu Planner`). Tabs:

1. **Menu**: the window with status badges (planned, pinned, eaten, empty). A day replaced by a stock change also shows a "replaced" badge (`replaced_reason` is set). Pin, edit, swap, log eaten. Warnings banner.
2. **Items**: search and filters (type, category, verified, stock). Add or edit: name, type, categories, portion, fat source, stock tracking, complete-meal flag, nutrition lookup or manual entry, confirm match.
3. **Categories**: name, minimum per 7 days, item count. Starter categories are editable and deletable.
4. **Rules**: blacklist and whitelist. A combination builder (pick categories) and item rules. Feasibility warnings.
5. **Stock**: yes/no per item, with a preview of how many dinners a "no" would replace before saving.
6. **Settings**: window length (7 to 60, default 14), household size (2), repeat gap (14), balance targets, dinner template (slot counts), language, USDA API key, nutrition retry.
7. **Import / export**: export the file; import with a preview.

Starter content on first install and database upgrade: a broad Belgian/European family-food catalog of meat and poultry cuts, fish and seafood, vegetarian proteins, vegetables, grains, potatoes, bread, pasta and prepared meals (including spaghetti bolognese, lasagne, macaroni and cheese, and pizza). Catalog items and categories are editable or deletable (Appendix A; migration v2).

## 10. Lovelace cards

Served by the integration at `/menu_planner/menu-planner-cards.js?v=<version>`. The integration registers the static path and adds the versioned URL through `frontend.add_extra_js_url`.

| Card | Element | Content | Actions |
|---|---|---|---|
| Today's dinner | `menu-planner-today-card` | Dinner title (item names joined with " · "), items with type icons, kcal or "unknown", balance chip, empty-day state | Log as eaten; Swap (three suggestions) |
| Stock check | `menu-planner-stock-card` | Distinct items in the window, unanswered first, yes/no buttons, "replaces N dinners" on "no" | Answer yes or no |
| Menu window | `menu-planner-window-card` | One row per day in the window (default 14 days): date, dinner, status badge | Tap a row for its components |

Visual editors: each card implements `getConfigForm()` with options for title, number of rows, show kcal, show balance, show stock impact, and unanswered only. Each card sets `preview: true` for the card picker.

Integration websocket commands: `menu_planner/window`, `menu_planner/today`, `menu_planner/stock`, `menu_planner/stock/set`, `menu_planner/stock/preview`, `menu_planner/eaten`, `menu_planner/swap/suggestions`, `menu_planner/swap/apply`. Swap apply accepts exactly one of a stored `dinner_id` or transient suggestion `item_ids`; today can be swapped until it is marked eaten.

Services for automations **(proposal)**: `menu_planner.log_eaten`, `menu_planner.set_stock` (item, in_stock), `menu_planner.swap_today`.

Sensors **(proposal)**: `sensor.menu_planner_today_dinner`, `sensor.menu_planner_tomorrow_dinner`, `sensor.menu_planner_warnings` (count, with a list attribute), `sensor.menu_planner_out_of_stock` (count, with a list attribute). Per-item stock binary sensors are deferred because dynamic entities add complexity.

## 11. Integration details

- `manifest.json`: domain `menu_planner`, name "Menu Planner", `config_flow: true`, `integration_type: hub` **(proposal)**, `iot_class: local_polling`, `codeowners`, `documentation`, `issue_tracker`, required dependency `websocket_api`, and after-dependencies `frontend` and `http`, `version`.
- Shopping list: call `shopping_list.add_item` and `shopping_list.remove_item` only when the service exists (`hass.services.has_service`).
- Coordinator: polls the add-on every 60 seconds and after each action. Each sync sends the HA language and time zone.
- Notifications: `persistent_notification.create` and `dismiss`, keyed by warning code and subject.

## 12. Repository layout and packaging

```
custom_components/menu_planner/   HA integration (Python), www/ (built cards), brand/icon.png
addon/                            config.yaml, Dockerfile, rootfs/ (s6 services), app/ (FastAPI, SQLite, domain, nutrition, io)
frontend/                         Lit + Material Web: panel/, cards/, shared/ (theme, i18n, API client)
tests/                            pytest: domain, db, api, io, integration
docs/                             PLAN.md, WORKFILE.md, API.md (Phase 1), mockups/
.github/workflows/                CI
repository.yaml                   add-on repository descriptor
hacs.json                         HACS metadata
README.md
```

Packaging:

- `repository.yaml`: name, url, maintainer.
- `addon/config.yaml`: name, slug `menu_planner`, quoted version, `arch: [amd64, aarch64]`, `init: false` (HA base image with s6), `ingress: true`, `ingress_port` 8099 (default), `panel_icon`, `panel_title`, `panel_admin: true` (no per-user roles in v1), `discovery: [menu_planner]`, `options: {log_level}` only. Other settings live in the panel to avoid two sources of truth. Image published to GHCR **(proposal)**.
- s6 scripts start with `#!/command/with-contenv bashio`.
- `hacs.json`: name, render_readme, and the minimum HA version (latest release at build time).
- Versioning: add-on and integration versions move together, tagged `vX.Y.Z`.
- License: MIT (decided).

## 13. Testing and CI

- Unit tests (pytest): generator (hard rules, soft priorities, feasibility), rules (blacklist, whitelist, minimums, repeat gap), balance scoring, roll-over and catch-up (injected clock), stock yes/no flow, import and export (merge and skip), nutrition clients (recorded fixtures, no live calls in CI).
- API tests (FastAPI TestClient): endpoints, token check on the internal listener, no token on the ingress listener.
- Frontend tests (Vitest): shared logic (i18n, API client, view models) and builds of the panel and cards bundles.
- Integration tests: config flow with discovery, sensors, websocket commands (`pytest-homeassistant-custom-component`).
- CI (GitHub Actions): ruff, pytest, `npm ci`, Vitest, build, hassfest, HACS action, add-on image build for amd64 and aarch64 (no push on pull requests).
- Manual checklist before release: install from the repository, discovery, cards, stock yes and no, midnight roll-over (a dev clock override such as `MENU_PLANNER_FAKE_NOW` **(proposal)**), import and export round trip.

## 14. Phases and parallel build

| Phase | Goal | Depends on | Output |
|---|---|---|---|
| 0 | Planning: plan, workfile, mockups, balance defaults | none | docs |
| 1 | Scaffolding and contract: repo layout, `.gitignore`, add-on skeleton (config, Dockerfile, FastAPI, token, options), integration skeleton (manifest, discovery flow), `docs/API.md`, repository interfaces shared by the data layer and the domain engine, Phase 1 checks (discovery, Core reachability, card registration) | 0 | skeletons, frozen API contract, repository interfaces |
| 2 | Data layer: SQLite schema, migrations, repositories, starter content | 1 | DB and tests |
| 3 | Domain engine: generator, rules, scoring, roll-over, stock, swap, feasibility | 1 (in-memory fakes until 2 lands) | engine and unit tests |
| 4 | Nutrition: Open Food Facts, USDA, cache, retry, manual entry | 2 | nutrition module and fixtures |
| 5 | Import and export: schema, preview, merge | 2 | io module and tests |
| 6 | Panel UI (Lit + Material Web): all tabs, EN and NL | 1 | panel bundle |
| 7 | Integration: coordinator, sensors, websocket commands, services, notifications, shopping sync, card serving | 1 (3 for real data) | integration |
| 8 | Lovelace cards: three cards, visual editors, EN and NL | 6, 7 | cards bundle |
| 9 | Tests and CI | 3 to 8 | green pipelines |
| 10 | Docs, install guide, v0.1.0 release | 9 | README, release |

Parallel build (after Phase 1, with `docs/API.md` frozen). Agents use claude-haiku-5.5, as requested:

| Agent | Owns | Phases |
|---|---|---|
| A | `addon/app/db/`, `addon/app/api/` | 2 |
| B | `addon/app/domain/`, `tests/domain/` (works against repository interfaces with in-memory fakes until A lands) | 3 |
| C | `addon/app/nutrition/`, `addon/app/io/`, their tests | 4, 5 |
| D | `custom_components/menu_planner/`, `tests/integration/` | 7 |
| E | `frontend/panel/`, `frontend/shared/` | 6 |
| F | `frontend/cards/` | 8 |
| G | `repository.yaml`, `hacs.json`, `addon/config.yaml`, `addon/Dockerfile`, `.github/`, `README.md` | 1, 9, 10 |

Rules: each agent edits only the files it owns. API changes go through `docs/API.md` and agent A. Only the coordinator edits `docs/WORKFILE.md`.

## 15. Assumptions (accepted by the user)

1. Unanswered stock means in stock.
2. Stock and repeat gap apply per item. Each item is one ingredient (no ingredient lists in v1).
3. Blacklist combinations use the union of categories across all components.
4. Swaps respect every hard rule, including stock and blacklist.
5. Missed midnight roll-overs catch up on startup.
6. Unverified items remain plannable and are excluded from balance scoring.
7. kcal is shown only when all components are verified.
8. Balance does not rank without portion weights.
9. Discovery is re-sent on each start, and the token persists in `/data`.
10. The integration type is `hub`; `websocket_api` is required, while `frontend` and `http` are after-dependencies used for the optional Lovelace bundle.
11. The add-on learns language and time zone from the integration's sync (`TZ` as fallback).
12. Starter minimums (fish at least 1, vegetarian at least 2 per 7 days) are editable defaults.

## 16. Risks and mitigations

| Risk | Mitigation |
|---|---|
| A common "no" (for example onion) replaces many dinners and empties days | Show the replacement count before saving; empty-day warnings; "no" can be undone |
| Wrong nutrition match (especially fresh produce on Open Food Facts) | Verified only after user confirms the match; show the matched product name |
| Discovery lifecycle or required role unverified | Phase 1 checks against the Supervisor docs and a dev instance |
| Balance targets come from a source that was not fetched | Editable; re-verify before release |
| Token leaks via discovery or logs | Never logged; stored in `/data`; not exposed on the host |
| Time zone mismatch between add-on and HA | Warning in the panel; sync from the integration |
| HACS icon missing | `brand/icon.png` placeholder until the user provides one |

## 17. Open items for the user

- License: decided, MIT.
- Brand icon: decided, a generated placeholder in Phase 1 (`brand/icon.png`); the user may replace it later.
- USDA API key: skipped for now (optional; without it the USDA step is skipped).
- Assumptions in section 15: accepted by the user.
- Time zone source, dinner title, and card element name: decided (section 4.5, section 10).

## Appendix A: Starter content

The starter catalog is defined in `addon/app/db/starter_content.py` and added by migration v2. It builds on the original v1 seeds and covers common poultry and meat cuts, Belgian and nearby fish/seafood, vegetarian proteins, familiar Belgian/European vegetables, potatoes, rice/grains, bread, pasta/noodles, and ready-made dinners. Prepared examples include lasagne, spaghetti bolognese, macaroni and cheese, pizza, vegetable lasagne, shepherd's pie, fish pie, vol-au-vent with fries, and stoemp with sausage.

Categories include fish, poultry, chicken, veal, pork, beef, lamb/game, seafood, vegetarian, legumes, pasta, rice/grains, potatoes, vegetables, Belgian, Asian, Mediterranean, and Mexican. Minimums remain editable: fish at least 1 and vegetarian at least 2 per 7 days. Component staples (for example spaghetti and lasagne sheets) remain distinct from complete dinner choices (for example spaghetti bolognese and lasagne).
