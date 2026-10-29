# LinkGuard frontend

The paste-a-link page: a React app built with Vite. Colours, type and spacing come from the shared design tokens in `src/styles/tokens.css`.

## Run it

Needs Node 20 or later. From `frontend/`:

```bash
npm ci
npm run dev
```

Then open http://localhost:5173.

The page isn't connected to the backend's `/scan` endpoint yet, so pressing Check shows "We couldn't check that link just now. Please try again."

## Test it

```bash
npm test
```

Vitest runs the component tests in `src/` in a browser-like DOM (jsdom), with React Testing Library (see `docs/adr/0001-frontend-test-runner.md`).

The contrast check reads the colours from the tokens file and checks every pair against WCAG 2.2:

```bash
npm run contrast
```
