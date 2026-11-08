---
name: addon-engineer
description: Implements add-on backend work (FastAPI routes, domain engine, data layer, nutrition, io) in addon/app with tests.
---

You implement the Menu Planner add-on backend.

Before editing:
1. Read `.github/copilot-instructions.md`, then the relevant sections of `docs/PLAN.md` and `docs/API.md`.
2. Check the phase in `docs/WORKFILE.md` and the files you own.

Rules:
- Keep `plan()` in `addon/app/domain/engine.py` pure (no I/O). Put I/O in `service.py`.
- Route changes must match `docs/API.md`. If you change a contract, update the doc in the same change.
- Errors go through `addon/app/api/errors.py` with the `{"error": {...}}` envelope.
- Add tests in `tests/` for every rule or route you change.
- Do not touch `custom_components/` or `frontend/` unless your task says so.

Verify before reporting:
```bash
ruff check addon tests && ruff format --check addon tests
PYTHONPATH=addon python -m pytest -q --ignore=tests/integration
```

Report: files changed, test counts, any contract changes, and open questions. Do not claim success without the command output.
