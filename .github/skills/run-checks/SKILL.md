---
name: run-checks
description: Run the Menu Planner lint, test, build, and workflow checks that match a change. Use before reporting any change as done.
---

# Run checks

Pick the smallest set that covers what changed.

| Changed | Run |
|---|---|
| `addon/**` | `ruff check addon tests && ruff format --check addon tests`, then `PYTHONPATH=addon python -m pytest -q --ignore=tests/integration` |
| `custom_components/**`, `tests/integration/**` | `python -m pytest -q tests/integration` (HA venv) |
| `frontend/panel/**` | `cd frontend/panel && npm test && npm run build` |
| `.github/workflows/**` | `actionlint .github/workflows/ci.yaml .github/workflows/build-addon.yaml` |
| `addon/Dockerfile`, `addon/config.yaml` | Also `docker buildx build --platform linux/arm/v7 addon` if Docker is available |

Rules:
- Read the actual output. Do not claim a pass from a sub-agent report alone.
- Report exact counts (for example "332 passed").
- If a tool is missing, say so. Do not install packages unless a manifest changed or a check failed for a missing package.
- Do not leave temporary files in the repo. Use `/tmp` for venvs and downloads.

Expected baseline at the time of writing: add-on 332 passed, integration 33 passed, panel 20 passed. Update this number when it changes.
