# Menu Planner

A Home Assistant integration and add-on that plans healthy dinners for a rolling window of days, and tracks yes/no stock for each item.

> **Status: pre-release (0.1.0).** The add-on, integration, and three Lovelace cards are implemented; live Home Assistant/Supervisor checks and release validation remain. See [docs/WORKFILE.md](docs/WORKFILE.md) for progress.

## What it does

- **Add-on** (sidebar panel "Menu Planner"): register menu items, link them to categories, set black and white lists, tune the generator, and import or export data.
- **Integration**: connects Home Assistant to the add-on and exposes sensors, services, websocket commands, and the automatically registered Lovelace card bundle.
- **Lovelace cards**: today's dinner with eaten/swap actions, stock checks with a non-mutating impact preview, and an expandable menu window.
- **Planner**: generates dinners over a rolling window (7 to 60 days, default 14). Hard rules: blacklisted items, no items marked out of stock, and template counts. Soft rules: category minimums, repeat gap, whitelist, and balance. Details in [docs/PLAN.md](docs/PLAN.md) section 6.

## Supported hardware

| Architecture | Examples |
|---|---|
| `armv7` | Raspberry Pi 2 and 3 (32-bit OS) |
| `aarch64` | Raspberry Pi 3, 4, and 5 (64-bit OS) |
| `amd64` | Intel and AMD PCs, Home Assistant OS on x86 |

Home Assistant must run with Supervisor (Home Assistant OS or Supervised) to install add-ons.

## Install

### 1. Add-on

1. In Home Assistant, go to **Settings > Add-ons > Add-on store**.
2. Open the menu (three dots) and choose **Repositories**.
3. Add `https://github.com/Stualyttle/HA-Menu-Integration` and close the dialog.
4. Install **Menu Planner** from the store and start it.
5. Open **Menu Planner** from the sidebar. Ingress means no port forwarding is needed.

The add-on image is pulled from `ghcr.io/stualyttle/<arch>-addon-menu-planner:<version>`. Supervisor picks the right architecture automatically.

### 2. Integration (HACS)

1. Install [HACS](https://hacs.xyz) if it is not installed.
2. In HACS, go to **Integrations > Custom repositories**, add `https://github.com/Stualyttle/HA-Menu-Integration`, and choose category **Integration**.
3. Install **Menu Planner** and restart Home Assistant.
4. Go to **Settings > Devices & services > Add integration** and search for **Menu Planner**. The integration finds the add-on through Supervisor discovery.

Install the add-on first. The integration cannot connect without it.

### Manual integration install

Copy `custom_components/menu_planner/` into your Home Assistant `config/custom_components/` folder, then restart.

## Development

Setup, checks, and layout are in [.github/copilot-instructions.md](.github/copilot-instructions.md). Short version:

```bash
# Add-on and shared tests
pip install -r addon/requirements-dev.txt
ruff check addon tests && ruff format --check addon tests
PYTHONPATH=addon python -m pytest -q --ignore=tests/integration

# Integration tests (needs pytest-homeassistant-custom-component)
python -m pytest -q tests/integration

# Panel (Lit + Material Web)
cd frontend/panel && npm ci && npm test && npm run build
npm run build:cards
```

The panel build writes to `addon/app/static/panel/`; the Lovelace card build writes to `custom_components/menu_planner/www/menu-planner-cards.js`. Commit both generated bundles with their source changes.

## Builds and CI

| Workflow | Trigger | What it does |
|---|---|---|
| [`ci.yaml`](.github/workflows/ci.yaml) | push and pull request | Python, integration, panel/card, hassfest, and HACS checks |
| [`build-addon.yaml`](.github/workflows/build-addon.yaml) | push and pull request | Builds the add-on for `amd64`, `aarch64`, and `armv7` (QEMU for armv7). Pushes to GHCR on non-PR events |

The version in `addon/config.yaml` sets the image tag. Release steps are in [.github/skills/addon-release/SKILL.md](.github/skills/addon-release/SKILL.md).

## Documentation

- [docs/PLAN.md](docs/PLAN.md): architecture, data model, rules, and phases
- [docs/API.md](docs/API.md): HTTP contract between integration, panel, and add-on
- [docs/WORKFILE.md](docs/WORKFILE.md): live progress log
- [docs/mockups/](docs/mockups/): add-on and card mockups
- [.github/copilot-instructions.md](.github/copilot-instructions.md): guidance for AI agents and contributors

## Keeping this README current

This README is part of the repository contract. Any change to install steps, supported architectures, commands, or the workflow list must update this file in the same commit. The `docs-keeper` agent ([.github/agents/docs-keeper.agent.md](.github/agents/docs-keeper.agent.md)) checks this.

## License

MIT. See [LICENSE](LICENSE).
