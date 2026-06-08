# 前端结构事实地图

**分析日期：** 2026-06-08

**范围：** `frontend/` 源码、测试、前端配置、`frontend/.planning/codebase/` 文档目录，以及必要的根级约定文件 `README.md`、`docs/frontend.md`、`docs/interfaces-runtime.md`、`INTERFACES.md`。跳过 `frontend/node_modules/`、`frontend/node_modules-wsl/`、`frontend/.next/`、`frontend/playwright-report/`、`frontend/test-results/`、`frontend/.swc/`。`frontend/.env.local`、`frontend/.env.local.example`、`frontend/.npmrc` 仅记录存在，不读取内容。

## 目录布局

```text
frontend/
├── app/                     # Next.js App Router 页面、layout 和全局样式
│   └── tender/              # `/tender` 工作台页面
├── components/
│   ├── chat/                # 三栏工作台中的类型侧栏、表单面板、聊天面板和任务消息
│   ├── forms/               # 招标表单、上传控件、模板候选、共享表单控件
│   └── layout/              # Header、Sidebar、MainLayout、HistorySection
├── hooks/                   # URL、hydration、SSE、任务状态、任务心跳 hooks
├── lib/                     # API client、SSE wrapper、表单转换、URL/API base helper
├── stores/                  # Zustand stores
├── types/                   # API、聊天和全局招标类型
├── utils/                   # 招标类型和 canonical URL 映射
├── mocks/                   # MSW handlers/server
├── __tests__/               # Jest 单元/集成测试、测试夹具、测试工具
├── e2e/                     # Playwright E2E specs
├── test-shims/              # Jest moduleNameMapper shim
├── tasks/                   # 前端任务工作区资料，不是 runtime 源码层
├── .planning/codebase/      # 前端事实文档
├── package.json             # npm 脚本、依赖、Node engine
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
- 关键文件：`frontend/app/page.tsx` 重定向到 `/tender`；`frontend/app/tender/page.tsx` 是工作台入口；`frontend/app/layout.tsx` 定义中文 HTML lang 和 metadata。

**`frontend/components/chat/`：**
- 用途：工作台三栏中的类型侧栏、表单挂载、聊天交互、任务消息和智能体过程卡。
- 包含：`ChatPanel.tsx`、`FormPanel.tsx`、`TenderTypeSidebar.tsx`、`MessageList.tsx`、`TaskLogMessage.tsx`、`TaskContentMessage.tsx`、`TaskDownloadMessage.tsx`、`AgentThinkingMessage.tsx`、`tenderFormRegistry.ts`。
- 关键文件：`frontend/components/chat/ChatPanel.tsx` 处理 agent run、rewrite、上传文件 rewrite、补充批注和下载；`frontend/components/chat/FormPanel.tsx` 处理 generate task；`frontend/components/chat/tenderFormRegistry.ts` 集中管理表单注册和 converter。

**`frontend/components/forms/`：**
- 用途：招标表单 wrapper、共享表单主体、上传、模板候选、模型选择和共享字段组件。
- 包含：`XjcgTenderForm.tsx`、`GngkTenderForm.tsx`、`GjgkTenderForm.tsx`、`TenderFormShared.tsx`、`FileUploader.tsx`、`TemplateCandidateDialog.tsx`、`ModelSelector.tsx`、`TenderNoInput.tsx`、`tenderFormConfig.ts`、`shared/`。
- 关键文件：`frontend/components/forms/TenderFormShared.tsx` 是表单状态、上传、候选、生成选项和 draft 同步的主要实现；`frontend/components/forms/tenderFormConfig.ts` 定义各 tender type 的默认插入锚点。

**`frontend/components/forms/shared/`：**
- 用途：表单内部复用的低层 UI building blocks。
- 包含：`FormSection.tsx`、`FormField.tsx`、`ErrorDisplay.tsx`、`InfoCard.tsx`、`buttonStyles.ts`、`index.ts`。
- 关键文件：`frontend/components/forms/shared/index.ts` 是该目录 barrel export。

**`frontend/components/layout/`：**
- 用途：通用布局和历史侧栏组件。
- 包含：`Header.tsx`、`HistorySection.tsx`、`MainLayout.tsx`、`Sidebar.tsx`。
- 关键文件：`frontend/components/layout/MainLayout.tsx` 组合 layout 组件；当前 `/tender` 工作台直接使用 `components/chat` 三栏布局。

**`frontend/hooks/`：**
- 用途：封装 hydration、URL 参数、SSE、任务状态轮询/确认、任务心跳和活跃任务摘要。
- 包含：`useUrlParams.ts`、`useHydrated.ts`、`useSSE.ts`、`useChatSSE.ts`、`useCurrentConversationTaskStatus.ts`、`useTaskHeartbeat.ts`、`useLatestActiveTaskSummary.ts`。
- 关键文件：`frontend/hooks/useChatSSE.ts` 是后端任务 SSE 到 store/UI 的核心映射；`frontend/hooks/useCurrentConversationTaskStatus.ts` 管理当前会话 task status polling；`frontend/hooks/useTaskHeartbeat.ts` 管理活跃 task heartbeat。

**`frontend/lib/`：**
- 用途：无 UI 依赖的 API client、SSE runtime、表单 payload 转换、数据同步和工具。
- 包含：`api.ts`、`apiBaseUrl.ts`、`sse.ts`、`formDataConverter.ts`、`gngkFormType.ts`、`tenderFetch.ts`、`chat-utils.ts`、`agentThinking.ts`、`utils.ts`。
- 关键文件：`frontend/lib/api.ts` 是后端调用边界；`frontend/lib/gngkFormType.ts` 是 `gngk` form type 分派真源；`frontend/lib/formDataConverter.ts` 是表单到 `GenerateRequest` 的转换边界；`frontend/lib/apiBaseUrl.ts` 同时服务 API client 和 `next.config.ts`。

**`frontend/stores/`：**
- 用途：Zustand 状态层。
- 包含：`chatStore.ts`、`chatStreamStore.ts`、`chatTaskSessionStore.ts`、`historyStore.ts`、`useAppStore.ts`。
- 关键文件：`frontend/stores/chatStore.ts` 是最大状态模块，负责会话、草稿、task summary、任务消息、URL 同步和后端重启收敛；`frontend/stores/chatStreamStore.ts` 保存运行中 stream；`frontend/stores/chatTaskSessionStore.ts` 保存 task resume 元数据。

**`frontend/types/`：**
- 用途：跨层 TypeScript 契约。
- 包含：`api.ts`、`chat.ts`、`index.ts`。
- 关键文件：`frontend/types/api.ts` 镜像后端 API/SSE/agent run；`frontend/types/chat.ts` 定义会话消息和过程卡 metadata；`frontend/types/index.ts` 定义前端 `TenderType` 并 re-export API 类型。

**`frontend/utils/`：**
- 用途：非 React 的共享映射工具。
- 包含：`tenderTypeMapper.ts`。
- 关键文件：`frontend/utils/tenderTypeMapper.ts` 负责 URL 参数解析、`TenderType` 判定和 canonical URL 构造。

**`frontend/mocks/`：**
- 用途：MSW handlers/server，供测试 mock 后端 API。
- 包含：`handlers.ts`、`server.ts`。
- 关键文件：`frontend/mocks/handlers.ts` 定义 mock endpoints；`frontend/mocks/server.ts` 暴露测试 server。

**`frontend/__tests__/`：**
- 用途：Jest 单元/集成测试、测试工厂和渲染工具。
- 包含：`unit/`、`integration/`、`mocks/`、`utils/`。
- 关键文件：`frontend/__tests__/unit/lib/test_api.test.ts`、`frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`、`frontend/__tests__/unit/stores/`、`frontend/__tests__/mocks/data-factories.ts`、`frontend/__tests__/utils/test-utils.tsx`。

**`frontend/e2e/`：**
- 用途：Playwright 浏览器契约测试。
- 包含：`test_*.spec.ts`。
- 关键文件：`frontend/e2e/test_url_conversation.spec.ts`、`frontend/e2e/test_generation_mode_agent.spec.ts`、`frontend/e2e/test_comment_supplement.spec.ts`、`frontend/e2e/test_agent_run_chat_panel.spec.ts`。

## 关键文件位置

**入口点：**
- `frontend/app/page.tsx`: 根路径重定向到 `/tender`。
- `frontend/app/layout.tsx`: 全局 metadata 和 `<html lang="zh-CN">`。
- `frontend/app/tender/page.tsx`: 工作台入口、URL 参数接入、会话心跳、招标数据预取。
- `frontend/lib/api.ts`: 后端 API、上传下载、agent run、任务 API 和模板候选入口。
- `frontend/hooks/useChatSSE.ts`: 任务 SSE 入口。

**配置：**
- `frontend/package.json`: npm scripts、dependencies、devDependencies、Node engine `>=20.9.0`。
- `frontend/package-lock.json`: npm lockfile。
- `frontend/next.config.ts`: `/api/:path*` rewrite、production cache header、allowed dev origins、image remote pattern、React strict mode。
- `frontend/tsconfig.json`: TypeScript strict、`@/*` alias、Next plugin、module resolution。
- `frontend/tsconfig.typecheck.json`: 类型检查专用配置。
- `frontend/eslint.config.mjs`: ESLint flat config、Next core web vitals/typescript、React hooks rule。
- `frontend/jest.config.ts`: Jest jsdom、Next Jest wrapper、`@/*` alias、MSW mapper、coverage scope。
- `frontend/playwright.config.ts`: E2E baseURL `http://localhost:8502`、dev server、Chromium project。
- `frontend/postcss.config.mjs`: Tailwind 4 PostCSS 插件配置。

**核心逻辑：**
- `frontend/components/chat/ChatPanel.tsx`: 聊天、agent run、rewrite、上传文件 rewrite、补充批注、下载和重试。
- `frontend/components/chat/FormPanel.tsx`: generate task 创建、当前任务状态、取消、表单挂载。
- `frontend/components/chat/TenderTypeSidebar.tsx`: 招标类型分组、会话列表和 URL 同步入口。
- `frontend/components/chat/MessageList.tsx`: 消息渲染分派和用户消息操作。
- `frontend/components/forms/TenderFormShared.tsx`: 表单主体、模板候选、上传、生成选项和 draft 同步。
- `frontend/components/forms/TemplateCandidateDialog.tsx`: 模板候选表格和选择/下载 UI。
- `frontend/stores/chatStore.ts`: 会话和任务状态主 store。
- `frontend/stores/chatStreamStore.ts`: 运行中 SSE stream 状态。
- `frontend/stores/chatTaskSessionStore.ts`: task resume session 状态。
- `frontend/lib/formDataConverter.ts`: 表单到 `GenerateRequest` 转换。
- `frontend/lib/gngkFormType.ts`: `gngk` form type 分派。
- `frontend/utils/tenderTypeMapper.ts`: URL 与 tender type 映射。

**类型与契约：**
- `frontend/types/index.ts`: 前端 `TenderType`、`TenderLx`、`FundLx` 和基础任务类型。
- `frontend/types/api.ts`: `GenerateRequest`、`AgentRunStreamRequest`、`AgentRunEvent`、SSE event、任务结果、模板候选、错误码。
- `frontend/types/chat.ts`: `Message`、`Conversation`、`TaskMessageKind`、`AgentThinkingCardState` 和 message metadata。

**测试：**
- `frontend/__tests__/unit/`: 模块级单元测试。
- `frontend/__tests__/integration/`: 集成测试样例。
- `frontend/__tests__/mocks/data-factories.ts`: 测试数据工厂。
- `frontend/__tests__/mocks/sse-mock.ts`: SSE 测试 mock。
- `frontend/__tests__/utils/test-utils.tsx`: Testing Library 渲染 helper。
- `frontend/mocks/handlers.ts`: MSW API mock。
- `frontend/e2e/`: Playwright specs。

**文档：**
- `frontend/.planning/codebase/ARCHITECTURE.md`: 前端架构事实地图。
- `frontend/.planning/codebase/STRUCTURE.md`: 前端结构事实地图。
- `docs/frontend.md`: 前端稳定约定。
- `docs/interfaces-runtime.md`: 跨前后端运行时契约。
- `INTERFACES.md`: 系统级接口边界。

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

## 新代码放置位置

**新功能：**
- 页面级入口：`frontend/app/`。
- 工作台交互：`frontend/components/chat/`。
- 表单、字段、上传、模板候选：`frontend/components/forms/` 或 `frontend/components/forms/shared/`。
- 状态：优先扩展 `frontend/stores/chatStore.ts`；纯 stream runtime 放 `frontend/stores/chatStreamStore.ts`；task resume 元数据放 `frontend/stores/chatTaskSessionStore.ts`。
- 测试： 按模块放到 `frontend/__tests__/unit/<scope>/test_*.test.ts(x)`；跨浏览器契约放到 `frontend/e2e/test_*.spec.ts`。

**新组件或模块：**
- 聊天消息或任务 UI：`frontend/components/chat/`。
- 表单控件：`frontend/components/forms/shared/`。
- 招标表单 wrapper：`frontend/components/forms/<Type>TenderForm.tsx`，并同步 `frontend/components/chat/tenderFormRegistry.ts`。
- 模型/选择控件：参照 `frontend/components/forms/ModelSelector.tsx` 和 `frontend/components/chat/ChatModelPicker.tsx` 的边界。

**工具：**
- 后端请求：只放 `frontend/lib/api.ts`，类型同步 `frontend/types/api.ts`。
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
- `TenderType` 或 `FormType` 变化：同步 `frontend/types/index.ts`、`frontend/types/api.ts`、`frontend/components/chat/tenderFormRegistry.ts`、`frontend/lib/formDataConverter.ts`、`frontend/lib/gngkFormType.ts`、`frontend/utils/tenderTypeMapper.ts`。
- Agent run / rewrite 变化：同步 `frontend/types/api.ts`、`frontend/lib/api.ts`、`frontend/components/chat/ChatPanel.tsx`、`frontend/stores/chatStore.ts`。

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
- 注意：Windows 与 WSL 原生依赖不可混用；`README.md` 记录两套目录切换策略。

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
- 用途：Jest moduleNameMapper shim。
- 是否生成：否。
- 是否提交：是。

**`frontend/.env.local`、`frontend/.env.local.example`、`frontend/.npmrc`：**
- 用途：环境和包管理配置文件。
- 是否生成：混合。
- 是否提交：`.env.local` 不应提交；`.env.local.example` 和 `.npmrc` 按仓库策略处理。
- 注意：不要在文档、日志、测试或最终回复中读取或记录实际内容。

---

*前端结构分析：2026-06-08*
