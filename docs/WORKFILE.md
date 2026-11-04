# Menu Planner: Workfile

Live progress for the build. Plan: [PLAN.md](PLAN.md). Mockups: [mockups/](mockups/).

Only the coordinator edits this file. Owners (A to G) are the parallel agents in PLAN section 14.

Legend: `[ ]` pending, `[~]` in progress, `[x]` done, `[!]` blocked.

Last updated: 2026-11-04

## Status

- **Phase:** 0, planning (review done)
- **Now:** Phase 1 scaffolding is ready to start once you approve the plan
- **Next:** Phase 1 (scaffolding and API contract)
- **Blockers:** none. The Dutch healthy-plate source (voedingscentrum.nl) could not be fetched, so the balance defaults (PLAN 6.9) are unverified. Check them before release.

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

- [ ] Repository layout and `.gitignore` for Python, Node, and SQLite data (PLAN 12)
- [ ] `repository.yaml`, `hacs.json`, `addon/config.yaml`
- [ ] Repository interfaces shared by the data layer and the domain engine (PLAN 14)
- [ ] Add-on skeleton: Dockerfile with s6, FastAPI app, internal listener with token, ingress listener, options
- [ ] Integration skeleton: `manifest.json`, config flow with `async_step_hassio`, confirm step
- [ ] Check: discovery works with no `hassio_api` (the docs say none is needed)
- [ ] Check: Core reaches the internal port without `ports:`
- [ ] Check: discovery lifecycle (re-send on start, removal on uninstall)
- [ ] Check: card registration with `frontend.add_extra_js_url`, or the manual resource fallback
- [ ] `docs/API.md`: frozen contract (endpoints, schemas, warning codes)

## Phase 2: Data layer

Depends on: 1. Owner: A.

- [ ] SQLite schema v1 (PLAN 5) with `PRAGMA user_version` migrations
- [ ] Repositories, with in-memory fakes for the domain tests
- [ ] Starter content (PLAN Appendix A)
- [ ] Unit tests

## Phase 3: Domain engine

Depends on: 1 (uses in-memory fakes until Phase 2 lands). Owner: B.

- [ ] Hard rules (PLAN 6.1)
- [ ] Soft rules and priority (6.2)
- [ ] Scoring with seeded tie-break (6.3)
- [ ] Greedy fill and re-planning (6.4)
- [ ] Window roll-over and catch-up (6.5)
- [ ] Stock yes/no flow (6.6)
- [ ] Empty days and warnings (6.7)
- [ ] Swap suggestions (6.8)
- [ ] Balance scoring (6.9)
- [ ] Feasibility check on rule save (6.4)
- [ ] Unit tests

## Phase 4: Nutrition

Depends on: 2. Owner: C.

- [ ] Open Food Facts client (recorded fixtures, no live calls in CI)
- [ ] USDA FoodData Central client (optional key)
- [ ] Permanent cache; refresh on request
- [ ] Retry with backoff; unverified fallback; manual entry
- [ ] Confirm-match step before an item is verified
- [ ] Tests

## Phase 5: Import and export

Depends on: 2. Owner: C.

- [ ] Export with `schema_version: 1` (secrets excluded)
- [ ] Import preview and merge (case-insensitive name match, skip existing)
- [ ] Round-trip tests

## Phase 6: Panel UI (Lit + Material Web)

Depends on: 1. Owner: E.

- [ ] Shared theme, i18n (EN and NL), and API client
- [ ] Menu, Items, Categories, Rules, Stock, Settings, and Import / export tabs
- [ ] Warnings banner
- [ ] Vitest

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
| 2026-11-04 | Phase 0 review done. Decisions recorded: MIT license; Lit + Material Web; time zone from the integration sync with `TZ` fallback; dinner title = item names joined with " · "; window card = `menu-planner-window-card`; brand icon placeholder; USDA key skipped for now; 12 assumptions accepted. Phase 1 checks need a Supervisor instance (available). | before writing files. Relaunched; `docs/mockups/addon-dashboard.html` and `docs/mockups/lovelace-cards.html` written and checked (no external URLs or resources). Known gaps: desktop card layout wraps to two rows; the week card shows 6 of 14 days; the dark theme is unchecked. |
