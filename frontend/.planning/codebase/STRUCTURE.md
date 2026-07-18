# 前端结构事实地图

**分析日期：** 2026-07-18

**范围：** `frontend/` 子项目。未读取 `.env`、`.env.*`、`.npmrc`、凭据或真实密钥文件。

## 目录布局

```text
frontend/
├── app/                     # Next.js App Router 页面、layout 和全局样式
│   └── tender/              # `/tender` 三栏招标工作台页面
├── components/
│   ├── chat/                # 类型侧栏、表单面板、聊天面板、消息卡、agent run UI
│   ├── forms/               # 招标表单、上传控件、模板候选、模型选择、共享字段
│   │   └── shared/          # 表单内部复用的低层 UI 构件
│   └── layout/              # 通用 Header、Sidebar、MainLayout、HistorySection（非 workbench 主路径）
├── hooks/                   # URL、hydration、SSE、任务状态、任务 heartbeat hooks
├── lib/                     # API client、SSE runtime、表单转换、URL/API base helper
├── stores/                  # Zustand stores
├── types/                   # API、聊天和全局招标类型
├── utils/                   # 招标类型和 canonical URL 映射
├── __tests__/               # Jest 单元测试、测试夹具
│   ├── mocks/               # 测试数据工厂、SSE mock
│   └── unit/                # 模块级单测，按源码作用域分包
├── e2e/                     # Playwright E2E specs
├── test-shims/              # 测试异步等待 helper
├── .planning/codebase/      # 前端事实文档
├── package.json             # npm scripts、依赖、Node engine
├── package-lock.json        # npm lockfile
├── next.config.ts           # Next rewrite/header/dev origin/image 配置
├── tsconfig.json            # TypeScript 主配置
├── tsconfig.typecheck.json  # 类型检查专用配置
├── eslint.config.mjs        # ESLint flat config
├── jest.config.ts           # Jest 配置
├── playwright.config.ts     # Playwright 配置
├── polyfills.js             # 测试/运行 polyfill
└── postcss.config.mjs       # Tailwind 4 PostCSS 插件
```

## 目录职责

**`frontend/app/`:**
- 职责： Next.js App Router 页面边界和全局样式。
- 包含： `layout.tsx`、`page.tsx`、`globals.css`、`tender/page.tsx`。
- 关键文件：
  - `frontend/app/page.tsx`：`redirect('/tender')`。
  - `frontend/app/tender/page.tsx`：工作台入口；组合 `TenderTypeSidebar` + `FormPanel` + `ChatPanel`；URL 会话、招标预取、conversation heartbeat。
  - `frontend/app/layout.tsx`：定义 `<html lang="zh-CN">` 和 metadata。

**`frontend/components/chat/`:**
- 职责： 工作台三栏中的类型侧栏、表单挂载、聊天交互、任务消息、agent run 和上传文件 rewrite UI。
- 包含： `ChatPanel.tsx`、`ChatInput.tsx`、`ChatModelPicker.tsx`、`FormPanel.tsx`、`TenderTypeSidebar.tsx`、`MessageList.tsx`、`TaskLogMessage.tsx`、`TaskContentMessage.tsx`、`TaskDownloadMessage.tsx`、`AgentThinkingMessage.tsx`、`DualColumnMessage.tsx`、`NewChatPopup.tsx`、`Skeleton.tsx`、`tenderFormRegistry.ts`。
- 关键文件：
  - `ChatPanel.tsx`：agent run、`rewrite_source` 上传、rewrite 终态回写、`createCommentSupplementTask`、下载。
  - `FormPanel.tsx`：generate task、`useChatSSE` / `useTaskHeartbeat` / `useCurrentConversationTaskStatus`。
  - `ChatInput.tsx`：`/rewrite` skill、Word 文件选择、`ChatModelPicker`。
  - `tenderFormRegistry.ts`：`TenderType` → 表单组件 / converter / 显示名。
- 备注： `DualColumnMessage.tsx`、`NewChatPopup.tsx`、`Skeleton.tsx` 已实现并有单测，但当前未被主流程 import（预留组件）。

**`frontend/components/forms/`:**
- 职责： 招标表单 wrapper、共享表单主体、上传、模板候选、模型选择和共享字段组件。
- 包含： `XjcgTenderForm.tsx`、`GngkTenderForm.tsx`、`GjgkTenderForm.tsx`、`TenderFormShared.tsx`、`FileUploader.tsx`、`TemplateCandidateDialog.tsx`、`ModelSelector.tsx`、`TenderNoInput.tsx`、`tenderFormConfig.ts`、`shared/`。
- 关键文件：
  - `TenderFormShared.tsx`：表单状态、上传、候选、生成选项（含 generate-only 字段）和 draft 同步。
  - `FileUploader.tsx`：经 `uploadFile` API helper 上传，不裸 `fetch`。
  - `TemplateCandidateDialog.tsx`：模板候选表格和选择/下载 UI（下载走代理 URL helper）。

**`frontend/components/forms/shared/`:**
- 职责： 表单内部复用的低层 UI 构件。
- 包含： `FormSection.tsx`、`FormField.tsx`、`ErrorDisplay.tsx`、`InfoCard.tsx`、`buttonStyles.ts`、`index.ts`。
- 关键文件： `frontend/components/forms/shared/index.ts` 是该目录的聚合导出入口。

**`frontend/components/layout/`:**
- 职责： 通用布局和历史侧栏组件。
- 包含： `Header.tsx`、`HistorySection.tsx`、`MainLayout.tsx`、`Sidebar.tsx`。
- 关键文件： `MainLayout.tsx` 组合 Sidebar + History + Header；**`/tender` 工作台不引用本目录**，直接使用 `components/chat/` 三栏。

**`frontend/hooks/`:**
- 职责： 封装 hydration、URL 参数、SSE（`useSSE`/`useChatSSE` 两层）、任务状态轮询/确认、任务 heartbeat 和活跃任务摘要。
- 包含： `useUrlParams.ts`、`useHydrated.ts`、`useSSE.ts`、`useChatSSE.ts`、`useCurrentConversationTaskStatus.ts`、`useTaskHeartbeat.ts`、`useLatestActiveTaskSummary.ts`。
- 关键文件：
  - `useChatSSE.ts`：任务 SSE → store/UI 映射。
  - `useSSE.ts`：`createSSEConnection` 生命周期；另导出 `useTaskProgress`。
  - `useUrlParams.ts`：深链参数解析（依赖 `tenderTypeMapper`）。
  - `useTaskHeartbeat.ts`：活跃 task heartbeat。
  - `useCurrentConversationTaskStatus.ts`：当前会话 task status polling。

**`frontend/lib/`:**
- 职责： API client、SSE runtime、表单转换、API base URL 解析和通用 helper。
- 包含： `api.ts`、`sse.ts`、`formDataConverter.ts`、`gngkFormType.ts`、`apiBaseUrl.ts`、`tenderFetch.ts`、`agentThinking.ts`、`chat-utils.ts`、`utils.ts`。
- 关键文件：
  - `api.ts`：唯一业务后端请求入口（组件禁止裸 `fetch`）。
  - `sse.ts`：`EventSource` 封装。
  - `formDataConverter.ts`：表单 → `GenerateRequest`（含 generation_*）。
  - `gngkFormType.ts`：`gngk` UI 类型 → 后端 form type。
  - `tenderFetch.ts`：招标详情预取与 draft 写入。
  - `agentThinking.ts`：agent run 前置 thinking card 状态机。
  - `chat-utils.ts`：消息/会话/日志纯函数。

**`frontend/stores/`:**
- 职责： Zustand 状态管理。
- 包含： `chatStore.ts`、`chatStreamStore.ts`、`chatTaskSessionStore.ts`、`historyStore.ts`、`useAppStore.ts`。
- 关键文件：
  - `chatStore.ts`：会话、draft（含 generate 字段与 `rewrite_file` / `pending_rewrite_*`）、任务消息组、URL 同步；persist `chat-storage`。
  - `chatStreamStore.ts`：运行中 SSE stream（内存）。
  - `chatTaskSessionStore.ts`：task resume 元数据；persist `chat-task-session-storage`。
  - `historyStore.ts`：生成历史列表；persist `tender-history-storage`（layout 路径）。
  - `useAppStore.ts`：侧栏/局部 UI；persist `tender-app-storage`（仅 `sidebarOpen`）。

**`frontend/types/`:**
- 职责： API、聊天、全局招标类型和测试类型补全。
- 包含： `api.ts`、`chat.ts`、`index.ts`、`jest-dom.d.ts`。
- 关键文件：
  - `api.ts`：`TaskKind`、`FileType`（含 `rewrite_source`）、`GenerateRequest`、`AgentRunStreamRequest` / `AgentRunRewriteContextSnapshot`（无 generation_*）、SSE 事件、`ErrorCodes`。
  - `chat.ts`：消息、会话、`TaskMessageKind`、agent thinking 状态。
  - `index.ts`：`TenderType`、`TenderLx`、`FundLx` 等 UI 级类型。

**`frontend/utils/`:**
- 职责： 非 React 的共享映射工具。
- 包含： `tenderTypeMapper.ts`。
- 关键文件： URL 参数解析、`TenderType` 判定（仅 `purchase_method`：`0`→`gjgk` / `2`→`gngk` / `5`→`xjcg`）、canonical URL 构造。

**`frontend/__tests__/`:**
- 职责： Jest 单元测试、测试数据工厂和 SSE mock。
- 包含： `unit/`（按 `app`/`components`/`hooks`/`lib`/`stores`/`types`/`utils` 分包）和 `mocks/`。
- 关键文件： `test_api.test.ts`、`test_use_chat_sse.test.tsx`、`test_form_data_converter.test.ts`、`stores/` 会话/任务单测、`data-factories.ts`、`sse-mock.ts`。

**`frontend/e2e/`:**
- 职责： Playwright 浏览器契约测试。
- 包含： `test_*.spec.ts`。
- 关键文件： `test_url_conversation.spec.ts`、`test_generation_mode_agent.spec.ts`、`test_comment_supplement.spec.ts`、`test_agent_run_chat_panel.spec.ts`、`test_tender_form_upload_slots.spec.ts`、`test_home.spec.ts`。

## 关键文件位置

**Entry Points:**
- `frontend/app/page.tsx`: 根路径进入 `/tender`。
- `frontend/app/layout.tsx`: 全局 metadata 和 `<html lang="zh-CN">`。
- `frontend/app/tender/page.tsx`: 工作台入口、URL 参数接入、会话 heartbeat、招标数据预取。
- `frontend/lib/api.ts`: 后端 API、上传下载、agent run、任务 API 和模板候选入口。
- `frontend/hooks/useChatSSE.ts`: 任务 SSE 到 store/UI 映射入口（底层 `lib/sse.ts`，封装层 `hooks/useSSE.ts`）。

**配置：**
- `frontend/package.json`: npm scripts、dependencies、devDependencies、Node engine `>=20.9.0`；dev 端口 `8502`。
- `frontend/package-lock.json`: npm lockfile。
- `frontend/next.config.ts`: `/api/:path*` rewrite、production cache header、allowed dev origins、image remote pattern、React strict mode。
- `frontend/tsconfig.json`: TypeScript 主配置、`@/*` alias、Next plugin、module resolution。
- `frontend/tsconfig.typecheck.json`: 类型检查专用配置。
- `frontend/eslint.config.mjs`: ESLint flat config、Next core web vitals/typescript、React hooks rule。
- `frontend/jest.config.ts`: Jest jsdom、Next Jest wrapper、`@/*` alias、coverage scope。
- `frontend/playwright.config.ts`: E2E baseURL、dev server、Chromium project。
- `frontend/postcss.config.mjs`: Tailwind 4 PostCSS 插件配置。

**Core Logic:**
- `frontend/components/chat/ChatPanel.tsx`: 聊天、agent run、rewrite、`rewrite_source` 上传、补充批注、下载和重试。
- `frontend/components/chat/ChatInput.tsx`: 聊天输入、`/rewrite` skill、上传文件 rewrite 文件卡、模型选择器。
- `frontend/components/chat/ChatModelPicker.tsx`: 聊天输入区模型下拉。
- `frontend/components/chat/FormPanel.tsx`: generate task 创建、当前任务状态、取消、表单挂载。
- `frontend/components/chat/TenderTypeSidebar.tsx`: 招标类型分组、会话列表和 URL 同步入口。
- `frontend/components/chat/MessageList.tsx`: 消息渲染分派和用户消息操作。
- `frontend/components/chat/TaskContentMessage.tsx`: AI 正文、rewrite 正文、`content_agent` / `comment_agent`。
- `frontend/components/chat/TaskDownloadMessage.tsx`: 任务产物下载卡和补充批注入口。
- `frontend/components/forms/TenderFormShared.tsx`: 表单主体、模板候选、上传、生成选项和 draft 同步。
- `frontend/components/forms/TemplateCandidateDialog.tsx`: 模板候选表格和选择/下载 UI。
- `frontend/stores/chatStore.ts`: 会话和任务状态主 store。
- `frontend/stores/chatStreamStore.ts`: 运行中 SSE stream 状态。
- `frontend/stores/chatTaskSessionStore.ts`: task resume session 状态。
- `frontend/lib/formDataConverter.ts`: 表单到 `GenerateRequest` 转换（含 generation_*）。
- `frontend/lib/gngkFormType.ts`: `gngk` form type 分派（UI 类型 → 后端 form_type）。
- `frontend/lib/tenderFetch.ts`: 招标详情预取和 draft 写入。
- `frontend/utils/tenderTypeMapper.ts`: URL 与 tender type 映射。

**Testing:**
- `frontend/__tests__/unit/`: 模块级单元测试，按 `app`、`components`、`hooks`、`lib`、`stores`、`types`、`utils` 分包。
- `frontend/__tests__/mocks/data-factories.ts`: 测试数据工厂。
- `frontend/__tests__/mocks/sse-mock.ts`: SSE 测试 mock。
- `frontend/test-shims/until-async.ts`: 测试异步等待 helper。
- `frontend/e2e/`: Playwright specs。

## 命名约定

**文件：**
- React 组件使用 PascalCase：`ChatPanel.tsx`、`FileUploader.tsx`。
- hooks 使用 `useXxx.ts`：`useChatSSE.ts`、`useTaskHeartbeat.ts`。
- stores 使用语义化 camelCase：`chatStore.ts`、`chatStreamStore.ts`。
- lib/utils 使用 camelCase 或功能名：`formDataConverter.ts`、`gngkFormType.ts`、`tenderTypeMapper.ts`。
- Jest 测试以 `test_` 开头并以 `.test.ts` / `.test.tsx` 结尾。
- Playwright 测试以 `test_` 开头并以 `.spec.ts` 结尾。
- Next App Router 页面保持框架命名：`page.tsx`、`layout.tsx`。

**Directories:**
- 按层级和职责命名：`app/`、`components/`、`hooks/`、`lib/`、`stores/`、`types/`、`utils/`。
- 组件按工作台区域分层：`chat/`、`forms/`、`layout/`。
- 表单低层复用控件放在 `forms/shared/`。
- 测试目录按测试类型和源码作用域分层：`__tests__/unit/components/chat/` 等。

## 新代码落位

**New Feature:**
- Primary code: 工作台页面编排放 `app/tender/page.tsx`；工作台交互放 `components/chat/`；表单、字段、上传、模板候选放 `components/forms/` 或 `forms/shared/`。
- Tests: 单元测试放 `__tests__/unit/<scope>/test_*.test.ts(x)`；浏览器契约放 `e2e/test_*.spec.ts`。

**New Component:**
- 聊天消息、任务 UI、侧栏、面板：`components/chat/`。
- 招标表单 wrapper：`components/forms/<Type>TenderForm.tsx`，并同步 `tenderFormRegistry.ts`。
- 表单字段/区块/错误展示等低层控件：`components/forms/shared/`。
- 通用布局壳（非 workbench 三栏）：`components/layout/`。
- Tests: 组件单测按作用域放 `__tests__/unit/components/chat/`、`forms/` 或 `layout/`。

**New Hook:**
- Implementation: `frontend/hooks/useXxx.ts`。
- SSE 生命周期类放 `useSSE.ts` 扩展或新 hook；任务 SSE 映射优先扩展 `useChatSSE.ts`。
- URL/hydration/task status/heartbeat 继续落在 `hooks/`，不要塞进组件内部重复实现。
- Tests: `__tests__/unit/hooks/test_use_xxx.test.tsx`。

**New Store:**
- 会话/任务/draft 主状态优先扩展 `stores/chatStore.ts`，避免再开平行会话 store。
- 运行中 SSE stream 状态放 `stores/chatStreamStore.ts`（内存）。
- 任务 resume 元数据放 `stores/chatTaskSessionStore.ts`。
- 非 workbench 局部 UI 可扩展 `useAppStore.ts` / `historyStore.ts`。
- Tests: `__tests__/unit/stores/test_*.test.ts`。

**New Types:**
- 后端 API shape、SSE、agent run、上传/任务类型：`types/api.ts`。
- 聊天消息、会话、messageKind、thinking 状态：`types/chat.ts`。
- UI 级招标类型与通用前端类型：`types/index.ts`。
- API shape 变更必须同步 `lib/api.ts`、调用方和测试。

**Utilities:**
- 通用 class/helper → `lib/utils.ts`。
- API base URL → `lib/apiBaseUrl.ts`。
- URL / tender type 映射 → `utils/tenderTypeMapper.ts`。
- 消息/会话纯函数 → `lib/chat-utils.ts`。
- 表单 → `GenerateRequest` → `lib/formDataConverter.ts`。
- `gngk` 后端 form type 分派 → `lib/gngkFormType.ts`（generate 与 rewrite 共用）。
- API helpers：后端请求只进 `lib/api.ts`，同步 `types/api.ts`。**禁止**在 `components/` 写裸 `fetch`。
- SSE helpers：`EventSource` → `lib/sse.ts`；生命周期 → `hooks/useSSE.ts`；任务映射 → `hooks/useChatSSE.ts`。

**Contracts 同步清单:**
- API shape 变化：同步 `types/api.ts`、`lib/api.ts`、相关调用组件、store 和测试。
- SSE 事件变化：同步 `types/api.ts`、`lib/sse.ts`、`hooks/useChatSSE.ts`、相关 unit tests。
- `TenderType` 或 `form_type` 变化：同步 `types/index.ts`、`types/api.ts`、`tenderFormRegistry.ts`、`formDataConverter.ts`、`gngkFormType.ts`、`tenderTypeMapper.ts`。
- **`gngk`：** 仅 UI 类型；后端 form type 只经 `gngkFormType.ts` 分派，generate 与 rewrite 共用。
- Agent run / rewrite：同步 `types/api.ts`、`lib/api.ts`、`ChatPanel.tsx`、`ChatInput.tsx`、`chatStore.ts`。
- 上传文件 rewrite：同步 `FileType`（`rewrite_source`）、`ChatInput`/`ChatPanel`、agent context 类型；**不要**把 generation_* 加入 rewrite 请求。
- 任务产物展示：同步 `types/chat.ts`、`chatStore.ts`、`useChatSSE.ts`、`MessageList.tsx`、`TaskDownloadMessage.tsx`。

**New Tests:**
- 单元：`__tests__/unit/<对应源码目录>/test_<topic>.test.ts(x)`。
- 测试工厂/SSE mock：`__tests__/mocks/`。
- E2E：`e2e/test_<topic>.spec.ts`。
- 异步等待 helper：优先复用 `test-shims/until-async.ts`。

## 特殊目录

**`frontend/.planning/codebase/`:**
- 职责： 前端事实文档，供后续计划和执行阶段消费。
- Generated: Yes.
- Committed: Yes，按仓库文档策略维护。

**`frontend/.next/`:**
- 职责： Next.js 构建/开发缓存。
- Generated: Yes.
- Committed: No.

**`frontend/.swc/`:**
- 职责： SWC/Next 相关缓存。
- Generated: Yes.
- Committed: No.

**`frontend/node_modules/`:**
- 职责： npm 依赖目录。
- Generated: Yes.
- Committed: No.

**`frontend/test-shims/`:**
- 职责： 测试异步等待 helper。
- Generated: No.
- Committed: Yes.

**`frontend/__tests__/mocks/`:**
- 职责： Jest 测试数据工厂和 SSE mock。
- Generated: No.
- Committed: Yes.

**环境配置文件：**
- 职责： 本地运行配置。
- Generated: Mixed.
- Committed: 真实环境文件不应提交。
- Notes: 不读取、不记录 `frontend/.env.local`、`.env.*`、`.npmrc` 或任何凭据内容；需要配置事实时从代码、示例说明或公开配置推断。

---

*前端结构分析：2026-07-18*
