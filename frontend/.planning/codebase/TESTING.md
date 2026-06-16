# 前端测试约定

**分析日期：** 2026-06-16

**范围：** `frontend/__tests__/`、`frontend/e2e/`、`frontend/test-shims/`、`frontend/jest.config.ts`、`frontend/playwright.config.ts`、`frontend/package.json`、`frontend/tsconfig.typecheck.json` 和前端事实文档。`frontend/.env.local`、`frontend/.env.local.example`、`frontend/.npmrc` 仅确认存在，不读取内容。

> 本轮（feat-wsq）已移除 MSW mock 层（`frontend/mocks/handlers.ts`、`frontend/mocks/server.ts`）、`jest.setup.ts`、`polyfills.ts`、`__tests__/utils/`（setup/test-utils）、`__tests__/integration/` 以及 `msw`、`jest-fetch-mock`、`und`、`undici` 依赖；Jest 本身仍在，单测改为直接 mock `globalThis.fetch`，setup 入口统一为 `jest.setup.js` / `polyfills.js`。

## 测试框架

**运行器：**
- Jest `^29.7.0` 用于单元测试和 Testing Library 集成测试。
- 配置：`frontend/jest.config.ts`。
- 环境：`jsdom`。
- `setupFiles`: `frontend/polyfills.js`。
- `setupFilesAfterEnv`: `frontend/jest.setup.js`（`jest.setup.ts` 与 `polyfills.ts` 已在本轮移除，入口统一为 `.js` 版本）。
- `frontend/types/jest-dom.d.ts`（本轮新增）补齐 `@testing-library/jest-dom` matcher 的全局 TS 类型，测试文件无需逐个 import。

**断言库：**
- Jest `expect`。
- `@testing-library/jest-dom`，由 `frontend/jest.setup.js` 注册。
- React 组件测试使用 `@testing-library/react` 和 `@testing-library/user-event`。

**E2E 运行器：**
- Playwright `@playwright/test` 用于浏览器契约测试。
- 配置：`frontend/playwright.config.ts`。
- `testDir` 为 `frontend/e2e/`。
- 浏览器项目为 `chromium`；非 CI 且 `PLAYWRIGHT_USE_SYSTEM_CHROME` 未设为 `0` 时使用系统 Chrome channel。

**运行命令：**
```bash
cd frontend
npm run lint           # ESLint flat config
npm run type-check     # tsc -p tsconfig.typecheck.json --noEmit
npm run test           # Jest 全量测试
npm run test:watch     # Jest watch
npm run test:coverage  # Jest coverage
npm run test:e2e       # Playwright E2E
npm run test:e2e:ui    # Playwright UI
npm run test:e2e:debug # Playwright debug
```

**WSL / 跨平台临时目录模式：**
```bash
cd frontend
TMPDIR=/tmp TMP=/tmp TEMP=/tmp npm run type-check
TMPDIR=/tmp TMP=/tmp TEMP=/tmp CI=1 npm test -- --runInBand
```

## 测试文件组织

**位置：**
- Jest 测试集中在 `frontend/__tests__/unit/`，不与源码文件并排。
- Playwright 测试集中在 `frontend/e2e/`。
- 测试数据工厂和 SSE mock 位于 `frontend/__tests__/mocks/`。
- 异步测试等待工具位于 `frontend/test-shims/until-async.ts`。
- 本轮已移除 `frontend/mocks/`（MSW handlers/server）、`frontend/__tests__/utils/`（setup/test-utils）和 `frontend/__tests__/integration/`；不要再向这些路径新增文件。

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

## 测试结构

**套件组织：**
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

**Hook 测试模式：**
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

**组件测试模式：**
```typescript
render(<ChatPanel />);

await user.type(screen.getByTestId('chat-input'), '请帮我改写这一段内容');
await user.click(screen.getByTestId('chat-send-button'));

expect(mockStreamAgentRun).toHaveBeenCalledWith(
  expect.objectContaining({ selected_skills: ['rewrite'] }),
  expect.any(Object)
);
```

实际模式见 `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`。

**模式：**
- 每个 store/hook 测试先清理 `window.localStorage` 和 `window.sessionStorage`。
- Zustand store 测试使用 `useXxxStore.setState()` 构造状态，再调用 action 并断言 state。
- API client 测试直接 mock `globalThis.fetch`，断言 endpoint、request body、错误码和返回值。
- 组件测试优先使用 role、label、text、testid 和 `userEvent`，避免依赖视觉 class。
- Playwright 测试用 `page.route()` mock `/api/*`，把不依赖 Word COM 的浏览器契约固定下来。

## Mock 方式

**框架：**
- Jest mock function / module mock。
- Playwright `page.route()`。

**Fetch Mock 模式：**
```typescript
globalThis.fetch = jest.fn().mockResolvedValue({
  ok: true,
  status: 200,
  json: async () => ({ success: true, data: { task_id: 'task-123' } }),
} as unknown as Response) as unknown as typeof fetch;
```

实际文件：`frontend/__tests__/unit/lib/test_api.test.ts`。

**SSE Mock 模式：**
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

实际文件：`frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`。

**需要 Mock 的内容：**
- 后端 API response、fetch stream、SSE hook、task status、heartbeat、sessionStorage/localStorage。
- Agent run NDJSON：`run_started`、`thinking_stage`、`task_accepted`、`needs_input`、`done`、`error`。
- Playwright 中的 `/api/generate`、`/api/agent/runs/stream`、`/api/stream/{taskId}`、`/api/tasks/{taskId}`、conversation heartbeat。
- Word COM、真实后端队列、真实下载文件内容、真实模板候选外部 URL。

**不要 Mock 的内容：**
- 纯转换逻辑：`frontend/lib/formDataConverter.ts`、`frontend/lib/gngkFormType.ts`、`frontend/utils/tenderTypeMapper.ts`。
- Store action 的状态迁移本身；组件测试可 mock API，但 store 测试要直接覆盖 action。
- API client 的 request body 关键字段；测试应断言真实 payload shape。

## 夹具与工厂

**测试数据：**
```typescript
export class ConversationFactory {
  static create(overrides?: Partial<Conversation>): Conversation {
    const now = Date.now();
    const id = generateId('conv');
    return {
      id,
      title: 'Test Conversation',
      tenderType: 'xjcg',
      messages: [],
      createdAt: now,
      updatedAt: now,
      ...overrides,
    };
  }
}
```

实际文件：`frontend/__tests__/mocks/data-factories.ts`。

**位置：**
- 通用数据工厂：`frontend/__tests__/mocks/data-factories.ts`。
- SSE mock：`frontend/__tests__/mocks/sse-mock.ts`。
- Testing Library render 现直接使用 `@testing-library/react`，不再经过 `frontend/__tests__/utils/test-utils.tsx`（本轮已移除）。
- Playwright session seed 使用 `page.addInitScript()` 写入 `sessionStorage`，见 `frontend/e2e/test_agent_run_chat_panel.spec.ts`、`frontend/e2e/test_generation_mode_agent.spec.ts`。

## 覆盖率

**要求：**
- `frontend/jest.config.ts` 配置全局 coverage threshold：`branches`、`functions`、`lines`、`statements` 均为 `50`。
- 覆盖率收集范围：`components/`、`hooks/`、`lib/`、`stores/`。
- 覆盖率排除：`.d.ts`、`node_modules`、`.next`、`__tests__/mocks/`。

**查看覆盖率：**
```bash
cd frontend
npm run test:coverage
```

## 测试类型

**单元测试：**
- API client：`frontend/__tests__/unit/lib/test_api.test.ts`。
- API base URL：`frontend/__tests__/unit/lib/test_api_base_url.test.ts`。
- SSE wrapper：`frontend/__tests__/unit/lib/test_sse.test.ts`。
- 表单 converter / gngk 分派：`frontend/__tests__/unit/lib/test_form_data_converter.test.ts`。
- tender type / canonical URL：`frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`。
- stores：`frontend/__tests__/unit/stores/`。
- hooks：`frontend/__tests__/unit/hooks/`。
- 组件：`frontend/__tests__/unit/components/`。
- 类型守卫 / SSE 类型：`frontend/__tests__/unit/types/test_api_sse_agent_step.test.ts`。

**集成测试：**
- 本轮已移除 `frontend/__tests__/integration/`（含 `test_example_component.test.tsx`）；跨模块行为由 unit suites 和 Playwright specs 覆盖，不再维护独立集成测试目录。

**E2E 测试：**
- Playwright specs 位于 `frontend/e2e/`。
- 覆盖 `/tender` 页面、URL 会话行为、agent run 聊天面板、生成方式切换、补充批注、上传槽位等浏览器契约。
- 示例：`frontend/e2e/test_home.spec.ts`、`frontend/e2e/test_url_conversation.spec.ts`、`frontend/e2e/test_agent_run_chat_panel.spec.ts`、`frontend/e2e/test_generation_mode_agent.spec.ts`、`frontend/e2e/test_comment_supplement.spec.ts`、`frontend/e2e/test_tender_form_upload_slots.spec.ts`。
- Playwright 配置的 `baseURL` 是 `http://localhost:8502`，`webServer.command` 是 `npm run dev -- --webpack`。

## 常见模式

**异步测试：**
```typescript
await waitFor(() => {
  expect(mockGetTaskStatus).toHaveBeenCalledWith('task-1');
});
```

实际文件：`frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`。

**错误测试：**
```typescript
await expect(createGenerateTask(validGenerateRequest)).rejects.toBeInstanceOf(ApiError);
await expect(createGenerateTask(validGenerateRequest)).rejects.toMatchObject({
  status: 400,
  code: 'REQ_INVALID_PARAM',
});
```

实际文件：`frontend/__tests__/unit/lib/test_api.test.ts`。

**Store 测试：**
- 清空 browser storage。
- 使用 `useChatStore.setState()` 建立 `conversations`、`currentConversationId`、`conversationDrafts`、`taskSummaries`、`taskMessageMap`。
- 调用 store action。
- 断言 conversation messages、task summary、stream store 或 persisted storage key。

实际文件：`frontend/__tests__/unit/stores/test_chat_store_task_messages.test.ts`、`frontend/__tests__/unit/stores/test_chat_store_conversation_scope.test.ts`。

**Playwright 测试：**
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

实际文件：`frontend/e2e/test_generation_mode_agent.spec.ts`。

## API Client 测试入口

- 新增或修改 API helper 时，先补 `frontend/__tests__/unit/lib/test_api.test.ts`。
- 必须覆盖 success response、wrapped/flat response 兼容、error response、network error、request body 和 endpoint。
- 上传文件类型变化必须断言 `FormData.file_type`，例如 `rewrite_source` 在 `frontend/__tests__/unit/lib/test_api.test.ts` 和 `frontend/__tests__/unit/components/forms/test_file_uploader.test.tsx` 中覆盖。
- 模板候选变化覆盖 `fetchTemplateCandidates()`、`selectTemplateCandidate()`、`getTemplateCandidateDownloadUrl()`。
- `NEXT_PUBLIC_API_URL` 或 rewrite/base URL 行为变化覆盖 `frontend/__tests__/unit/lib/test_api_base_url.test.ts`，并人工检查 `frontend/next.config.ts`。

## 类型同步测试入口

- API/SSE 类型变化覆盖 `frontend/__tests__/unit/types/test_api_sse_agent_step.test.ts`、`frontend/__tests__/unit/lib/test_sse.test.ts`、`frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`。
- `TaskKind`、`TaskStatus`、`SSEDoneEvent`、`TaskResult`、写回摘要字段变化要覆盖任务消息和下载卡：`frontend/__tests__/unit/components/chat/test_message_list.test.tsx`、`frontend/__tests__/unit/components/chat/test_task_content_message.test.tsx`、`frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`。
- Agent run NDJSON 事件变化覆盖 `frontend/__tests__/unit/lib/test_api.test.ts` 的 `streamAgentRun` 相关 suites 和 `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`。

## 表单、状态与上传测试入口

- 表单 UI 和 draft 同步：`frontend/__tests__/unit/components/forms/test_tender_form_shared.test.tsx`。
- 表单 wrapper：`frontend/__tests__/unit/components/forms/test_xjcg_tender_form.test.tsx`、`frontend/__tests__/unit/components/forms/test_gngk_tender_form.test.tsx`。
- 上传控件：`frontend/__tests__/unit/components/forms/test_file_uploader.test.tsx`。
- 表单 converter：`frontend/__tests__/unit/lib/test_form_data_converter.test.ts`。
- 表单注册表：`frontend/__tests__/unit/components/chat/test_tender_form_registry.test.tsx`。
- URL / 会话 identity：`frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`、`frontend/__tests__/unit/stores/test_chat_store_conversation_scope.test.ts`、`frontend/e2e/test_url_conversation.spec.ts`。
- 上传槽位浏览器契约：`frontend/e2e/test_tender_form_upload_slots.spec.ts`。

## Generate-only 字段测试入口

- `generation_mode`、`comment_generation_mode`、`style_writeback_mode` 进入 generate payload：`frontend/__tests__/unit/lib/test_form_data_converter.test.ts`、`frontend/__tests__/unit/components/chat/test_tender_form_registry.test.tsx`、`frontend/e2e/test_generation_mode_agent.spec.ts`。
- 这些字段不得进入 agent run / rewrite payload：`frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx` 断言 `streamAgentRun` payload 不含 `generation_mode` 和 `comment_generation_mode`。
- `comment_generation_mode=off` 的浏览器行为由 `frontend/e2e/test_generation_mode_agent.spec.ts` 覆盖。
- `style_writeback_mode` 的 draft UI 行为由 `frontend/__tests__/unit/components/forms/test_tender_form_shared.test.tsx` 覆盖。

## Agent Run、Rewrite 与补充批注测试入口

- `$skill` / slash skill 输入和 `selected_skills` 解析：`frontend/__tests__/unit/components/chat/test_chat_input.test.tsx`。
- Agent run payload、thinking card、fake task、rewrite 文件链路：`frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`。
- 上传文件 rewrite 必须覆盖 `uploadFile(file, 'rewrite_source')`、`uploaded_files`、`rewrite_context` 和 `selected_skills: ['rewrite']`。
- Agent run 浏览器契约：`frontend/e2e/test_agent_run_chat_panel.spec.ts`。
- 补充批注任务创建和 `comment_agent` 展示：`frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`、`frontend/__tests__/unit/components/chat/test_message_list.test.tsx`、`frontend/e2e/test_comment_supplement.spec.ts`。
- rewrite 和 `comment_supplement` 下载卡不得再次显示补充批注动作，覆盖在 `frontend/components/chat/TaskDownloadMessage.tsx` 相关组件测试和 message list 测试。

## Playwright 约定

- 使用 `page.route()` mock 后端，不依赖真实 FastAPI、Word COM 或真实文件下载。
- 使用 `page.addInitScript()` 预置 `sessionStorage`，保持 `/tender` 页面进入指定会话状态。
- locator 优先使用 role、accessible name、`data-testid` 和限定容器。
- 收集 `console` error 和 `pageerror`，测试末尾断言为空。
- 需要落地 evidence 的 specs 可以写入 `tasks/<requirement-slug>/screenshots/` 和 `tasks/<requirement-slug>/logs/`，现有示例位于 `frontend/e2e/test_generation_mode_agent.spec.ts`。

## 验证选择矩阵

- 纯文档变更：运行 `git diff --check`，并扫描改动文档中是否出现密钥/token 模式。
- API client 变更：运行 `npm run type-check`、`npm test -- --runTestsByPath __tests__/unit/lib/test_api.test.ts`。
- API base URL / Next rewrite 变更：运行 `npm run type-check`、`npm test -- --runTestsByPath __tests__/unit/lib/test_api_base_url.test.ts`，必要时跑 `npm run test:e2e`。
- 表单 / converter / `gngk` 分派变更：运行 `npm test -- --runTestsByPath __tests__/unit/lib/test_form_data_converter.test.ts __tests__/unit/components/forms/test_tender_form_shared.test.tsx __tests__/unit/components/chat/test_tender_form_registry.test.tsx`。
- 上传 rewrite / agent run 变更：运行 `npm test -- --runTestsByPath __tests__/unit/components/chat/test_chat_panel.test.tsx __tests__/unit/lib/test_api.test.ts`，并按风险跑 `npm run test:e2e -- test_agent_run_chat_panel.spec.ts`。
- SSE / task 消息变更：运行 `npm test -- --runTestsByPath __tests__/unit/lib/test_sse.test.ts __tests__/unit/hooks/test_use_chat_sse.test.tsx __tests__/unit/types/test_api_sse_agent_step.test.ts`。
- URL / 会话变更：运行 `npm test -- --runTestsByPath __tests__/unit/utils/test_tender_type_mapper.test.ts __tests__/unit/stores/test_chat_store_conversation_scope.test.ts`，并跑 `npm run test:e2e -- test_url_conversation.spec.ts`。
- 浏览器交互变更：至少运行相关 Playwright spec；跨工作台改动再运行 `npm run test:e2e`。

## 测试覆盖缺口

- 真实后端 + Word COM 生成闭环不属于常规前端 Jest / Playwright 覆盖，需要 Windows Python、pywin32 和本机 Word/WPS COM 环境。
- Playwright 当前主要验证 mock 后端下的前端契约，不能证明生成 `.docx` 内容正确。
- 本轮移除 MSW 后不再有统一 mock 层；复杂 agent run、SSE 和任务事件依赖单测内的 `globalThis.fetch` mock 或 Playwright `page.route()`。
- `frontend/test-shims/until-async.ts` 在本轮 `jest.config.ts` 移除 `'^until-async
` moduleNameMapper 映射后，可能变为无引用孤儿文件；新增引用前先确认是否仍被使用。

---

*测试分析：2026-06-16*
