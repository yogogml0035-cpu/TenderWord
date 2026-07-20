# 前端编码约定

**分析日期：** 2026-07-21

**范围：** `frontend/` 的组件、hooks、stores、API client、类型、表单、上传、SSE/agent run、测试和配置文件。`frontend/.env.local`、`frontend/.env.local.example`、`frontend/.npmrc` 仅确认存在，不读取内容，不在文档中记录任何密钥、token、客户原文或私有下载路径。

## 命名模式

**文件：**
- React 组件文件使用 PascalCase，例如 `frontend/components/chat/ChatPanel.tsx`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/components/forms/FileUploader.tsx`。
- hooks 使用 `useXxx.ts`，例如 `frontend/hooks/useChatSSE.ts`、`frontend/hooks/useCurrentConversationTaskStatus.ts`、`frontend/hooks/useTaskHeartbeat.ts`。
- Zustand store 使用语义化 camelCase 文件名，例如 `frontend/stores/chatStore.ts`、`frontend/stores/chatStreamStore.ts`、`frontend/stores/chatTaskSessionStore.ts`。
- 纯 helper 放在 `frontend/lib/` 或 `frontend/utils/`，文件名使用 camelCase 或领域名，例如 `frontend/lib/formDataConverter.ts`、`frontend/lib/apiBaseUrl.ts`、`frontend/lib/gngkFormType.ts`、`frontend/lib/tenderFetch.ts`、`frontend/lib/agentThinking.ts`、`frontend/utils/tenderTypeMapper.ts`。
- Jest 文件集中在 `frontend/__tests__/unit/`，命名为 `test_*.test.ts` 或 `test_*.test.tsx`，例如 `frontend/__tests__/unit/lib/test_api.test.ts`。
- Playwright 文件集中在 `frontend/e2e/`，命名为 `test_*.spec.ts`，例如 `frontend/e2e/test_generation_mode_agent.spec.ts`。

**函数：**
- React component 使用 PascalCase：`ChatPanel`、`TenderFormShared`、`FileUploader`。
- hooks 使用 `use` 前缀：`useChatSSE()`、`useSSE()`、`useUrlParams()`。
- 事件处理函数使用 `handleXxx`：`handleRewriteFileUpload`、`handleGenerationModeChange`、`handleTemplateCandidateSelect`。
- 表单转换函数使用 `convertXxxFormToApiRequest`：`convertXjcgFormToApiRequest()`、`convertGngkFormToApiRequest()`、`convertGjgkFormToApiRequest()`，实现位于 `frontend/lib/formDataConverter.ts`。
- 解析、归一化、分派、构造函数使用 `parseXxx`、`normalizeXxx`、`resolveXxx`、`buildXxx`，例如 `parseTenderUrlParams()`、`normalizeApiBaseUrl()`、`resolveGngkFormType()`、`buildCanonicalSearchParams()`。
- Tailwind class 合并使用 `cn()`，实现位于 `frontend/lib/utils.ts`（`twMerge(clsx(...))`）。

**变量：**
- 前端本地变量使用 camelCase，例如 `conversationId`、`taskId`、`selectedSkillsForRequest`、`templateDialogOpen`。
- 后端 payload 字段保持 snake_case，不在契约层强行改名，例如 `form_type`、`tender_lx`、`fund_lx`、`file_paths`、`generation_mode`，真源在 `frontend/types/api.ts`。
- UI 招标类型固定使用 `TenderType` 的 `xjcg`、`gngk`、`gjgk`，不要把后端 `FormType` 当作前端页面类型。
- `task_id`、`conversation_id` 等后端字段在 API/SSE 类型中保持原名；组件和 store 的局部参数可使用 `taskId`、`conversationId`。

**类型：**
- interface、type、union 使用 PascalCase：`GenerateRequest`、`AgentRunStreamRequest`、`ConversationFormDraft`、`SSEAgentStepEvent`。
- API、SSE、agent run、任务状态和上传契约集中在 `frontend/types/api.ts`。
- 聊天消息、任务卡片、会话和 message metadata 类型集中在 `frontend/types/chat.ts`。
- 前端 UI 全局类型在 `frontend/types/index.ts`，该文件 re-export `./api`（`export * from './api'`），但新增后端契约字段的真源仍是 `frontend/types/api.ts`。

## 代码风格

**格式化：**
- 使用 Prettier 3（`package.json` 中 `prettier` `^3.8.1`），配置在 `frontend/.prettierrc`。
- 保持 `semi: true`、`singleQuote: true`、`printWidth: 100`、`tabWidth: 2`、`trailingComma: "es5"`。
- Tailwind class 排序由 `prettier-plugin-tailwindcss` 处理。
- `frontend/.prettierignore` 排除 `node_modules`、`.next`、`out`、`dist`、`*.log`。
- 命令：`npm run format`（`prettier --write .`）、`npm run format:check`（`prettier --check .`）。

**Lint：**
- 使用 ESLint 9 flat config，配置在 `frontend/eslint.config.mjs`。
- 继承 `eslint-config-next/core-web-vitals` 和 `eslint-config-next/typescript`。
- 启用 `eslint-plugin-react-hooks`，`react-hooks/set-state-in-effect` 为 `warn`。
- ESLint 忽略 `.next/**`、`out/**`、`build/**`、`next-env.d.ts`、`node_modules-*/**`、`coverage/**`、`playwright-report/**`、`test-results/**`。
- 运行命令：`npm run lint`（即 `eslint`）。

**TypeScript：**
- `frontend/tsconfig.json` 启用 `strict: true`、`jsx: "react-jsx"`、`moduleResolution: "bundler"`、`baseUrl: "."` 和 `@/*` alias。
- 类型检查入口是 `frontend/tsconfig.typecheck.json`（继承 `tsconfig.json`，排除 `.next/dev`），命令为 `npm run type-check`（即 `tsc -p tsconfig.typecheck.json --noEmit`）。
- `frontend/next.config.ts` 中 `typescript.ignoreBuildErrors` 为 `false`，不要依赖构建跳过类型错误。
- Node 引擎要求 `>=20.9.0`（`frontend/package.json` `engines`）。

## 导入组织

**顺序：**
1. React、Next、Node 或第三方库，例如 `react`、`next/navigation`、`lucide-react`、`@playwright/test`。
2. 项目绝对路径导入，使用 `@/*` alias，例如 `@/lib/api`、`@/stores/chatStore`、`@/types/api`。
3. 同目录相对导入，例如 `./MessageList`、`./shared`、`./tenderFormConfig`。
4. 类型导入使用 `import type`，尤其是 `frontend/types/api.ts`、`frontend/types/chat.ts`、组件 props 和测试 helper。

**路径别名：**
- `@/*` 映射到 `frontend/*`，配置在 `frontend/tsconfig.json`。
- Jest 中 `^@/(.*)$` 映射到 `<rootDir>/$1`，配置在 `frontend/jest.config.ts`。

**示例：**
```typescript
import { useCallback } from 'react';
import { Upload } from 'lucide-react';
import { uploadFile, ApiError } from '@/lib/api';
import type { FileType } from '@/types/api';
```

## 错误处理

**模式：**
- 后端请求错误统一收敛为 `ApiError`，实现位于 `frontend/lib/api.ts`。
- API helper 优先解析 wrapped success payload `{ success: true, data: ... }`，并兼容少量 flat response；新增 endpoint 优先使用 wrapped response。
- 网络错误统一抛出 `ApiError`，`code` 为 `NETWORK_ERROR`；`streamNdjson()` 对 `AbortError` 保留原始 abort 语义。
- API 错误码和 HTTP status 保留在 `ApiError.code` 与 `ApiError.status`，UI 展示优先使用 `ApiError.message`。
- `TASK_CANNOT_CANCEL` 在 `cancelTask()` 中视为 non-fatal noop；任务取消按钮不应因此显示失败。
- 任务终态、SSE 中断、后端重启、`TASK_NOT_FOUND` 必须通过 `frontend/hooks/useChatSSE.ts`、`frontend/stores/chatStore.ts`、`frontend/stores/chatTaskSessionStore.ts` 收敛为完成、失败、取消或本地中断态。

**API helper 模式：**
```typescript
export async function createGenerateTask(params: GenerateRequest): Promise<CreateTaskData> {
  return request<CreateTaskData>('/api/generate', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}
```

## 日志

**框架：** `console`。

**模式：**
- SSE 连接、重连和异常排障日志集中在 `frontend/lib/sse.ts`。
- 用户可见任务日志不依赖 console，统一由 `frontend/components/chat/TaskLogMessage.tsx`、`frontend/components/chat/TaskContentMessage.tsx`、`frontend/components/chat/TaskDownloadMessage.tsx` 渲染。
- Playwright specs 收集 `console` error 和 `pageerror` 并断言为空，示例在 `frontend/e2e/test_generation_mode_agent.spec.ts`、`frontend/e2e/test_comment_supplement.spec.ts`、`frontend/e2e/test_agent_run_chat_panel.spec.ts`。
- 不在 console、测试夹具、长期文档或 UI 摘要中输出真实密钥、完整客户原文、traceback、token 或私有下载路径。

## 注释

**何时写注释：**
- 注释只解释不显然的业务边界、跨端契约或兼容原因。
- 合理示例：`frontend/lib/gngkFormType.ts` 中说明工程类复用服务链路；`frontend/utils/tenderTypeMapper.ts` 中说明前端判型只依赖 `purchase_method`。
- 不用注释替代类型、测试或命名；新增 API 字段必须同步 `frontend/types/api.ts` 和测试。

**JSDoc/TSDoc：**
- 公共 helper、底层 hook 和测试工厂可以保留短 TSDoc，例如 `frontend/hooks/useSSE.ts`、`frontend/__tests__/mocks/data-factories.ts`。
- 组件内部简单 handler 不需要 JSDoc；优先通过函数名和局部变量名表达意图。

## 函数设计

**规模：**
- 纯转换、解析、归一化逻辑放入 `frontend/lib/` 或 `frontend/utils/` 并补单测，例如 `frontend/lib/formDataConverter.ts`、`frontend/lib/apiBaseUrl.ts`、`frontend/lib/tenderFetch.ts`、`frontend/utils/tenderTypeMapper.ts`。
- 大组件只做 UI 编排和事件分发。修改 `frontend/components/chat/ChatPanel.tsx`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/stores/chatStore.ts` 时保持局部修改。
- 不在 JSX 中拼复杂后端 payload；先在 helper 或局部 builder 中构造，再交给 API client。

**参数：**
- 跨层 helper 使用对象参数降低歧义，例如 `resolveGngkFormType({ tender_lx, fund_lx, ifzgcg })`。
- API helper 参数类型必须来自 `frontend/types/api.ts`，例如 `GenerateRequest`、`AgentRunStreamRequest`、`CommentSupplementTaskRequest`。
- URL 与 tender type helper 接收明确领域对象，例如 `CanonicalUrlParams`。

**返回值：**
- API helper 返回解包后的业务 data，失败时 throw `ApiError`。
- parser 对无法识别的流事件返回 `null` 并忽略该事件，见 `frontend/lib/api.ts` 的 `parseAgentRunEvent()`。
- hook 返回稳定状态对象和操作函数，组件不重复实现 SSE 连接状态或任务状态判断。

## 模块设计

**导出：**
- API client 统一从 `frontend/lib/api.ts` 导出具名 helper、`api` 对象（`get/post/put/delete`）、`streamNdjson`、`streamAgentRun`、`ApiError` 和 `API_BASE_URL`。
- Zustand store 文件导出 `useXxxStore`，并保留 default export 的既有写法。
- 类型模块只放类型、常量和类型守卫，不引入 UI 组件。
- 表单注册集中在 `frontend/components/chat/tenderFormRegistry.ts`，新增招标类型必须同步 component map、display name map 和 converter map。

**聚合导出文件：**
- `frontend/types/index.ts` 重新导出 `./api`，但不要把 API 真源迁出 `frontend/types/api.ts`。
- `frontend/components/forms/shared/index.ts` 聚合共享表单控件；新增共享表单控件时同步该入口。

## 组件与状态约定

**组件：**
- Next App Router 页面位于 `frontend/app/`；交互组件以 `'use client'` 开头，例如 `frontend/components/chat/ChatPanel.tsx`、`frontend/components/forms/TenderFormShared.tsx`、hooks 与 layout 客户端组件。
- 根布局 `frontend/app/layout.tsx` 使用 `lang="zh-CN"`，标题与描述为中文产品文案。
- 表单 wrapper 只绑定招标类型差异；共享逻辑、上传、模板候选、生成方式和插入锚点留在 `frontend/components/forms/TenderFormShared.tsx`。
- 共享表单 UI 放在 `frontend/components/forms/shared/`，使用 `FormSection`、`FormField`、`ErrorDisplay`、`InfoCard` 和 shared button class（`secondaryActionButtonClassName`）。
- 样式使用 Tailwind CSS 4 + `clsx` / `tailwind-merge`；class 合并走 `cn()`。

**状态（Zustand）：**
- 会话、草稿、任务摘要、任务消息分组由 `frontend/stores/chatStore.ts` 维护，通过 `sessionStorage` key `chat-storage` 持久化；`partialize` 保留 `conversations`、`currentConversationId`、`selectedTenderType`、`conversationDrafts`、`taskSummaries`、`unreadConversationResults`。
- 运行中的 SSE 日志、AI 文本、进度、agent step 临时快照放在 `frontend/stores/chatStreamStore.ts`，不持久化。
- 任务恢复用的 `lastEventId` 放在 `frontend/stores/chatTaskSessionStore.ts`，通过 `sessionStorage` key `chat-task-session-storage` 持久化。
- 历史列表状态在 `frontend/stores/historyStore.ts`（`sessionStorage` key `tender-history-storage`）。
- UI 基础状态在 `frontend/stores/useAppStore.ts`（`localStorage` key `tender-app-storage`，`partialize` 仅 `sidebarOpen`）。
- Store 测试或组件测试设置状态时使用 `useXxxStore.setState()`，不要绕过 store action 修改浏览器 storage JSON。

## API Client 约定

- 所有后端 JSON、上传、下载、NDJSON、模板候选、任务状态和 heartbeat 请求统一走 `frontend/lib/api.ts`。
- 组件不得裸写后端 `fetch()`；当前源码中 `fetch(` 只出现在 `frontend/lib/api.ts`（`request()`、`streamNdjson()`、`fetchTenderDataWithType()`、`downloadFile()`）。组件/hooks/stores 中无裸 `fetch`。
- 组件侧消费点示例：`ChatPanel`、`FormPanel`、`TenderFormShared`、`FileUploader` 均 `import` 自 `@/lib/api`。
- `NEXT_PUBLIC_API_URL` 解析集中在 `frontend/lib/apiBaseUrl.ts`（支持逗号分隔多候选、按当前 hostname 匹配、默认 `http://localhost:8000`）；修改该链路时同时检查 `frontend/next.config.ts` 的 `rewrites()` 和 `allowedDevOrigins`。
- 开发服默认前端端口 `8502`（`npm run dev` / `npm start`）；后端默认 `8000`。
- SSE URL 由 `frontend/lib/api.ts` 的 `getTaskStreamUrl()` 或 `frontend/hooks/useChatSSE.ts` 经 `frontend/lib/sse.ts` 创建，不在组件里拼后端 stream URL。
- 模板候选只通过项目内 API helper：`fetchTemplateCandidates()`、`selectTemplateCandidate()`、`getTemplateCandidateDownloadUrl()`。组件不直接访问外部模板候选 URL。
- 文件上传使用 `uploadFile()` / `uploadFiles()`；下载使用 `downloadFile()` / `getDownloadUrl()`。
- `POST /api/agent/runs/stream` 是右侧聊天的 NDJSON 入口，前端解析在 `frontend/lib/api.ts` 的 `streamAgentRun()` 和 `parseAgentRunEvent()`。
- 招标数据拉取的 draft 同步逻辑封装在 `frontend/lib/tenderFetch.ts` 的 `syncTenderDataDraft()`，调用 `fetchTenderDataWithType()`，组件不直接拼 `/api/tender/{tender_no}`。

**主要 API helper 清单（`frontend/lib/api.ts`）：**
- 招标：`fetchTenderData`、`fetchTenderDataWithType`
- 模板候选：`fetchTemplateCandidates`、`selectTemplateCandidate`、`getTemplateCandidateDownloadUrl`
- 上传：`uploadFile`、`uploadFiles`
- 任务：`createGenerateTask`、`createCommentSupplementTask`、`getTaskStatus`、`cancelTask`、`getTaskList`、`sendTaskHeartbeat`、`sendConversationHeartbeat`
- 流：`streamNdjson`、`streamAgentRun`
- 下载：`downloadFile`、`getDownloadUrl`、`getTaskStreamUrl`

## 类型同步与跨端契约

- API shape 变化必须同步 `frontend/types/api.ts`、`frontend/lib/api.ts`、相关 component/store/hook 和测试。
- SSE 事件变化必须同步 `frontend/types/api.ts`、`frontend/lib/sse.ts` named event 注册（`connected`、`log`、`llm`、`progress`、`agent_step`、`status`、`error`、`done`、`heartbeat`）、`frontend/hooks/useChatSSE.ts` 事件映射、`frontend/__tests__/unit/lib/test_sse.test.ts` 和 `frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`。
- `TaskKind`（`generate | rewrite | comment_supplement`）、`TaskStatus`、`SSEDoneEvent`、`TaskResult`、`StyleWritebackSummary`、`CommentWritebackSummary` 改动必须同步 `frontend/types/chat.ts`、下载卡和消息列表相关测试。
- 新增或修改招标类型必须同步 `frontend/types/index.ts`、`frontend/types/api.ts`、`frontend/utils/tenderTypeMapper.ts`、`frontend/components/chat/tenderFormRegistry.ts`、`frontend/components/forms/tenderFormConfig.ts`、`frontend/lib/formDataConverter.ts` 和相关测试。
- `gngk` 在前端只是一种 UI 类型，后端 `form_type` 必须由 `frontend/lib/gngkFormType.ts` 按 `tender_lx + fund_lx + ifzgcg` 分派。
- agent run 的 `model` 联合为 `'deepseek' | 'qwen' | 'doubao'`，`runtime` 联合为 `'fake' | 'deepagents'`；改动需同步 `frontend/types/api.ts`、`parseAgentRunEvent()`、`AgentRunStartedEventData` 和测试夹具。

## 表单与上传约定

- `TenderFormShared` 的初始化优先级保持 `draft > URL > default`，实现位于 `frontend/components/forms/TenderFormShared.tsx`。
- 表单上传槽位只保留模板文件和技术参数文件：`file_paths.template` 与 `file_paths.tender_params`，转换逻辑在 `frontend/lib/formDataConverter.ts`。
- `FileUploader` 通过 `fileType` 传递上传类型，常用值为 `template`、`params`、`rewrite_source`（`FileType` 另含 `qualification`），类型定义在 `frontend/types/api.ts`。
- 生成表单中的 `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 只属于 generate payload。
- `ChatPanel` 构造 `AgentRunStreamRequest` 时不得携带 `generation_mode`、`comment_generation_mode`、`style_writeback_mode`。
- 上传文件 rewrite 使用 `uploadFile(file, 'rewrite_source')`，并在 draft 中写入 `rewrite_file` 和一次性 `selected_skills: ['rewrite']`，实现位于 `frontend/components/chat/ChatPanel.tsx`。
- `selected_skills` 是一次性 agent run 字段，发送后清空；存在 `rewrite_file` 时可隐式选择 `rewrite`。
- rewrite 上下文只通过 `context_snapshot.rewrite_context` 提供受控字段：`form_type`、`insertion_config`、`tender_lx`、`fund_source_lx`、可选 `tender_data_snapshot`。

## SSE 与 Agent Run 约定

- 底层连接：`frontend/lib/sse.ts` 的 `createSSEConnection()` 使用浏览器 `EventSource`，支持 `lastEventId` 查询参数、事件去重、可选自动重连与 heartbeat timeout。
- React 封装：`frontend/hooks/useSSE.ts` 管理连接生命周期；任务流业务映射在 `frontend/hooks/useChatSSE.ts`（写 `chatStreamStore` / `chatStore` / `chatTaskSessionStore`）。
- `task_accepted` 才创建后台任务并接入 task/SSE 链路；`needs_input` 只追加普通 AI 提示，不创建任务。
- `agent_step` 过程卡由 `frontend/hooks/useChatSSE.ts` 映射到 `frontend/stores/chatStore.ts` 的 task message group；运行中快照先放 `frontend/stores/chatStreamStore.ts`。
- `content_agent` 和 `comment_agent` 过程卡复用 `agent_step` 事件族；generate workflow 不应渲染 `comment_agent` 过程卡。
- rewrite 和 `comment_supplement` 任务使用 agent-step 卡，不再创建普通 `task-content` 卡。
- thinking 卡阶段标签与视图状态映射在 `frontend/lib/agentThinking.ts`（如 `understand`、`execute`、`tool`、`retry`），与 `AgentThinkingViewStageKey` 对齐。
- SSE reconnect、`lastEventId`、heartbeat 和后端重启恢复由 `frontend/lib/sse.ts`、`frontend/hooks/useChatSSE.ts`、`frontend/stores/chatTaskSessionStore.ts` 管理。
- Agent run NDJSON 事件族（`parseAgentRunEvent`）：`run_started`、`thinking_stage`、`tool_call`、`task_accepted`、`needs_input`、`done`、`error`。

## i18n / 语言约定

- 当前前端未引入 i18n 框架（无 `next-intl` / `react-i18next`），UI 中文文案以字面量直接写在组件中（如 `components/chat/ChatPanel.tsx`、`components/forms/ModelSelector.tsx`）。
- 后端约定的中文提示串作为 `default*Message` 写在 `frontend/lib/api.ts`（如 `defaultErrorMessage`、`protocolErrorMessage`、`noBodyMessage`），不要随意改写。
- 前端事实文档使用简体中文说明正文；代码标识符、路径、命令、配置键和 API 名称保持原文。

## 项目技能与文档约束

- 代码和配置是真源；长期文档只沉淀稳定边界和可执行约定。
- 前端代码改动至少运行 `npm run lint`、`npm run type-check` 和相关测试（具体命令见 `TESTING.md`）。
- 只改与当前任务直接相关的文件；quality focus 只维护 `frontend/.planning/codebase/CONVENTIONS.md` 和 `frontend/.planning/codebase/TESTING.md`。
- 文档型变更至少运行 `git diff --check`，并扫描本轮改动文档中的密钥/token 模式。
- `.env`、token、客户原文不得写入文档、日志或测试夹具。

---

*前端约定分析：2026-07-21*
