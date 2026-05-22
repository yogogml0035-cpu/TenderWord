# Codebase Structure

**Analysis Date:** 2026-05-22

## Directory Layout

```text
frontend/
├── app/                         # Next.js App Router routes and global CSS
│   ├── page.tsx                 # `/` entry page
│   └── tender/page.tsx          # `/tender` three-column workspace
├── components/                  # React UI components
│   ├── chat/                    # Workspace, chat, task, and tender navigation UI
│   ├── forms/                   # Tender forms, shared form controls, uploads, template dialog
│   └── layout/                  # General page layout/sidebar/header components
├── hooks/                       # React hooks for URL parsing, hydration, SSE, heartbeats, polling
├── lib/                         # API client, SSE client, converters, tender lookup, utilities
├── stores/                      # Zustand stores for conversations, streams, sessions, history, UI
├── types/                       # Frontend tender, API, and chat TypeScript contracts
├── utils/                       # URL and tender type mapping helpers
├── __tests__/                   # Jest unit/integration tests and test utilities
├── e2e/                         # Playwright E2E specs
├── mocks/                       # MSW handlers/server for tests
├── test-shims/                  # Test-only module shims
├── .planning/codebase/          # Frontend-scoped GSD codebase maps
├── package.json                 # Frontend scripts and dependencies
├── next.config.ts               # Next.js runtime and API rewrite configuration
├── jest.config.ts               # Jest configuration
├── playwright.config.ts         # Playwright configuration
├── tsconfig.json                # TypeScript configuration and `@/*` alias
└── app/globals.css              # Tailwind import, CSS variables, shared utility classes
```

## Directory Purposes

**`frontend/app/`:**
- Purpose: Own Next.js route boundaries and global app styling.
- Contains: `frontend/app/layout.tsx`, `frontend/app/page.tsx`, `frontend/app/tender/page.tsx`, `frontend/app/globals.css`, and `frontend/app/favicon.ico`.
- Key files: `frontend/app/tender/page.tsx` for the main workspace; `frontend/app/layout.tsx` for app metadata and global CSS import.

**`frontend/components/chat/`:**
- Purpose: Own the three-column tender workspace, chat composer, conversation navigation, and task message presentation.
- Contains: `frontend/components/chat/TenderTypeSidebar.tsx`, `frontend/components/chat/FormPanel.tsx`, `frontend/components/chat/ChatPanel.tsx`, `frontend/components/chat/ChatInput.tsx`, `frontend/components/chat/MessageList.tsx`, `frontend/components/chat/TaskLogMessage.tsx`, `frontend/components/chat/TaskContentMessage.tsx`, `frontend/components/chat/TaskDownloadMessage.tsx`, and `frontend/components/chat/tenderFormRegistry.ts`.
- Key files: `frontend/components/chat/FormPanel.tsx` for generate tasks and task monitoring; `frontend/components/chat/ChatPanel.tsx` for chat/rewrite/edit flows; `frontend/components/chat/tenderFormRegistry.ts` for tender form registration.

**`frontend/components/forms/`:**
- Purpose: Own tender form implementation, shared input controls, upload controls, and template candidate selection UI.
- Contains: `frontend/components/forms/TenderFormShared.tsx`, thin wrappers in `frontend/components/forms/XjcgTenderForm.tsx`, `frontend/components/forms/GngkTenderForm.tsx`, `frontend/components/forms/GjgkTenderForm.tsx`, defaults in `frontend/components/forms/tenderFormConfig.ts`, upload UI in `frontend/components/forms/FileUploader.tsx`, and template dialog UI in `frontend/components/forms/TemplateCandidateDialog.tsx`.
- Key files: `frontend/components/forms/TenderFormShared.tsx` for form behavior; `frontend/components/forms/tenderFormConfig.ts` for insertion defaults; `frontend/components/forms/shared/` for reusable field/card/error components.

**`frontend/components/layout/`:**
- Purpose: Hold general layout/sidebar/header components outside the `/tender` three-column implementation.
- Contains: `frontend/components/layout/MainLayout.tsx`, `frontend/components/layout/Sidebar.tsx`, `frontend/components/layout/HistorySection.tsx`, and `frontend/components/layout/Header.tsx`.
- Key files: `frontend/components/layout/MainLayout.tsx` and `frontend/components/layout/Sidebar.tsx`.

**`frontend/hooks/`:**
- Purpose: Encapsulate browser/react side effects such as hydration detection, URL parsing, task SSE wiring, task heartbeat, and task status polling.
- Contains: `frontend/hooks/useHydrated.ts`, `frontend/hooks/useUrlParams.ts`, `frontend/hooks/useSSE.ts`, `frontend/hooks/useChatSSE.ts`, `frontend/hooks/useTaskHeartbeat.ts`, `frontend/hooks/useCurrentConversationTaskStatus.ts`, and `frontend/hooks/useLatestActiveTaskSummary.ts`.
- Key files: `frontend/hooks/useChatSSE.ts` for task event mapping; `frontend/hooks/useCurrentConversationTaskStatus.ts` for queue/running status polling; `frontend/hooks/useTaskHeartbeat.ts` for missing/terminal task detection.

**`frontend/lib/`:**
- Purpose: Hold non-component runtime helpers and backend-facing clients.
- Contains: `frontend/lib/api.ts`, `frontend/lib/apiBaseUrl.ts`, `frontend/lib/sse.ts`, `frontend/lib/formDataConverter.ts`, `frontend/lib/tenderFetch.ts`, `frontend/lib/chat-utils.ts`, and `frontend/lib/utils.ts`.
- Key files: `frontend/lib/api.ts` for endpoint helpers; `frontend/lib/formDataConverter.ts` for generate payload conversion; `frontend/lib/apiBaseUrl.ts` for backend URL resolution.

**`frontend/stores/`:**
- Purpose: Hold Zustand stores for persisted and transient client state.
- Contains: `frontend/stores/chatStore.ts`, `frontend/stores/chatStreamStore.ts`, `frontend/stores/chatTaskSessionStore.ts`, `frontend/stores/historyStore.ts`, and `frontend/stores/useAppStore.ts`.
- Key files: `frontend/stores/chatStore.ts` for conversations, drafts, tasks, unread state, and URL sync; `frontend/stores/chatStreamStore.ts` for live task stream state; `frontend/stores/chatTaskSessionStore.ts` for SSE resume metadata.

**`frontend/types/`:**
- Purpose: Hold TypeScript contracts used across frontend UI, stores, and API client.
- Contains: `frontend/types/index.ts`, `frontend/types/api.ts`, and `frontend/types/chat.ts`.
- Key files: `frontend/types/api.ts` for API/SSE/task contracts; `frontend/types/index.ts` for frontend tender identity types; `frontend/types/chat.ts` for conversation/message contracts.

**`frontend/utils/`:**
- Purpose: Hold pure utility modules that do not fit the shared `lib/` runtime helpers.
- Contains: `frontend/utils/tenderTypeMapper.ts`.
- Key files: `frontend/utils/tenderTypeMapper.ts` for purchase method mapping, URL parsing, and canonical URL construction.

**`frontend/__tests__/`:**
- Purpose: Hold Jest tests, test utilities, and mocks.
- Contains: Unit tests under `frontend/__tests__/unit/`, integration example tests under `frontend/__tests__/integration/`, mocks under `frontend/__tests__/mocks/`, and test utilities under `frontend/__tests__/utils/`.
- Key files: `frontend/__tests__/unit/lib/test_api.test.ts`, `frontend/__tests__/unit/lib/test_form_data_converter.test.ts`, `frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`, `frontend/__tests__/unit/stores/test_session_persistence.test.ts`, and component tests under `frontend/__tests__/unit/components/`.

**`frontend/e2e/`:**
- Purpose: Hold Playwright specs for browser-level user-visible behavior.
- Contains: `frontend/e2e/test_home.spec.ts` and `frontend/e2e/test_url_conversation.spec.ts`.
- Key files: `frontend/playwright.config.ts` sets `testDir: './e2e'` and `baseURL: 'http://localhost:8502'`.

**`frontend/mocks/`:**
- Purpose: Hold MSW mock handlers and server setup for frontend tests.
- Contains: `frontend/mocks/handlers.ts` and `frontend/mocks/server.ts`.
- Key files: `frontend/jest.config.ts` maps MSW modules and ignores mock folders for coverage.

**`frontend/.planning/codebase/`:**
- Purpose: Hold frontend-scoped GSD architecture and structure maps.
- Contains: `frontend/.planning/codebase/ARCHITECTURE.md` and `frontend/.planning/codebase/STRUCTURE.md`.
- Key files: These files are intentionally separate from root `.planning/codebase/`.

## Key File Locations

**Entry Points:**
- `frontend/app/layout.tsx`: Root layout and metadata.
- `frontend/app/page.tsx`: Home route linking to `/tender`.
- `frontend/app/tender/page.tsx`: Main workspace route, URL bootstrap, tender data prefetch, and conversation heartbeat.
- `frontend/package.json`: `npm run dev`, `npm run build`, `npm run lint`, `npm run type-check`, `npm run test`, and `npm run test:e2e`.

**Configuration:**
- `frontend/next.config.ts`: API rewrite, dev origin calculation, cache headers, image host, strict TypeScript build behavior.
- `frontend/tsconfig.json`: Strict TypeScript configuration, Next plugin, and `@/*` path alias.
- `frontend/jest.config.ts`: Jest with `next/jest`, jsdom, setup files, path aliases, coverage collection, and thresholds.
- `frontend/playwright.config.ts`: Playwright browser, base URL, web server command, retries, traces, screenshots, and video settings.
- `frontend/eslint.config.mjs`: Next core web vitals, Next TypeScript, ignored build outputs, and React hooks rule override.
- `frontend/.prettierrc`: Prettier formatting rules and Tailwind class sorting plugin.
- `frontend/postcss.config.mjs`: Tailwind 4 PostCSS plugin.
- `frontend/.nvmrc`: Node major version hint.
- `frontend/.env.local`: Environment configuration file present; do not read or quote values.
- `frontend/.env.local.example`: Environment example file present for local setup.

**Core Logic:**
- `frontend/lib/api.ts`: All typed API helpers, `ApiError`, upload/download helpers, task helpers, user stream NDJSON parser, and task stream URL builder.
- `frontend/lib/apiBaseUrl.ts`: Base URL candidate parsing and host-aware backend URL resolution.
- `frontend/lib/formDataConverter.ts`: Convert `XjcgTenderFormData`, `GngkTenderFormData`, and `GjgkTenderFormData` into `GenerateRequest`.
- `frontend/lib/tenderFetch.ts`: Fetch tender data and write tender lookup state into drafts.
- `frontend/lib/sse.ts`: Low-level `EventSource` connection with reconnect, heartbeat timeout, and Last-Event-ID query support.
- `frontend/utils/tenderTypeMapper.ts`: Purchase method to tender type mapping, canonical URL params, and URL parsing.
- `frontend/stores/chatStore.ts`: Conversation, draft, task, unread result, task message, and URL sync state.
- `frontend/hooks/useChatSSE.ts`: Task SSE event-to-store adapter.
- `frontend/hooks/useCurrentConversationTaskStatus.ts`: Queue/running status polling and overlay progress source.
- `frontend/hooks/useTaskHeartbeat.ts`: Task heartbeat polling for missing and terminal tasks.

**UI Composition:**
- `frontend/components/chat/TenderTypeSidebar.tsx`: Tender type navigation and conversation list.
- `frontend/components/chat/FormPanel.tsx`: Form panel orchestration and generate task lifecycle.
- `frontend/components/chat/ChatPanel.tsx`: Chat/rewrite/edit composer orchestration and downloads.
- `frontend/components/chat/MessageList.tsx`: Message rendering.
- `frontend/components/forms/TenderFormShared.tsx`: Shared tender form implementation.
- `frontend/components/forms/shared/`: Shared form UI primitives.

**Testing:**
- `frontend/__tests__/unit/app/test_chat_page.test.tsx`: Route-level workspace tests.
- `frontend/__tests__/unit/components/chat/`: Chat component tests.
- `frontend/__tests__/unit/components/forms/`: Form component tests.
- `frontend/__tests__/unit/hooks/`: Hook tests for SSE, heartbeat, and task status.
- `frontend/__tests__/unit/lib/`: API, SSE, converter, URL base, and chat utility tests.
- `frontend/__tests__/unit/stores/`: Store and session persistence tests.
- `frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`: URL/tender mapping tests.
- `frontend/e2e/test_home.spec.ts`: Home route E2E coverage.
- `frontend/e2e/test_url_conversation.spec.ts`: URL conversation behavior E2E coverage.

## Naming Conventions

**Files:**
- App Router pages use `page.tsx`, as in `frontend/app/page.tsx` and `frontend/app/tender/page.tsx`.
- React components use PascalCase filenames, as in `frontend/components/chat/ChatPanel.tsx`, `frontend/components/forms/TenderFormShared.tsx`, and `frontend/components/layout/MainLayout.tsx`.
- React hooks use `use*.ts`, as in `frontend/hooks/useChatSSE.ts`, `frontend/hooks/useUrlParams.ts`, and `frontend/hooks/useHydrated.ts`.
- Zustand stores use lower camelCase filenames ending in `Store.ts`, as in `frontend/stores/chatStore.ts`, `frontend/stores/historyStore.ts`, and `frontend/stores/useAppStore.ts`.
- Test files use `test_` prefixes, as in `frontend/__tests__/unit/lib/test_api.test.ts`, `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`, and `frontend/e2e/test_url_conversation.spec.ts`.
- Shared form exports use an `index.ts` barrel only inside `frontend/components/forms/shared/`.

**Directories:**
- UI is grouped by product surface under `frontend/components/chat/`, `frontend/components/forms/`, and `frontend/components/layout/`.
- Tests are grouped by type and module path under `frontend/__tests__/unit/`, `frontend/__tests__/integration/`, and `frontend/e2e/`.
- Runtime helpers are grouped under `frontend/lib/`; pure tender URL mapping lives under `frontend/utils/`.
- Frontend-scoped planning docs live under `frontend/.planning/codebase/`.

**Imports:**
- Use the `@/*` alias configured in `frontend/tsconfig.json` and `frontend/jest.config.ts` for cross-directory imports.
- Use relative imports for same-folder component relationships, as in `frontend/components/chat/ChatPanel.tsx` importing `./MessageList` and `./ChatInput`.
- Keep frontend contracts in `frontend/types/` and import type-only values with `import type` where possible, as seen in `frontend/components/chat/tenderFormRegistry.ts` and `frontend/lib/formDataConverter.ts`.

## Where to Add New Code

**New Workspace Route:**
- Primary code: `frontend/app/<route>/page.tsx`.
- Shared layout/components: `frontend/components/layout/` or a new domain folder under `frontend/components/`.
- Tests: `frontend/__tests__/unit/app/test_<route>_page.test.tsx` and `frontend/e2e/test_<route>.spec.ts`.

**New Tender Type:**
- Frontend type: `frontend/types/index.ts`.
- API form type union: `frontend/types/api.ts`.
- URL mapping and canonical params: `frontend/utils/tenderTypeMapper.ts`.
- Form wrapper: `frontend/components/forms/<Type>TenderForm.tsx`.
- Form defaults: `frontend/components/forms/tenderFormConfig.ts`.
- Registry entry: `frontend/components/chat/tenderFormRegistry.ts`.
- Form-to-API converter: `frontend/lib/formDataConverter.ts`.
- Sidebar display entry: `frontend/components/chat/TenderTypeSidebar.tsx`.
- Tests: `frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`, `frontend/__tests__/unit/lib/test_form_data_converter.test.ts`, `frontend/__tests__/unit/components/chat/test_tender_form_registry.test.tsx`, and a form test under `frontend/__tests__/unit/components/forms/`.

**New Form Control or Section:**
- Shared primitive: `frontend/components/forms/shared/`.
- Shared behavior in the tender form: `frontend/components/forms/TenderFormShared.tsx`.
- Type-specific thin wrapper only when the public form data type differs: `frontend/components/forms/XjcgTenderForm.tsx`, `frontend/components/forms/GngkTenderForm.tsx`, or `frontend/components/forms/GjgkTenderForm.tsx`.
- Tests: `frontend/__tests__/unit/components/forms/test_tender_form_shared.test.tsx` or a new `test_<control>.test.tsx` under `frontend/__tests__/unit/components/forms/`.

**New API Endpoint Helper:**
- Request/response types: `frontend/types/api.ts`.
- Helper function: `frontend/lib/api.ts`.
- Component usage: call the helper from the relevant component or hook, such as `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/chat/FormPanel.tsx`, or `frontend/components/chat/ChatPanel.tsx`.
- Tests: `frontend/__tests__/unit/lib/test_api.test.ts`.

**New SSE Event Type:**
- Event type contract: `frontend/types/api.ts`.
- EventSource listener if the backend event name is new: `frontend/lib/sse.ts`.
- Task event handling: `frontend/hooks/useChatSSE.ts`.
- Stream/task state shape if needed: `frontend/stores/chatStreamStore.ts` or `frontend/stores/chatStore.ts`.
- UI rendering: `frontend/components/chat/TaskLogMessage.tsx`, `frontend/components/chat/TaskContentMessage.tsx`, or a new component under `frontend/components/chat/`.
- Tests: `frontend/__tests__/unit/lib/test_sse.test.ts` and `frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`.

**New Store State:**
- Conversation-scoped persistent state: `frontend/stores/chatStore.ts`.
- Live task stream state: `frontend/stores/chatStreamStore.ts`.
- Persisted task stream resume metadata: `frontend/stores/chatTaskSessionStore.ts`.
- Sidebar/UI preferences: `frontend/stores/useAppStore.ts`.
- Generation history state: `frontend/stores/historyStore.ts`.
- Tests: `frontend/__tests__/unit/stores/`.

**New Template Candidate Behavior:**
- API types: `frontend/types/api.ts`.
- API helpers: `frontend/lib/api.ts`.
- Form orchestration: `frontend/components/forms/TenderFormShared.tsx`.
- Dialog presentation: `frontend/components/forms/TemplateCandidateDialog.tsx`.
- Tests: `frontend/__tests__/unit/components/forms/test_tender_form_shared.test.tsx` and `frontend/__tests__/unit/lib/test_api.test.ts`.

**New Utility:**
- Styling/class utilities: `frontend/lib/utils.ts`.
- Chat/conversation utilities: `frontend/lib/chat-utils.ts`.
- Tender URL/type mapping: `frontend/utils/tenderTypeMapper.ts`.
- API base URL behavior: `frontend/lib/apiBaseUrl.ts`.
- Tests: matching `frontend/__tests__/unit/lib/test_*.test.ts` or `frontend/__tests__/unit/utils/test_*.test.ts`.

## Special Directories

**`frontend/.next/`:**
- Purpose: Next.js build/dev output.
- Generated: Yes.
- Committed: No; ignored by `frontend/.prettierignore`, `frontend/eslint.config.mjs`, and standard Next.js workflows.

**`frontend/node_modules/`:**
- Purpose: Installed npm dependencies for `frontend/package.json`.
- Generated: Yes.
- Committed: No.

**`frontend/playwright-report/`:**
- Purpose: HTML report output from Playwright configured in `frontend/playwright.config.ts`.
- Generated: Yes.
- Committed: No; ignored by `frontend/eslint.config.mjs`.

**`frontend/test-results/`:**
- Purpose: Playwright failure artifacts such as screenshots and videos configured in `frontend/playwright.config.ts`.
- Generated: Yes.
- Committed: No; ignored by `frontend/eslint.config.mjs`.

**`frontend/.swc/`:**
- Purpose: SWC/Next compiler cache.
- Generated: Yes.
- Committed: No.

**`frontend/.planning/codebase/`:**
- Purpose: Frontend-scoped codebase maps for GSD planning.
- Generated: No.
- Committed: Yes, when frontend codebase maps are refreshed.

**`frontend/.env.local`:**
- Purpose: Local frontend environment configuration.
- Generated: Developer-local.
- Committed: No; do not read or quote values.

**`frontend/.env.local.example`:**
- Purpose: Example frontend environment configuration for setup.
- Generated: No.
- Committed: Yes.

---

*Structure analysis: 2026-05-22*
