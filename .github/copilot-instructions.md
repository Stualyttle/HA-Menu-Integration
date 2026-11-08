# Menu Planner: Copilot instructions

Home Assistant integration (HACS, domain `menu_planner`) plus a companion add-on (FastAPI + SQLite). The add-on plans healthy dinners over a rolling window (7 to 60 days, default 14) and tracks yes/no stock per item. The panel is Lit + Material Web.

## Read first

- `docs/PLAN.md`: source of truth for architecture, data model (§5), rules (§6), nutrition (§7), integration (§10), phases (§14), and assumptions (§15).
- `docs/API.md`: frozen HTTP contract between integration/panel and add-on. Change it only together with the code.
- `docs/WORKFILE.md`: live progress. Coordinator-owned. Update it with every completed batch of work.
- `docs/mockups/`: approved visual references for the panel and cards.

## Layout

| Path | What |
|---|---|
| `addon/app/` | FastAPI app. `api/` routers and errors, `domain/` pure planner logic (`engine.py`, `service.py`, `config.py`), data layer, nutrition, io. |
| `addon/rootfs/` | S6 service scripts (`services.d/menu_planner/run` uses `#!/command/with-contenv bashio`). |
| `addon/config.yaml`, `addon/Dockerfile` | Add-on manifest and image build. `BUILD_FROM` derives from `BUILD_ARCH`. |
| `custom_components/menu_planner/` | HA integration: config flow, coordinator (60 s poll), sensors, services, websocket commands. |
| `frontend/panel/` | Lit panel source (Vite). Build output goes to `addon/app/static/panel/`. |
| `tests/` | `tests/integration/` for the HA integration (needs `/tmp/ha-venv`); other tests are add-on tests. |
| `.github/workflows/` | `ci.yaml` (lint, test, hassfest, HACS). `build-addon.yaml` (per-arch GHCR images). |

## Commands

Run the smallest command that covers your change.

```bash
# Add-on lint and tests (venv with addon/requirements-dev.txt)
ruff check addon tests && ruff format --check addon tests
PYTHONPATH=addon python -m pytest -q --ignore=tests/integration

# Integration tests (venv with pytest-homeassistant-custom-component)
python -m pytest -q tests/integration

# Panel
cd frontend/panel && npm test && npm run build

# Workflows
actionlint .github/workflows/ci.yaml .github/workflows/build-addon.yaml
```

## Conventions

- Python 3.12 target. Ruff line length 100. Rule sets: `E,F,W,I,B,UP,SIM,RUF`.
- Keep the planner pure. `plan()` in `addon/app/domain/engine.py` has no I/O. The async facade `MenuPlanner` in `service.py` does I/O.
- The add-on never calls HA Core. The integration calls the add-on's internal port (8098) with `X-Menu-Planner-Token`, compared with `hmac.compare_digest`. The panel uses Ingress (8099) with no token.
- Errors use the envelope `{"error": {"code","message","details"}}` via `install_error_handlers` in `addon/app/api/errors.py`. The 401 body is `{"detail": ...}` (documented exception in `docs/API.md`).
- A dinner is a set of 0 to 2 items per type (`MAX_SLOT_COUNT` in `addon/app/domain/config.py`). Dedupe by sorted item-id set.
- Soft rules have priority: category minimums, repeat gap, whitelist, balance. Hard rules: blacklist, "no" stock never planned, template counts, pinned and eaten days fixed.
- Only comment code that needs clarification.
- Commits include the trailer `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.

## Home Assistant gotchas

- `homeassistant_api: true` grants full admin. Do not enable it.
- Discovery: the add-on POSTs to `http://supervisor/discovery` with `SUPERVISOR_TOKEN`. Import `HassioServiceInfo` from `homeassistant.helpers.service_info.hassio`.
- Supervisor skips folders named `rootfs` and hidden folders.
- Cards register with `window.customCards.push` and implement `getConfigForm()`, `getGridOptions()`, `getCardSize()`.

## Keep docs current

Any change to behavior, routes, install steps, supported architectures, or workflows must update, in the same change:
- `docs/API.md` for HTTP changes
- `docs/WORKFILE.md` (status and log)
- `README.md` for install, usage, or support changes
- `docs/PLAN.md` if a decision changes
- The relevant `.github/agents/*.agent.md` or `.github/skills/*/SKILL.md` if a workflow changes

## Phase work

Work is split into phases (PLAN §14). Parallel sub-agents each own a phase. The coordinator reconciles interfaces, updates the WORKFILE, and makes commits. Sub-agents may report success before verification, so re-run checks yourself before claiming done.
