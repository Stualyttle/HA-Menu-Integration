# Menu Planner: Workfile

Live progress for the build. Plan: [PLAN.md](PLAN.md). Mockups: [mockups/](mockups/).

Only the coordinator edits this file. Owners (A to G) are the parallel agents in PLAN section 14.

Legend: `[ ]` pending, `[~]` in progress, `[x]` done, `[!]` blocked.

Last updated: 2026-11-04 (Phases 2 to 6 committed in `5e39391`; workfile and API docs reconciled)

## Status

- **Phase:** Phases 2 to 6 committed (`5e39391`). Phase 1 code is done; its live checks are deferred. Phase 3 is partial (see below).
- **Now:** No agents running. Docs reconciled with the code. Next: candidate generation (Phase 3, 6.4) and the missing add-on routes.
- **Next:** Confirm the candidate-generation design with the user. Then build the menu, sync, nutrition, import/export, and rules-check routes (currently "planned" in `docs/API.md`). Phase 7 (integration) and Phase 8 (cards) follow. Live Supervisor checks stay pending until the user provides HA access.
- **Blockers:** Phase 3 has no candidate generation: the planner can only pick from dinners already stored, and no route creates them. The panel calls routes that do not exist yet (`frontend/shared/api/client.js`), so those calls return 404. The Dutch healthy-plate source (voedingscentrum.nl) could not be fetched, so the balance defaults (PLAN 6.9) are unverified. Check them before release.

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
- [ ] Greedy fill and re-planning (6.4). Blocked: candidate generation from template counts is missing; `valid_pool` (`addon/app/domain/engine.py` line 65) reads stored dinners only.
- [ ] Window roll-over and catch-up (6.5)
- [ ] Stock yes/no flow (6.6). The stock PUT side effects are placeholders (`addon/app/api/stock.py` lines 46–57).
- [ ] Empty days and warnings (6.7)
- [x] Swap suggestions (6.8) (domain logic; no route yet)
- [x] Balance scoring (6.9). Targets are unverified.
- [ ] Feasibility check on rule save (6.4). The check route is planned, not implemented.
- [x] Unit tests (`tests/domain/`)

## Phase 4: Nutrition

Depends on: 2. Owner: C. Status: partial (`5e39391`).

- [x] Open Food Facts client (recorded fixtures, no live calls in CI). Fixtures are hand-modeled because the live API was in maintenance (`addon/app/nutrition/clients.py`).
- [x] USDA FoodData Central client (optional key; the key is not yet configured in the panel)
- [x] Permanent cache; refresh on request (`addon/app/nutrition/service.py`)
- [x] Retry with backoff; unverified fallback; manual entry. Retries need an external scheduler to call `run_due_retries`.
- [x] Confirm-match step before an item is verified (domain)
- [ ] Lookup and manual-entry routes (`POST .../nutrition/lookup`, `PUT .../nutrition`). Planned in `docs/API.md`.
- [x] Tests (`tests/nutrition/`)

## Phase 5: Import and export

Depends on: 2. Owner: C. Status: partial (`5e39391`).

- [x] Export with `schema_version: 1` (secrets excluded) (`addon/app/io/export.py`)
- [x] Import preview and merge (case-insensitive name match, skip existing) (`addon/app/io/importer.py`)
- [x] Round-trip tests (`tests/io/`)
- [ ] HTTP routes for export and import. Planned in `docs/API.md`.

## Phase 6: Panel UI (Lit + Material Web)

Depends on: 1. Owner: E. Status: code and Vitest done (`5e39391`); browser behavior not yet checked.

- [x] Shared theme, i18n (EN and NL), and API client (`frontend/shared/`)
- [x] Menu, Items, Categories, Rules, Stock, Settings, and Import / export tabs (`frontend/panel/`)
- [x] Warnings banner
- [x] Vitest (18 tests per agent E; not re-run in the docs pass)
- [ ] Browser check. Calls to planned routes will fail until the routers exist.
- [ ] Bundle rebuilt against the current API. Grep for external URLs.

## Phase 7: Integration

Depends on: 1 (real data needs 3). Owner: D.

- [ ] Coordinator: 60 s poll and after each action; syncs language and time zone
- [ ] Sensors: today, tomorrow, warnings, out of stock
- [ ] Websocket commands and services
- [ ] Persistent notifications (create and dismiss by code and subject)
- [ ] Shopping-list sync (only when the service exists)
- [ ] Card bundle served and registered
- [ ] Integration tests

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
