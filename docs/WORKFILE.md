# Menu Planner: Workfile

Live progress for the build. Plan: [PLAN.md](PLAN.md). Mockups: [mockups/](mockups/).

Only the coordinator edits this file. Owners (A to G) are the parallel agents in PLAN section 14.

Legend: `[ ]` pending, `[~]` in progress, `[x]` done, `[!]` blocked.

Last updated: 2026-11-04 (wave 1 committed as `a2d9ac5`; README, Copilot rules, agents, skills, and CI/build workflows added)

## Status

- **Phase:** Wave 1 committed (`a2d9ac5`). Phase 9 partly done: CI and multi-arch build workflows exist; docs and agent rules added. Phase 1 live checks are deferred.
- **Now:** Committing README, Copilot rules, and build workflows. Open questions for the user: 401 body format, whether read paths persist dinners, and whether to align the panel's 13 `TODO(API)` calls.
- **Next:** Align the panel's `TODO(API)` calls with backend routes. Then Phase 8 (cards) and Phases 9 to 10.
- **Blockers:** Live Supervisor checks need HA access details. The balance defaults (PLAN 6.9) are unverified. Open design questions: whether read paths persist dinners, whether `check_rules` persists candidates, the 500-candidate cap, and that household size does not scale portions.

Verification (wave 1): ruff check and format clean. Add-on pytest 332 passed. Integration pytest 33 passed. Panel Vitest 20 passed; build succeeded. 38 operations, no duplicate routes.

## Phase 0: Planning

Depends on: none

- [x] Requirements gathered in five question rounds (answers in PLAN.md)
- [x] Architecture checked against HA docs: discovery, add-on security, Ingress, HACS, card API
- [x] Plan written: `docs/PLAN.md`
- [x] Workfile created: `docs/WORKFILE.md`
- [x] Folders created: `docs/`, `docs/mockups/`
- [x] Mockups: add-on dashboard and Lovelace cards (`docs/mockups/`)
- [x] Review of plan and mockups with you
- [x] Assumptions confirmed (PLAN section 15): accepted
- [x] Open items answered (PLAN section 17): license MIT; brand icon placeholder in Phase 1; USDA key skipped for now
- [x] Decisions: frontend Lit + Material Web; time zone from integration sync with `TZ` fallback; Today's card shows item names joined with " · "; window card is `menu-planner-window-card`; Home Assistant with Supervisor available for Phase 1 checks

## Phase 1: Scaffolding and API contract

Depends on: 0. Owner: coordinator (packaging: G).

- [x] Repository layout and `.gitignore` for Python, Node, and SQLite data (PLAN 12)
- [x] `repository.yaml`, `hacs.json`, `addon/config.yaml` (YAML parse-checked; `addon/build.yaml` base image tag still unverified)
- [x] Repository interfaces shared by the data layer and the domain engine (PLAN 14): `addon/app/models.py`, `addon/app/ports.py`
- [x] Add-on skeleton: Dockerfile with s6, FastAPI app, internal listener with token, ingress listener, options
- [x] Integration skeleton: `manifest.json`, config flow with `async_step_hassio`, confirm step (imports under HA 2026.10.4 harness)
- [ ] Check: discovery works with no `hassio_api` (the docs say none is needed)
- [ ] Check: Core reaches the internal port without `ports:`
- [ ] Check: discovery lifecycle (re-send on start, removal on uninstall)
- [ ] Check: card registration with `frontend.add_extra_js_url`, or the manual resource fallback
- [x] `docs/API.md`: frozen contract (endpoints, schemas, warning codes)
- [x] Lint and tests: `ruff check`, `ruff format --check`, `pytest tests/addon` (9 passed)

## Phase 2: Data layer

Depends on: 1. Owner: A. Status: done (`5e39391`).

- [x] SQLite schema v1 (PLAN 5) with `PRAGMA user_version` migrations (`addon/app/db/migrations.py`)
- [x] Repositories, with in-memory fakes for the domain tests (`addon/app/db/repositories.py`)
- [x] Starter content (PLAN Appendix A), seeded by `_seed_starter_content`
- [x] Unit tests (`tests/db/`)

## Phase 3: Domain engine

Depends on: 1 (uses in-memory fakes until Phase 2 lands). Owner: B. Status: partial (`5e39391`).

- [x] Hard rules (PLAN 6.1) (`addon/app/domain/rules.py`)
- [x] Soft rules and priority (6.2)
- [x] Scoring with seeded tie-break (6.3) (`addon/app/domain/scoring.py`)
- [x] Candidate generation from template counts, capped at 500 with seeded sampling (`addon/app/domain/candidates.py`). Persisted by `MenuPlanner.load()`.
- [x] Greedy fill and re-planning (6.4). Replan route: `POST /api/menu/replan`.
- [ ] Window roll-over and catch-up (6.5). Needs a review of the design decision on persisting dinners in read paths.
- [x] Stock yes/no flow (6.6). PUT `/api/stock/{id}` returns the real engine diff; `shopping` is a placeholder.
- [x] Empty days and warnings (6.7)
- [x] Swap suggestions (6.8). Routes: GET and POST `/api/menu/{date}/swap`.
- [x] Balance scoring (6.9). Targets are unverified.
- [x] Feasibility check on rule save (6.4). `POST /api/rules/check` (no persistence).
- [x] Unit tests (`tests/domain/`)

## Phase 4: Nutrition

Depends on: 2. Owner: C. Status: partial (`5e39391`).

- [x] Open Food Facts client (recorded fixtures, no live calls in CI). Fixtures are hand-modeled because the live API was in maintenance (`addon/app/nutrition/clients.py`).
- [x] USDA FoodData Central client (optional key; the key is not yet configured in the panel)
- [x] Permanent cache; refresh on request (`addon/app/nutrition/service.py`)
- [x] Retry with backoff; unverified fallback; manual entry. Retries need an external scheduler to call `run_due_retries`.
- [x] Confirm-match step before an item is verified (domain)
- [x] Lookup and manual-entry routes: GET `/api/items/{id}/nutrition/lookup`, PUT `/api/items/{id}/nutrition` (`addon/app/api/nutrition.py`)
- [x] Tests (`tests/nutrition/`)

## Phase 5: Import and export

Depends on: 2. Owner: C. Status: partial (`5e39391`).

- [x] Export with `schema_version: 1` (secrets excluded) (`addon/app/io/export.py`)
- [x] Import preview and merge (case-insensitive name match, skip existing) (`addon/app/io/importer.py`)
- [x] Round-trip tests (`tests/io/`)
- [x] HTTP routes: GET `/api/export`, POST `/api/import/preview`, POST `/api/import` (`addon/app/api/io.py`). History import returns 400.

## Phase 6: Panel UI (Lit + Material Web)

Depends on: 1. Owner: E. Status: code and Vitest done (`5e39391`); browser behavior not yet checked.

- [x] Shared theme, i18n (EN and NL), and API client (`frontend/shared/`)
- [x] Menu, Items, Categories, Rules, Stock, Settings, and Import / export tabs (`frontend/panel/`)
- [x] Warnings banner
- [x] Vitest (18 tests per agent E; not re-run in the docs pass)
- [ ] Browser check.
- [ ] Align 13 `TODO(API)` calls in `frontend/shared/api/client.js` with the backend routes. `menu.replan` and `settings.retryLookups` still reject with `not_implemented`.
- [x] Bundle rebuilt (`addon/app/static/panel/`). Grep for external URLs: pending.

## Phase 7: Integration

Depends on: 1 (real data needs 3). Owner: D. Status: wave 1 (`custom_components/menu_planner/`), 33 integration tests pass.

- [x] Coordinator: 60 s poll; POSTs `/api/sync` with language and time zone. Accepts list or `{days:[...]}` for `/api/menu`. Verify against bare-array output.
- [x] Sensors: today, tomorrow, warnings, out of stock (`sensor.py`)
- [x] Websocket commands (`menu_planner/*`) and services (`log_eaten`, `set_stock`, `swap_today`)
- [ ] Persistent notifications (create and dismiss by code and subject)
- [ ] Shopping-list sync (deferred, PLAN 11)
- [ ] Card bundle served and registered
- [x] Integration tests (`tests/integration/`)

## Phase 8: Lovelace cards

Depends on: 6 and 7. Owner: F.

- [ ] Today's dinner card (log as eaten, swap)
- [ ] Stock check card (yes/no, impact count)
- [ ] Menu window card
- [ ] Visual editors via `getConfigForm()`
- [ ] EN and NL strings

## Phase 9: Tests and CI

Depends on: 3 to 8. Owner: G.

- [ ] CI: ruff, pytest, Vitest, build, hassfest, HACS action, add-on image for amd64 and aarch64
- [ ] Manual checklist (PLAN 13)

## Phase 10: Docs and release

Depends on: 9. Owner: G.

- [ ] README and install guide
- [ ] Release `v0.1.0`

## Log

| Date | Done |
|---|---|
| 2026-11-04 | Repository inspected: greenfield, one commit (`0e2da4f`). |
| 2026-11-04 | Requirements gathered (five question rounds). HA add-on, discovery, and card docs checked. |
| 2026-11-04 | `docs/PLAN.md` written. `docs/` and `docs/mockups/` created. |
| 2026-11-04 | `docs/WORKFILE.md` created. Mockup sub-agent started. |
| 2026-11-04 | Discovery facts recorded in PLAN 4.3 (no `hassio_api`; repeat discovery updates in place). Phase 3 and 8 dependencies aligned with `todo_deps`. |
| 2026-11-04 | Phase 1 code written: packaging, add-on skeleton (ingress, internal token listener, discovery), integration config flow, `docs/API.md`. Fixed `HassioServiceInfo` import (now `homeassistant.helpers.service_info.hassio`). Lint and 9 add-on tests pass. Live Supervisor checks pending (need HA access). |
| 2026-11-04 | Phase 0 review done. Decisions recorded: MIT license; Lit + Material Web; time zone from the integration sync with `TZ` fallback; dinner title = item names joined with " · "; window card = `menu-planner-window-card`; brand icon placeholder; USDA key skipped for now; 12 assumptions accepted. Phase 1 checks need a Supervisor instance (available). |
| 2026-11-04 | Mockup sub-agent relaunched; `docs/mockups/addon-dashboard.html` and `docs/mockups/lovelace-cards.html` written and checked (no external URLs or resources). Known gaps: desktop card layout wraps to two rows; the week card shows 6 of 14 days; the dark theme is unchecked. |
| 2026-11-04 | Phases 2 to 6 landed as parallel sub-agents, committed in `5e39391`. Starter content seeded; stored-dinner pool only (candidate generation missing). |
| 2026-11-04 | Multi-item refactor: a dinner is a set of 0 to 2 items per type. Dedupe by sorted item-id set. Verified 242 passing. |
| 2026-11-04 | Template update returns 400 (not 500) for domain errors and all-zero templates. Error handlers in `addon/app/api/errors.py`. Suite at 243 passing; ruff clean. |
| 2026-11-04 | Workfile and `docs/API.md` reconciled with the code. Unbuilt routes (menu, sync, nutrition lookup and PUT, rules check, export, import) marked planned. Error codes corrected (400, not 422). |
| 2026-11-04 | Wave 1 (5 parallel agents, claude-haiku-5.5): menu, sync, rules check, nutrition, import/export routes; candidate generation; integration; panel. `DATA_ROUTERS` updated. Verified: 332 add-on, 33 integration, 20 panel tests; ruff clean; no duplicate routes. Not yet committed. |
| 2026-11-04 | `docs/API.md` reconciled with wave 1. Lookup is GET (was documented as POST). Routes and bodies updated. |
| 2026-11-04 | Wave 1 committed as `a2d9ac5`. |
| 2026-11-04 | Build: `addon/config.yaml` arch list now armv7, aarch64, amd64, with an `image:` template for GHCR. `addon/build.yaml` removed; `addon/Dockerfile` picks the base image from `BUILD_ARCH`. Added `.github/workflows/ci.yaml` and `build-addon.yaml`. Both pass actionlint. Not yet run on GitHub. |
| 2026-11-04 | Copilot rules added: `.github/copilot-instructions.md`, four agents (addon, integration, panel, docs-keeper), and three skills (run-checks, workfile-update, addon-release). |
| 2026-11-04 | `README.md` written (HACS and add-on install, architecture support, dev commands, workflows). Added `LICENSE` (MIT). |
