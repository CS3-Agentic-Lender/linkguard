---
status: accepted
---

# Vitest as the frontend test runner

The frontend is a React app, so it needs a test runner that understands JSX and modern JavaScript modules. We use **Vitest**, because the React app is built with Vite, and Vitest reuses Vite's own config and transforms, so tests need no separate Babel or TypeScript setup. Its test API (`describe`, `it`, `expect`) matches Jest's, so anyone who knows Jest can write Vitest tests, and React Testing Library works with it unchanged.

Accepted by the team in Sprint 1, when the paste-a-link story agreed to set up the frontend with Vite and React. That story installs Vitest with the app and adds its first passing test, run with `npm test` from `frontend/`.

## Considered options

- **Vitest** (chosen): fast, shares Vite's config, Jest-compatible API, coverage through `@vitest/coverage-v8` when we want it. Fits only if the app uses Vite; if it doesn't, Jest is the safer pick.
- **Jest**: the long-standing default with the most tutorials. Needs Babel or `ts-jest` to handle JSX and ES modules, which is extra config to keep in step with the app's build tool.
- **Node's built-in test runner** (`node --test`): no dependency, but no JSX support and no browser-like DOM, so it can't test React components without the same extra tooling.

## Consequences

- If the React app ticket picks a build tool other than Vite, revisit this decision before writing component tests.
- Component tests will also need `@testing-library/react` and `jsdom`. They are added with the first component test, not now.
