# External Integrations

**Analysis Date:** 2026-05-22

## Scope

**Frontend-only map:**
- Integration evidence is limited to `frontend/` plus root setup constraints in `AGENTS.md`, `README.md`, `scripts/start-dev.ps1`, `scripts/start-dev-wsl.sh`, and `scripts/stop-build.ps1`.
- Backend implementation is not analyzed; backend routes are documented only as frontend-facing API/SSE/download contracts present in `frontend/lib/api.ts`, `frontend/lib/sse.ts`, `frontend/types/api.ts`, and frontend callers.

## APIs & External Services

**TenderWord backend HTTP API:**
- Service: backend REST-like API under `/api`.
  - SDK/Client: native `fetch` wrapped by `request<T>()`, `api.get/post/put/delete`, and specialized helpers in `frontend/lib/api.ts`.
  - Base URL: resolved by `resolveApiBaseUrl()` in `frontend/lib/apiBaseUrl.ts`; Next dev rewrites `/api/:path*` to the configured backend API in `frontend/next.config.ts`.
  - Auth: no `Authorization` or bearer-token handling is implemented in `frontend/lib/api.ts`; the scoped scan did not detect frontend auth wiring in `frontend/`.

**Tender lookup:**
- `GET /api/tender/{tender_no}` is called by `fetchTenderDataWithType()` and `fetchTenderData()` in `frontend/lib/api.ts`.
- Tender lookup results are normalized and written into form drafts by `frontend/lib/tenderFetch.ts`.
- URL-driven lookup is triggered from `frontend/app/tender/page.tsx` through `useUrlParams()` in `frontend/hooks/useUrlParams.ts`.

**Generation, edit, tasks, and queue state:**
- `POST /api/generate`, `POST /api/edit`, `GET /api/tasks/{task_id}`, `DELETE /api/tasks/{task_id}`, `POST /api/tasks/{task_id}/heartbeat`, and `GET /api/tasks` are wrapped in `frontend/lib/api.ts`.
- Generation submission is built by `frontend/components/chat/FormPanel.tsx` using converters from `frontend/components/chat/tenderFormRegistry.ts` and `frontend/lib/formDataConverter.ts`.
- Edit task creation is built by `frontend/components/chat/ChatPanel.tsx`, with `gngk` frontend type dispatch mirrored locally in `resolveEditFormType()` and generation dispatch mirrored in `frontend/lib/formDataConverter.ts`.
- Current task polling and queue progress are handled by `frontend/hooks/useCurrentConversationTaskStatus.ts`.
- Task heartbeat and missing-task cleanup are handled by `frontend/hooks/useTaskHeartbeat.ts`.

**User chat and rewrite routing stream:**
- `POST /api/user/stream` is consumed as newline-delimited JSON by `streamUserMessage()` and `streamNdjson()` in `frontend/lib/api.ts`.
- The stream parser accepts `route`, `task_accepted`, `chunk`, `done`, and `error` events typed in `frontend/types/api.ts`.
- `frontend/components/chat/ChatPanel.tsx` maps route events to normal chat, rewrite task creation, or edit task creation UI state.
- This stream uses `fetch` and `ReadableStream`, not `EventSource`, in `frontend/lib/api.ts`.

**SSE task progress stream:**
- `GET /api/stream/{task_id}` is the task progress EventSource endpoint produced by `getTaskStreamUrl()` in `frontend/lib/api.ts` and consumed by `frontend/lib/sse.ts`.
- `frontend/lib/sse.ts` creates `EventSource` connections, tracks `lastEventId`, deduplicates event ids, supports optional query-param resume, and can auto-reconnect.
- SSE event types are `connected`, `log`, `llm`, `progress`, `status`, `error`, `done`, and `heartbeat` in `frontend/types/api.ts`.
- `frontend/hooks/useChatSSE.ts` maps task SSE events into chat task log, content, and download messages stored by `frontend/stores/chatStore.ts` and transient stream state in `frontend/stores/chatStreamStore.ts`.
- Before resuming an existing running task, `frontend/hooks/useChatSSE.ts` checks `GET /api/tasks/{task_id}` and handles `TASK_NOT_FOUND` or `404` by discarding stale local state.

**File upload:**
- `POST /api/upload` and `POST /api/upload/multiple` are wrapped by `uploadFile()` and `uploadFiles()` in `frontend/lib/api.ts`.
- Upload requests use browser `FormData` and let the browser set multipart headers in `frontend/lib/api.ts`.
- Drag/drop and file input are implemented in `frontend/components/forms/FileUploader.tsx`.
- Edit-mode file upload in the chat composer uses `uploadFile(file, 'origin_tender')` in `frontend/components/chat/ChatPanel.tsx`.

**Generated document download:**
- `GET /api/download/{file_path}` is wrapped by `downloadFile()` and `getDownloadUrl()` in `frontend/lib/api.ts`.
- `downloadFile()` returns a `Blob`; `frontend/components/chat/ChatPanel.tsx` turns that blob into a browser object URL and clicks an anchor for download.
- Task completion output and style writeback summaries are carried in `SSEDoneEvent`, `TaskResult`, and `StyleWritebackSummary` in `frontend/types/api.ts`.

**Template candidates and template download proxy:**
- `GET /api/template-candidates`, `POST /api/template-candidates/select`, and `GET /api/template-candidates/download` are wrapped by `fetchTemplateCandidates()`, `selectTemplateCandidate()`, and `getTemplateCandidateDownloadUrl()` in `frontend/lib/api.ts`.
- `frontend/components/forms/TenderFormShared.tsx` loads candidates, selects candidates, and maps selected backend files back into upload state.
- `frontend/components/forms/TemplateCandidateDialog.tsx` renders candidate rows and uses the backend download proxy URL for template links.
- Frontend-only callers should keep using the project `/api/template-candidates*` helpers in `frontend/lib/api.ts`; `AGENTS.md` explicitly forbids direct external template-list or file-download calls from the frontend.

**Conversation heartbeat:**
- `POST /api/conversations/{conversation_id}/heartbeat` is wrapped by `sendConversationHeartbeat()` in `frontend/lib/api.ts`.
- `frontend/app/tender/page.tsx` sends heartbeat requests for known conversations and calls `handleBackendRestart()` from `frontend/stores/chatStore.ts` when the backend instance id changes.

## Data Storage

**Browser session storage:**
- Chat conversations, current conversation id, selected tender type, drafts, task summaries, and unread result flags persist under `chat-storage` using `sessionStorage` in `frontend/stores/chatStore.ts`.
- Generation history persists under `tender-history-storage` using `sessionStorage` in `frontend/stores/historyStore.ts`.
- Task SSE resume metadata persists under `chat-task-session-storage` using `sessionStorage` in `frontend/stores/chatTaskSessionStore.ts`.
- `frontend/__tests__/unit/stores/test_session_persistence.test.ts` verifies the chat, history, and task-session stores are present in `sessionStorage` and absent from `localStorage`.

**Transient in-memory state:**
- Active SSE logs, AI text snapshots, progress, node labels, and `lastEventId` are kept in-memory by `frontend/stores/chatStreamStore.ts`.
- Current page URL state is synchronized through `window.history.replaceState()` in `frontend/utils/tenderTypeMapper.ts`.

**Other persisted UI state:**
- Sidebar open state is persisted under `tender-app-storage` by `frontend/stores/useAppStore.ts`.
- `frontend/stores/useAppStore.ts` does not configure the `createJSONStorage(() => sessionStorage)` adapter used by `frontend/stores/chatStore.ts`, `frontend/stores/historyStore.ts`, and `frontend/stores/chatTaskSessionStore.ts`.

**Databases:**
- No frontend database client is detected in `frontend/package.json`, `frontend/lib/`, or `frontend/stores/`.

**File Storage:**
- Frontend does not write files directly to cloud or local disk; uploads and downloads are brokered through backend API helpers in `frontend/lib/api.ts`.
- Local browser download uses `Blob`, `window.URL.createObjectURL()`, anchor click, and `window.URL.revokeObjectURL()` in `frontend/components/chat/ChatPanel.tsx`.

**Caching:**
- No frontend cache service is detected in `frontend/package.json`.
- Browser/session persistence is implemented through Zustand middleware in `frontend/stores/chatStore.ts`, `frontend/stores/historyStore.ts`, `frontend/stores/chatTaskSessionStore.ts`, and `frontend/stores/useAppStore.ts`.
- Next production cache headers for static assets and page responses are configured in `frontend/next.config.ts`.

## Authentication & Identity

**Auth Provider:**
- Not detected in frontend scope. `frontend/lib/api.ts` does not attach auth headers, `frontend/types/api.ts` does not define login/session token models, and the scoped search found no frontend `Authorization` or bearer-token integration.

**Frontend identity model:**
- Conversation identity is local frontend state in `frontend/stores/chatStore.ts`.
- URL identity for tender conversations is represented by `tenderno`, `purchase_method`, `tender_lx`, and `fund_lx` parsed in `frontend/hooks/useUrlParams.ts` and canonicalized in `frontend/utils/tenderTypeMapper.ts`.
- `gngk` conversation matching includes `tenderType + tenderno + tender_lx + fund_lx` in `frontend/stores/chatStore.ts`.

## Browser & Runtime Boundaries

**Required browser APIs:**
- `fetch`, `Response`, `Blob`, `FormData`, `URLSearchParams`, `TextDecoder`, and `ReadableStream` are used by `frontend/lib/api.ts`.
- `EventSource` is required by `frontend/lib/sse.ts`.
- File input and drag/drop are used by `frontend/components/forms/FileUploader.tsx`.
- Object URLs are used by `frontend/components/chat/ChatPanel.tsx`.
- `sessionStorage` is used by `frontend/stores/chatStore.ts`, `frontend/stores/historyStore.ts`, and `frontend/stores/chatTaskSessionStore.ts`.
- `window.history.replaceState()` is used by `frontend/utils/tenderTypeMapper.ts`.

**Runtime event hooks:**
- Task heartbeat refreshes on `focus`, `pageshow`, `online`, and `visibilitychange` in `frontend/hooks/useTaskHeartbeat.ts`.
- Conversation heartbeat uses the same browser lifecycle events in `frontend/app/tender/page.tsx`.

**Test polyfills:**
- Jest polyfills `TextDecoder`, `TextEncoder`, `MessageChannel`, `ReadableStream`, `WritableStream`, and stream queuing strategies in `frontend/polyfills.js` and `frontend/polyfills.ts`.
- Jest setup mocks `matchMedia`, `ResizeObserver`, `IntersectionObserver`, `scrollTo`, `HTMLCanvasElement.getContext`, and `BroadcastChannel` in `frontend/jest.setup.js` and `frontend/jest.setup.ts`.

## Monitoring & Observability

**Error Tracking:**
- No Sentry, Datadog, LogRocket, analytics, or frontend observability SDK is detected in `frontend/package.json` or frontend source searches.

**Logs:**
- Frontend runtime logging uses `console.warn`, `console.log`, and `console.error` in `frontend/lib/sse.ts`, `frontend/components/chat/FormPanel.tsx`, and `frontend/components/chat/ChatPanel.tsx`.
- User-visible API errors use the `ApiError` class in `frontend/lib/api.ts` and UI handling in `frontend/components/chat/ChatPanel.tsx`, `frontend/components/chat/FormPanel.tsx`, and `frontend/components/forms/TenderFormShared.tsx`.
- Task progress and logs are frontend-consumed SSE data typed in `frontend/types/api.ts` and rendered through `frontend/hooks/useChatSSE.ts`, `frontend/stores/chatStore.ts`, and chat task components under `frontend/components/chat/`.

## CI/CD & Deployment

**Hosting:**
- No hosting platform file is detected in frontend scope; `frontend/next.config.ts` configures Next runtime behavior and production headers.

**CI Pipeline:**
- No `.github/workflows/` directory is detected during this scoped scan.
- Playwright behavior changes under `CI` in `frontend/playwright.config.ts`.
- `AGENTS.md` states frontend validation commands and that CI-grade browser coverage should be Playwright specs under `frontend/e2e/test_*.spec.ts`.

**Development launch:**
- `frontend/package.json` launches dev and production Next servers on port `8502`.
- `scripts/start-dev.ps1` validates frontend prerequisites and starts the frontend from Windows.
- `scripts/start-dev-wsl.sh` validates WSL prerequisites and runs `npm run dev` from `frontend/`.
- `scripts/stop-build.ps1` stops the recorded frontend process or frees the frontend port.

## Environment Configuration

**Required env vars / runtime flags:**
- `NEXT_PUBLIC_API_URL` - frontend API base URL candidate list, read in `frontend/lib/apiBaseUrl.ts` and `frontend/next.config.ts`.
- `NODE_ENV` - production header switch in `frontend/next.config.ts`.
- `CI` - Playwright retries/workers/forbidOnly/server reuse in `frontend/playwright.config.ts`.
- `PLAYWRIGHT_USE_SYSTEM_CHROME` - local Playwright browser channel selection in `frontend/playwright.config.ts`.
- `WSL_DISTRO_NAME` - WSL detection in `scripts/start-dev-wsl.sh`.

**Secrets location:**
- `frontend/.env.local` is present and required by startup scripts, but its contents must not be read or committed.
- `frontend/.env.local.example` is present as the committed example path; do not document its values.
- `frontend/.gitignore` ignores `.env*` and explicitly allows `frontend/.env.local.example`.
- `frontend/.npmrc` is present but contents are not read or documented.

## Webhooks & Callbacks

**Incoming:**
- Not applicable for frontend scope. The Next app in `frontend/app/` does not define frontend API route handlers in the scoped scan.

**Outgoing:**
- JSON HTTP requests go through `request<T>()` and helper functions in `frontend/lib/api.ts`.
- NDJSON chat/rewrite streaming goes through `streamNdjson()` and `streamUserMessage()` in `frontend/lib/api.ts`.
- SSE task progress goes through `createSSEConnection()` in `frontend/lib/sse.ts` and `useChatSSE()` in `frontend/hooks/useChatSSE.ts`.
- Browser lifecycle callbacks for task/conversation liveness are registered in `frontend/hooks/useTaskHeartbeat.ts` and `frontend/app/tender/page.tsx`.

---

*Integration audit: 2026-05-22*
