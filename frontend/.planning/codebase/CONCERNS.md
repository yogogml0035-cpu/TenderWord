# Codebase Concerns

**Analysis Date:** 2026-05-22

**Scope:** Frontend only: `frontend/`, with frontend constraints from `AGENTS.md` and `README.md`. Backend implementation is not analyzed except where frontend request, SSE, download, or task contracts create frontend risk.

## Tech Debt

**Monolithic form, chat, and store modules:**
- Issue: The highest-risk frontend behavior is concentrated in very large files: `frontend/components/forms/TenderFormShared.tsx`, `frontend/stores/chatStore.ts`, `frontend/components/chat/ChatPanel.tsx`, `frontend/components/chat/FormPanel.tsx`, `frontend/hooks/useChatSSE.ts`, and `frontend/lib/api.ts`.
- Files: `frontend/components/forms/TenderFormShared.tsx`, `frontend/stores/chatStore.ts`, `frontend/components/chat/ChatPanel.tsx`, `frontend/components/chat/FormPanel.tsx`, `frontend/hooks/useChatSSE.ts`, `frontend/lib/api.ts`
- Impact: Changes to form initialization, URL sync, template candidates, task lifecycle, edit/rewrite, and SSE completion require editing broad components with many local helpers and effects.
- Fix approach: Extract focused units before feature work: `frontend/components/forms/TenderFormShared.tsx` should split template candidate loading, insertion config state, and upload sections; `frontend/stores/chatStore.ts` should split task-message lifecycle helpers from conversation draft/session helpers; `frontend/components/chat/ChatPanel.tsx` should split normal chat stream, rewrite task acceptance, edit task creation, and download handling.

**Tender type identity and backend `form_type` routing are duplicated:**
- Issue: `gngk` form-type routing exists in both generate and edit paths instead of a single shared resolver.
- Files: `frontend/lib/formDataConverter.ts`, `frontend/components/chat/ChatPanel.tsx`, `frontend/utils/tenderTypeMapper.ts`, `frontend/components/chat/tenderFormRegistry.ts`, `frontend/types/api.ts`, `AGENTS.md`
- Impact: A new tender subtype or a rule change such as `tender_lx=1` engineering behavior can diverge between generate, rewrite, edit, URL identity, and registry behavior.
- Fix approach: Add a shared frontend resolver module for tender identity and backend form type under `frontend/utils/` or `frontend/lib/`, then make `frontend/lib/formDataConverter.ts` and `frontend/components/chat/ChatPanel.tsx` call that resolver. Keep tests in `frontend/__tests__/unit/lib/test_form_data_converter.test.ts`, `frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`, and `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`.

**Conversation persistence API is stubbed while UI state is local-only:**
- Issue: Conversation API helpers return mock success or no-op data instead of calling backend endpoints.
- Files: `frontend/lib/api.ts`, `frontend/stores/chatStore.ts`, `frontend/stores/chatTaskSessionStore.ts`, `frontend/stores/historyStore.ts`, `AGENTS.md`
- Impact: Future code may assume `saveConversation`, `getConversations`, `deleteConversation`, or `updateConversationTitle` persist data, while the current source of truth is `sessionStorage`.
- Fix approach: Either remove unused API helpers from `frontend/lib/api.ts` or implement real endpoints and update `frontend/types/api.ts`, `frontend/stores/chatStore.ts`, and tests together.

**Legacy history/sidebar path is separate from the active tender workspace:**
- Issue: `frontend/stores/historyStore.ts`, `frontend/components/layout/HistorySection.tsx`, `frontend/components/layout/Sidebar.tsx`, and `frontend/components/layout/MainLayout.tsx` define a history UI/store, but the active tender page uses `frontend/components/chat/TenderTypeSidebar.tsx` and `frontend/stores/chatStore.ts`.
- Files: `frontend/stores/historyStore.ts`, `frontend/components/layout/HistorySection.tsx`, `frontend/components/layout/Sidebar.tsx`, `frontend/components/layout/MainLayout.tsx`, `frontend/app/tender/page.tsx`, `frontend/components/chat/TenderTypeSidebar.tsx`
- Impact: There are two history/session concepts. The layout history download link also constructs `/api/download/...` directly instead of using `frontend/lib/api.ts`.
- Fix approach: Treat `frontend/stores/chatStore.ts` as the active session source. Remove or reconnect the legacy history path before adding generation history features.

**API parsing assumes JSON for several endpoints:**
- Issue: The generic request helper and tender lookup path call `response.json()` directly.
- Files: `frontend/lib/api.ts`
- Impact: Empty responses, HTML error pages, reverse-proxy errors, or backend 204 responses can surface as raw `SyntaxError` instead of the expected `ApiError` contract.
- Fix approach: Reuse `parseJsonSafely` in `request` and `fetchTenderDataWithType`, and keep `ApiError.code` / `ApiError.status` stable for callers in `frontend/components/chat/FormPanel.tsx`, `frontend/components/chat/ChatPanel.tsx`, and `frontend/components/forms/TenderFormShared.tsx`.

**Frontend task result contract handles style writeback but not comment writeback:**
- Issue: Frontend types and task completion plumbing preserve `style_writeback`, while `comment_writeback_*` fields are not represented.
- Files: `frontend/types/api.ts`, `frontend/hooks/useChatSSE.ts`, `frontend/stores/chatStore.ts`, `frontend/components/chat/TaskDownloadMessage.tsx`, `AGENTS.md`
- Impact: If backend task results or SSE `done` events include comment writeback summaries, the frontend can drop them from message metadata and UI state.
- Fix approach: Add explicit `CommentWritebackSummary` types in `frontend/types/api.ts`, parse them in `frontend/hooks/useChatSSE.ts`, persist them in `frontend/stores/chatStore.ts`, and add assertions in `frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`.

**Local dependency installation drift is visible:**
- Issue: `npm ls` reports installed `frontend/node_modules/eslint-config-next` and `frontend/node_modules/jest` versions that do not satisfy `frontend/package.json`, while `frontend/package-lock.json` resolves different versions.
- Files: `frontend/package.json`, `frontend/package-lock.json`, `frontend/node_modules/`
- Impact: Local lint/test behavior can differ from a clean `npm ci`, which makes failures hard to reproduce.
- Fix approach: Run clean install with `npm ci` in `frontend/`, then keep `frontend/package.json` and `frontend/package-lock.json` synchronized.

## Known Bugs

**URL fetch failure advertises retry but only closes the message:**
- Symptoms: The failed tender-data overlay says users can retry, but the only visible action clears the error, and the URL-processing key is recorded before `syncTenderDataDraft` finishes.
- Files: `frontend/app/tender/page.tsx`, `frontend/lib/tenderFetch.ts`
- Trigger: Open `/tender` with a valid tender URL whose `/api/tender/{tenderno}` request fails, then try the same URL again without changing parameters.
- Workaround: Manually change the URL or tender number to force a different processing key.

**Non-JSON API failures can bypass frontend error normalization:**
- Symptoms: `request` and `fetchTenderDataWithType` can throw JSON parsing errors that do not include `ApiError.code` or `ApiError.status`.
- Files: `frontend/lib/api.ts`
- Trigger: Backend, proxy, or Next rewrite returns an empty body or non-JSON error body for JSON endpoints such as `/api/tasks/{taskId}` or `/api/tender/{tenderno}`.
- Workaround: Callers catch generic errors in some places, but UI loses stable error codes and statuses.

**File extension enforcement is only a browser hint for shared uploads:**
- Symptoms: Shared form uploads pass `accept=".doc,.docx"`, but validation only checks file size.
- Files: `frontend/components/forms/FileUploader.tsx`, `frontend/components/forms/TenderFormShared.tsx`
- Trigger: Drag-and-drop a non-Word file into the shared uploader.
- Workaround: Backend upload validation must reject invalid files; frontend should add extension/MIME checks for immediate feedback.

**Legacy download link bypasses the central API helper:**
- Symptoms: The layout sidebar builds a direct `/api/download/${encodeURIComponent(item.outputFile)}` href and does not include `download_name`.
- Files: `frontend/components/layout/Sidebar.tsx`, `frontend/lib/api.ts`
- Trigger: A history item with `outputFile` is rendered through the legacy layout sidebar.
- Workaround: Use active chat download messages through `frontend/components/chat/TaskDownloadMessage.tsx` and `frontend/components/chat/ChatPanel.tsx`.

## Security Considerations

**Production security headers are minimal:**
- Risk: Production headers set cache behavior but do not set CSP, `X-Frame-Options` or `frame-ancestors`, `X-Content-Type-Options`, `Referrer-Policy`, or permissions policy.
- Files: `frontend/next.config.ts`
- Current mitigation: Next.js escapes React-rendered content in `frontend/components/chat/MessageList.tsx` and template strings in `frontend/components/forms/TemplateCandidateDialog.tsx`.
- Recommendations: Add security headers in `frontend/next.config.ts` before exposing the frontend outside a trusted local/LAN environment.

**Session storage contains tender workflow state and message content:**
- Risk: Tender numbers, project data, chat messages, task summaries, and upload metadata are stored in browser `sessionStorage`.
- Files: `frontend/stores/chatStore.ts`, `frontend/stores/chatTaskSessionStore.ts`, `frontend/stores/historyStore.ts`
- Current mitigation: State is page-session scoped rather than persisted to `localStorage`.
- Recommendations: Keep sensitive customer text out of logs and avoid adding long-term browser persistence without a retention policy and cleanup path.

**API base URL accepts public runtime configuration:**
- Risk: All frontend API calls resolve from `NEXT_PUBLIC_API_URL` or derived host logic, and malformed or unintended candidates can become request targets.
- Files: `frontend/lib/apiBaseUrl.ts`, `frontend/next.config.ts`, `README.md`
- Current mitigation: `frontend/lib/apiBaseUrl.ts` prefers candidates matching the current host or localhost aliases when `window.location` exists.
- Recommendations: Validate allowed protocols/hosts explicitly and document deployment-safe values without committing `.env` contents.

**Template candidate downloads rely entirely on backend proxy safety:**
- Risk: Candidate file URLs are passed to the project download proxy, and the frontend does not validate protocols or hosts before rendering links.
- Files: `frontend/lib/api.ts`, `frontend/components/forms/TemplateCandidateDialog.tsx`, `AGENTS.md`
- Current mitigation: `AGENTS.md` requires backend whitelist enforcement for external download links.
- Recommendations: Keep frontend calls routed only through `/api/template-candidates/download` and avoid direct external URLs in components.

**Dev dependency audit reports moderate vulnerabilities:**
- Risk: `npm audit --json` reports moderate issues in development dependencies, including `brace-expansion`, `ws`, and direct dependency `und` via `uuid`.
- Files: `frontend/package.json`, `frontend/package-lock.json`
- Current mitigation: `npm audit --omit=dev --json` reports no production vulnerabilities.
- Recommendations: Remove unused direct dependencies such as `und` and `undici` if they remain unreferenced in frontend source, then refresh `frontend/package-lock.json`.

## Performance Bottlenecks

**Task log streaming grows without a frontend cap:**
- Problem: `appendLog` copies and appends the full log array for each SSE log, and `TaskLogMessage` renders all normalized logs.
- Files: `frontend/stores/chatStreamStore.ts`, `frontend/hooks/useChatSSE.ts`, `frontend/components/chat/TaskLogMessage.tsx`
- Cause: `frontend/hooks/useSSE.ts` bounds generic message history, but task-specific logs in `frontend/stores/chatStreamStore.ts` are unbounded until task cleanup.
- Improvement path: Cap task log arrays, keep a summarized overflow count, and move full diagnostic detail out of user-visible state.

**Conversation heartbeat scales with all session conversations:**
- Problem: The tender page sends heartbeat requests for every conversation ID every 30 seconds and again on focus, `pageshow`, online, and visibility changes.
- Files: `frontend/app/tender/page.tsx`, `frontend/lib/api.ts`
- Cause: `frontend/app/tender/page.tsx` builds `conversationIdsKey` from all conversations in `frontend/stores/chatStore.ts`.
- Improvement path: Heartbeat only conversations with active or resumable tasks, or add a batched backend heartbeat endpoint and a frontend debouncer.

**Template candidate cache is unbounded per mounted form:**
- Problem: Template candidate responses are cached by tender number and project name without eviction.
- Files: `frontend/components/forms/TenderFormShared.tsx`
- Cause: `templateCandidateCache` grows with every unique tender/project key while the form component remains mounted.
- Improvement path: Keep only the latest key or use a small LRU cache for `frontend/components/forms/TenderFormShared.tsx`.

**Large shared form state causes broad rerender risk:**
- Problem: `TenderFormShared` owns upload state, URL-derived defaults, fetched tender data, insertion config caches, generation style caches, template candidate modal state, and submit validation.
- Files: `frontend/components/forms/TenderFormShared.tsx`
- Cause: Many concerns are stateful inside one component and many handlers depend on shared draft state.
- Improvement path: Extract `useTenderInsertionConfig`, `useTemplateCandidates`, and `useTenderDraftSync` hooks with focused tests.

## Fragile Areas

**SSE terminal handling spans several independent mechanisms:**
- Files: `frontend/lib/sse.ts`, `frontend/hooks/useSSE.ts`, `frontend/hooks/useChatSSE.ts`, `frontend/hooks/useTaskHeartbeat.ts`, `frontend/components/chat/FormPanel.tsx`, `frontend/components/chat/ChatPanel.tsx`, `frontend/stores/chatStore.ts`
- Why fragile: Task completion can arrive through SSE `done`, SSE `error`, heartbeat terminal state, task status fallback, cancel response, or backend restart detection.
- Safe modification: Keep all new task states and event types covered in `frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`, `frontend/__tests__/unit/hooks/test_use_task_heartbeat.test.tsx`, `frontend/__tests__/unit/components/chat/test_form_panel.test.tsx`, and `frontend/e2e/test_url_conversation.spec.ts`.
- Test coverage: Unit coverage exists for key hooks, but browser E2E only covers a stale task and does not cover a full mocked SSE success/download path.

**Persisted `sessionStorage` schema has no explicit migration layer:**
- Files: `frontend/stores/chatStore.ts`, `frontend/stores/chatTaskSessionStore.ts`, `frontend/stores/historyStore.ts`, `frontend/stores/useAppStore.ts`
- Why fragile: Zustand persist defaults to versioned storage behavior, but these stores do not define explicit `version` or `migrate` functions for evolving conversation, draft, task, or history shapes.
- Safe modification: Add schema versioning before changing persisted fields such as `conversationDrafts`, `taskSummaries`, pending edit/rewrite fields, or task message metadata.
- Test coverage: `frontend/__tests__/unit/stores/test_session_persistence.test.ts` and `frontend/e2e/test_url_conversation.spec.ts` cover selected fixtures, but not cross-version migration.

**`gngk` conversation identity is easy to bypass:**
- Files: `frontend/stores/chatStore.ts`, `frontend/app/tender/page.tsx`, `frontend/components/forms/TenderFormShared.tsx`, `frontend/utils/tenderTypeMapper.ts`, `AGENTS.md`
- Why fragile: `findGngkConversationByIdentity` includes `tender_lx` and `fund_lx`, while the public `findConversationByTenderNo` only matches tender number and tender type.
- Safe modification: Use identity-aware helpers whenever `tenderType === 'gngk'`; do not call `findConversationByTenderNo` for `gngk` flows.
- Test coverage: `frontend/__tests__/unit/stores/test_chat_store_conversation_scope.test.ts` and `frontend/e2e/test_url_conversation.spec.ts` cover core cases.

**Edit workflow depends on generated-file metadata to chain edits:**
- Files: `frontend/components/chat/ChatPanel.tsx`, `frontend/stores/chatStore.ts`, `frontend/hooks/useChatSSE.ts`
- Why fragile: Completed edit tasks update `edit_file` from download-message metadata, and missing output metadata falls back to refilling chat input.
- Safe modification: Preserve `outputFile`, `fileName`, task kind, and writeback metadata through `frontend/hooks/useChatSSE.ts` and `frontend/stores/chatStore.ts` before changing edit UI behavior.
- Test coverage: `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx` covers edit creation paths; E2E does not cover completed edit chaining.

**User-visible task logs can expose backend diagnostics if the backend emits them as progress logs:**
- Files: `frontend/hooks/useChatSSE.ts`, `frontend/components/chat/TaskLogMessage.tsx`, `AGENTS.md`
- Why fragile: The frontend renders every SSE `log` message stored in stream state, and only special-cases style writeback wording.
- Safe modification: Keep diagnostic details in backend execution logs; if frontend filtering is added, filter centrally in `frontend/hooks/useChatSSE.ts`.
- Test coverage: `frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx` covers event mapping, but not redaction or diagnostic filtering.

## Scaling Limits

**Browser session storage is the practical session capacity limit:**
- Current capacity: Browser-specific `sessionStorage` quotas apply to `frontend/stores/chatStore.ts`, `frontend/stores/chatTaskSessionStore.ts`, and `frontend/stores/historyStore.ts`.
- Limit: Large chat histories, streamed content, task summaries, tender data snapshots, and upload metadata can exceed storage quota or slow hydration.
- Scaling path: Move durable history to a real backend conversation store or persist compact summaries only.

**Active conversation list drives heartbeat load:**
- Current capacity: Heartbeat load grows with the number of conversations in `frontend/stores/chatStore.ts`.
- Limit: Many conversations in one page session trigger many `/api/conversations/{id}/heartbeat` requests from `frontend/app/tender/page.tsx`.
- Scaling path: Track active task conversation IDs separately and heartbeat only those IDs.

**Task logs and streamed AI text are held in memory until cleanup:**
- Current capacity: Each active task gets a `TaskStreamState` in `frontend/stores/chatStreamStore.ts`.
- Limit: Long SSE sessions grow `logs` and `aiText` in memory and trigger state copies on every update.
- Scaling path: Cap logs, coalesce progress, and store large completed content only once in final task messages.

## Dependencies at Risk

**Clean install and local install can disagree:**
- Risk: `frontend/package.json` and `frontend/package-lock.json` resolve `eslint-config-next`, `jest`, and `jest-environment-jsdom`, while local `frontend/node_modules/` reports invalid versions through `npm ls`.
- Impact: `npm run lint`, `npm run test`, and local IDE behavior can differ from clean installs.
- Migration plan: Recreate `frontend/node_modules/` with `npm ci`; avoid editing lockfile manually.

**Unused or unclear dependencies add audit and maintenance noise:**
- Risk: Direct dependencies `und` and `undici` appear in `frontend/package.json` and `frontend/package-lock.json`, but no frontend source import is detected under `frontend/`.
- Impact: Extra dependencies increase audit surface and make `npm audit` harder to triage.
- Migration plan: Remove unused packages after confirming no script/runtime dependency, then run `npm ci`, `npm run type-check`, and `npm run test`.

## Missing Critical Features

**Durable conversation history is not implemented in the frontend API client:**
- Problem: Conversation API helper functions in `frontend/lib/api.ts` are stubs, while active history lives in `frontend/stores/chatStore.ts`.
- Blocks: Cross-tab history, backend-side conversation recovery, and multi-device task history.

**Comment writeback summary handling is not represented:**
- Problem: Frontend task result types in `frontend/types/api.ts` and completion plumbing in `frontend/hooks/useChatSSE.ts` only model style writeback.
- Blocks: UI visibility and persisted metadata for comment writeback results required by `AGENTS.md`.

**Full user-path E2E coverage is incomplete:**
- Problem: Existing Playwright coverage focuses on home page, URL/session behavior, stale task interruption, sidebar behavior, and basic form shell.
- Blocks: Regression confidence for mocked task creation -> SSE progress -> completion -> download, edit completion chaining, template candidate select/download, and failed SSE UI.
- Files: `frontend/e2e/test_home.spec.ts`, `frontend/e2e/test_url_conversation.spec.ts`, `frontend/playwright.config.ts`

## Test Coverage Gaps

**Template candidate modal lacks E2E coverage:**
- What's not tested: Browser flow for opening the candidate dialog, rendering ranked candidates, blocking non-selectable candidates, selecting files, downloading reference files, and refresh errors.
- Files: `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/forms/TemplateCandidateDialog.tsx`, `frontend/__tests__/unit/components/forms/test_tender_form_shared.test.tsx`, `frontend/e2e/test_url_conversation.spec.ts`
- Risk: Backend contract changes to `row_index`, `selectable`, `blocked_reason`, or selected file payloads can pass unit mocks but fail in browser behavior.
- Priority: High

**SSE success path lacks browser-level regression coverage:**
- What's not tested: A full mocked EventSource flow from queued/running progress through `llm`, `done`, download card rendering, and button download behavior.
- Files: `frontend/lib/sse.ts`, `frontend/hooks/useSSE.ts`, `frontend/hooks/useChatSSE.ts`, `frontend/components/chat/TaskDownloadMessage.tsx`, `frontend/e2e/test_url_conversation.spec.ts`
- Risk: EventSource, reconnect, Last-Event-ID, or task result metadata changes can regress without Playwright coverage.
- Priority: High

**API malformed response handling is not covered:**
- What's not tested: Empty body, non-JSON error body, and proxy HTML error body behavior for `request` and `fetchTenderDataWithType`.
- Files: `frontend/lib/api.ts`, `frontend/__tests__/unit/lib/test_api.test.ts`
- Risk: UI callers receive generic runtime errors instead of `ApiError`.
- Priority: Medium

**Persisted store migration is not covered:**
- What's not tested: Loading older persisted `chat-storage`, `chat-task-session-storage`, `tender-history-storage`, and app store payloads after schema changes.
- Files: `frontend/stores/chatStore.ts`, `frontend/stores/chatTaskSessionStore.ts`, `frontend/stores/historyStore.ts`, `frontend/stores/useAppStore.ts`, `frontend/__tests__/unit/stores/test_session_persistence.test.ts`
- Risk: User sessions break or stale running tasks reconnect incorrectly after frontend schema changes.
- Priority: Medium

**Production header behavior is not covered:**
- What's not tested: Security/cache headers emitted by `frontend/next.config.ts` in production mode.
- Files: `frontend/next.config.ts`, `frontend/playwright.config.ts`
- Risk: Deployment changes can remove or miss required headers without failing tests.
- Priority: Low

---

*Concerns audit: 2026-05-22*
