# 前端结构事实地图

**分析日期：** 2026-06-08

**范围：** 仅 `frontend/` 源码、测试、前端配置和 `frontend/.planning/codebase/` 文档目录。跳过 `node_modules/`、`node_modules-wsl/`、`.next/`、`playwright-report/`、`test-results/` 等生成或依赖目录。

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
├── .planning/codebase/      # 前端事实文档
├── package.json             # npm 脚本、依赖、Node engine
├── package-lock.json        # npm lockfile
├── next.config.ts           # Next rewrite/header/dev origin/image 配置
├── tsconfig.json            # TypeScript 主配置
├── tsconfig.typecheck.json  # 稳定 type-check 配置
├── eslint.config.mjs        # ESLint flat config
├── jest.config.ts           # Jest 配置
├── playwright.config.ts     # Playwright 配置
└── postcss.config.mjs       # Tailwind 4 PostCSS 插件
```

## 目录职责

**`frontend/app/`：**
- 用途：Next.js App Router 页面边界和全局样式。
- 包含：`layout.tsx`、`page.tsx`、`globals.css`、`tender/page.tsx`。
- 关键文件：`frontend/app/page.tsx` 重定向到 `/tender`；`frontend/app/tender/page.tsx` 是工作台入口。

**`frontend/components/chat/`：**
- 用途：工作台三栏中的类型侧栏、表单挂载、聊天交互、任务消息和智能体过程卡。
- 包含：`ChatPanel.tsx`、`FormPanel.tsx`、`TenderTypeSidebar.tsx`、`MessageList.tsx`、`Task*Message.tsx`、`AgentThinkingMessage.tsx`、`tenderFormRegistry.ts`。
- 关键文件：`frontend/components/chat/ChatPanel.tsx` 处理 agent run/rewrite/补充批注；`frontend/components/chat/FormPanel.tsx` 处理 generate task。

**`frontend/components/forms/`：**
- 用途：招标表单 wrapper、共享表单主体、上传、模板候选、模型选择和共享字段组件。
- 包含：`XjcgTenderForm.tsx`、`GngkTenderForm.tsx`、`GjgkTenderForm.tsx`、`TenderFormShared.tsx`、`FileUploader.tsx`、`TemplateCandidateDialog.tsx`、`shared/`。
- 关键文件：`frontend/components/forms/TenderFormShared.tsx` 是表单状态和上传/候选/生成选项的主要实现；`frontend/components/forms/tenderFormConfig.ts` 定义默认插入锚点。

**`frontend/components/layout/`：**
- 用途：通用布局和历史侧栏组件。
- 包含：`Header.tsx`、`HistorySection.tsx`、`MainLayout.tsx`、`Sidebar.tsx`。
- 关键文件：`frontend/components/layout/MainLayout.tsx` 使用 `next/navigation` 和 layout 组件组合。

**`frontend/hooks/`：**
- 用途：封装 hydration、URL 参数、SSE、任务状态轮询/确认和心跳。
- 包含：`useUrlParams.ts`、`useHydrated.ts`、`useSSE.ts`、`useChatSSE.ts`、`useCurrentConversationTaskStatus.ts`、`useTaskHeartbeat.ts`、`useLatestActiveTaskSummary.ts`。
- 关键文件：`frontend/hooks/useChatSSE.ts` 是后端任务 SSE 到 store/UI 的核心映射。

**`frontend/lib/`：**
- 用途：无 UI 依赖的 API client、SSE runtime、表单 payload 转换、数据同步和工具。
- 包含：`api.ts`、`apiBaseUrl.ts`、`sse.ts`、`formDataConverter.ts`、`gngkFormType.ts`、`tenderFetch.ts`、`chat-utils.ts`、`agentThinking.ts`、`utils.ts`。
- 关键文件：`frontend/lib/api.ts` 是后端调用边界；`frontend/lib/gngkFormType.ts` 是 `gngk` form type 分派真源。

**`frontend/stores/`：**
- 用途：Zustand 状态层。
- 包含：`chatStore.ts`、`chatStreamStore.ts`、`chatTaskSessionStore.ts`、`historyStore.ts`、`useAppStore.ts`。
- 关键文件：`frontend/stores/chatStore.ts` 是最大状态模块，负责会话、草稿、task summary、任务消息和 URL 同步。

**`frontend/types/`：**
- 用途：跨层 TypeScript 契约。
- 包含：`api.ts`、`chat.ts`、`index.ts`。
- 关键文件：`frontend/types/api.ts` 镜像后端 API/SSE/agent run；`frontend/types/chat.ts` 定义会话消息和过程卡 metadata；`frontend/types/index.ts` 定义前端 `TenderType` 并 re-export API 类型。

**`frontend/utils/`：**
- 用途：非 React 的共享映射工具。
- 包含：`tenderTypeMapper.ts`。
- 关键文件：`frontend/utils/tenderTypeMapper.ts` 负责 URL 参数解析、`TenderType` 判定和 canonical URL 构造。

**`frontend/__tests__/`：**
- 用途：Jest 单元/集成测试、测试工厂和渲染工具。
- 包含：`unit/`、`integration/`、`mocks/`、`utils/`。
- 关键文件：`frontend/__tests__/unit/lib/test_api.test.ts`、`frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`、`frontend/__tests__/unit/stores/`。

**`frontend/e2e/`：**
- 用途：Playwright 浏览器契约测试。
- 包含：`test_*.spec.ts`。
- 关键文件：`frontend/e2e/test_url_conversation.spec.ts`、`frontend/e2e/test_generation_mode_agent.spec.ts`、`frontend/e2e/test_comment_supplement.spec.ts`。

## 关键文件位置

**Entry Points：**
- `frontend/app/page.tsx`: 根路径重定向。
- `frontend/app/tender/page.tsx`: 工作台入口、URL 参数接入、会话心跳。
- `frontend/lib/api.ts`: 后端 API 和 agent run 入口。
- `frontend/hooks/useChatSSE.ts`: 任务 SSE 入口。

**Configuration：**
- `frontend/package.json`: npm scripts、dependencies、Node engine。
- `frontend/next.config.ts`: Next rewrite/header/allowedDevOrigins/image/reactStrictMode。
- `frontend/tsconfig.json`: TS strict、`@/*` alias。
- `frontend/tsconfig.typecheck.json`: 类型检查专用 include/exclude。
- `frontend/eslint.config.mjs`: lint 配置。
- `frontend/.prettierrc`: 格式化配置。
- `frontend/jest.config.ts`: Jest 配置。
- `frontend/playwright.config.ts`: Playwright 配置。

**Core Logic：**
- `frontend/components/chat/ChatPanel.tsx`: 聊天、agent run、rewrite、上传文件 rewrite、补充批注和下载。
- `frontend/components/chat/FormPanel.tsx`: generate task 创建和表单挂载。
- `frontend/components/forms/TenderFormShared.tsx`: 表单主体、模板候选、上传和 draft 同步。
- `frontend/stores/chatStore.ts`: 会话和任务状态主 store。
- `frontend/lib/formDataConverter.ts`: 表单到 `GenerateRequest` 转换。
- `frontend/lib/gngkFormType.ts`: `gngk` form type 分派。
- `frontend/utils/tenderTypeMapper.ts`: URL 与 tender type 映射。

**Testing：**
- `frontend/__tests__/unit/`: 模块级单元测试。
- `frontend/__tests__/integration/`: 集成测试样例。
- `frontend/__tests__/mocks/data-factories.ts`: 测试数据工厂。
- `frontend/__tests__/utils/test-utils.tsx`: Testing Library render helper。
- `frontend/mocks/handlers.ts`: MSW API mock。
- `frontend/e2e/`: Playwright specs。

## 命名约定

**Files：**
- React 组件：PascalCase，例如 `frontend/components/chat/ChatPanel.tsx`、`frontend/components/forms/FileUploader.tsx`。
- hooks：`useXxx.ts`，例如 `frontend/hooks/useChatSSE.ts`。
- stores：语义化 camelCase 文件名，例如 `frontend/stores/chatStore.ts`。
- lib/utils：camelCase 或功能名，例如 `frontend/lib/formDataConverter.ts`、`frontend/utils/tenderTypeMapper.ts`。
- Jest 测试：必须以 `test_` 开头并以 `.test.ts` 或 `.test.tsx` 结尾，例如 `frontend/__tests__/unit/lib/test_api.test.ts`。
- Playwright 测试：必须以 `test_` 开头并以 `.spec.ts` 结尾，例如 `frontend/e2e/test_home.spec.ts`。

**Directories：**
- 按层级和职责命名：`app/`、`components/`、`hooks/`、`lib/`、`stores/`、`types/`、`utils/`。
- 测试目录按测试类型和源码作用域分层：`frontend/__tests__/unit/components/chat/`、`frontend/__tests__/unit/lib/`。

## 新代码放置位置

**New Feature：**
- 页面级入口：`frontend/app/`。
- 工作台交互：`frontend/components/chat/`。
- 表单/字段/上传相关：`frontend/components/forms/` 或 `frontend/components/forms/shared/`。
- 状态：优先扩展 `frontend/stores/chatStore.ts`；纯 stream runtime 放 `frontend/stores/chatStreamStore.ts`；task resume 元数据放 `frontend/stores/chatTaskSessionStore.ts`。
- Tests: 按模块放到 `frontend/__tests__/unit/<scope>/test_*.test.ts(x)`；跨浏览器契约放到 `frontend/e2e/test_*.spec.ts`。

**New Component/Module：**
- 聊天消息或任务 UI：`frontend/components/chat/`。
- 表单控件：`frontend/components/forms/shared/`。
- 模型/选择控件：参照 `frontend/components/forms/ModelSelector.tsx` 和 `frontend/components/chat/ChatModelPicker.tsx` 的现有边界。

**Utilities：**
- 后端请求：只放 `frontend/lib/api.ts`，类型同步 `frontend/types/api.ts`。
- SSE 底层能力：`frontend/lib/sse.ts`。
- 任务 SSE 到 UI/store 映射：`frontend/hooks/useChatSSE.ts`。
- 表单 payload 转换：`frontend/lib/formDataConverter.ts`。
- `gngk` form type 分派：`frontend/lib/gngkFormType.ts`。
- URL 或 tender type 映射：`frontend/utils/tenderTypeMapper.ts`。
- 通用 class/helper：`frontend/lib/utils.ts`。

## 特殊目录

**`frontend/.planning/codebase/`：**
- 用途：前端事实文档，供后续计划和执行阶段消费。
- 是否生成目录：是。
- 是否提交：是，按仓库文档策略维护。

**`frontend/.next/`：**
- 用途：Next.js 构建/开发缓存。
- 是否生成目录：是。
- 是否提交：否。

**`frontend/node_modules/` 与 `frontend/node_modules-wsl/`：**
- 用途：平台依赖目录。
- 是否生成目录：是。
- 是否提交：否。
- 注意：Windows 与 WSL 原生依赖不可混用。

**`frontend/playwright-report/` 与 `frontend/test-results/`：**
- 用途：Playwright 测试报告和失败证据。
- 是否生成目录：是。
- 是否提交：否。

**`frontend/.playwright-cli/`：**
- 用途：Playwright CLI 或浏览器调试状态目录。
- 是否生成目录：是。
- 是否提交：否。

**`frontend/tasks/`：**
- 用途：前端范围存在任务目录；本次未作为产品源码事实来源深入读取。
- 是否生成目录：混合，按任务工作区约定处理。
- 是否提交：取决于任务文档策略。

---

*前端结构分析：2026-06-08*
