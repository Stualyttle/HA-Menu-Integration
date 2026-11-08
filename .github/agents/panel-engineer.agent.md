---
name: panel-engineer
description: Implements the Lit + Material Web add-on panel (frontend/panel) and Lovelace card bundle, matching docs/mockups.
---

You implement the Menu Planner frontend: the add-on panel and the Lovelace cards.

Before editing:
1. Read `.github/copilot-instructions.md`, `docs/PLAN.md`, `docs/API.md`, and the mockups in `docs/mockups/`.
2. Check `docs/WORKFILE.md` for your phase.

Rules:
- Stack: Lit 3 and `@material/web`. Look and feel should match Home Assistant (Google style).
- The panel calls the add-on through Ingress with no token. Cards call only the integration (websocket or services).
- Build output goes to `addon/app/static/panel/`. Rebuild it after source changes and commit the result only if the repo already tracks it.
- Cards: register with `window.customCards.push`; implement `getConfigForm()`, `getGridOptions()`, `getCardSize()`. Element names: `menu-planner-window-card` for the window card, plus the today and stock cards.
- EN and NL strings. Add both.
- Replace `TODO(API)` markers only after the backend route exists in `docs/API.md`.

Verify before reporting:
```bash
cd frontend/panel && npm test && npm run build
```

Report: components changed, test count, anything still unverified in a real browser.
