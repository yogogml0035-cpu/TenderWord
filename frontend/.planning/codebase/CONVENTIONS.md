# Coding Conventions

**Analysis Date:** 2026-05-22

## Scope

**Frontend scope only:**
- Use this map for `frontend/` code and root frontend guidance from `AGENTS.md` and `README.md`.
- Do not use this map as backend implementation guidance; shared API implications are referenced only through `frontend/types/api.ts`, `frontend/lib/api.ts`, and `AGENTS.md`.
- Repo-local project skills are not detected under `.codex/skills/` or `.agents/skills/`.

## Naming Patterns

**Files:**
- Use `PascalCase.tsx` for React component modules in `frontend/components/`, such as `frontend/components/chat/ChatPanel.tsx`, `frontend/components/forms/TenderFormShared.tsx`, and `frontend/components/forms/FileUploader.tsx`.
- Use `camelCase.ts` for hooks, stores, utilities, and API modules in `frontend/hooks/`, `frontend/stores/`, `frontend/lib/`, and `frontend/utils/`, such as `frontend/hooks/useChatSSE.ts`, `frontend/stores/chatStore.ts`, `frontend/lib/formDataConverter.ts`, and `frontend/utils/tenderTypeMapper.ts`.
- Use route files required by Next.js App Router in `frontend/app/`, such as `frontend/app/page.tsx`, `frontend/app/layout.tsx`, and `frontend/app/tender/page.tsx`.
- Use centralized test naming outside source folders, with `test_` prefixes under `frontend/__tests__/unit/`, `frontend/__tests__/integration/`, and `frontend/e2e/`, as required by `AGENTS.md`.

**Functions:**
- Use `camelCase` for helper functions and action handlers in `frontend/lib/api.ts`, `frontend/lib/formDataConverter.ts`, `frontend/utils/tenderTypeMapper.ts`, `frontend/components/chat/ChatPanel.tsx`, and `frontend/components/forms/TenderFormShared.tsx`.
- Use `useXxx` naming for React hooks in `frontend/hooks/useSSE.ts`, `frontend/hooks/useChatSSE.ts`, `frontend/hooks/useTaskHeartbeat.ts`, `frontend/hooks/useCurrentConversationTaskStatus.ts`, and `frontend/hooks/useUrlParams.ts`.
- Use `convertXxxFormToApiRequest` names for form-to-API converters in `frontend/lib/formDataConverter.ts`.
- Use `resolveXxx`, `normalizeXxx`, `parseXxx`, and `buildXxx` helper names for pure mapping logic in `frontend/lib/apiBaseUrl.ts`, `frontend/utils/tenderTypeMapper.ts`, `frontend/lib/tenderFetch.ts`, and `frontend/components/forms/TenderFormShared.tsx`.

**Variables:**
- Use `const` by default for module constants and derived values in `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/chat/FormPanel.tsx`, `frontend/hooks/useTaskHeartbeat.ts`, and `frontend/lib/sse.ts`.
- Use uppercase names for module-level constants in `frontend/lib/apiBaseUrl.ts`, `frontend/lib/sse.ts`, `frontend/stores/chatStore.ts`, and `frontend/hooks/useTaskHeartbeat.ts`.
- Use descriptive local state names with `local`, `current`, `selected`, `effective`, or `pending` prefixes where the value mirrors UI or task state in `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/chat/ChatPanel.tsx`, and `frontend/components/chat/FormPanel.tsx`.
- Use `Ref` suffixes for React refs in `frontend/components/chat/ChatPanel.tsx`, `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/chat/TenderTypeSidebar.tsx`, and `frontend/hooks/useSSE.ts`.

**Types:**
- Keep cross-module app types in `frontend/types/index.ts`, chat types in `frontend/types/chat.ts`, and backend-facing API types in `frontend/types/api.ts`.
- Use exported `interface` declarations for public props, state, and API object shapes in `frontend/types/api.ts`, `frontend/types/chat.ts`, `frontend/components/forms/TenderFormShared.tsx`, and `frontend/components/chat/tenderFormRegistry.ts`.
- Use literal union types for constrained domain values in `frontend/types/index.ts`, `frontend/types/api.ts`, `frontend/types/chat.ts`, and `frontend/components/forms/ModelSelector.tsx`.
- Use type guards for runtime validation of unknown payloads in `frontend/types/chat.ts`, `frontend/lib/api.ts`, `frontend/utils/tenderTypeMapper.ts`, and `frontend/components/chat/FormPanel.tsx`.

## Code Style

**Formatting:**
- Format with Prettier using semicolons, single quotes, trailing commas where valid in ES5, `printWidth: 100`, and `tabWidth: 2` from `frontend/.prettierrc`.
- Keep Tailwind class ordering managed by `prettier-plugin-tailwindcss` configured in `frontend/.prettierrc` and installed through `frontend/package.json`.
- Prefer `cn()` for conditional class merging in reusable UI modules, using `frontend/lib/utils.ts` with `clsx` and `tailwind-merge`, as seen in `frontend/components/forms/shared/FormField.tsx`, `frontend/components/forms/shared/ErrorDisplay.tsx`, and `frontend/components/forms/FileUploader.tsx`.
- Use global Tailwind 4 and CSS token definitions from `frontend/app/globals.css`; do not create a separate design-token source outside `frontend/app/globals.css`.

**Linting:**
- Use ESLint 9 with Next.js core web vitals, Next TypeScript rules, and `eslint-plugin-react-hooks` from `frontend/eslint.config.mjs`.
- Treat `react-hooks/set-state-in-effect` as a warning, matching `frontend/eslint.config.mjs`.
- Keep generated and runtime-output directories ignored by lint through `frontend/eslint.config.mjs`, including `.next/**`, `coverage/**`, `playwright-report/**`, and `test-results/**` relative to `frontend/`.
- Run lint with `npm run lint` from `frontend/package.json`.

**TypeScript:**
- Keep `strict: true`, `moduleResolution: "bundler"`, `jsx: "react-jsx"`, and `noEmit: true` from `frontend/tsconfig.json`.
- Use the `@/*` alias from `frontend/tsconfig.json` for cross-folder imports in `frontend/app/tender/page.tsx`, `frontend/components/chat/ChatPanel.tsx`, `frontend/lib/api.ts`, and `frontend/stores/chatStore.ts`.
- Use `import type` for type-only imports in `frontend/components/chat/tenderFormRegistry.ts`, `frontend/components/forms/TenderFormShared.tsx`, `frontend/stores/chatStore.ts`, and `frontend/lib/formDataConverter.ts`.
- Run type checking with `npm run type-check` from `frontend/package.json`.

## React and UI Patterns

**Client components:**
- Add `'use client';` to interactive components and hooks under `frontend/components/`, `frontend/hooks/`, and `frontend/app/tender/page.tsx`.
- Leave static app shell files server-compatible when possible, as shown by `frontend/app/page.tsx` and `frontend/app/layout.tsx`.
- Export named React functions and keep a default export for compatibility in component modules such as `frontend/components/chat/ChatPanel.tsx`, `frontend/components/forms/XjcgTenderForm.tsx`, `frontend/components/forms/GngkTenderForm.tsx`, and `frontend/components/forms/GjgkTenderForm.tsx`.
- Keep variant-specific tender form wrappers thin and route all shared form behavior through `frontend/components/forms/TenderFormShared.tsx`.

**Component structure:**
- Put chat workspace UI under `frontend/components/chat/`, form UI under `frontend/components/forms/`, shared form primitives under `frontend/components/forms/shared/`, and layout primitives under `frontend/components/layout/`.
- Use `frontend/components/chat/tenderFormRegistry.ts` as the registry for tender form display names, components, and converters.
- Use `frontend/components/forms/tenderFormConfig.ts` as the frontend source for per-type insertion defaults.
- Use `data-testid` only for stable UI contracts that tests target, as seen in `frontend/components/chat/TenderTypeSidebar.tsx`, `frontend/components/chat/ChatInput.tsx`, `frontend/components/forms/TemplateCandidateDialog.tsx`, and `frontend/components/forms/FileUploader.tsx`.

**Accessibility:**
- Prefer role and accessible-name semantics when the element has a natural user-facing contract, as tested in `frontend/e2e/test_home.spec.ts` and `frontend/e2e/test_url_conversation.spec.ts`.
- Use explicit alert semantics for reusable error UI through `role="alert"` in `frontend/components/forms/shared/ErrorDisplay.tsx`.
- Keep form labels bound to input IDs in shared fields through `frontend/components/forms/shared/FormField.tsx`.

## Import Organization

**Order:**
1. Import React, Next.js, and package dependencies first, as in `frontend/components/chat/ChatPanel.tsx`, `frontend/components/forms/TenderFormShared.tsx`, and `frontend/app/tender/page.tsx`.
2. Import app modules through `@/` aliases for cross-folder dependencies, as in `frontend/components/chat/FormPanel.tsx`, `frontend/hooks/useChatSSE.ts`, and `frontend/lib/formDataConverter.ts`.
3. Import relative sibling modules for same-folder components, as in `frontend/components/chat/ChatPanel.tsx`, `frontend/components/chat/MessageList.tsx`, and `frontend/components/forms/XjcgTenderForm.tsx`.
4. Import types with `import type` where no runtime value is needed, as in `frontend/types/chat.ts`, `frontend/stores/chatStore.ts`, and `frontend/components/chat/tenderFormRegistry.ts`.

**Path aliases:**
- Use `@/*` for root-relative frontend imports according to `frontend/tsconfig.json`.
- Keep API imports centralized through `@/lib/api` and API types through `@/types/api`, as seen in `frontend/components/chat/ChatPanel.tsx`, `frontend/components/chat/FormPanel.tsx`, and `frontend/components/forms/TenderFormShared.tsx`.
- Keep tender identity imports centralized through `@/utils/tenderTypeMapper`, as seen in `frontend/app/tender/page.tsx`, `frontend/stores/chatStore.ts`, and `frontend/components/chat/TenderTypeSidebar.tsx`.

## API Client Conventions

**Network access:**
- Route frontend network requests through `frontend/lib/api.ts`; `AGENTS.md` explicitly forbids raw component-level backend `fetch` for normal JSON requests.
- Add new JSON endpoints with the private `request<T>()` helper in `frontend/lib/api.ts`.
- Add streaming endpoints with `streamNdjson()` or a dedicated helper in `frontend/lib/api.ts`, following `streamUserMessage()` in `frontend/lib/api.ts`.
- Add download URL helpers in `frontend/lib/api.ts`, following `getDownloadUrl()` and `getTemplateCandidateDownloadUrl()` in `frontend/lib/api.ts`.

**Base URL and proxy:**
- Resolve backend base URLs with `frontend/lib/apiBaseUrl.ts`; do not duplicate base URL parsing in components.
- Keep Next.js dev proxy rewrites in `frontend/next.config.ts` aligned with `frontend/lib/apiBaseUrl.ts`.
- Do not read or document values from `frontend/.env.local`; use only public variable names and defaults encoded in `frontend/lib/apiBaseUrl.ts` and `frontend/.env.local.example`.

**Contracts:**
- Mirror backend-facing request and response shapes in `frontend/types/api.ts`; `AGENTS.md` names `frontend/types/api.ts` and `frontend/lib/api.ts` as frontend truth sources for shared API and task status contracts.
- When adding a generate form field, update `frontend/types/api.ts`, `frontend/lib/formDataConverter.ts`, `frontend/components/forms/TenderFormShared.tsx`, and related tests under `frontend/__tests__/unit/`.
- When changing SSE event payloads, update `frontend/types/api.ts`, `frontend/lib/sse.ts`, `frontend/hooks/useSSE.ts`, `frontend/hooks/useChatSSE.ts`, and related tests under `frontend/__tests__/unit/hooks/`.
- When changing template candidate behavior, update `frontend/types/api.ts`, `frontend/lib/api.ts`, `frontend/components/forms/TemplateCandidateDialog.tsx`, and `frontend/components/forms/TenderFormShared.tsx`.

## State, Session, and URL Conventions

**State management:**
- Use Zustand stores under `frontend/stores/`, with `create()` and middleware from `zustand/middleware` as shown in `frontend/stores/chatStore.ts`, `frontend/stores/historyStore.ts`, `frontend/stores/chatTaskSessionStore.ts`, and `frontend/stores/useAppStore.ts`.
- Keep conversation, draft, task summary, and URL synchronization state in `frontend/stores/chatStore.ts`.
- Keep transient SSE runtime text and logs in `frontend/stores/chatStreamStore.ts`.
- Keep task stream resume metadata in `frontend/stores/chatTaskSessionStore.ts`.
- Keep generation history state in `frontend/stores/historyStore.ts`.

**Session persistence:**
- Persist current-page conversations and task recovery state to `sessionStorage` through `createJSONStorage(() => sessionStorage)` in `frontend/stores/chatStore.ts` and `frontend/stores/chatTaskSessionStore.ts`.
- Persist history to `sessionStorage` through `frontend/stores/historyStore.ts`.
- Only persist the fields selected by `partialize` in `frontend/stores/chatStore.ts`, `frontend/stores/historyStore.ts`, and `frontend/stores/chatTaskSessionStore.ts`.
- Treat restored running tasks as local snapshots until confirmed through task status APIs, following `frontend/hooks/useCurrentConversationTaskStatus.ts`, `frontend/hooks/useTaskHeartbeat.ts`, `frontend/hooks/useChatSSE.ts`, and `AGENTS.md`.

**URL identity:**
- Build canonical query strings with `buildCanonicalSearchParams()` in `frontend/utils/tenderTypeMapper.ts`.
- Rewrite browser URLs with `syncBrowserUrlToConversation()` in `frontend/utils/tenderTypeMapper.ts` and store method `syncUrlToCurrentConversation()` in `frontend/stores/chatStore.ts`.
- Parse URL parameters with `useUrlParams()` in `frontend/hooks/useUrlParams.ts`, backed by `parseTenderUrlParams()` in `frontend/utils/tenderTypeMapper.ts`.
- Keep `TenderFormShared` initialization order as `draft > URL > default` in `frontend/components/forms/TenderFormShared.tsx`, matching `AGENTS.md`.
- Match `gngk` conversations by `tenderType + tenderno + tender_lx + fund_lx` through `frontend/app/tender/page.tsx` and `frontend/stores/chatStore.ts`.

## Tender Type and Form Conventions

**Type identity:**
- Keep frontend tender type literals in `frontend/types/index.ts`.
- Keep backend `form_type` literals in `frontend/types/api.ts`.
- Keep URL mapping by `purchase_method` in `frontend/utils/tenderTypeMapper.ts`.
- Keep form component and converter registration in `frontend/components/chat/tenderFormRegistry.ts`.
- Keep per-type insertion defaults in `frontend/components/forms/tenderFormConfig.ts`.

**GNGK subtype mapping:**
- Keep `gngk` generate mapping in `frontend/lib/formDataConverter.ts`, where `tender_lx + fund_lx` resolves to the backend form type.
- Keep `gngk` edit mapping synchronized in `frontend/components/chat/ChatPanel.tsx`, where `resolveEditFormType()` repeats the same backend form type decision for edit tasks.
- Any change to `gngk` subtype mapping must update both `frontend/lib/formDataConverter.ts` and `frontend/components/chat/ChatPanel.tsx`, as required by `AGENTS.md`.
- Add or update coverage in `frontend/__tests__/unit/lib/test_form_data_converter.test.ts`, `frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`, and `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx` when changing mapping behavior.

## Error Handling

**Patterns:**
- Normalize API failures to `ApiError` with `message`, `code`, and `status` in `frontend/lib/api.ts`.
- Display user-facing error text from `ApiError.message` where possible, as in `frontend/components/chat/ChatPanel.tsx`, `frontend/components/forms/FileUploader.tsx`, `frontend/components/forms/TenderFormShared.tsx`, and `frontend/lib/tenderFetch.ts`.
- Preserve `code` and `status` for task-not-found handling in `frontend/hooks/useCurrentConversationTaskStatus.ts`, `frontend/hooks/useTaskHeartbeat.ts`, and `frontend/lib/api.ts`.
- Treat `TASK_NOT_FOUND` and HTTP `404` from task status as local interruption state before opening task SSE streams, following `frontend/hooks/useCurrentConversationTaskStatus.ts`, `frontend/hooks/useTaskHeartbeat.ts`, `frontend/hooks/useChatSSE.ts`, and `AGENTS.md`.
- Keep reusable form errors in `frontend/components/forms/shared/ErrorDisplay.tsx`.

**User messaging:**
- Store and show concise user-facing task messages through `frontend/components/chat/ChatPanel.tsx`, `frontend/components/chat/FormPanel.tsx`, `frontend/hooks/useChatSSE.ts`, and `frontend/stores/chatStore.ts`.
- Do not expose backend diagnostic details as user progress UI; `AGENTS.md` requires frontend user SSE progress to stay outcome-first and concise.
- Keep template candidate old-year rejection user-facing behavior in `frontend/components/forms/TenderFormShared.tsx` and `frontend/components/forms/TemplateCandidateDialog.tsx`.

## Logging

**Framework:** `console` only.

**Patterns:**
- Use `console.error` sparingly for task creation, cancellation, and SSE failure diagnostics in `frontend/components/chat/FormPanel.tsx`.
- Use `console.log` and `console.warn` only inside the low-level SSE client in `frontend/lib/sse.ts`.
- Keep persistent user-visible logs in chat task messages and stream stores through `frontend/hooks/useChatSSE.ts`, `frontend/stores/chatStreamStore.ts`, and `frontend/stores/chatStore.ts`.
- Do not log secrets, customer source documents, or environment file contents; `AGENTS.md` forbids printing or recording secrets and customer text.

## Comments

**When to comment:**
- Keep comments for non-obvious product constraints and protocol behavior, such as URL processing in `frontend/app/tender/page.tsx`, canonical URL behavior in `frontend/utils/tenderTypeMapper.ts`, SSE reconnect behavior in `frontend/lib/sse.ts`, and draft priority in `frontend/components/forms/TenderFormShared.tsx`.
- Keep comments concise around task recovery, queue behavior, and stale task handling in `frontend/components/chat/FormPanel.tsx`, `frontend/hooks/useChatSSE.ts`, and `frontend/hooks/useCurrentConversationTaskStatus.ts`.
- Avoid comments that restate trivial JSX or state setters in new code under `frontend/components/` and `frontend/hooks/`.

**JSDoc/TSDoc:**
- Use JSDoc/TSDoc for exported reusable modules and public prop contracts in `frontend/components/forms/shared/FormField.tsx`, `frontend/components/forms/shared/ErrorDisplay.tsx`, `frontend/hooks/useSSE.ts`, `frontend/hooks/useUrlParams.ts`, `frontend/lib/formDataConverter.ts`, and `frontend/lib/sse.ts`.
- Keep examples in JSDoc only when they document reusable helpers, as in `frontend/utils/tenderTypeMapper.ts` and `frontend/lib/formDataConverter.ts`.

## Function Design

**Size:**
- Prefer small pure helper functions for parsing, normalization, and mapping in `frontend/lib/apiBaseUrl.ts`, `frontend/utils/tenderTypeMapper.ts`, `frontend/lib/tenderFetch.ts`, and `frontend/lib/chat-utils.ts`.
- For large stateful components such as `frontend/components/forms/TenderFormShared.tsx`, `frontend/stores/chatStore.ts`, and `frontend/components/chat/ChatPanel.tsx`, keep new behavior in extracted helper functions or store actions rather than adding more inline branching.
- Keep variant wrappers thin, following `frontend/components/forms/XjcgTenderForm.tsx`, `frontend/components/forms/GngkTenderForm.tsx`, and `frontend/components/forms/GjgkTenderForm.tsx`.

**Parameters:**
- Use object parameters for helpers with multiple inputs or callbacks, as in `frontend/lib/tenderFetch.ts`, `frontend/lib/api.ts`, `frontend/hooks/useSSE.ts`, and `frontend/hooks/useChatSSE.ts`.
- Use explicit union-typed parameters for domain decisions, as in `frontend/utils/tenderTypeMapper.ts`, `frontend/lib/formDataConverter.ts`, and `frontend/components/chat/ChatPanel.tsx`.

**Return Values:**
- Return typed data from pure mapping helpers in `frontend/lib/formDataConverter.ts`, `frontend/utils/tenderTypeMapper.ts`, and `frontend/lib/apiBaseUrl.ts`.
- Return discriminated error-or-request objects for preflight builders that can fail validation, as in `buildEditTaskRequest()` in `frontend/components/chat/ChatPanel.tsx`.
- Return `null` for absent optional runtime data where the caller branches on existence, as in `frontend/lib/tenderFetch.ts`, `frontend/hooks/useCurrentConversationTaskStatus.ts`, and `frontend/stores/chatStore.ts`.

## Module Design

**Exports:**
- Export named functions and types from reusable modules in `frontend/lib/`, `frontend/hooks/`, `frontend/utils/`, and `frontend/types/`.
- Keep default exports in component and hook modules where existing imports may depend on them, such as `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/chat/ChatPanel.tsx`, `frontend/hooks/useSSE.ts`, and `frontend/hooks/useUrlParams.ts`.
- Re-export shared form primitives through the barrel file `frontend/components/forms/shared/index.ts`.

**Barrel Files:**
- Use `frontend/components/forms/shared/index.ts` for shared form primitive exports.
- Do not add broad barrels for `frontend/components/chat/`, `frontend/lib/`, or `frontend/stores/` unless the local import pattern changes across those directories.

**Where to add frontend code:**
- Add pages and route-level behavior under `frontend/app/`.
- Add chat workspace behavior under `frontend/components/chat/`.
- Add form behavior and tender form variants under `frontend/components/forms/`.
- Add reusable form primitives under `frontend/components/forms/shared/`.
- Add API helpers under `frontend/lib/api.ts` and base URL helpers under `frontend/lib/apiBaseUrl.ts`.
- Add pure frontend utility logic under `frontend/lib/` or `frontend/utils/`, matching `frontend/lib/chat-utils.ts`, `frontend/lib/tenderFetch.ts`, and `frontend/utils/tenderTypeMapper.ts`.
- Add persistent UI/session state under `frontend/stores/`.

---

*Convention analysis: 2026-05-22*
