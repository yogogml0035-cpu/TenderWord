# 前端测试事实地图

**分析日期：** 2026-05-31

**范围：** `frontend/__tests__/`、`frontend/e2e/` 与前端验证命令。

## 测试框架

- 单元/集成：Jest + Testing Library + jsdom。
- API mock：MSW。
- E2E：Playwright。
- Jest 配置：`frontend/jest.config.ts`。
- Playwright 配置：`frontend/playwright.config.ts`。

## 测试文件组织

```text
frontend/__tests__/
├── integration/
├── mocks/
├── unit/
│   ├── app/
│   ├── components/
│   ├── hooks/
│   ├── lib/
│   ├── stores/
│   └── utils/
└── utils/

frontend/e2e/
└── test_*.spec.ts
```

新增或重命名测试必须以 `test_` 开头；不要在源码目录旁边并排放测试文件。

## 关键覆盖入口

- 页面：`frontend/__tests__/unit/app/test_home_page.test.tsx`、`frontend/__tests__/unit/app/test_chat_page.test.tsx`。
- 聊天组件：`frontend/__tests__/unit/components/chat/`。
- 表单组件：`frontend/__tests__/unit/components/forms/`。
- API client：`frontend/__tests__/unit/lib/test_api.test.ts`、`test_api_base_url.test.ts`。
- 表单转换器与 `gngk` form type 分派：`frontend/__tests__/unit/lib/test_form_data_converter.test.ts`、`frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`。
- SSE：`frontend/__tests__/unit/lib/test_sse.test.ts`、`frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`、`frontend/__tests__/unit/types/test_api_sse_agent_step.test.ts`。
- store：`frontend/__tests__/unit/stores/`。
- URL 映射：`frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`。
- E2E：`frontend/e2e/test_home.spec.ts`、`frontend/e2e/test_url_conversation.spec.ts`、`frontend/e2e/test_generation_mode_agent.spec.ts`。
- 补充批注：`frontend/__tests__/unit/lib/test_api.test.ts`、`frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`、`frontend/__tests__/unit/components/chat/test_message_list.test.tsx`、`frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`、`frontend/e2e/test_comment_supplement.spec.ts`。

## Mock 与测试夹具

- `frontend/mocks/handlers.ts` 与 `frontend/mocks/server.ts` 提供 MSW mock。
- `frontend/__tests__/mocks/` 和 `frontend/__tests__/utils/` 提供测试数据与渲染工具。
- task 恢复 fixture 必须包含 `conversation.currentTaskId`、`activeTaskIds`、`taskSummaries` 和对应消息 `taskId`。
- agent step fixture 应区分未完成快照和完成态过程卡，避免把高频 stream 片段直接持久化。
- Playwright 可用 `page.route` mock 后端，优先覆盖不依赖 Word COM 的前端契约。

## 验证命令

常规前端验证：

```bash
cd frontend
npm run lint
npm run type-check
npm run test
```

WSL 推荐：

```bash
cd frontend
TMPDIR=/tmp TMP=/tmp TEMP=/tmp npm run lint
TMPDIR=/tmp TMP=/tmp TEMP=/tmp npm run type-check
TMPDIR=/tmp TMP=/tmp TEMP=/tmp CI=1 npm test -- --runInBand
```

E2E：

```bash
cd frontend
npm run test:e2e
```

文档变更：

```bash
git diff --check
```

## Playwright 约定

- E2E 统一放在 `frontend/e2e/test_*.spec.ts`。
- `baseURL` 是 `http://localhost:8502`。
- 稳定行为应固化为 Playwright spec，DevTools/浏览器观察只算探路。
- locator 优先使用 role + accessible name、`data-testid` 或限定容器，避免宽泛 `getByText()`。
- 涉及真实任务创建、SSE、完成和下载且需要后端/COM 时，验证说明要写清环境和 mock 范围。

## 按变更类型选择测试

- API client：`frontend/__tests__/unit/lib/test_api.test.ts`，必要时同步类型测试。
- URL / 会话：`test_tender_type_mapper.test.ts`、`test_chat_store_conversation_scope.test.ts`、`frontend/e2e/test_url_conversation.spec.ts`。
- 表单/转换器：相关表单测试、`test_form_data_converter.test.ts`、`test_chat_panel.test.tsx` 中的 edit form type 覆盖、注册表测试。
- SSE/任务：`test_use_chat_sse.test.tsx`、`test_sse.test.ts`、`test_api_sse_agent_step.test.ts`、task store 测试、`test_use_task_heartbeat.test.tsx`。
- 模板候选：表单与 API client 测试，必要时补弹窗交互测试。
- UI/页面：相关组件测试，真实浏览器契约补 Playwright。
- 智能体生成方式与批注开关：`test_tender_form_shared.test.tsx`、`test_form_data_converter.test.ts`、`test_chat_panel.test.tsx`、`test_generation_mode_agent.spec.ts`。
- 补充批注：API client、下载卡动作、`comment_agent` 过程卡、任务下载卡和 mock E2E。

## 覆盖缺口

- 真实后端 + Word COM 任务链路不适合作为常规前端单测。
- 下载文件内容和 Word 结果验证应由后端/人工 Windows 环境承担。
- 目前 E2E 覆盖仍偏 URL 和首页基础行为，复杂任务 UI 可继续扩展 mock E2E。

---

*前端测试分析：2026-05-31*
