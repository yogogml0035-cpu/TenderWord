# Testing Patterns

**Analysis Date:** 2026-05-22

## Scope

**Frontend scope only:**
- Use this map for `frontend/` tests and root frontend validation rules in `AGENTS.md` and `README.md`.
- Do not use this map as backend testing guidance; backend contracts are referenced only through frontend API types and mocked frontend callers in `frontend/types/api.ts`, `frontend/lib/api.ts`, and `frontend/mocks/handlers.ts`.
- Do not read or assert values from `frontend/.env.local`; tests should use public config helpers from `frontend/lib/apiBaseUrl.ts` and mocks in `frontend/__tests__/`.

## Test Framework

**Runner:**
- Use Jest 29 for unit and integration tests through `frontend/jest.config.ts` and `frontend/package.json`.
- Use `next/jest` from `frontend/jest.config.ts` so tests load Next.js config from `frontend/next.config.ts`.
- Use `jest-environment-jsdom` from `frontend/jest.config.ts` for React, hook, and browser storage behavior.
- Use Playwright for E2E tests through `frontend/playwright.config.ts` and `frontend/package.json`.

**Assertion Library:**
- Use Jest expectations and Testing Library matchers configured by `@testing-library/jest-dom` in `frontend/jest.setup.js`.
- Use React Testing Library from `@testing-library/react` in `frontend/__tests__/unit/` and `frontend/__tests__/integration/`.
- Use Playwright `expect` from `@playwright/test` in `frontend/e2e/test_home.spec.ts` and `frontend/e2e/test_url_conversation.spec.ts`.

**Run Commands:**
```bash
cd frontend
npm run lint            # ESLint validation from `frontend/package.json`
npm run type-check      # TypeScript no-emit validation from `frontend/package.json`
npm run test            # Jest suite from `frontend/package.json`
npm run test:watch      # Jest watch mode from `frontend/package.json`
npm run test:coverage   # Jest coverage from `frontend/package.json`
npm run test:e2e        # Playwright E2E from `frontend/package.json`
npm run test:e2e:ui     # Playwright UI mode from `frontend/package.json`
npm run test:e2e:debug  # Playwright debug mode from `frontend/package.json`
```

**WSL command shape:**
```bash
cd frontend
npm run lint
npm run type-check
TMPDIR=/tmp TMP=/tmp TEMP=/tmp CI=1 npm test -- --runInBand
```

- Use the WSL temp-dir pattern from `AGENTS.md` when running frontend Jest in WSL.
- Prefer Linux `node` and `npm` inside WSL, as required by `AGENTS.md` and described for frontend setup in `README.md`.

## Test File Organization

**Location:**
- Put unit tests under `frontend/__tests__/unit/<module_scope>/`.
- Put integration tests under `frontend/__tests__/integration/<module_scope>/`.
- Put Playwright E2E tests under `frontend/e2e/`.
- Put shared test utilities under `frontend/__tests__/utils/`.
- Put frontend test-only mocks under `frontend/__tests__/mocks/` and MSW request handlers under `frontend/mocks/`.

**Naming:**
- Name new frontend unit tests as `frontend/__tests__/unit/<module_scope>/test_*.test.ts` or `frontend/__tests__/unit/<module_scope>/test_*.test.tsx`, following `AGENTS.md`.
- Name new frontend integration tests as `frontend/__tests__/integration/<module_scope>/test_*.test.ts` or `frontend/__tests__/integration/<module_scope>/test_*.test.tsx`, following `AGENTS.md`.
- Name new Playwright specs as `frontend/e2e/test_*.spec.ts`, following `AGENTS.md`.
- Do not add new co-located tests beside source files in `frontend/components/`, `frontend/lib/`, `frontend/utils/`, `frontend/hooks/`, or `frontend/stores/`, because `AGENTS.md` requires centralized frontend tests.

**Structure:**
```text
frontend/
├── __tests__/
│   ├── unit/
│   │   ├── app/test_*.test.tsx
│   │   ├── components/test_*.test.tsx
│   │   ├── hooks/test_*.test.tsx
│   │   ├── lib/test_*.test.ts
│   │   ├── stores/test_*.test.ts
│   │   └── utils/test_*.test.ts
│   ├── integration/
│   │   └── examples/test_*.test.tsx
│   ├── mocks/
│   │   ├── data-factories.ts
│   │   └── sse-mock.ts
│   └── utils/
│       ├── setup.ts
│       └── test-utils.tsx
├── e2e/
│   └── test_*.spec.ts
├── jest.config.ts
├── jest.setup.js
└── playwright.config.ts
```

- Keep Jest test discovery aligned with `testMatch` and `testPathIgnorePatterns` in `frontend/jest.config.ts`.
- Keep E2E files excluded from Jest by `frontend/jest.config.ts` and included by `frontend/playwright.config.ts`.

## Test Structure

**Suite Organization:**
```typescript
describe('formDataConverter', () => {
  it.each([
    { tender_lx: 0 as const, fund_lx: 0 as const, expected: 'gngk_hw_zc_tender' },
    { tender_lx: 2 as const, fund_lx: 1 as const, expected: 'gngk_fw_cz_tender' },
  ])('maps gngk tender_lx=$tender_lx fund_lx=$fund_lx to $expected', ({ tender_lx, fund_lx, expected }) => {
    // Match the table-driven mapping style in `frontend/__tests__/unit/lib/test_form_data_converter.test.ts`.
  });
});
```

- Use `describe()` blocks around one module or behavior area, as in `frontend/__tests__/unit/lib/test_api.test.ts`, `frontend/__tests__/unit/lib/test_form_data_converter.test.ts`, and `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`.
- Use `it.each()` for matrix behavior such as tender type and `gngk` subtype mappings in `frontend/__tests__/unit/lib/test_form_data_converter.test.ts` and `frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`.
- Use `beforeEach()` to reset mocks, browser storage, and Zustand state in `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`, `frontend/__tests__/unit/stores/test_chat_store_conversation_scope.test.ts`, and `frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`.
- Use `afterEach()` for timer and mock cleanup in hook tests such as `frontend/__tests__/unit/hooks/test_use_task_heartbeat.test.tsx`.

**Async Testing:**
```typescript
const { result } = renderHook(() => useCurrentConversationTaskStatus(60000));

await waitFor(() => {
  expect(result.current.currentTaskStatus).toBe('running');
});
```

- Use `waitFor()` for async React and hook state transitions in `frontend/__tests__/unit/hooks/test_use_current_conversation_task_status.test.tsx`, `frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`, and `frontend/__tests__/unit/components/forms/test_tender_form_shared.test.tsx`.
- Use `act()` around manual store updates, timer advancement, and simulated SSE event callbacks in `frontend/__tests__/unit/stores/test_chat_store_conversation_scope.test.ts`, `frontend/__tests__/unit/hooks/test_use_task_heartbeat.test.tsx`, and `frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`.
- Use fake timers only inside tests that need interval control, and restore real timers in `afterEach()` or `finally`, following `frontend/__tests__/unit/hooks/test_use_task_heartbeat.test.tsx` and `frontend/__tests__/unit/hooks/test_use_current_conversation_task_status.test.tsx`.

**Error Testing:**
```typescript
await expect(createGenerateTask(validGenerateRequest)).rejects.toBeInstanceOf(ApiError);
await expect(createGenerateTask(validGenerateRequest)).rejects.toMatchObject({
  code: 'NETWORK_ERROR',
  status: 0,
});
```

- Assert `ApiError` class, `code`, and `status` for API failures in `frontend/__tests__/unit/lib/test_api.test.ts`.
- Assert task-not-found recovery and stale task interruption in `frontend/__tests__/unit/hooks/test_use_task_heartbeat.test.tsx`, `frontend/__tests__/unit/hooks/test_use_current_conversation_task_status.test.tsx`, and `frontend/e2e/test_url_conversation.spec.ts`.

## Mocking

**Framework:** Jest mocks, manual browser mocks, direct `fetch` mocks, MSW handlers, and Playwright `page.route()`.

**Jest Module Mocks:**
```typescript
jest.mock('@/lib/api', () => {
  const actual = jest.requireActual('@/lib/api');
  return {
    ...actual,
    cancelTask: jest.fn(),
    createEditTask: jest.fn(),
    streamUserMessage: jest.fn(),
    uploadFile: jest.fn(),
  };
});
```

- Mock API helpers at module boundaries in component and hook tests, as in `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`, `frontend/__tests__/unit/components/forms/test_tender_form_shared.test.tsx`, and `frontend/__tests__/unit/hooks/test_use_task_heartbeat.test.tsx`.
- Mock heavy child components when testing parent orchestration, as in `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`.
- Mock `useHydrated()` to return stable hydration state for client component tests, as in `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx` and `frontend/__tests__/unit/app/test_chat_page.test.tsx`.

**Fetch Mocks:**
```typescript
globalThis.fetch = jest.fn().mockResolvedValue({
  ok: true,
  status: 200,
  json: async () => ({ success: true, data: { task_id: 'test-task-123' } }),
} as unknown as Response);
```

- Use direct `globalThis.fetch` mocks for API client unit tests in `frontend/__tests__/unit/lib/test_api.test.ts`.
- Use stream reader mocks for NDJSON stream tests in `frontend/__tests__/unit/lib/test_api.test.ts`.
- Keep API client tests focused on URL construction, request body serialization, response unwrapping, and `ApiError` behavior in `frontend/__tests__/unit/lib/test_api.test.ts`.

**MSW:**
```typescript
import { setupServer } from 'msw/node';
import { handlers } from './handlers';

export const server = setupServer(...handlers);
```

- Use MSW server setup from `frontend/mocks/server.ts` when tests need request-level backend mocks.
- Add shared API handlers to `frontend/mocks/handlers.ts` for reusable endpoint behavior.
- Keep one-off component mock behavior near the specific test file when the scenario is local to `frontend/__tests__/unit/components/`.

**SSE Mocks:**
- Use `frontend/__tests__/mocks/sse-mock.ts` for SSE event factories and mock SSE connection behavior.
- Mock `useSSE()` directly when testing chat stream orchestration in `frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`.
- Assert `lastEventId`, runtime stream state, task message groups, and terminal task handling in `frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`.

**Playwright Route Mocks:**
```typescript
await page.route('**/api/tasks/task-stale', async (route) => {
  await route.fulfill({
    status: 404,
    contentType: 'application/json',
    body: JSON.stringify({ detail: { success: false, error: { code: 'TASK_NOT_FOUND' } } }),
  });
});
```

- Use `page.route()` for frontend flows that can be validated without a real backend or Word COM, as shown in `frontend/e2e/test_url_conversation.spec.ts`.
- Use `page.addInitScript()` to seed `sessionStorage` for URL/session restoration and stale task recovery scenarios in `frontend/e2e/test_url_conversation.spec.ts`.

**What to Mock:**
- Mock backend APIs through `frontend/lib/api.ts` boundaries in component and hook tests under `frontend/__tests__/unit/`.
- Mock `useSSE()` or EventSource behavior when verifying stream state transitions in `frontend/__tests__/unit/hooks/`.
- Mock child components when the test target is parent orchestration, as in `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`.
- Mock browser storage and URL state when testing session or canonical URL behavior in `frontend/__tests__/unit/stores/`, `frontend/__tests__/unit/components/forms/`, and `frontend/e2e/`.

**What NOT to Mock:**
- Do not mock pure mappers under test, such as `frontend/lib/formDataConverter.ts`, `frontend/utils/tenderTypeMapper.ts`, and `frontend/lib/apiBaseUrl.ts`.
- Do not bypass `frontend/lib/api.ts` in tests of component network behavior; mock the exported API helpers from `frontend/lib/api.ts`.
- Do not use live backend or Word COM for normal frontend unit tests under `frontend/__tests__/unit/`.

## Fixtures and Factories

**Test Data:**
```typescript
export class ConversationFactory {
  static create(overrides?: Partial<Conversation>): Conversation {
    return {
      id: generateId('conv'),
      title: 'Test Conversation',
      tenderType: 'xjcg',
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
      ...overrides,
    };
  }
}
```

- Use factory classes from `frontend/__tests__/mocks/data-factories.ts` for reusable conversation, message, log, and task objects.
- Use local test builders when the fixture is tightly coupled to one behavior, as in `frontend/__tests__/unit/components/forms/test_tender_form_shared.test.tsx` and `frontend/__tests__/unit/lib/test_api.test.ts`.
- Keep route/session fixtures aligned with persisted store shape in `frontend/stores/chatStore.ts`, `frontend/stores/chatTaskSessionStore.ts`, and `frontend/e2e/test_url_conversation.spec.ts`.

**Location:**
- Shared test factories live in `frontend/__tests__/mocks/data-factories.ts`.
- SSE event factories live in `frontend/__tests__/mocks/sse-mock.ts`.
- Testing Library helper render utilities live in `frontend/__tests__/utils/test-utils.tsx`.
- Jest environment setup lives in `frontend/jest.setup.js`, with a TypeScript counterpart present in `frontend/jest.setup.ts`.

## Coverage

**Requirements:**
- Global Jest coverage thresholds are 50% for branches, functions, lines, and statements in `frontend/jest.config.ts`.
- Coverage collection includes `frontend/components/`, `frontend/hooks/`, `frontend/lib/`, and `frontend/stores/` through `frontend/jest.config.ts`.
- Coverage collection excludes declaration files, `frontend/node_modules/`, `frontend/.next/`, and `frontend/mocks/` through `frontend/jest.config.ts`.

**View Coverage:**
```bash
cd frontend
npm run test:coverage
```

- Keep coverage reports out of lint scope through `frontend/eslint.config.mjs` and out of Jest source collection through `frontend/jest.config.ts`.

## Test Types

**Unit Tests:**
- Use unit tests for pure mappers and helpers in `frontend/__tests__/unit/lib/test_form_data_converter.test.ts`, `frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`, `frontend/__tests__/unit/lib/test_api_base_url.test.ts`, and `frontend/__tests__/unit/lib/test_chat_utils.test.ts`.
- Use unit tests for API client behavior in `frontend/__tests__/unit/lib/test_api.test.ts`.
- Use unit tests for store behavior in `frontend/__tests__/unit/stores/test_chat_store_conversation_scope.test.ts`, `frontend/__tests__/unit/stores/test_chat_store_task_messages.test.ts`, `frontend/__tests__/unit/stores/test_session_persistence.test.ts`, and `frontend/__tests__/unit/stores/test_app_store.test.ts`.
- Use unit tests for hooks in `frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`, `frontend/__tests__/unit/hooks/test_use_task_heartbeat.test.tsx`, and `frontend/__tests__/unit/hooks/test_use_current_conversation_task_status.test.tsx`.
- Use unit tests for components in `frontend/__tests__/unit/components/chat/`, `frontend/__tests__/unit/components/forms/`, and `frontend/__tests__/unit/components/layout/`.

**Integration Tests:**
- Existing integration coverage is minimal and lives in `frontend/__tests__/integration/examples/test_example_component.test.tsx`.
- Add integration tests under `frontend/__tests__/integration/<module_scope>/` when multiple frontend modules interact but do not need a real browser, such as a form plus store plus mocked API boundary.
- Use `renderWithProviders()` from `frontend/__tests__/utils/test-utils.tsx` when an integration test needs common providers.

**E2E Tests:**
- Use Playwright specs in `frontend/e2e/test_home.spec.ts` for homepage navigation and `frontend/e2e/test_url_conversation.spec.ts` for tender workspace URL/session behavior.
- Base Playwright at `http://localhost:8502` through `frontend/playwright.config.ts`.
- Let Playwright start the frontend with `npm run dev` through `frontend/playwright.config.ts`.
- Use Chromium only unless `frontend/playwright.config.ts` adds more projects.
- Keep trace, screenshot, and video behavior aligned with `frontend/playwright.config.ts`.

## Critical Frontend Coverage Areas

**API client:**
- Cover JSON success wrappers, flat endpoint compatibility, network failures, endpoint URL encoding, FormData uploads, downloads, template candidate APIs, task heartbeat, and NDJSON streams in `frontend/__tests__/unit/lib/test_api.test.ts`.
- Cover base URL normalization, comma-separated public API candidates, browser-location matching, and fallbacks in `frontend/__tests__/unit/lib/test_api_base_url.test.ts`.

**Tender type mapping:**
- Cover frontend `TenderType` URL mapping in `frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`.
- Cover `gngk` `tender_lx + fund_lx` backend form type mapping in `frontend/__tests__/unit/lib/test_form_data_converter.test.ts`.
- Cover display/component/converter registry behavior in `frontend/__tests__/unit/components/chat/test_tender_form_registry.test.tsx`.

**Session and URL behavior:**
- Cover conversation-scoped selectors, draft isolation, same tender number handling, and `gngk` identity matching in `frontend/__tests__/unit/stores/test_chat_store_conversation_scope.test.ts`.
- Cover session persistence shape in `frontend/__tests__/unit/stores/test_session_persistence.test.ts`.
- Cover browser-level URL/session behavior and stale task recovery in `frontend/e2e/test_url_conversation.spec.ts`.

**Forms:**
- Cover shared form defaults, draft priority, URL integration, template candidate behavior, file uploader integration, and form submit payloads in `frontend/__tests__/unit/components/forms/test_tender_form_shared.test.tsx`.
- Cover wrapper form behavior in `frontend/__tests__/unit/components/forms/test_xjcg_tender_form.test.tsx` and `frontend/__tests__/unit/components/forms/test_gngk_tender_form.test.tsx`.
- Cover file uploader validation and upload behavior in `frontend/__tests__/unit/components/forms/test_file_uploader.test.tsx`.

**Chat, tasks, and SSE:**
- Cover chat composer, normal chat, rewrite/edit task acceptance, file edit upload, cancellation, and model changes in `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx` and `frontend/__tests__/unit/components/chat/test_chat_input.test.tsx`.
- Cover task message grouping and task message updates in `frontend/__tests__/unit/stores/test_chat_store_task_messages.test.ts`.
- Cover SSE runtime state, terminal events, stale events, and last event ID handling in `frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`.
- Cover heartbeat terminal state and missing task handling in `frontend/__tests__/unit/hooks/test_use_task_heartbeat.test.tsx`.

## Validation Gates

**Minimum for frontend changes:**
- Run `npm run lint` from `frontend/package.json` for lint validation.
- Run `npm run type-check` from `frontend/package.json` for TypeScript validation.
- Run relevant Jest tests with `npm run test` or a targeted Jest command from `frontend/package.json` and `frontend/jest.config.ts`.
- Run `npm run test:e2e` from `frontend/package.json` when the change affects browser navigation, URL canonicalization, `sessionStorage`, task recovery, template dialogs, visible progress, or download entry state, as required by `AGENTS.md`.

**Change-to-test mapping:**
- For API client or types changes, update and run `frontend/__tests__/unit/lib/test_api.test.ts` and relevant `frontend/types/api.ts` consumers.
- For `gngk` form type mapping, update and run `frontend/__tests__/unit/lib/test_form_data_converter.test.ts`, `frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`, and `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`.
- For URL/session behavior, update and run `frontend/__tests__/unit/stores/test_chat_store_conversation_scope.test.ts`, `frontend/__tests__/unit/stores/test_session_persistence.test.ts`, and `frontend/e2e/test_url_conversation.spec.ts`.
- For task recovery, SSE, or heartbeat behavior, update and run `frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`, `frontend/__tests__/unit/hooks/test_use_task_heartbeat.test.tsx`, `frontend/__tests__/unit/hooks/test_use_current_conversation_task_status.test.tsx`, and `frontend/e2e/test_url_conversation.spec.ts`.
- For form UI behavior, update and run tests under `frontend/__tests__/unit/components/forms/` plus `frontend/e2e/test_url_conversation.spec.ts` when the browser-visible workflow changes.

## Playwright Patterns

**Selectors:**
- Prefer `getByRole()` for visible navigation and headings, as in `frontend/e2e/test_home.spec.ts`.
- Prefer `getByTestId()` for repeated or stateful UI elements, as in `frontend/e2e/test_url_conversation.spec.ts` and supported by `frontend/components/chat/TenderTypeSidebar.tsx`.
- Use scoped or exact text only when the text is stable and unique, as in `frontend/e2e/test_home.spec.ts` and `frontend/e2e/test_url_conversation.spec.ts`.
- Avoid broad global text selectors for repeated UI text, matching the locator guidance in `AGENTS.md`.

**Session setup:**
- Use `page.addInitScript()` to seed `window.sessionStorage` before navigation in `frontend/e2e/test_url_conversation.spec.ts`.
- Keep seeded `chat-storage` and `chat-task-session-storage` shapes aligned with `frontend/stores/chatStore.ts` and `frontend/stores/chatTaskSessionStore.ts`.
- Include `conversation.currentTaskId`, `activeTaskIds`, `taskSummaries`, and message `taskId` for restored running task fixtures, as required by `AGENTS.md` and exercised in `frontend/e2e/test_url_conversation.spec.ts`.

**Network setup:**
- Use `page.route()` for task status and stream endpoints when validating frontend behavior without backend or Word COM in `frontend/e2e/test_url_conversation.spec.ts`.
- Assert that stale restored tasks do not open `/api/stream/{task_id}` before task status confirmation, as shown by `streamRequestCount` in `frontend/e2e/test_url_conversation.spec.ts`.

## Common Patterns

**Store reset pattern:**
```typescript
window.localStorage.clear();
window.sessionStorage.clear();

useChatStore.setState((state) => ({
  ...state,
  conversations: [],
  currentConversationId: null,
  activeTaskIds: [],
  taskSummaries: {},
}));
```

- Reset `localStorage`, `sessionStorage`, and affected Zustand slices before store-heavy tests in `frontend/__tests__/unit/stores/test_chat_store_conversation_scope.test.ts`, `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`, and `frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`.

**Component interaction pattern:**
```typescript
const user = userEvent.setup();
render(<TenderFormShared tenderType="xjcg" onSubmit={jest.fn()} />);
await user.click(screen.getByRole('button', { name: /提交/ }));
```

- Use `userEvent.setup()` for realistic interactions in `frontend/__tests__/unit/components/forms/test_tender_form_shared.test.tsx`, `frontend/__tests__/unit/components/chat/test_chat_input.test.tsx`, and `frontend/__tests__/integration/examples/test_example_component.test.tsx`.
- Use Testing Library `screen` queries and `within()` for component DOM assertions in `frontend/__tests__/unit/components/forms/test_tender_form_shared.test.tsx`.

**Hook testing pattern:**
```typescript
const { result } = renderHook(() => useTaskHeartbeat(['task-1']));

await act(async () => {
  jest.advanceTimersByTime(5000);
  await Promise.resolve();
});
```

- Use `renderHook()` for hooks in `frontend/__tests__/unit/hooks/test_use_task_heartbeat.test.tsx`, `frontend/__tests__/unit/hooks/test_use_current_conversation_task_status.test.tsx`, and `frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`.

---

*Testing analysis: 2026-05-22*
