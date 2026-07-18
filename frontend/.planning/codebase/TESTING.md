# 前端测试约定

**分析日期：** 2026-07-18

**范围：** `frontend/__tests__/`、`frontend/e2e/`、`frontend/test-shims/`、`frontend/jest.config.ts`、`frontend/jest.setup.js`、`frontend/polyfills.js`、`frontend/playwright.config.ts`、`frontend/package.json`、`frontend/tsconfig.typecheck.json`。`frontend/.env.local`、`frontend/.env.local.example`、`frontend/.npmrc` 仅确认存在，不读取内容。

## 测试框架

**运行器：**
- Jest `^29.7.0`（`jest-environment-jsdom` `^30.3.0`）用于单元测试和 Testing Library 组件测试。
- 配置：`frontend/jest.config.ts`，经 `next/jest.js` 创建（`dir: './'` 以加载 `next.config.ts` 和 `.env`）。
- 环境：`jsdom`。
- `setupFiles`: `frontend/polyfills.js`（为 jsdom 补齐 `TextDecoder/TextEncoder`、`MessageChannel`、`ReadableStream/WritableStream/TransformStream` 等 Stream API，供 `streamNdjson()` 测试使用）。
- `setupFilesAfterEnv`: `frontend/jest.setup.js`。
- `testMatch`: `**/?(*.)+(spec|test).[jt]s?(x)`。
- `coverageProvider`: `v8`。
- `moduleNameMapper`: `^@/(.*)$` → `<rootDir>/$1`。

**断言库：**
- Jest `expect`。
- `@testing-library/jest-dom` 由 `frontend/jest.setup.js` 注册；该文件还补齐 `matchMedia`、`ResizeObserver`、`IntersectionObserver`、`window.scrollTo`、`HTMLCanvasElement.getContext`、`BroadcastChannel`，并过滤 `ReactDOM.render is no longer supported` 警告。
- React 组件测试使用 `@testing-library/react` `^16.2.0` 和 `@testing-library/user-event` `^14.6.1`。

**E2E 运行器：**
- Playwright `@playwright/test` `^1.58.2` 用于浏览器契约测试。
- 配置：`frontend/playwright.config.ts`。
- `testDir` 为 `./e2e`，`fullyParallel: true`，CI 下 `forbidOnly: true`、`retries: 2`、`workers: 1`。
- 项目为 `chromium`（`devices['Desktop Chrome']`）；非 CI 且 `PLAYWRIGHT_USE_SYSTEM_CHROME !== '0'` 时使用系统 Chrome channel。
- `baseURL` 为 `http://localhost:8502`，`webServer.command` 为 `npm run dev -- --webpack`，`reuseExistingServer: !CI`。
- `trace: 'on-first-retry'`、`screenshot: 'only-on-failure'`、`video: 'retain-on-failure'`、`reporter: 'html'`。

**运行命令：**
```bash
cd frontend
npm run lint           # eslint
npm run type-check     # tsc -p tsconfig.typecheck.json --noEmit
npm run test           # jest（全量）
npm run test:watch     # jest --watch
npm run test:coverage  # jest --coverage
npm run test:e2e       # playwright test
npm run test:e2e:ui    # playwright test --ui
npm run test:e2e:debug # playwright test --debug
```

**窄范围命令：**
```bash
cd frontend
npm test -- --runTestsByPath __tests__/unit/lib/test_api.test.ts
npm test -- --runTestsByPath __tests__/unit/hooks/test_use_chat_sse.test.tsx
npm run test:e2e -- test_agent_run_chat_panel.spec.ts
```

## 测试文件组织

**位置：**
- Jest 测试集中在 `frontend/__tests__/unit/`，不与源码文件并排。
- Playwright 测试集中在 `frontend/e2e/`。
- 测试数据工厂和 SSE mock 位于 `frontend/__tests__/mocks/`。
- 异步测试等待工具位于 `frontend/test-shims/until-async.ts`。
- 当前未检测到 `frontend/__tests__/integration/`；跨模块行为优先覆盖在 unit suites 和 Playwright specs 中。
- Jest 忽略 `node_modules/`、`node_modules-wsl/`、`.next/`、`e2e/`（`testPathIgnorePatterns`），并把 `node_modules-wsl/` 列入 `modulePathIgnorePatterns`。

**命名：**
- Jest 测试文件使用 `test_*.test.ts` 或 `test_*.test.tsx`。
- Playwright 测试文件使用 `test_*.spec.ts`。
- 测试工具、fixture、mock 文件不使用 `test_` 前缀，例如 `frontend/__tests__/mocks/data-factories.ts`。

**结构：**
```text
frontend/__tests__/
├── mocks/
│   ├── data-factories.ts
│   └── sse-mock.ts
└── unit/
    ├── app/
    ├── components/
    │   ├── chat/
    │   ├── forms/
    │   └── layout/
    ├── hooks/
    ├── lib/
    ├── stores/
    ├── types/
    └── utils/

frontend/e2e/
└── test_*.spec.ts
```

**当前 inventory（2026-07-18）：**
- Jest unit：约 31 个 `test_*.test.*` 文件，分布在 app / components / hooks / lib / stores / types / utils。
- Playwright e2e：6 个 spec——`test_home.spec.ts`、`test_url_conversation.spec.ts`、`test_agent_run_chat_panel.spec.ts`、`test_generation_mode_agent.spec.ts`、`test_comment_supplement.spec.ts`、`test_tender_form_upload_slots.spec.ts`。

## 测试结构

**Suite 组织：**
```typescript
describe('API Client', () => {
  beforeEach(() => {
    globalThis.fetch = jest.fn() as unknown as typeof fetch;
  });

  describe('createGenerateTask', () => {
    it('returns task data for wrapped success response', async () => {
      const result = await createGenerateTask(validGenerateRequest);
      expect(result.task_id).toBe('task-123');
    });
  });
});
```

实际模式见 `frontend/__tests__/unit/lib/test_api.test.ts`。

**Hook 测试：**
```typescript
jest.mock('@/hooks/useSSE', () => ({ useSSE: jest.fn() }));
jest.mock('@/lib/api', () => ({ getTaskStatus: jest.fn() }));

renderHook(() =>
  useChatSSE({
    taskId: 'task-1',
    conversationId: 'conv-1',
  })
);
```

实际模式见 `frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`。

**组件测试：**
```typescript
render(<FileUploader autoUpload={true} fileType="rewrite_source" />);
await user.upload(input, file);
await waitFor(() => expect(mockUploadFile).toHaveBeenCalledWith(file, 'rewrite_source'));
```

实际模式见 `frontend/__tests__/unit/components/forms/test_file_uploader.test.tsx`。

**Store 测试：**
- 每个 store/hook 测试先清理 `window.localStorage` 和 `window.sessionStorage`。
- 使用 `useChatStore.setState()`、`useChatStreamStore.setState()`、`useChatTaskSessionStore.setState()` 构造状态。
- 调用 store action 后断言 `conversations`、`taskMessageMap`、`taskSummaries`、`conversationDrafts`、browser storage。

实际模式见 `frontend/__tests__/unit/stores/test_chat_store_task_messages.test.ts`、`frontend/__tests__/unit/stores/test_chat_store_conversation_scope.test.ts`、`frontend/__tests__/unit/stores/test_session_persistence.test.ts`、`frontend/__tests__/unit/stores/test_app_store.test.ts`。

## Mock 方式

**框架：**
- Jest mock function / module mock。
- Playwright `page.route()`。

**Fetch mock（JSON）：**
```typescript
globalThis.fetch = jest.fn().mockResolvedValue({
  ok: true,
  status: 200,
  json: async () => ({ success: true, data: { task_id: 'task-123' } }),
} as unknown as Response) as unknown as typeof fetch;
```

**Fetch mock（NDJSON stream）：**
```typescript
// test_api.test.ts 中的 mockFetchStream 模式：
// 返回 body.getReader()，逐行 yield TextEncoder 编码的 NDJSON 行
```

实际文件：`frontend/__tests__/unit/lib/test_api.test.ts`（含 `mockFetchJson`、`mockFetchBlob`、`mockFetchStream`）。

**SSE 连接 mock（EventSource）：**
```typescript
// test_sse.test.ts：替换 global.EventSource 为 MockEventSource
// 支持 addEventListener / emit / emitError，断言 URL 与 lastEventId 查询参数
```

实际文件：`frontend/__tests__/unit/lib/test_sse.test.ts`。

**SSE hook mock（业务层）：**
```typescript
act(() => {
  latestOptions?.onMessage?.({
    event: 'done',
    id: '4',
    data: {
      task_id: 'task-1',
      task_kind: 'generate',
      success: true,
      message: '生成完成',
    },
  });
});
```

实际文件：`frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`（`jest.mock('@/hooks/useSSE')`，捕获 `latestOptions` 后手动注入事件）。

**共享 SSE mock 工具：**
- `frontend/__tests__/mocks/sse-mock.ts` 提供 `SSEMock`（`connect/on/emit/queueEvent/flushQueue`）与事件工厂：`createLogEvent`、`createLLMEvent`、`createProgressEvent`、`createStatusEvent`、`createErrorEvent`、`createDoneEvent`、`simulateTaskFlow`。

**Playwright route mock：**
```typescript
await page.route('**/api/generate', async (route) => {
  const payload = await route.request().postDataJSON();
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ success: true, data: { task_id: 'task-1' } }),
  });
});
```

Agent run NDJSON：
```typescript
function toNdjsonLines(events: Array<Record<string, unknown>>): string {
  return `${events.map((event) => JSON.stringify(event)).join('\n')}\n`;
}

await page.route('**/api/agent/runs/stream', async (route) => {
  agentRunPayload = (await route.request().postDataJSON()) as Record<string, unknown>;
  await route.fulfill({
    status: 200,
    contentType: 'application/x-ndjson',
    body: toNdjsonLines([...]),
  });
});
```

实际文件：`frontend/e2e/test_agent_run_chat_panel.spec.ts`、`frontend/e2e/test_generation_mode_agent.spec.ts`。

**sessionStorage 预置（Playwright）：**
```typescript
await page.addInitScript(({ conversationId, draft, messages }) => {
  window.sessionStorage.setItem(
    'chat-storage',
    JSON.stringify({
      state: {
        conversations: [/* ... */],
        currentConversationId: conversationId,
        conversationDrafts: { [conversationId]: { /* draft */ } },
        // ...
      },
      version: 0,
    })
  );
}, { conversationId, draft, messages });
```

实际文件：`frontend/e2e/test_agent_run_chat_panel.spec.ts`（`seedConversation`）。

**需要 mock 的内容：**
- 后端 API response、fetch stream、SSE hook、task status、heartbeat、sessionStorage/localStorage。
- Agent run NDJSON 事件族：`run_started`、`thinking_stage`、`tool_call`、`task_accepted`、`needs_input`、`done`、`error`。
- Playwright 中的 `/api/generate`、`/api/agent/runs/stream`、`/api/stream/{taskId}`、`/api/tasks/{taskId}`、`/api/comment-supplement`、`/api/upload`、conversation heartbeat。
- Word COM、真实后端队列、真实文件下载内容、真实模板候选外部 URL。

**不要 mock 的内容：**
- 纯转换逻辑：`frontend/lib/formDataConverter.ts`、`frontend/lib/gngkFormType.ts`、`frontend/utils/tenderTypeMapper.ts`。
- Store action 的状态迁移本身；组件测试可 mock API，但 store 测试要直接覆盖 action。
- API client 的 request body 关键字段；测试应断言真实 payload shape。

## 夹具与工厂

**测试数据：**
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

实际文件：`frontend/__tests__/mocks/data-factories.ts`，提供 `ConversationFactory`、`MessageFactory`、`LogEntryFactory`、`TaskFactory`（含 `createRunning`/`createCompleted`/`createFailed`）、`DualColumnContentFactory`，均支持 `overrides` 合并。

**位置：**
- 通用数据工厂：`frontend/__tests__/mocks/data-factories.ts`。
- SSE mock：`frontend/__tests__/mocks/sse-mock.ts`。
- 文件上传测试局部创建 `File`，例如 `frontend/__tests__/unit/components/forms/test_file_uploader.test.tsx`。
- Playwright 使用 `page.addInitScript()` 写入 `sessionStorage`，见 `frontend/e2e/test_agent_run_chat_panel.spec.ts`、`frontend/e2e/test_generation_mode_agent.spec.ts`、`frontend/e2e/test_url_conversation.spec.ts`、`frontend/e2e/test_tender_form_upload_slots.spec.ts`、`frontend/e2e/test_comment_supplement.spec.ts`。
- 异步轮询等待：`frontend/test-shims/until-async.ts` 的 `until(check, { interval, timeout })`。

## 覆盖率

**要求：**
- `frontend/jest.config.ts` 配置全局 coverage threshold：`branches`、`functions`、`lines`、`statements` 均为 `50`。
- 覆盖率收集范围：`components/`、`hooks/`、`lib/`、`stores/`（`collectCoverageFrom`）。
- 覆盖率排除：`.d.ts`、`node_modules`、`.next`。

**查看覆盖率：**
```bash
cd frontend
npm run test:coverage
```

## 测试类型

**Unit Tests：**
- API client：`frontend/__tests__/unit/lib/test_api.test.ts`。
- API base URL：`frontend/__tests__/unit/lib/test_api_base_url.test.ts`。
- SSE wrapper：`frontend/__tests__/unit/lib/test_sse.test.ts`。
- chat helper：`frontend/__tests__/unit/lib/test_chat_utils.test.ts`。
- 表单 converter / `gngk` 分派：`frontend/__tests__/unit/lib/test_form_data_converter.test.ts`。
- tender type / canonical URL：`frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`。
- stores：`frontend/__tests__/unit/stores/`（含 `test_app_store.test.ts`、`test_chat_store_*`、`test_session_persistence.test.ts`）。
- hooks：`frontend/__tests__/unit/hooks/`（`test_use_chat_sse`、`test_use_current_conversation_task_status`、`test_use_task_heartbeat`）。
- 组件：`frontend/__tests__/unit/components/`（chat / forms / layout）。
- API/SSE 类型守卫：`frontend/__tests__/unit/types/test_api_sse_agent_step.test.ts`。
- 页面：`frontend/__tests__/unit/app/test_chat_page.test.tsx`、`frontend/__tests__/unit/app/test_home_page.test.tsx`。

**Integration Tests：**
- 未检测到单独的 `frontend/__tests__/integration/` 目录。
- 跨模块行为通过 focused unit suites 和 Playwright specs 覆盖，例如 `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`、`frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`。

**E2E Tests：**
- Playwright specs 位于 `frontend/e2e/`。
- 覆盖首页、`/tender` 页面、URL 会话行为、agent run 聊天面板、生成方式切换、补充批注、上传槽位和任务展示。
- 示例：`frontend/e2e/test_home.spec.ts`、`frontend/e2e/test_url_conversation.spec.ts`、`frontend/e2e/test_agent_run_chat_panel.spec.ts`、`frontend/e2e/test_generation_mode_agent.spec.ts`、`frontend/e2e/test_comment_supplement.spec.ts`、`frontend/e2e/test_tender_form_upload_slots.spec.ts`。
- Specs 使用 mock 后端（`page.route()`），不依赖真实 FastAPI、Word COM 或真实文件下载。

## 常见模式

**异步测试：**
```typescript
await waitFor(() => {
  expect(mockGetTaskStatus).toHaveBeenCalledWith('task-1');
});
```

实际文件：`frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`。复杂等待可借助 `frontend/test-shims/until-async.ts`。

**错误测试：**
```typescript
await expect(createGenerateTask(validGenerateRequest)).rejects.toBeInstanceOf(ApiError);
await expect(createGenerateTask(validGenerateRequest)).rejects.toMatchObject({
  status: 400,
  code: 'REQ_INVALID_PARAM',
});
```

实际文件：`frontend/__tests__/unit/lib/test_api.test.ts`。

**表单与上传测试：**
- 上传控件测试断言 `uploadFile(file, fileType)` 的 `fileType`，例如 `rewrite_source` 和 `params`。
- 表单转换测试断言 `file_paths` 只包含 `template`、`tender_params`。
- `gngk` 分派测试覆盖 `tender_lx + fund_lx + ifzgcg` 到后端 `form_type` 的映射。

实际文件：`frontend/__tests__/unit/components/forms/test_file_uploader.test.tsx`、`frontend/__tests__/unit/components/forms/test_tender_no_input.test.tsx`、`frontend/__tests__/unit/lib/test_form_data_converter.test.ts`。

**Agent Run 测试：**
- `ChatPanel` 测试 mock `streamAgentRun()` 并逐个推送 `AgentRunEvent`。
- 需要覆盖 `selected_skills` 一次性发送、上传文件 rewrite、`needs_input` 不创建任务、`task_accepted` 接入任务链路。
- `generation_mode`、`comment_generation_mode`、`style_writeback_mode` 不得进入 agent run payload。

实际文件：`frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`。

**SSE 测试：**
- `useChatSSE` 测试通过 mock `useSSE()` 捕获 `latestOptions`，再用 `act()` 手动注入 `log`、`llm`、`progress`、`agent_step`、`done`、`error`。
- 运行中内容保存在 `chatStreamStore`，终态才落到 `chatStore` 的 message group。
- `TASK_NOT_FOUND` 和 backend restart 路径必须覆盖。
- 底层 `createSSEConnection` 用 `MockEventSource` 测 URL 选择、正常关闭不重连、`lastEventId` 等。

实际文件：`frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`、`frontend/__tests__/unit/lib/test_sse.test.ts`。

**Playwright 测试：**
- 使用 `page.route()` mock 后端接口和 SSE/NDJSON stream。
- 使用 `page.addInitScript()` 预置 `sessionStorage` 的 `chat-storage`。
- locator 优先使用 role、accessible name、`data-testid` 和限定容器（如 `chat-send-button`、`chat-skill-picker`、`agent-thinking-card`、`tender-type-button-xjcg`）。
- 收集 `console` error 和 `pageerror`，测试末尾断言 `consoleErrors` 为空（`expect(consoleErrors).toEqual([])`），见 `frontend/e2e/test_agent_run_chat_panel.spec.ts`。
- 需要留 evidence 时写入 requirement-scoped `tasks/<requirement-slug>/screenshots/` 与 `tasks/<requirement-slug>/logs/`，示例在 `frontend/e2e/test_generation_mode_agent.spec.ts`、`frontend/e2e/test_comment_supplement.spec.ts`、`frontend/e2e/test_agent_run_chat_panel.spec.ts`。

## 验证选择矩阵

- 纯文档变更：运行 `git diff --check`，并扫描改动文档中的密钥/token 模式；不需要跑 Jest 或 Playwright。
- API client 变更：运行 `npm run type-check`、`npm test -- --runTestsByPath __tests__/unit/lib/test_api.test.ts`。
- API base URL / Next rewrite 变更：运行 `npm run type-check`、`npm test -- --runTestsByPath __tests__/unit/lib/test_api_base_url.test.ts`，必要时运行 `npm run test:e2e`。
- 表单 / converter / `gngk` 分派变更：运行 `npm test -- --runTestsByPath __tests__/unit/lib/test_form_data_converter.test.ts __tests__/unit/components/forms/test_tender_form_shared.test.tsx __tests__/unit/components/chat/test_tender_form_registry.test.tsx`。
- 上传 rewrite / agent run 变更：运行 `npm test -- --runTestsByPath __tests__/unit/components/chat/test_chat_panel.test.tsx __tests__/unit/lib/test_api.test.ts`，按风险运行 `npm run test:e2e -- test_agent_run_chat_panel.spec.ts`。
- SSE / task 消息变更：运行 `npm test -- --runTestsByPath __tests__/unit/lib/test_sse.test.ts __tests__/unit/hooks/test_use_chat_sse.test.tsx __tests__/unit/types/test_api_sse_agent_step.test.ts`。
- URL / 会话变更：运行 `npm test -- --runTestsByPath __tests__/unit/utils/test_tender_type_mapper.test.ts __tests__/unit/stores/test_chat_store_conversation_scope.test.ts`，并运行 `npm run test:e2e -- test_url_conversation.spec.ts`。
- 浏览器交互变更：至少运行相关 Playwright spec；跨工作台改动再运行 `npm run test:e2e`。

## 覆盖边界

- Jest / Playwright 不证明真实 `.docx` 生成内容正确；完整 Word 生成闭环需要 Windows Python、pywin32 和本机 Word/WPS COM 环境。
- Playwright 当前主要验证 mock 后端下的前端契约，不能替代后端队列、LangGraph、Word COM 和外部模板候选真实链路。
- 测试夹具、console 日志、截图、长期文档不得包含真实密钥、token、客户原文、私有下载路径或完整 traceback。

---

*前端测试分析：2026-07-18*
