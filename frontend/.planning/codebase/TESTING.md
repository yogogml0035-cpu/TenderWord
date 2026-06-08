# 前端测试事实地图

**分析日期：** 2026-06-08

**范围：** `frontend/__tests__/`、`frontend/e2e/`、`frontend/mocks/`、`frontend/jest.config.ts`、`frontend/playwright.config.ts` 和前端验证脚本。

## 测试框架

**运行器：**
- Jest `^29.7.0` - 单元/集成测试。
- Config: `frontend/jest.config.ts`。
- Environment: `jsdom`。
- Setup: `setupFiles` 使用 `frontend/polyfills.js`，`setupFilesAfterEnv` 使用 `frontend/jest.setup.js`。
- 注意：`frontend/jest.setup.ts` 存在，但当前 Jest 配置实际引用的是 `frontend/jest.setup.js`。

**断言库：**
- Jest expect。
- `@testing-library/jest-dom`，见 `frontend/jest.setup.js`。
- Testing Library React 和 user-event，见 `frontend/__tests__/unit/components/`。

**E2E 运行器：**
- Playwright `@playwright/test`。
- Config: `frontend/playwright.config.ts`。
- Browser project: Chromium，非 CI 默认可使用系统 Chrome channel。

**运行命令：**

```bash
cd frontend
npm run lint           # ESLint
npm run type-check     # tsc -p tsconfig.typecheck.json --noEmit
npm run test           # Jest 全量测试
npm run test:watch     # Jest watch
npm run test:coverage  # Jest coverage
npm run test:e2e       # Playwright E2E
```

WSL 或跨 Windows 环境运行前端测试时优先使用：

```bash
cd frontend
TMPDIR=/tmp TMP=/tmp TEMP=/tmp npm run type-check
TMPDIR=/tmp TMP=/tmp TEMP=/tmp CI=1 npm test -- --runInBand
```

## 测试文件组织

**位置：**
- Jest 测试集中在 `frontend/__tests__/`，不与源码文件并排。
- Playwright 测试集中在 `frontend/e2e/`。
- MSW mock 集中在 `frontend/mocks/`。

**命名：**
- Jest 测试文件：`test_*.test.ts` 或 `test_*.test.tsx`。
- Playwright 测试文件：`test_*.spec.ts`。
- 测试工具/fixture 不一定以 `test_` 开头，例如 `frontend/__tests__/mocks/data-factories.ts`。

**结构：**

```text
frontend/__tests__/
├── integration/
│   └── examples/
├── mocks/
│   ├── data-factories.ts
│   └── sse-mock.ts
├── unit/
│   ├── app/
│   ├── components/
│   │   ├── chat/
│   │   ├── forms/
│   │   └── layout/
│   ├── hooks/
│   ├── lib/
│   ├── stores/
│   ├── types/
│   └── utils/
└── utils/
    ├── setup.ts
    └── test-utils.tsx

frontend/e2e/
└── test_*.spec.ts
```

## 测试结构

**测试套件组织：**

```typescript
describe('API Client', () => {
  beforeEach(() => {
    globalThis.fetch = jest.fn() as unknown as typeof fetch;
  });

  describe('createGenerateTask', () => {
    it('should return task info on success', async () => {
      // arrange fetch mock
      // act
      // assert returned task fields and request body
    });
  });
});
```

实际示例见 `frontend/__tests__/unit/lib/test_api.test.ts`。

**Hook Testing Pattern：**

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

实际示例见 `frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`。

**模式：**
- 每个 store/hook 测试先清理 `window.localStorage` 和 `window.sessionStorage`。
- Zustand store 测试使用 `useXxxStore.setState()` 构造状态。
- API client 测试直接 mock `globalThis.fetch` 并验证 request body、错误码和返回值。
- 组件测试使用 Testing Library 的 role/text/testid，必要时用 `userEvent`。
- Playwright 测试用 `page.route` mock 后端时，把不依赖 Word COM 的浏览器契约固化为 E2E。

## Mock 方式

**框架：**
- Jest mocks。
- MSW for API mock server。
- Playwright route mocks for browser tests。

**MSW Pattern：**

```typescript
import { setupServer } from 'msw/node';
import { handlers } from './handlers';

export const server = setupServer(...handlers);
```

实际文件：`frontend/mocks/server.ts`、`frontend/mocks/handlers.ts`。

**Fetch Mock Pattern：**

```typescript
globalThis.fetch = jest.fn().mockResolvedValue({
  ok: true,
  status: 200,
  json: async () => ({ success: true, data: {} }),
} as unknown as Response) as unknown as typeof fetch;
```

实际文件：`frontend/__tests__/unit/lib/test_api.test.ts`。

**What to Mock：**
- 后端 API response、fetch stream、SSE hook、task status、sessionStorage/localStorage。
- Word COM、真实后端队列、真实下载文件内容和外部模板文件 URL。

**What NOT to Mock：**
- 纯转换/解析 helper 的核心逻辑，例如 `frontend/lib/formDataConverter.ts`、`frontend/lib/gngkFormType.ts`、`frontend/utils/tenderTypeMapper.ts`。
- Store reducer/action 的状态迁移本身，除非测试目标是 UI 组件且 store 行为已在 store 测试覆盖。

## 夹具与工厂

**测试数据：**

```typescript
export class ConversationFactory {
  static create(overrides?: Partial<Conversation>): Conversation {
    const now = Date.now();
    return {
      id: generateId('conv'),
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
- Testing Library render helper：`frontend/__tests__/utils/test-utils.tsx`。
- MSW handlers：`frontend/mocks/handlers.ts`。

## 覆盖率

**Requirements：**
- `frontend/jest.config.ts` 配置全局 coverage threshold：branches/functions/lines/statements 均为 50。
- Coverage 收集范围：`components/`、`hooks/`、`lib/`、`stores/`。
- Coverage 排除：`.d.ts`、`node_modules`、`.next`、`frontend/mocks/`。

**查看覆盖率：**

```bash
cd frontend
npm run test:coverage
```

## 测试类型

**单元测试：**
- Scope: API client、pure helper、stores、hooks、组件细节和类型守卫。
- Examples: `frontend/__tests__/unit/lib/test_api.test.ts`、`frontend/__tests__/unit/stores/test_chat_store_task_messages.test.ts`、`frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`。

**集成测试：**
- Scope: Testing Library provider/render 示例和跨小模块行为。
- Examples: `frontend/__tests__/integration/examples/test_example_component.test.tsx`。

**E2E 测试：**
- Framework: Playwright。
- Scope: `/tender` 页面、URL 会话行为、agent run 聊天面板、生成模式、补充批注、上传槽位等浏览器契约。
- Examples: `frontend/e2e/test_home.spec.ts`、`frontend/e2e/test_url_conversation.spec.ts`、`frontend/e2e/test_generation_mode_agent.spec.ts`、`frontend/e2e/test_comment_supplement.spec.ts`。

## 常见模式

**异步测试：**

```typescript
await waitFor(() => {
  expect(mockGetTaskStatus).toHaveBeenCalledWith('task-1');
});

act(() => {
  latestOptions?.onMessage?.({ event: 'llm', data: payload });
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

**Store Testing：**
- 清空 browser storage。
- `useChatStore.setState()` 建立 conversations、currentConversationId、activeTaskIds、taskMessageMap。
- 调用 store action。
- 断言 conversation messages、task summary、stream store 或 storage key。

**Playwright Pattern：**
- Playwright config 的 baseURL 是 `http://localhost:8502`。
- `webServer.command` 是 `npm run dev -- --webpack`。
- locator 优先使用 role、accessible name、`data-testid` 或限定容器。
- 对不依赖真实后端/Word COM 的流程，使用 `page.route` mock `/api/*`。

## 按变更类型选择测试

- API client：`frontend/__tests__/unit/lib/test_api.test.ts`。
- API base URL / Next rewrite 相关：`frontend/__tests__/unit/lib/test_api_base_url.test.ts`，必要时人工检查 `frontend/next.config.ts`。
- URL / 会话 identity：`frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`、`frontend/__tests__/unit/stores/test_chat_store_conversation_scope.test.ts`、`frontend/e2e/test_url_conversation.spec.ts`。
- 表单和 converter：`frontend/__tests__/unit/components/forms/`、`frontend/__tests__/unit/lib/test_form_data_converter.test.ts`、`frontend/__tests__/unit/components/chat/test_tender_form_registry.test.tsx`。
- `gngk` 分派：`frontend/__tests__/unit/lib/test_form_data_converter.test.ts`、`frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`。
- SSE / task：`frontend/__tests__/unit/lib/test_sse.test.ts`、`frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`、`frontend/__tests__/unit/types/test_api_sse_agent_step.test.ts`。
- Agent run / rewrite：`frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`、`frontend/e2e/test_agent_run_chat_panel.spec.ts`。
- 补充批注：`frontend/__tests__/unit/lib/test_api.test.ts`、`frontend/__tests__/unit/components/chat/test_message_list.test.tsx`、`frontend/e2e/test_comment_supplement.spec.ts`。

## 测试覆盖缺口

- 真实后端 + Word COM 生成闭环不属于常规前端 Jest 覆盖；需要 Windows Python、pywin32 和 Word/WPS COM 环境。
- Playwright 当前更适合验证 mock 后端下的前端契约，不能证明生成文件内容正确。
- `frontend/jest.setup.ts` 与 `frontend/jest.setup.js` 并存，当前配置只使用 `.js`，修改测试 setup 时要同步确认实际入口。
- `frontend/mocks/handlers.ts` 的基础 mock 覆盖有限，复杂任务事件更多依赖单测内 mock 或 Playwright route。

---

*前端测试分析：2026-06-08*
