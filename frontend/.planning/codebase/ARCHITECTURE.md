<!-- refreshed: 2026-05-22 -->
# Architecture

**Analysis Date:** 2026-05-22

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                    Next.js App Router                        │
│  `frontend/app/layout.tsx`, `frontend/app/page.tsx`,          │
│  `frontend/app/tender/page.tsx`                               │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│                  Tender Workspace Shell                      │
├──────────────────┬──────────────────┬───────────────────────┤
│ Tender Type Nav  │ Form Panel       │ Chat / Task Panel      │
│ `frontend/components/chat/TenderTypeSidebar.tsx`              │
│ `frontend/components/chat/FormPanel.tsx`                      │
│ `frontend/components/chat/ChatPanel.tsx`                      │
└────────┬─────────┴────────┬─────────┴──────────┬────────────┘
         │                  │                     │
         ▼                  ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Client State and Runtime Streams                │
│ `frontend/stores/chatStore.ts`                               │
│ `frontend/stores/chatStreamStore.ts`                          │
│ `frontend/stores/chatTaskSessionStore.ts`                     │
└────────┬────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│              Frontend API / SSE Boundary                     │
│ `frontend/lib/api.ts`, `frontend/lib/sse.ts`,                 │
│ `frontend/hooks/useChatSSE.ts`, `frontend/hooks/useTaskHeartbeat.ts` |
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Root layout | Defines the app metadata, language, and global CSS import for every route. | `frontend/app/layout.tsx` |
| Home page | Provides the `/` entry screen and links users into the workspace route. | `frontend/app/page.tsx` |
| Tender page | Owns the three-column workspace, URL parameter intake, conversation bootstrap, tender-data prefetch, and conversation heartbeat. | `frontend/app/tender/page.tsx` |
| Tender type sidebar | Groups conversations by frontend tender type, creates/selects conversations, renames/deletes them, and syncs blank conversation URLs. | `frontend/components/chat/TenderTypeSidebar.tsx` |
| Form panel | Mounts the registered form for the selected tender type, creates generate tasks, attaches SSE and heartbeat monitoring, and renders queue/running overlays. | `frontend/components/chat/FormPanel.tsx` |
| Chat panel | Handles normal chat, rewrite routing, edit task creation, edit-file upload, task cancellation, message retry, and download actions. | `frontend/components/chat/ChatPanel.tsx` |
| Message list | Renders normal messages plus task log/content/download message variants. | `frontend/components/chat/MessageList.tsx` |
| Shared tender form | Implements tender lookup, file upload, template candidate selection, insertion anchors, generation style, style writeback mode, and form validation. | `frontend/components/forms/TenderFormShared.tsx` |
| Tender form registry | Maps `TenderType` values to display names, form components, and form-to-API converters. | `frontend/components/chat/tenderFormRegistry.ts` |
| API client | Centralizes JSON requests, upload, task creation/status/cancel/heartbeat, downloads, template candidates, SSE URL building, and user NDJSON streams. | `frontend/lib/api.ts` |
| SSE runtime | Wraps `EventSource` with reconnect, heartbeat timeout, Last-Event-ID query support, and duplicate event suppression. | `frontend/lib/sse.ts` |
| Main persisted store | Holds conversations, drafts, task summaries, task-message mappings, unread result state, selected type, and canonical URL sync helpers. | `frontend/stores/chatStore.ts` |
| Stream store | Holds in-memory task logs, AI text, progress, current node, and last SSE event id. | `frontend/stores/chatStreamStore.ts` |
| Task session store | Persists task stream resume metadata in `sessionStorage`. | `frontend/stores/chatTaskSessionStore.ts` |

## Pattern Overview

**Overall:** Client-heavy Next.js App Router workspace with Zustand session persistence and a centralized API/SSE boundary.

**Key Characteristics:**
- Use App Router pages only for route boundaries and workspace composition; the stateful `/tender` route is a client component in `frontend/app/tender/page.tsx`.
- Use three explicit workspace panels, not nested page subroutes, for the tender type list, form, and chat/task timeline in `frontend/components/chat/TenderTypeSidebar.tsx`, `frontend/components/chat/FormPanel.tsx`, and `frontend/components/chat/ChatPanel.tsx`.
- Use `frontend/stores/chatStore.ts` as the main session model and keep live SSE payload state in `frontend/stores/chatStreamStore.ts`.
- Use `frontend/lib/api.ts` for all backend-facing request helpers; API request and response shapes are mirrored in `frontend/types/api.ts`.
- Use `frontend/utils/tenderTypeMapper.ts` and `frontend/stores/chatStore.ts` for canonical URL construction and browser URL replacement.

## Layers

**Routing Layer:**
- Purpose: Define route boundaries and compose the workspace shell.
- Location: `frontend/app/`
- Contains: `frontend/app/layout.tsx`, `frontend/app/page.tsx`, `frontend/app/tender/page.tsx`, and `frontend/app/globals.css`.
- Depends on: Next.js App Router APIs from `next/link` and `next/navigation`, plus workspace components from `frontend/components/chat/`.
- Used by: Browser navigation to `/` and `/tender`; Playwright base routes in `frontend/e2e/test_home.spec.ts` and `frontend/e2e/test_url_conversation.spec.ts`.

**Workspace UI Layer:**
- Purpose: Present the three-column tender workflow and task state.
- Location: `frontend/components/chat/`
- Contains: Conversation navigation, form panel, chat panel, composer, message list, and task message components in `frontend/components/chat/TenderTypeSidebar.tsx`, `frontend/components/chat/FormPanel.tsx`, `frontend/components/chat/ChatPanel.tsx`, `frontend/components/chat/ChatInput.tsx`, `frontend/components/chat/TaskLogMessage.tsx`, `frontend/components/chat/TaskContentMessage.tsx`, and `frontend/components/chat/TaskDownloadMessage.tsx`.
- Depends on: Stores in `frontend/stores/`, hooks in `frontend/hooks/`, API helpers in `frontend/lib/api.ts`, and types in `frontend/types/`.
- Used by: `frontend/app/tender/page.tsx`.

**Form Layer:**
- Purpose: Capture tender-specific inputs, fetch tender metadata, upload files, select templates, validate submission readiness, and emit normalized form data.
- Location: `frontend/components/forms/`
- Contains: Shared implementation in `frontend/components/forms/TenderFormShared.tsx`, thin type wrappers in `frontend/components/forms/XjcgTenderForm.tsx`, `frontend/components/forms/GngkTenderForm.tsx`, `frontend/components/forms/GjgkTenderForm.tsx`, defaults in `frontend/components/forms/tenderFormConfig.ts`, upload controls in `frontend/components/forms/FileUploader.tsx`, and template candidate UI in `frontend/components/forms/TemplateCandidateDialog.tsx`.
- Depends on: `frontend/lib/tenderFetch.ts`, `frontend/lib/api.ts`, `frontend/utils/tenderTypeMapper.ts`, `frontend/stores/chatStore.ts`, and shared controls in `frontend/components/forms/shared/`.
- Used by: `frontend/components/chat/FormPanel.tsx` through `frontend/components/chat/tenderFormRegistry.ts`.

**State Layer:**
- Purpose: Store persistent session state, transient stream data, and UI history.
- Location: `frontend/stores/`
- Contains: Main chat/session/task store in `frontend/stores/chatStore.ts`, stream runtime in `frontend/stores/chatStreamStore.ts`, SSE resume metadata in `frontend/stores/chatTaskSessionStore.ts`, history state in `frontend/stores/historyStore.ts`, and sidebar/UI state in `frontend/stores/useAppStore.ts`.
- Depends on: Zustand and Zustand middleware declared in `frontend/package.json`, type contracts in `frontend/types/`, and URL sync helpers in `frontend/utils/tenderTypeMapper.ts`.
- Used by: Workspace components in `frontend/components/chat/`, layout components in `frontend/components/layout/`, and SSE hooks in `frontend/hooks/`.

**API and Streaming Layer:**
- Purpose: Own backend-facing HTTP calls, file downloads, NDJSON user streams, and task SSE streams.
- Location: `frontend/lib/` and `frontend/hooks/`
- Contains: API client in `frontend/lib/api.ts`, base URL resolver in `frontend/lib/apiBaseUrl.ts`, `EventSource` wrapper in `frontend/lib/sse.ts`, task SSE mapper in `frontend/hooks/useChatSSE.ts`, generic SSE hook in `frontend/hooks/useSSE.ts`, heartbeat hook in `frontend/hooks/useTaskHeartbeat.ts`, and task-status polling in `frontend/hooks/useCurrentConversationTaskStatus.ts`.
- Depends on: API event and model types in `frontend/types/api.ts`.
- Used by: `frontend/components/chat/FormPanel.tsx`, `frontend/components/chat/ChatPanel.tsx`, `frontend/components/forms/TenderFormShared.tsx`, and `frontend/components/forms/FileUploader.tsx`.

**Type and Mapping Layer:**
- Purpose: Centralize frontend tender identity, API request/response contracts, chat model types, and URL mapping.
- Location: `frontend/types/` and `frontend/utils/`
- Contains: `TenderType`, `TenderLx`, and `FundLx` in `frontend/types/index.ts`; API contracts in `frontend/types/api.ts`; chat/message contracts in `frontend/types/chat.ts`; URL and purchase-method mapping in `frontend/utils/tenderTypeMapper.ts`.
- Depends on: No runtime services.
- Used by: Forms, stores, API client, route bootstrap, and tests across `frontend/__tests__/unit/`.

## Data Flow

### `/tender` Deep-Link and Conversation Bootstrap

1. `frontend/hooks/useUrlParams.ts` parses `tender_lx`, `purchase_method`, `fund_lx`, and `tenderno` through `frontend/utils/tenderTypeMapper.ts`.
2. `frontend/app/tender/page.tsx` waits for hydration via `frontend/hooks/useHydrated.ts`, selects the URL tender type in `frontend/stores/chatStore.ts`, and computes a gngk identity key from `tenderType + tenderno + tender_lx + fund_lx`.
3. `frontend/app/tender/page.tsx` reuses an existing conversation with `findConversationByTenderNo` or `findGngkConversationByIdentity` from `frontend/stores/chatStore.ts`, or creates one with `createConversation`.
4. `frontend/app/tender/page.tsx` writes URL-derived `tender_lx` and `fund_lx` into the draft before `frontend/components/forms/TenderFormShared.tsx` initializes, preserving the draft-over-URL priority.
5. `frontend/app/tender/page.tsx` calls `syncTenderDataDraft` from `frontend/lib/tenderFetch.ts`, which calls `fetchTenderDataWithType` in `frontend/lib/api.ts` and updates `ConversationFormDraft` in `frontend/stores/chatStore.ts`.
6. `frontend/components/chat/FormPanel.tsx` and `frontend/components/chat/ChatPanel.tsx` read the current conversation and draft from `frontend/stores/chatStore.ts`.

### Generate Task Path

1. `frontend/components/forms/TenderFormShared.tsx` validates tender number, tender data, uploaded files, technical parameter files, and insertion anchors.
2. `frontend/components/chat/FormPanel.tsx` receives form data through `tenderFormComponentMap` in `frontend/components/chat/tenderFormRegistry.ts`.
3. `frontend/components/chat/FormPanel.tsx` selects the converter from `tenderFormConverterMap` in `frontend/components/chat/tenderFormRegistry.ts`.
4. `frontend/lib/formDataConverter.ts` maps frontend `TenderType` and gngk `tender_lx + fund_lx` to backend `GenerateRequest.form_type` values defined in `frontend/types/api.ts`.
5. `frontend/components/chat/FormPanel.tsx` calls `createGenerateTask` in `frontend/lib/api.ts`, then calls `startTask` in `frontend/stores/chatStore.ts`.
6. `frontend/components/chat/FormPanel.tsx` immediately calls `getTaskStatus` in `frontend/lib/api.ts` to hydrate queue/progress metadata into `taskSummaries` in `frontend/stores/chatStore.ts`.
7. `frontend/hooks/useCurrentConversationTaskStatus.ts` polls `getTaskStatus` and `getTaskList` from `frontend/lib/api.ts` for queue/running overlays.
8. `frontend/hooks/useChatSSE.ts` connects to `/api/stream/{taskId}` through `frontend/hooks/useSSE.ts` and `frontend/lib/sse.ts` once the task is running.
9. `frontend/hooks/useChatSSE.ts` maps `log`, `llm`, `progress`, `done`, and `error` events from `frontend/types/api.ts` into `frontend/stores/chatStreamStore.ts` and task messages in `frontend/stores/chatStore.ts`.
10. `frontend/components/chat/MessageList.tsx` renders the task group with `frontend/components/chat/TaskLogMessage.tsx`, `frontend/components/chat/TaskContentMessage.tsx`, and `frontend/components/chat/TaskDownloadMessage.tsx`.
11. `frontend/components/chat/ChatPanel.tsx` downloads completed files through `downloadFile` in `frontend/lib/api.ts`.

### Normal Chat, Rewrite, and Edit Path

1. `frontend/components/chat/ChatInput.tsx` keeps composer text in the current conversation draft through `frontend/components/chat/ChatPanel.tsx` and `frontend/stores/chatStore.ts`.
2. For normal chat, `frontend/components/chat/ChatPanel.tsx` calls `streamUserMessage` in `frontend/lib/api.ts`, which posts NDJSON to `/api/user/stream`.
3. `frontend/lib/api.ts` parses user stream events into the `UserStreamEvent` union from `frontend/types/api.ts`.
4. For `route: reply`, `frontend/components/chat/ChatPanel.tsx` appends chunk/done content to a normal AI message in `frontend/stores/chatStore.ts`.
5. For `route: rewrite`, `frontend/components/chat/ChatPanel.tsx` handles `task_accepted`, calls `startTask` in `frontend/stores/chatStore.ts`, and leaves task progress to `frontend/hooks/useChatSSE.ts`.
6. For edit mode, `frontend/components/chat/ChatPanel.tsx` uploads the edit file through `uploadFile` in `frontend/lib/api.ts`, builds an `EditTaskRequest` from `frontend/types/api.ts`, calls `createEditTask`, and starts the accepted task in `frontend/stores/chatStore.ts`.
7. `frontend/components/chat/ChatPanel.tsx` cancels a normal stream through an `AbortController` and cancels task work through `cancelTask` in `frontend/lib/api.ts`.

### Template Candidate Path

1. `frontend/components/forms/TenderFormShared.tsx` opens `frontend/components/forms/TemplateCandidateDialog.tsx` from the file-upload section.
2. `frontend/components/forms/TenderFormShared.tsx` calls `fetchTemplateCandidates` in `frontend/lib/api.ts` with tender number and optional project name.
3. `frontend/components/forms/TemplateCandidateDialog.tsx` displays `TemplateCandidate` rows from `frontend/types/api.ts` and builds stable row keys with `buildTemplateCandidateRowKey`.
4. `frontend/components/forms/TenderFormShared.tsx` calls `selectTemplateCandidate` in `frontend/lib/api.ts`, converts selected backend files into `UploadedFile` objects, and writes them to the draft file cache in `frontend/stores/chatStore.ts`.
5. `frontend/components/forms/TemplateCandidateDialog.tsx` uses `getTemplateCandidateDownloadUrl` from `frontend/lib/api.ts` for candidate download links.

**State Management:**
- Persistent conversation, draft, task summary, and unread-result state belongs in `frontend/stores/chatStore.ts` and is persisted with `createJSONStorage(() => sessionStorage)`.
- Persisted task stream resume metadata belongs in `frontend/stores/chatTaskSessionStore.ts` and is persisted with `createJSONStorage(() => sessionStorage)`.
- Live stream payloads belong in `frontend/stores/chatStreamStore.ts` and are cleared after terminal task handling in `frontend/hooks/useChatSSE.ts` and `frontend/components/chat/FormPanel.tsx`.
- UI-only sidebar state belongs in `frontend/stores/useAppStore.ts`; generation history snapshots belong in `frontend/stores/historyStore.ts`.

## Key Abstractions

**TenderType:**
- Purpose: Frontend tender family identifier for `xjcg`, `gngk`, and `gjgk`.
- Examples: `frontend/types/index.ts`, `frontend/components/chat/tenderFormRegistry.ts`, `frontend/utils/tenderTypeMapper.ts`.
- Pattern: Use `TenderType` for frontend routing, UI grouping, and form component selection; convert to backend `form_type` only at API request boundaries.

**GenerateRequest and EditTaskRequest:**
- Purpose: Typed frontend mirrors of task creation payloads.
- Examples: `frontend/types/api.ts`, `frontend/lib/formDataConverter.ts`, `frontend/components/chat/ChatPanel.tsx`.
- Pattern: Generate requests are produced by converter functions in `frontend/lib/formDataConverter.ts`; edit requests are built in `frontend/components/chat/ChatPanel.tsx`.

**ConversationFormDraft:**
- Purpose: Per-conversation persisted form/composer state.
- Examples: `frontend/stores/chatStore.ts`, `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/chat/ChatInput.tsx`.
- Pattern: Forms and chat panels write draft updates through `updateConversationDraft`; do not create independent local persistence for conversation-scoped form state.

**Task Message Group:**
- Purpose: Bind one task id to separate log, content, and download AI messages.
- Examples: `TaskMessageGroupIds` and `LocatedTaskMessageGroup` in `frontend/stores/chatStore.ts`; renderers in `frontend/components/chat/TaskLogMessage.tsx`, `frontend/components/chat/TaskContentMessage.tsx`, and `frontend/components/chat/TaskDownloadMessage.tsx`.
- Pattern: Use `startTask`, `ensureTaskLogMessage`, `ensureTaskContentMessage`, `completeTask`, `failTask`, and `cancelTask` from `frontend/stores/chatStore.ts` instead of appending ad hoc task messages.

**SSE Stream State:**
- Purpose: Hold transient logs, AI text, progress, current node, and last event id for running tasks.
- Examples: `frontend/stores/chatStreamStore.ts`, `frontend/hooks/useChatSSE.ts`, `frontend/lib/sse.ts`.
- Pattern: `useChatSSE` translates backend event names into store updates and terminal task transitions.

**Canonical URL Parameters:**
- Purpose: Keep browser query parameters aligned with selected conversation identity.
- Examples: `buildCanonicalSearchParams` and `syncBrowserUrlToConversation` in `frontend/utils/tenderTypeMapper.ts`; `syncUrlToCurrentConversation` in `frontend/stores/chatStore.ts`.
- Pattern: Update URL through these helpers only; do not patch individual query parameters in components.

**Tender Form Registry:**
- Purpose: Single frontend registry for tender display names, form components, and generate converters.
- Examples: `frontend/components/chat/tenderFormRegistry.ts`, form wrappers in `frontend/components/forms/XjcgTenderForm.tsx`, `frontend/components/forms/GngkTenderForm.tsx`, and `frontend/components/forms/GjgkTenderForm.tsx`.
- Pattern: Add or change a tender form through the registry plus converter map, not by branching in `frontend/components/chat/FormPanel.tsx`.

## Entry Points

**Home Route:**
- Location: `frontend/app/page.tsx`
- Triggers: Browser navigation to `/`.
- Responsibilities: Link users to `/tender` and render a small feature overview.

**Tender Workspace Route:**
- Location: `frontend/app/tender/page.tsx`
- Triggers: Browser navigation to `/tender` with or without canonical query parameters.
- Responsibilities: Parse URL parameters, select or create conversations, fetch tender data, run conversation heartbeat, and render `TenderTypeSidebar`, `FormPanel`, and `ChatPanel`.

**Development Server:**
- Location: `frontend/package.json`
- Triggers: `npm run dev`.
- Responsibilities: Runs Next.js on port `8502`.

**Next Configuration:**
- Location: `frontend/next.config.ts`
- Triggers: Next.js dev/build/start lifecycle.
- Responsibilities: Computes allowed dev origins, proxies `/api/:path*` to the resolved backend base URL, sets production cache headers, configures localhost backend images, and enables strict TypeScript build behavior.

**API Boundary:**
- Location: `frontend/lib/api.ts`
- Triggers: Form submission, chat streams, task status polling, uploads, downloads, template candidate actions, and heartbeats.
- Responsibilities: Normalize request headers/body, parse wrapped API success/error payloads, throw `ApiError`, and expose typed endpoint helpers.

**SSE Boundary:**
- Location: `frontend/hooks/useChatSSE.ts`
- Triggers: Active task state in `frontend/components/chat/FormPanel.tsx`.
- Responsibilities: Confirm task state before connecting, map SSE payloads to stores, finalize terminal tasks, and recover from missing tasks.

## Architectural Constraints

- **Runtime:** Next.js, React, Tailwind, and Zustand versions are declared in `frontend/package.json`; Node `>=20.9.0` is required by `frontend/package.json` and `frontend/.nvmrc`.
- **API prefix:** Frontend requests target `/api/...` helpers in `frontend/lib/api.ts`, while dev rewrites proxy `/api/:path*` in `frontend/next.config.ts`.
- **Base URL:** Resolve API base URL through `frontend/lib/apiBaseUrl.ts`; it reads `NEXT_PUBLIC_API_URL` candidates and can derive the backend host from `window.location`.
- **Global state:** Shared mutable client state is intentionally concentrated in Zustand stores under `frontend/stores/`.
- **Session persistence:** Conversation state, drafts, task summaries, task stream sessions, history, and sidebar state use browser storage in `frontend/stores/chatStore.ts`, `frontend/stores/chatTaskSessionStore.ts`, `frontend/stores/historyStore.ts`, and `frontend/stores/useAppStore.ts`.
- **Hydration:** Components that read persisted session state gate user-visible state with `frontend/hooks/useHydrated.ts`.
- **URL identity:** Canonical URL construction is centralized in `frontend/utils/tenderTypeMapper.ts` and `frontend/stores/chatStore.ts`.
- **gngk identity:** `frontend/app/tender/page.tsx` and `frontend/stores/chatStore.ts` match gngk conversations by `tenderno + tender_lx + fund_lx`.
- **SSE resume:** `frontend/lib/sse.ts`, `frontend/hooks/useChatSSE.ts`, and `frontend/stores/chatTaskSessionStore.ts` preserve `lastEventId` for late join or refresh recovery.
- **Circular imports:** No circular dependency tooling was detected; import direction should remain pages -> components -> hooks/stores/lib/types based on imports observed in `frontend/app/tender/page.tsx`, `frontend/components/chat/FormPanel.tsx`, `frontend/components/forms/TenderFormShared.tsx`, and `frontend/stores/chatStore.ts`.
- **Authentication:** Not detected in the frontend; `frontend/lib/api.ts` does not attach auth headers.

## Anti-Patterns

### Raw Backend Calls in Components

**What happens:** Components could call `fetch` directly instead of adding typed helpers.
**Why it's wrong:** Error normalization, wrapped response handling, base URL resolution, and request serialization live in `frontend/lib/api.ts`.
**Do this instead:** Add a helper in `frontend/lib/api.ts`, mirror the contract in `frontend/types/api.ts`, and call the helper from components such as `frontend/components/forms/TenderFormShared.tsx` or `frontend/components/chat/ChatPanel.tsx`.

### URL Query Patching Outside the Mapper

**What happens:** Components could manually mutate individual query parameters.
**Why it's wrong:** gngk conversation identity depends on multiple parameters staying synchronized.
**Do this instead:** Use `syncBrowserUrlToConversation` and `buildCanonicalSearchParams` in `frontend/utils/tenderTypeMapper.ts`, or the store-level `syncUrlToCurrentConversation` in `frontend/stores/chatStore.ts`.

### Duplicated Tender Type Registration

**What happens:** A new tender type could be added only in one UI component or only in an API converter.
**Why it's wrong:** The frontend tender type appears in `frontend/types/index.ts`, `frontend/utils/tenderTypeMapper.ts`, `frontend/components/chat/tenderFormRegistry.ts`, `frontend/components/forms/tenderFormConfig.ts`, `frontend/lib/formDataConverter.ts`, and tests under `frontend/__tests__/unit/`.
**Do this instead:** Update the type, URL mapper, registry, form defaults, converter, API type union, and related tests together.

### Ad Hoc Task Message Mutation

**What happens:** Components could append task log/content/download messages directly.
**Why it's wrong:** Terminal cleanup, unread result marking, task-message grouping, stream clearing, and backend restart handling are implemented in `frontend/stores/chatStore.ts`.
**Do this instead:** Use task methods from `frontend/stores/chatStore.ts` and stream updates from `frontend/hooks/useChatSSE.ts`.

## Error Handling

**Strategy:** Normalize backend errors into `ApiError`, show user-facing messages in the UI, and keep task terminal state consistent through store transitions.

**Patterns:**
- JSON request errors are parsed by `buildApiError` and thrown as `ApiError` in `frontend/lib/api.ts`.
- Chat and form components display `ApiError.message` through composer notices, form errors, template dialog errors, or task messages in `frontend/components/chat/ChatPanel.tsx` and `frontend/components/forms/TenderFormShared.tsx`.
- Missing or terminal tasks are detected by `frontend/hooks/useTaskHeartbeat.ts`, `frontend/hooks/useCurrentConversationTaskStatus.ts`, and `frontend/hooks/useChatSSE.ts`, then reconciled through `discardStaleTask`, `completeTask`, `failTask`, or `cancelTask` in `frontend/stores/chatStore.ts`.
- Backend restart is detected through conversation heartbeat in `frontend/app/tender/page.tsx` and handled by `handleBackendRestart` in `frontend/stores/chatStore.ts`.
- Download failures in `frontend/components/chat/ChatPanel.tsx` currently log to console and show an alert.

## Cross-Cutting Concerns

**Logging:** User-visible task logs are rendered by `frontend/components/chat/TaskLogMessage.tsx`; debug and failure messages use `console.error` or `console.warn` in `frontend/lib/sse.ts`, `frontend/components/chat/FormPanel.tsx`, and `frontend/components/chat/ChatPanel.tsx`.

**Validation:** URL validation lives in `frontend/utils/tenderTypeMapper.ts` and `frontend/hooks/useUrlParams.ts`; form validation lives in `frontend/components/forms/TenderFormShared.tsx`; API payload parsing lives in `frontend/lib/api.ts`; type-level contracts live in `frontend/types/api.ts`.

**Authentication:** Not detected in frontend files; `frontend/lib/api.ts` makes unauthenticated browser requests.

**Styling:** Tailwind 4 is configured through `frontend/app/globals.css` and `frontend/postcss.config.mjs`; shared class merging uses `cn` from `frontend/lib/utils.ts`.

**Testing Hooks:** Architecture-critical flows have unit and E2E coverage locations in `frontend/__tests__/unit/` and `frontend/e2e/`; Playwright uses `http://localhost:8502` in `frontend/playwright.config.ts`.

---

*Architecture analysis: 2026-05-22*
