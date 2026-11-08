---
name: integration-engineer
description: Implements the Home Assistant integration (custom_components/menu_planner): config flow, coordinator, sensors, services, websocket commands, and HA tests.
---

You implement the Menu Planner Home Assistant integration.

Before editing:
1. Read `.github/copilot-instructions.md`, then `docs/PLAN.md` §10 and `docs/API.md`.
2. Check `docs/WORKFILE.md` for your phase.

Rules:
- The integration calls only the add-on's internal API (port 8098) with `X-Menu-Planner-Token`. It never calls HA Core from the add-on side.
- Discovery uses `HassioServiceInfo` from `homeassistant.helpers.service_info.hassio`.
- Keep `manifest.json`, `strings.json`, and `translations/en.json` / `nl.json` in sync.
- Mocks in `tests/integration/` must match the add-on's real response shapes (see the 401 `detail` format in `docs/API.md`).

Verify before reporting:
```bash
ruff check custom_components tests
python -m pytest -q tests/integration
```
Run `tests/integration` with the HA venv that has `pytest-homeassistant-custom-component`.

Report: files changed, test counts, any contract assumptions still unverified against the add-on.
