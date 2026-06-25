# 前端结构事实地图

**分析日期：** 2026-06-25

**范围：** `frontend/` 子项目。未读取 `.env`、`.env.*`、`.npmrc`、凭据或真实密钥文件。

## 目录布局

```text
frontend/
├── app/                     # Next.js App Router 页面、layout 和全局样式
│   └── tender/              # `/tender` 三栏招标工作台页面
├── components/
│   ├── chat/                # 类型侧栏、表单面板、聊天面板、消息卡、agent run UI
│   ├── forms/               # 招标表单、上传控件、模板候选、模型选择、共享字段
│   └── layout/              # 通用 Header、Sidebar、MainLayout、HistorySection
├── hooks/                   # URL、hydration、SSE、任务状态、任务 heartbeat hooks
├── lib/                     # API client、SSE runtime、表单转换、URL/API base helper
├── stores/                  # Zustand stores
├── types/                   # API、聊天和全局招标类型
├── utils/                   # 招标类型和 canonical URL 映射
├── __tests__/               # Jest 单元测试、测试夹具
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
└── postcss.config.mjs       # Tailwind 4 PostCSS 插件
```

## 目录职责

**`frontend/app/`:**
- 职责： Next.js App Router 页面边界和全局样式。
- 包含： `layout.tsx`、`page.tsx`、`globals.css`、`tender/page.tsx`。
- 关键文件： `frontend/app/page.tsx` 进入 `/tender`；`frontend/app/tender/page.tsx` 是工作台入口；`frontend/app/layout.tsx` 定义中文 HTML lang 和 metadata。

**`frontend/components/chat/`:**
- 职责： 工作台三栏中的类型侧栏、表单挂载、聊天交互、任务消息、agent run 和上传文件 rewrite UI。
- 包含： `ChatPanel.tsx`、`ChatInput.tsx`、`FormPanel.tsx`、`TenderTypeSidebar.tsx`、`MessageList.tsx`、`TaskLogMessage.tsx`、`TaskContentMessage.tsx`、`TaskDownloadMessage.tsx`、`AgentThinkingMessage.tsx`、`tenderFormRegistry.ts`。
- 关键文件： `frontend/components/chat/ChatPanel.tsx` 处理 agent run、rewrite、上传文件 rewrite、补充批注和下载；`frontend/components/chat/FormPanel.tsx` 处理 generate task；`frontend/components/chat/ChatInput.tsx` 处理 `/rewrite` skill 和 Word 文件选择。

**`frontend/components/forms/`:**
- 职责： 招标表单 wrapper、共享表单主体、上传、模板候选、模型选择和共享字段组件。
- 包含： `XjcgTenderForm.tsx`、`GngkTenderForm.tsx`、`GjgkTenderForm.tsx`、`TenderFormShared.tsx`、`FileUploader.tsx`、`TemplateCandidateDialog.tsx`、`ModelSelector.tsx`、`TenderNoInput.tsx`、`tenderFormConfig.ts`、`shared/`。
- 关键文件： `frontend/components/forms/TenderFormShared.tsx` 是表单状态、上传、候选、生成选项和 draft 同步的主要实现；`frontend/components/forms/FileUploader.tsx` 调用上传 API；`frontend/components/forms/TemplateCandidateDialog.tsx` 展示模板候选。

**`frontend/components/forms/shared/`:**
- 职责： 表单内部复用的低层 UI 构件。
- 包含： `FormSection.tsx`、`FormField.tsx`、`ErrorDisplay.tsx`、`InfoCard.tsx`、`buttonStyles.ts`、`index.ts`。
- 关键文件： `frontend/components/forms/shared/index.ts` 是该目录的聚合导出入口。

**`frontend/components/layout/`:**
- 职责： 通用布局和历史侧栏组件。
- 包含： `Header.tsx`、`HistorySection.tsx`、`MainLayout.tsx`、`Sidebar.tsx`。
- 关键文件： `frontend/components/layout/MainLayout.tsx` 是通用 layout 组合；`/tender` 工作台直接使用 `frontend/components/chat/` 三栏组件。

**`frontend/hooks/`:**
- 职责： 封装 hydration、URL 参数、SSE、任务状态轮询/确认、任务 heartbeat 和活跃任务摘要。
- 包含： `useUrlParams.ts`、`useHydrated.ts`、`useSSE.ts`、`useChatSSE.ts`、`useCurrentConversationTaskStatus.ts`、`useTaskHeartbeat.ts`、`useLatestActiveTaskSummary.ts`。
- 关键文件： `frontend/hooks/useChatSSE.ts` 是后端任务 SSE 到 store/UI 的核心映射；`frontend/hooks/useCurrentConversationTaskStatus.ts` 管理当前会话 task status polling；`frontend/hooks/useTaskHeartbeat.ts` 管理活跃 task heartbeat。

**`frontend/lib/`:**
- 职责： API client、SSE runtime、表单转换、API base URL 解析和通用 helper。
- 包含： `api.ts`、`sse.ts`、`formDataConverter.ts`、`gngkFormType.ts`、`apiBaseUrl.ts`、`tenderFetch.ts`、`agentThinking.ts`、`chat-utils.ts`、`utils.ts`。
- 关键文件： `frontend/lib/api.ts` 是后端 API 入口；`frontend/lib/sse.ts` 是 EventSource 封装；`frontend/lib/formDataConverter.ts` 是表单到 `GenerateRequest` 转换；`frontend/lib/gngkFormType.ts` 负责 `gngk` form type 分派。

**`frontend/stores/`:**
- 职责： Zustand 状态管理。
- 包含： `chatStore.ts`、`chatStreamStore.ts`、`chatTaskSessionStore.ts`、`historyStore.ts`、`useAppStore.ts`。
- 关键文件： `frontend/stores/chatStore.ts` 是会话和任务状态主 store；`frontend/stores/chatStreamStore.ts` 维护运行中 SSE stream；`frontend/stores/chatTaskSessionStore.ts` 维护 task resume 元数据。

**`frontend/types/`:**
- 职责： API、聊天、全局招标类型和测试类型补全。
- 包含： `api.ts`、`chat.ts`、`index.ts`、`jest-dom.d.ts`。
- 关键文件： `frontend/types/api.ts` 定义 client-side 请求契约；`frontend/types/chat.ts` 定义消息、会话、任务消息种类和 agent thinking 状态；`frontend/types/index.ts` 定义 `TenderType`、`TenderLx`、`FundLx`。

**`frontend/utils/`:**
- 职责： 非 React 的共享映射工具。
- 包含： `tenderTypeMapper.ts`。
- 关键文件： `frontend/utils/tenderTypeMapper.ts` 负责 URL 参数解析、`TenderType` 判定和 canonical URL 构造。

**`frontend/__tests__/`:**
- 职责： Jest 单元测试、测试数据工厂和 SSE mock。
- 包含： `unit/` 和 `mocks/`。
- 关键文件： `frontend/__tests__/unit/lib/test_api.test.ts`、`frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`、`frontend/__tests__/unit/stores/`、`frontend/__tests__/mocks/data-factories.ts`、`frontend/__tests__/mocks/sse-mock.ts`。

**`frontend/e2e/`:**
- 职责： Playwright 浏览器契约测试。
- 包含： `test_*.spec.ts`。
- 关键文件： `frontend/e2e/test_url_conversation.spec.ts`、`frontend/e2e/test_generation_mode_agent.spec.ts`、`frontend/e2e/test_comment_supplement.spec.ts`、`frontend/e2e/test_agent_run_chat_panel.spec.ts`、`frontend/e2e/test_tender_form_upload_slots.spec.ts`。

## 关键文件位置

**Entry Points:**
- `frontend/app/page.tsx`: 根路径进入 `/tender`。
- `frontend/app/layout.tsx`: 全局 metadata 和 `<html lang="zh-CN">`。
- `frontend/app/tender/page.tsx`: 工作台入口、URL 参数接入、会话 heartbeat、招标数据预取。
- `frontend/lib/api.ts`: 后端 API、上传下载、agent run、任务 API 和模板候选入口。
- `frontend/hooks/useChatSSE.ts`: 任务 SSE 入口。

**配置：**
- `frontend/package.json`: npm scripts、dependencies、devDependencies、Node engine `>=20.9.0`。
- `frontend/package-lock.json`: npm lockfile。
- `frontend/next.config.ts`: `/api/:path*` rewrite、production cache header、allowed dev origins、image remote pattern、React strict mode。
- `frontend/tsconfig.json`: TypeScript 主配置、`@/*` alias、Next plugin、module resolution。
- `frontend/tsconfig.typecheck.json`: 类型检查专用配置。
- `frontend/eslint.config.mjs`: ESLint flat config、Next core web vitals/typescript、React hooks rule。
- `frontend/jest.config.ts`: Jest jsdom、Next Jest wrapper、`@/*` alias、coverage scope。
- `frontend/playwright.config.ts`: E2E baseURL、dev server、Chromium project。
- `frontend/postcss.config.mjs`: Tailwind 4 PostCSS 插件配置。

**Core Logic:**
- `frontend/components/chat/ChatPanel.tsx`: 聊天、agent run、rewrite、上传文件 rewrite、补充批注、下载和重试。
- `frontend/components/chat/ChatInput.tsx`: 聊天输入、`/rewrite` skill、上传文件 rewrite 文件卡。
- `frontend/components/chat/FormPanel.tsx`: generate task 创建、当前任务状态、取消、表单挂载。
- `frontend/components/chat/TenderTypeSidebar.tsx`: 招标类型分组、会话列表和 URL 同步入口。
- `frontend/components/chat/MessageList.tsx`: 消息渲染分派和用户消息操作。
- `frontend/components/chat/TaskContentMessage.tsx`: AI 正文、rewrite 正文、`content_agent` 和 `comment_agent` 过程展示。
- `frontend/components/chat/TaskDownloadMessage.tsx`: 任务产物下载卡和补充批注入口。
- `frontend/components/forms/TenderFormShared.tsx`: 表单主体、模板候选、上传、生成选项和 draft 同步。
- `frontend/components/forms/TemplateCandidateDialog.tsx`: 模板候选表格和选择/下载 UI。
- `frontend/stores/chatStore.ts`: 会话和任务状态主 store。
- `frontend/stores/chatStreamStore.ts`: 运行中 SSE stream 状态。
- `frontend/stores/chatTaskSessionStore.ts`: task resume session 状态。
- `frontend/lib/formDataConverter.ts`: 表单到 `GenerateRequest` 转换。
- `frontend/lib/gngkFormType.ts`: `gngk` form type 分派。
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
- React 组件使用 PascalCase：`frontend/components/chat/ChatPanel.tsx`、`frontend/components/forms/FileUploader.tsx`。
- hooks 使用 `useXxx.ts`：`frontend/hooks/useChatSSE.ts`、`frontend/hooks/useTaskHeartbeat.ts`。
- stores 使用语义化 camelCase：`frontend/stores/chatStore.ts`、`frontend/stores/chatStreamStore.ts`。
- lib/utils 使用 camelCase 或功能名：`frontend/lib/formDataConverter.ts`、`frontend/lib/gngkFormType.ts`、`frontend/utils/tenderTypeMapper.ts`。
- Jest 测试以 `test_` 开头并以 `.test.ts` 或 `.test.tsx` 结尾：`frontend/__tests__/unit/lib/test_api.test.ts`。
- Playwright 测试以 `test_` 开头并以 `.spec.ts` 结尾：`frontend/e2e/test_home.spec.ts`。
- Next App Router 页面保持框架命名：`page.tsx`、`layout.tsx`。

**Directories:**
- 按层级和职责命名：`app/`、`components/`、`hooks/`、`lib/`、`stores/`、`types/`、`utils/`。
- 组件按工作台区域分层：`frontend/components/chat/`、`frontend/components/forms/`、`frontend/components/layout/`。
- 表单低层复用控件放在 `frontend/components/forms/shared/`。
- 测试目录按测试类型和源码作用域分层：`frontend/__tests__/unit/components/chat/`、`frontend/__tests__/unit/lib/`、`frontend/__tests__/unit/stores/`。

## 新代码落位

**New Feature:**
- Primary code: 工作台页面编排放 `frontend/app/tender/page.tsx`；工作台交互放 `frontend/components/chat/`；表单、字段、上传、模板候选放 `frontend/components/forms/` 或 `frontend/components/forms/shared/`。
- Tests: 单元测试放 `frontend/__tests__/unit/<scope>/test_*.test.ts(x)`；浏览器契约放 `frontend/e2e/test_*.spec.ts`。

**New Component/Module:**
- Implementation: 聊天消息或任务 UI 放 `frontend/components/chat/`；表单控件放 `frontend/components/forms/shared/`；招标表单 wrapper 放 `frontend/components/forms/<Type>TenderForm.tsx` 并同步 `frontend/components/chat/tenderFormRegistry.ts`。
- Tests: 组件单测按作用域放 `frontend/__tests__/unit/components/chat/` 或 `frontend/__tests__/unit/components/forms/`。

**Utilities:**
- Shared helpers: 通用 class/helper 放 `frontend/lib/utils.ts`；API base URL helper 放 `frontend/lib/apiBaseUrl.ts`；URL 或 tender type 映射放 `frontend/utils/tenderTypeMapper.ts`。
- API helpers: 后端请求放 `frontend/lib/api.ts`，同步 `frontend/types/api.ts`。
- SSE helpers: 底层 `EventSource` 能力放 `frontend/lib/sse.ts`；任务 SSE 到 UI/store 映射放 `frontend/hooks/useChatSSE.ts`。
- State helpers: 主会话/任务状态扩展 `frontend/stores/chatStore.ts`；纯 stream runtime 放 `frontend/stores/chatStreamStore.ts`；task resume 元数据放 `frontend/stores/chatTaskSessionStore.ts`。

**Contracts:**
- API shape 变化：同步 `frontend/types/api.ts`、`frontend/lib/api.ts`、相关调用组件、store 和测试。
- SSE 事件变化：同步 `frontend/types/api.ts`、`frontend/lib/sse.ts`、`frontend/hooks/useChatSSE.ts`、`frontend/__tests__/unit/lib/test_sse.test.ts`、`frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`。
- `TenderType` 或 `form_type` 变化：同步 `frontend/types/index.ts`、`frontend/types/api.ts`、`frontend/components/chat/tenderFormRegistry.ts`、`frontend/lib/formDataConverter.ts`、`frontend/lib/gngkFormType.ts`、`frontend/utils/tenderTypeMapper.ts`。
- Agent run / rewrite 变化：同步 `frontend/types/api.ts`、`frontend/lib/api.ts`、`frontend/components/chat/ChatPanel.tsx`、`frontend/components/chat/ChatInput.tsx`、`frontend/stores/chatStore.ts`。
- 上传文件 rewrite 变化：同步 `frontend/types/api.ts` 的 `FileType` / agent context、`frontend/components/chat/ChatInput.tsx`、`frontend/components/chat/ChatPanel.tsx` 和相关测试。
- 任务产物展示变化：同步 `frontend/types/chat.ts`、`frontend/stores/chatStore.ts`、`frontend/hooks/useChatSSE.ts`、`frontend/components/chat/MessageList.tsx`、`frontend/components/chat/TaskDownloadMessage.tsx`。

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

*前端结构分析：2026-06-25*
