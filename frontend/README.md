# LinkGuard frontend

The paste-a-link page: a React app built with Vite. Colours, type and spacing come from the shared design tokens in `src/styles/tokens.css`.

## Run it with the backend

The page sends each pasted link to the backend's `POST /scan`, so run both, in two terminals.

1. The backend, from `backend/` (needs Python 3.12 and uv, see `backend/README.md`):

   ```bash
   uv sync
   uv run uvicorn app.main:app --reload
   ```

   It listens on http://127.0.0.1:8000.

2. The frontend, from `frontend/`. Needs Node 22.22.2 or later on the 22 line, 24.15.0 or later on the 24 line, or Node 26 and up (the `engines` range in `package.json`, set by the locked jsdom and Vitest). Node 20 won't work. Check with `node --version`.

   ```bash
   npm ci
   npm run dev
   ```

   Then open http://localhost:5173.

The Vite dev server passes `/scan` on to the backend (see `vite.config.js`), so the page only ever calls its own address. If the backend runs on another port, set `BACKEND_URL` before `npm run dev`, for example `BACKEND_URL=http://127.0.0.1:8001 npm run dev`. Until the trained model is served, every check shows "Checking isn't switched on yet, so we can't give a result for this link." If the backend isn't running, the page shows "We couldn't check that link just now. Please try again."

## Test it

```bash
npm test
```

Vitest runs the component tests in `src/` in a browser-like DOM (jsdom), with React Testing Library (see `docs/adr/0001-frontend-test-runner.md`).

The contrast check reads the colours from the tokens file and checks every pair against WCAG 2.2:

```bash
npm run contrast
```

## The phishing charts

Under the paste-a-link form, the page shows charts comparing phishing and legitimate links. They are drawn from `ml/reports/chart_summary.json`, which the chart numbers script in `ml/` writes, so the page only shows what that file holds. Each chart is plain bars with the group name and value as text, plus a table of the same numbers for screen readers, with no chart library (see `docs/adr/0003-chart-drawing.md`). To change the numbers or takeaways, rerun the chart numbers script and commit the new file. Bar colours are tokens in `src/styles/tokens.css`, each with a 3:1 pair in `scripts/check-contrast.mjs`.
