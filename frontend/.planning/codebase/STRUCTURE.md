# 前端结构事实地图

**分析日期：** 2026-06-16

**范围：** `frontend/` 源码、测试、前端配置、`README.md` 和 `frontend/.planning/codebase/` 文档目录。跳过 `frontend/node_modules/`、`frontend/node_modules-wsl/`、`frontend/.next/`、`frontend/playwright-report/`、`frontend/test-results/`、`frontend/.swc/`。未读取 `frontend/.env.local`、`backend/.env`、`.npmrc` 或真实密钥文件。

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
├── __tests__/               # Jest 单元测试、测试夹具（unit/、mocks/）
├── e2e/                     # Playwright E2E specs
├── test-shims/              # 测试异步等待 helper（until-async.ts）
├── tasks/                   # 前端任务工作区资料，不是 runtime 源码层
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

**`frontend/app/`：**
- 用途：Next.js App Router 页面边界和全局样式。
- 包含：`layout.tsx`、`page.tsx`、`globals.css`、`tender/page.tsx`。
- 关键文件：`frontend/app/page.tsx` 进入 `/tender`；`frontend/app/tender/page.tsx` 是工作台入口；`frontend/app/layout.tsx` 定义中文 HTML lang 和 metadata。

**`frontend/components/chat/`：**
- 用途：工作台三栏中的类型侧栏、表单挂载、聊天交互、任务消息、agent run 和上传文件 rewrite UI。
- 包含：`ChatPanel.tsx`、`ChatInput.tsx`、`FormPanel.tsx`、`TenderTypeSidebar.tsx`、`MessageList.tsx`、`TaskLogMessage.tsx`、`TaskContentMessage.tsx`、`TaskDownloadMessage.tsx`、`AgentThinkingMessage.tsx`、`tenderFormRegistry.ts`。
- 关键文件：`frontend/components/chat/ChatPanel.tsx` 处理 agent run、rewrite、上传文件 rewrite、补充批注和下载；`frontend/components/chat/FormPanel.tsx` 处理 generate task；`frontend/components/chat/ChatInput.tsx` 处理 rewrite skill 和 Word 文件选择；`frontend/components/chat/tenderFormRegistry.ts` 管理表单注册和 converter。

**`frontend/components/forms/`：**
- 用途：招标表单 wrapper、共享表单主体、上传、模板候选、模型选择和共享字段组件。
- 包含：`XjcgTenderForm.tsx`、`GngkTenderForm.tsx`、`GjgkTenderForm.tsx`、`TenderFormShared.tsx`、`FileUploader.tsx`、`TemplateCandidateDialog.tsx`、`ModelSelector.tsx`、`TenderNoInput.tsx`、`tenderFormConfig.ts`、`shared/`。
- 关键文件：`frontend/components/forms/TenderFormShared.tsx` 是表单状态、上传、候选、生成选项和 draft 同步的主要实现；`frontend/components/forms/FileUploader.tsx` 调用上传 API；`frontend/components/forms/TemplateCandidateDialog.tsx` 展示模板候选。

**`frontend/components/forms/shared/`：**
- 用途：表单内部复用的低层 UI 构件。
- 包含：`FormSection.tsx`、`FormField.tsx`、`ErrorDisplay.tsx`、`InfoCard.tsx`、`buttonStyles.ts`、`index.ts`。
- 关键文件：`frontend/components/forms/shared/index.ts` 是该目录的聚合导出入口。

**`frontend/components/layout/`：**
- 用途：通用布局和历史侧栏组件。
- 包含：`Header.tsx`、`HistorySection.tsx`、`MainLayout.tsx`、`Sidebar.tsx`。
- 关键文件：`frontend/components/layout/MainLayout.tsx` 组合 layout 组件；`frontend/app/tender/page.tsx` 的工作台使用 `frontend/components/chat/` 三栏组件。

**`frontend/hooks/`：**
- 用途：封装 hydration、URL 参数、SSE、任务状态轮询/确认、任务 heartbeat 和活跃任务摘要。
- 包含：`useUrlParams.ts`、`useHydrated.ts`、`useSSE.ts`、`useChatSSE.ts`、`useCurrentConversationTaskStatus.ts`、`useTaskHeartbeat.ts`、`useLatestActiveTaskSummary.ts`。
- 关键文件：`frontend/hooks/useChatSSE.ts` 是后端任务 SSE 到 store/UI 的核心映射；`frontend/hooks/useCurrentConversationTaskStatus.ts` 管理当前会话 task status polling；`frontend/hooks/useTaskHeartbeat.ts` 管理活跃 task heartbeat。

**`frontend/lib/`：**
- 用途：API client、SSE runtime、表单转换、API base URL 解析和通用 helper。
- 包含：`api.ts`、`sse.ts`、`formDataConverter.ts`、`gngkFormType.ts`、`apiBaseUrl.ts`、`tenderFetch.ts`、`agentThinking.ts`、`chat-utils.ts`、`utils.ts`。
- 关键文件：`frontend/lib/api.ts` 是后端 API 唯一入口（统一 `request<T>` + `api.*` + `streamNdjson`，不写裸 fetch）；`frontend/lib/sse.ts` 是 EventSource 封装；`frontend/lib/formDataConverter.ts` 是表单到 `GenerateRequest` 转换；`frontend/lib/gngkFormType.ts` 负责 `gngk` form type 分派。

**`frontend/stores/`：**
- 用途：Zustand 状态管理。
- 包含：`chatStore.ts`、`chatStreamStore.ts`、`chatTaskSessionStore.ts`、`historyStore.ts`、`useAppStore.ts`。
- 关键文件：`frontend/stores/chatStore.ts` 是会话和任务状态主 store；`frontend/stores/chatStreamStore.ts` 维护运行中 SSE stream；`frontend/stores/chatTaskSessionStore.ts` 维护 task resume 元数据。

**`frontend/types/`：**
- 用途：API、聊天、全局招标类型和测试类型补全。
- 包含：`api.ts`、`chat.ts`、`index.ts`、`jest-dom.d.ts`。
- 关键文件：`frontend/types/api.ts` 定义 client-side 请求契约（声明后端 routes 和 Pydantic models 是 source of truth）；`frontend/types/jest-dom.d.ts`（本轮新增）补齐 jest-dom matcher 全局 TS 类型。

**`frontend/utils/`：**
- 用途：非 React 的共享映射工具。
- 包含：`tenderTypeMapper.ts`。
- 关键文件：`frontend/utils/tenderTypeMapper.ts` 负责 URL 参数解析、`TenderType` 判定和 canonical URL 构造。

**`frontend/__tests__/`：**
- 用途：Jest 单元测试、测试数据工厂和 SSE mock。
- 包含：`unit/`（按 app/components/hooks/lib/stores/types/utils 分包）、`mocks/`（`data-factories.ts`、`sse-mock.ts`）。
- 关键文件：`frontend/__tests__/unit/lib/test_api.test.ts`、`frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`、`frontend/__tests__/unit/stores/`、`frontend/__tests__/mocks/data-factories.ts`。
- 约束：本轮已移除 `frontend/mocks/`（MSW handlers/server）、`frontend/__tests__/utils/`（setup/test-utils）和 `frontend/__tests__/integration/`；不要再向这些路径新增文件，单测直接 mock `globalThis.fetch`。

**`frontend/e2e/`：**
- 用途：Playwright 浏览器契约测试。
- 包含：`test_*.spec.ts`。
- 关键文件：`frontend/e2e/test_url_conversation.spec.ts`、`frontend/e2e/test_generation_mode_agent.spec.ts`、`frontend/e2e/test_comment_supplement.spec.ts`、`frontend/e2e/test_agent_run_chat_panel.spec.ts`、`frontend/e2e/test_tender_form_upload_slots.spec.ts`。

## 关键文件位置

**入口点：**
- `frontend/app/page.tsx`: 根路径进入 `/tender`。
- `frontend/app/layout.tsx`: 全局 metadata 和 `<html lang="zh-CN">`。
- `frontend/app/tender/page.tsx`: 工作台入口、URL 参数接入、会话 heartbeat、招标数据预取。
- `frontend/lib/api.ts`: 后端 API、上传下载、agent run、任务 API 和模板候选入口。
- `frontend/hooks/useChatSSE.ts`: 任务 SSE 入口。

**配置：**
- `frontend/package.json`: npm scripts、dependencies、devDependencies、Node engine `>=20.9.0`。
- `frontend/package-lock.json`: npm lockfile。
- `frontend/next.config.ts`: `/api/:path*` rewrite、production cache header、allowed dev origins、image remote pattern、React strict mode。
- `frontend/tsconfig.json`: TypeScript strict、`@/*` alias、Next plugin、module resolution。
- `frontend/tsconfig.typecheck.json`: 类型检查专用配置。
- `frontend/eslint.config.mjs`: ESLint flat config、Next core web vitals/typescript、React hooks rule。
- `frontend/jest.config.ts`: Jest jsdom、Next Jest wrapper、`@/*` alias、coverage scope（本轮已移除 MSW mapper 与 `'^until-async$'` 映射）。
- `frontend/playwright.config.ts`: E2E baseURL `http://localhost:8502`、dev server、Chromium project。
- `frontend/postcss.config.mjs`: Tailwind 4 PostCSS 插件配置。

**核心逻辑：**
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

**测试：**
- `frontend/__tests__/unit/`: 模块级单元测试（按 app/components/hooks/lib/stores/types/utils 分包）。
- `frontend/__tests__/mocks/data-factories.ts`: 测试数据工厂。
- `frontend/__tests__/mocks/sse-mock.ts`: SSE 测试 mock。
- `frontend/test-shims/until-async.ts`: 测试异步等待 helper（注意：本轮 jest.config 已移除对应 moduleNameMapper 映射，使用前先确认引用关系）。
- `frontend/e2e/`: Playwright specs。

**文档：**
- `frontend/.planning/codebase/ARCHITECTURE.md`: 前端架构事实地图。
- `frontend/.planning/codebase/STRUCTURE.md`: 前端结构事实地图。
- `README.md`: 根级安装、启动和运行入口说明。

## 命名约定

**文件：**
- React 组件使用 PascalCase：`frontend/components/chat/ChatPanel.tsx`、`frontend/components/forms/FileUploader.tsx`。
- hooks 使用 `useXxx.ts`：`frontend/hooks/useChatSSE.ts`、`frontend/hooks/useTaskHeartbeat.ts`。
- stores 使用语义化 camelCase：`frontend/stores/chatStore.ts`、`frontend/stores/chatStreamStore.ts`。
- lib/utils 使用 camelCase 或功能名：`frontend/lib/formDataConverter.ts`、`frontend/lib/gngkFormType.ts`、`frontend/utils/tenderTypeMapper.ts`。
- Jest 测试以 `test_` 开头并以 `.test.ts` 或 `.test.tsx` 结尾：`frontend/__tests__/unit/lib/test_api.test.ts`。
- Playwright 测试以 `test_` 开头并以 `.spec.ts` 结尾：`frontend/e2e/test_home.spec.ts`。
- Next App Router 页面保持框架命名：`page.tsx`、`layout.tsx`。

**目录：**
- 按层级和职责命名：`app/`、`components/`、`hooks/`、`lib/`、`stores/`、`types/`、`utils/`。
- 组件按工作台区域分层：`frontend/components/chat/`、`frontend/components/forms/`、`frontend/components/layout/`。
- 表单低层复用控件放在 `frontend/components/forms/shared/`。
- 测试目录按测试类型和源码作用域分层：`frontend/__tests__/unit/components/chat/`、`frontend/__tests__/unit/lib/`、`frontend/__tests__/unit/stores/`。

## 新代码落位

**新功能：**
- 工作台页面编排：`frontend/app/tender/page.tsx`。
- 工作台交互：`frontend/components/chat/`。
- 表单、字段、上传、模板候选：`frontend/components/forms/` 或 `frontend/components/forms/shared/`。
- API 请求：`frontend/lib/api.ts`，同步 `frontend/types/api.ts`。
- 状态：优先扩展 `frontend/stores/chatStore.ts`；纯 stream runtime 放 `frontend/stores/chatStreamStore.ts`；task resume 元数据放 `frontend/stores/chatTaskSessionStore.ts`。
- 测试：按模块放到 `frontend/__tests__/unit/<scope>/test_*.test.ts(x)`；跨浏览器契约放到 `frontend/e2e/test_*.spec.ts`。

**新组件或模块：**
- 聊天消息或任务 UI：`frontend/components/chat/`。
- 聊天输入能力：`frontend/components/chat/ChatInput.tsx`，能力请求同步 `frontend/components/chat/ChatPanel.tsx` 和 `frontend/types/api.ts`。
- 任务产物展示：`frontend/components/chat/TaskDownloadMessage.tsx` 和 `frontend/components/chat/MessageList.tsx`。
- 智能体过程展示：`frontend/components/chat/TaskContentMessage.tsx`、`frontend/stores/chatStore.ts`、`frontend/hooks/useChatSSE.ts`。
- 表单控件：`frontend/components/forms/shared/`。
- 招标表单 wrapper：`frontend/components/forms/<Type>TenderForm.tsx`，同步 `frontend/components/chat/tenderFormRegistry.ts`。

**工具：**
- 后端请求：`frontend/lib/api.ts`。
- API base URL 或 Next rewrite 相关：`frontend/lib/apiBaseUrl.ts` 和 `frontend/next.config.ts` 一起检查。
- SSE 底层能力：`frontend/lib/sse.ts`。
- 任务 SSE 到 UI/store 映射：`frontend/hooks/useChatSSE.ts`。
- 表单 payload 转换：`frontend/lib/formDataConverter.ts`。
- `gngk` form type 分派：`frontend/lib/gngkFormType.ts`。
- URL 或 tender type 映射：`frontend/utils/tenderTypeMapper.ts`。
- 通用 class/helper：`frontend/lib/utils.ts`。

**契约：**
- API shape 变化：同步 `frontend/types/api.ts`、`frontend/lib/api.ts`、相关调用组件、store 和测试。
- SSE 事件变化：同步 `frontend/types/api.ts`、`frontend/lib/sse.ts`、`frontend/hooks/useChatSSE.ts`、`frontend/__tests__/unit/lib/test_sse.test.ts`、`frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`。
- `TenderType` 或 `form_type` 变化：同步 `frontend/types/index.ts`、`frontend/types/api.ts`、`frontend/components/chat/tenderFormRegistry.ts`、`frontend/lib/formDataConverter.ts`、`frontend/lib/gngkFormType.ts`、`frontend/utils/tenderTypeMapper.ts`。
- Agent run / rewrite 变化：同步 `frontend/types/api.ts`、`frontend/lib/api.ts`、`frontend/components/chat/ChatPanel.tsx`、`frontend/components/chat/ChatInput.tsx`、`frontend/stores/chatStore.ts`。
- 上传文件 rewrite 变化：同步 `frontend/types/api.ts` 的 `FileType` / agent context、`frontend/components/chat/ChatInput.tsx`、`frontend/components/chat/ChatPanel.tsx` 和相关测试。
- 任务产物展示变化：同步 `frontend/types/chat.ts`、`frontend/stores/chatStore.ts`、`frontend/hooks/useChatSSE.ts`、`frontend/components/chat/MessageList.tsx`、`frontend/components/chat/TaskDownloadMessage.tsx`。

## 特殊目录

**`frontend/.planning/codebase/`：**
- 用途：前端事实文档，供后续计划和执行阶段消费。
- 是否生成：是。
- 是否提交：是，按仓库文档策略维护。

**`frontend/.next/`：**
- 用途：Next.js 构建/开发缓存。
- 是否生成：是。
- 是否提交：否。

**`frontend/node_modules/` 与 `frontend/node_modules-wsl/`：**
- 用途：平台依赖目录。
- 是否生成：是。
- 是否提交：否。
- 注意：Windows 与 WSL 原生依赖目录分离，相关运行约束记录在 `README.md`。

**`frontend/playwright-report/` 与 `frontend/test-results/`：**
- 用途：Playwright 测试报告和失败证据。
- 是否生成：是。
- 是否提交：否。

**`frontend/.playwright-cli/`：**
- 用途：Playwright CLI 或浏览器调试状态目录。
- 是否生成：是。
- 是否提交：否。

**`frontend/.swc/`：**
- 用途：SWC/Next 相关缓存。
- 是否生成：是。
- 是否提交：否。

**`frontend/tasks/`：**
- 用途：前端范围的任务工作区资料和执行证据。
- 是否生成：混合。
- 是否提交：取决于任务工作区策略；不要把它当成 runtime 源码层。

**`frontend/test-shims/`：**
- 用途：测试异步等待 helper（`until-async.ts`）。
- 是否生成：否。
- 是否提交：是。
- 注意：本轮 `jest.config.ts` 已移除 `'^until-async$'` moduleNameMapper 映射；新增引用前先确认该文件是否仍被使用。

**环境配置文件：**
- 用途：本地运行配置。
- 是否生成：混合。
- 是否提交：真实环境文件不应提交。
- 注意：文档、日志、测试夹具和最终回复不得读取或记录 `frontend/.env.local`、`backend/.env` 或真实密钥内容。

---

*结构分析：2026-06-16*
