# Technology Stack

**Analysis Date:** 2026-05-22

## Scope

**Frontend-only map:**
- Analyze implementation under `frontend/`.
- Use root setup constraints only where they directly affect frontend execution: `AGENTS.md`, `README.md`, `scripts/start-dev.ps1`, `scripts/start-dev-wsl.sh`, and `scripts/stop-build.ps1`.
- Do not treat backend implementation as stack evidence; frontend API boundaries are taken from `frontend/lib/api.ts`, `frontend/lib/apiBaseUrl.ts`, and `frontend/types/api.ts`.

## Languages

**Primary:**
- TypeScript - application, hooks, stores, API client, config, and tests in `frontend/app/`, `frontend/components/`, `frontend/hooks/`, `frontend/stores/`, `frontend/lib/`, `frontend/types/`, `frontend/utils/`, `frontend/next.config.ts`, `frontend/jest.config.ts`, and `frontend/playwright.config.ts`.
- TSX / React JSX - page and component UI in `frontend/app/page.tsx`, `frontend/app/tender/page.tsx`, `frontend/components/chat/`, `frontend/components/forms/`, and `frontend/components/layout/`.

**Secondary:**
- CSS with Tailwind directives - global styling and theme tokens in `frontend/app/globals.css`.
- JavaScript - Jest setup and runtime polyfills in `frontend/jest.setup.js` and `frontend/polyfills.js`.
- Shell / PowerShell - frontend startup and shutdown orchestration in `scripts/start-dev-wsl.sh`, `scripts/start-dev.ps1`, and `scripts/stop-build.ps1`.

## Runtime

**Environment:**
- Node.js `>=20.9.0` is required by `frontend/package.json`; `frontend/.nvmrc` pins major version `20`; `README.md` recommends Node 20 LTS for frontend setup.
- Browser runtime is required for DOM APIs, `fetch`, `EventSource`, file input, object URLs, `sessionStorage`, URL search params, and history replacement used by `frontend/lib/api.ts`, `frontend/lib/sse.ts`, `frontend/components/forms/FileUploader.tsx`, `frontend/components/chat/ChatPanel.tsx`, `frontend/stores/chatStore.ts`, `frontend/stores/historyStore.ts`, `frontend/stores/chatTaskSessionStore.ts`, and `frontend/utils/tenderTypeMapper.ts`.
- Development server runs on port `8502` through `next dev -p 8502` in `frontend/package.json`; Playwright uses `http://localhost:8502` in `frontend/playwright.config.ts`; root scripts reference the same frontend port in `scripts/stop-build.ps1`.

**Package Manager:**
- Use npm. `frontend/package-lock.json` is present with lockfile version `3`; `README.md` recommends `npm ci`; `frontend/package.json` defines npm scripts.
- `frontend/.npmrc` is present but contents are not read or documented; `README.md` states the frontend registry constraint.
- Lockfile: present at `frontend/package-lock.json`.

## Frameworks

**Core:**
- Next.js `^16.2.6` - app routing, build, dev server, rewrites, headers, image config, and strict TypeScript build behavior in `frontend/package.json`, `frontend/app/layout.tsx`, `frontend/app/page.tsx`, `frontend/app/tender/page.tsx`, and `frontend/next.config.ts`.
- React `19.2.3` and React DOM `19.2.3` - client components and hooks in `frontend/package.json`, `frontend/app/tender/page.tsx`, `frontend/components/chat/`, `frontend/components/forms/`, and `frontend/hooks/`.
- Tailwind CSS `^4` with `@tailwindcss/postcss` - utility styling and theme tokens in `frontend/package.json`, `frontend/postcss.config.mjs`, and `frontend/app/globals.css`.
- Zustand `^5.0.11` - frontend state and persistence in `frontend/package.json`, `frontend/stores/chatStore.ts`, `frontend/stores/historyStore.ts`, `frontend/stores/chatTaskSessionStore.ts`, `frontend/stores/chatStreamStore.ts`, and `frontend/stores/useAppStore.ts`.

**Testing:**
- Jest `^29.7.0` with `next/jest` and `jest-environment-jsdom` - unit and integration tests configured by `frontend/jest.config.ts` and invoked from `frontend/package.json`.
- Testing Library - React DOM assertions and interaction tests through `@testing-library/react`, `@testing-library/jest-dom`, and `@testing-library/user-event` in `frontend/package.json`, `frontend/jest.setup.js`, `frontend/jest.setup.ts`, and `frontend/__tests__/`.
- MSW `^2.12.10` - backend API mocks in `frontend/mocks/handlers.ts` and `frontend/mocks/server.ts`; Jest module mappings for MSW internals live in `frontend/jest.config.ts`.
- Playwright `^1.58.2` - E2E tests in `frontend/e2e/` and configuration in `frontend/playwright.config.ts`.

**Build/Dev:**
- TypeScript `^5` - strict, no-emit checking with Next plugin and `@/*` path alias in `frontend/tsconfig.json`.
- ESLint `^9`, `eslint-config-next 16.1.6`, and `eslint-plugin-react-hooks ^7.0.1` - linting through `frontend/eslint.config.mjs`.
- Prettier `^3.8.1` and `prettier-plugin-tailwindcss ^0.7.2` - formatting through `frontend/.prettierrc` and `frontend/.prettierignore`.
- Next production headers and static asset caching are configured in `frontend/next.config.ts`.

## Package Scripts

**Run from `frontend/`:**
```bash
npm run dev            # Next dev server on port 8502 (`frontend/package.json`)
npm run build          # Next production build (`frontend/package.json`)
npm run start          # Next production server on port 8502 (`frontend/package.json`)
npm run lint           # ESLint (`frontend/package.json`, `frontend/eslint.config.mjs`)
npm run type-check     # tsc --noEmit (`frontend/package.json`, `frontend/tsconfig.json`)
npm run format         # Prettier write (`frontend/package.json`, `frontend/.prettierrc`)
npm run format:check   # Prettier check (`frontend/package.json`, `frontend/.prettierrc`)
npm run test           # Jest (`frontend/package.json`, `frontend/jest.config.ts`)
npm run test:watch     # Jest watch (`frontend/package.json`)
npm run test:coverage  # Jest coverage (`frontend/package.json`, `frontend/jest.config.ts`)
npm run test:e2e       # Playwright (`frontend/package.json`, `frontend/playwright.config.ts`)
npm run test:e2e:ui    # Playwright UI (`frontend/package.json`)
npm run test:e2e:debug # Playwright debug (`frontend/package.json`)
```

**Root orchestration:**
- Windows startup checks `frontend/package.json`, `frontend/.env.local`, `frontend/node_modules`, and `frontend/node_modules/.bin/next.cmd` before launching the frontend through `scripts/start-dev.ps1`.
- WSL startup checks `frontend/package.json`, `frontend/.env.local`, `frontend/node_modules`, and `npm`, then runs `npm run dev` from `frontend/` through `scripts/start-dev-wsl.sh`.
- Shutdown removes frontend runtime state and frees port `8502` through `scripts/stop-build.ps1`.

## Key Dependencies

**Critical:**
- `next` `^16.2.6` - page routing, dev server, rewrites, headers, and build in `frontend/package.json` and `frontend/next.config.ts`.
- `react` `19.2.3` / `react-dom` `19.2.3` - component runtime in `frontend/package.json`, `frontend/app/`, and `frontend/components/`.
- `zustand` `^5.0.11` - application state, current-session persistence, task stream state, and history in `frontend/package.json` and `frontend/stores/`.
- `tailwindcss` `^4` and `@tailwindcss/postcss` `^4` - CSS pipeline in `frontend/package.json`, `frontend/postcss.config.mjs`, and `frontend/app/globals.css`.
- `lucide-react` `^0.575.0` - icon components used throughout `frontend/app/page.tsx`, `frontend/app/tender/page.tsx`, `frontend/components/chat/`, and `frontend/components/forms/`.
- `clsx` `^2.1.1` and `tailwind-merge` `^3.5.0` - class composition via `frontend/lib/utils.ts`.

**Infrastructure:**
- `typescript` `^5`, `@types/node` `^20`, `@types/react` `^19`, and `@types/react-dom` `^19` - static typing in `frontend/package.json` and `frontend/tsconfig.json`.
- `jest`, `next/jest`, `jest-environment-jsdom`, and Testing Library packages - unit/integration tests in `frontend/jest.config.ts`, `frontend/jest.setup.js`, and `frontend/__tests__/`.
- `msw` - HTTP API mocking in `frontend/mocks/handlers.ts` and `frontend/mocks/server.ts`.
- `@playwright/test` - browser E2E validation in `frontend/playwright.config.ts` and `frontend/e2e/`.
- `undici` and `und` are listed as dev dependencies in `frontend/package.json`; Node/browser polyfills are implemented locally in `frontend/polyfills.js` and `frontend/polyfills.ts`.

## Configuration

**Environment:**
- `NEXT_PUBLIC_API_URL` is the frontend-visible API base URL override read by `frontend/lib/apiBaseUrl.ts` and `frontend/next.config.ts`.
- `NODE_ENV` controls production header behavior in `frontend/next.config.ts`.
- `CI` controls Playwright retries, workers, `forbidOnly`, and server reuse in `frontend/playwright.config.ts`.
- `PLAYWRIGHT_USE_SYSTEM_CHROME` controls whether local Playwright uses the system Chrome channel in `frontend/playwright.config.ts`.
- `frontend/.env.local` exists and is required by root startup scripts, but values must not be read or documented; `frontend/.env.local.example` exists as the committed example path and `frontend/.gitignore` ignores `.env*` while allowing the example.

**Build:**
- Next config: `frontend/next.config.ts`.
- TypeScript config: `frontend/tsconfig.json`.
- PostCSS config: `frontend/postcss.config.mjs`.
- ESLint config: `frontend/eslint.config.mjs`.
- Prettier config: `frontend/.prettierrc` and `frontend/.prettierignore`.
- Jest config/setup: `frontend/jest.config.ts`, `frontend/jest.setup.js`, `frontend/polyfills.js`.
- Playwright config: `frontend/playwright.config.ts`.

**Path Aliases:**
- Use `@/*` for root-relative frontend imports, configured in `frontend/tsconfig.json` and mirrored for Jest in `frontend/jest.config.ts`.

## Frontend Entry Points

**Pages:**
- Home page: `frontend/app/page.tsx`.
- Tender workspace page: `frontend/app/tender/page.tsx`.
- Root layout and global metadata: `frontend/app/layout.tsx`.
- Global CSS and Tailwind theme: `frontend/app/globals.css`.

**Core Runtime Modules:**
- API client and endpoint helpers: `frontend/lib/api.ts`.
- API base URL resolution: `frontend/lib/apiBaseUrl.ts`.
- SSE client: `frontend/lib/sse.ts`.
- Chat/task SSE mapping: `frontend/hooks/useChatSSE.ts`.
- Form-to-API request conversion: `frontend/lib/formDataConverter.ts`.
- URL type mapping and canonical URL sync: `frontend/utils/tenderTypeMapper.ts`.
- Tender data fetch helper: `frontend/lib/tenderFetch.ts`.

## Platform Requirements

**Development:**
- Full system development assumes Windows plus Word COM for backend execution, while frontend logic itself runs as a browser/Next.js app; this cross-environment constraint is stated in `README.md` and `AGENTS.md`.
- WSL frontend execution must use Linux `node` and `npm`, with Linux temp directories for frontend tests; this validation rule is stated in `AGENTS.md`.
- Fresh frontend setup uses `npm ci` from `frontend/`, with `frontend/.env.local` and `frontend/node_modules` required by `README.md`, `scripts/start-dev.ps1`, and `scripts/start-dev-wsl.sh`.

**Production:**
- Production build/start are `next build` and `next start -p 8502` from `frontend/package.json`.
- Production cache headers are configured in `frontend/next.config.ts`.
- No frontend hosting platform configuration is detected in `frontend/`, root `README.md`, or `.github/workflows/` during this scoped scan.

---

*Stack analysis: 2026-05-22*
