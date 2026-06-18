<!-- refreshed: 2026-06-18 -->
# Architecture

**分析日期：** 2026-06-18

**范围：** `frontend/` 子项目。分析覆盖 App Router 工作台、API client、hooks、Zustand 状态流、上传、generate/rewrite/comment_supplement UI 边界、SSE 与目录分层。未读取 `.env`、`.env.*`、`.npmrc`、凭据或真实密钥文件。

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                    Next.js App Router                        │
│      `frontend/app/page.tsx`, `frontend/app/tender/page.tsx`  │
└───────────────┬─────────────────────────────┬───────────────┘
                │                             │
                ▼                             ▼
┌───────────────────────────────┐ ┌───────────────────────────┐
│ 三栏工作台 UI                  │ │ URL / hydration / heartbeat │
│ `frontend/components/chat/`    │ │ `frontend/hooks/`           │
│ `frontend/components/forms/`   │ │ `frontend/app/tender/page.tsx` │
└───────────────┬───────────────┘ └──────────────┬────────────┘
                │                                │
                ▼                                ▼
┌─────────────────────────────────────────────────────────────┐
│             Zustand 会话、草稿、任务、stream 状态             │
│             `frontend/stores/`                               │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│ API client / SSE / NDJSON / 表单转换 / URL 映射               │
│ `frontend/lib/`, `frontend/hooks/`, `frontend/utils/`, `frontend/types/` │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│ TenderWord FastAPI `/api/*`                                  │
│ `frontend/next.config.ts`, `frontend/lib/api.ts`              │
└─────────────────────────────────────────────────────────────┘
```

前端是 TenderWord 的浏览器工作台，负责招标类型选择、URL 深链、会话与草稿、招标信息预取、模板候选、文件上传、generate 任务创建、agent run、上传文件 rewrite、补充批注、SSE 进度和下载入口。浏览器端不执行 Word COM、LLM、检索、真实文件落盘或外部模板候选直连；这些能力由后端 `/api/*` 封装。

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Root route | `/` 重定向到 `/tender` | `frontend/app/page.tsx` |
| Workbench page | 三栏布局、URL 参数建会话、招标数据预取、conversation heartbeat、后端重启收敛 | `frontend/app/tender/page.tsx` |
| Tender type sidebar | 招标类型分组、会话选择/创建/重命名/删除、类型切换时同步 URL | `frontend/components/chat/TenderTypeSidebar.tsx` |
| Form panel | 挂载当前招标表单、创建 generate task、绑定 SSE/heartbeat/任务状态、取消任务 | `frontend/components/chat/FormPanel.tsx` |
| Chat panel | 右侧聊天、agent run、上传文件 rewrite、补充批注、下载、取消和重试 | `frontend/components/chat/ChatPanel.tsx` |
| Chat input | 普通消息输入、`/rewrite` skill、上传文件 rewrite 文件选择、模型选择 | `frontend/components/chat/ChatInput.tsx` |
| Message list | 按 `messageKind` 分派普通消息、任务日志、AI 正文、agent-step、下载卡和 thinking card | `frontend/components/chat/MessageList.tsx` |
| Task content card | 展示普通 AI 正文、rewrite 正文、`content_agent` 和 `comment_agent` 过程 | `frontend/components/chat/TaskContentMessage.tsx` |
| Task download card | 展示下载入口、批注写回警告、generate 产物的补充批注按钮 | `frontend/components/chat/TaskDownloadMessage.tsx` |
| Shared tender form | 招标信息、模板/参数上传、模板候选、插入锚点、生成模式和 draft 同步 | `frontend/components/forms/TenderFormShared.tsx` |
| Form registry | `TenderType` 到显示名、表单组件、converter 的映射 | `frontend/components/chat/tenderFormRegistry.ts` |
| API client | JSON、上传、下载、NDJSON agent run、任务、模板候选 API helper | `frontend/lib/api.ts` |
| SSE runtime | `EventSource` 包装、named events、重连、heartbeat、last event id 去重 | `frontend/lib/sse.ts` |
| Task SSE hook | 任务状态确认、SSE 事件到 stream/store/messages 的映射 | `frontend/hooks/useChatSSE.ts` |
| Main chat store | 会话、草稿、任务摘要、任务消息组、URL 同步、后端重启收敛 | `frontend/stores/chatStore.ts` |
| Stream store | 运行中日志、AI 文本、agent step 快照、进度和 last event id | `frontend/stores/chatStreamStore.ts` |
| URL mapper | URL 参数解析、`TenderType` 判定、canonical query 构造 | `frontend/utils/tenderTypeMapper.ts` |
| API types | 后端 payload、任务、agent run、SSE、错误码和模板候选类型 | `frontend/types/api.ts` |

## Pattern Overview

**Overall:** Next.js App Router + 客户端工作台 + Zustand 状态层 + 统一 API/SSE 边界。

**Key Characteristics:**
- 页面层只组合路由、三栏 UI 和启动副作用；长期业务状态放在 `frontend/stores/`。
- 后端请求集中到 `frontend/lib/api.ts`；组件调用 helper，不在组件内实现请求协议。
- `TenderType` 是前端 UI 类型；后端 `GenerateRequest.form_type` 由 `frontend/lib/formDataConverter.ts` 和 `frontend/lib/gngkFormType.ts` 生成。
- 任务链路以 `task_id` 为主键，SSE、任务消息组、下载卡、补充批注和 rewrite 产物续写都围绕 task summary 收敛。
- 会话、草稿、任务摘要和未读结果持久化到 `sessionStorage`；SSE stream runtime 是内存态，task resume metadata 单独持久化。

## Layers

**Route Layer:**
- 职责： 定义页面入口、metadata、全局样式和 `/tender` 工作台页面。
- Location: `frontend/app/`
- 包含： `layout.tsx`、`page.tsx`、`tender/page.tsx`、`globals.css`。
- Depends on: Next.js、React、workspace components、hooks、stores。
- Used by: 浏览器访问 `/` 和 `/tender`。

**Workbench UI Layer:**
- 职责： 展示三栏招标操作界面、聊天消息、表单、上传、下载和任务状态。
- Location: `frontend/components/chat/`、`frontend/components/forms/`、`frontend/components/layout/`
- 包含： `ChatPanel`、`FormPanel`、`MessageList`、`TaskLogMessage`、`TaskContentMessage`、`TaskDownloadMessage`、`TenderFormShared`、`FileUploader`、`TemplateCandidateDialog`。
- Depends on: `frontend/stores/`、`frontend/hooks/`、`frontend/lib/api.ts`、`frontend/types/`。
- Used by: `frontend/app/tender/page.tsx`。

**State Layer:**
- 职责： 保存会话、草稿、任务摘要、任务消息分组、运行中 stream、历史和局部 UI 状态。
- Location: `frontend/stores/`
- 包含： `chatStore.ts`、`chatStreamStore.ts`、`chatTaskSessionStore.ts`、`historyStore.ts`、`useAppStore.ts`。
- Depends on: Zustand、`frontend/types/`、纯 helper。
- Used by: 页面、聊天组件、表单组件、任务 hooks。

**Integration Layer:**
- 职责： 后端 API、SSE、NDJSON、上传下载、表单 payload 转换、URL canonical 化。
- Location: `frontend/lib/`、`frontend/hooks/`、`frontend/utils/`
- 包含： `api.ts`、`apiBaseUrl.ts`、`sse.ts`、`formDataConverter.ts`、`gngkFormType.ts`、`tenderFetch.ts`、`useChatSSE.ts`、`tenderTypeMapper.ts`。
- Depends on: 浏览器 `fetch`、`EventSource`、`URL`、`FormData` APIs 和 `frontend/types/`。
- Used by: 工作台 UI 和 stores。

**Type Layer:**
- 职责： 定义跨层契约和类型守卫。
- Location: `frontend/types/`
- 包含： `api.ts`、`chat.ts`、`index.ts`、`jest-dom.d.ts`。
- Depends on: TypeScript 类型系统。
- Used by: API client、stores、hooks、组件 props 和测试。

## Data Flow

### Primary Request Path

1. `/` 通过 `redirect('/tender')` 进入工作台 (`frontend/app/page.tsx:3`)。
2. `TenderPageContent` 解析 URL、建立或选择 conversation，并按需预取招标数据 (`frontend/app/tender/page.tsx:34`, `frontend/app/tender/page.tsx:58`)。
3. `TenderFormShared` 以 `draft > URL > default` 初始化表单状态、文件状态、生成模式和插入锚点 (`frontend/components/forms/TenderFormShared.tsx:632`, `frontend/components/forms/TenderFormShared.tsx:679`)。
4. `TenderFormShared` 校验招标编号、招标信息、模板文件、技术参数文件和插入锚点，组装 `BaseTenderFormData` (`frontend/components/forms/TenderFormShared.tsx:1544`)。
5. `FormPanel` 使用 `tenderFormConverterMap` 生成 `GenerateRequest` 并附加 `conversation_id` (`frontend/components/chat/FormPanel.tsx:368`)。
6. `createGenerateTask()` 调用 `/api/generate`；`chatStore.startTask()` 建立任务摘要和消息组 (`frontend/lib/api.ts:807`, `frontend/components/chat/FormPanel.tsx:392`)。
7. `useCurrentConversationTaskStatus()`、`useTaskHeartbeat()` 和 `useChatSSE()` 同步 queue/running/terminal 状态 (`frontend/hooks/useCurrentConversationTaskStatus.ts:88`, `frontend/hooks/useTaskHeartbeat.ts:16`, `frontend/hooks/useChatSSE.ts:175`)。
8. `chatStore.completeTask()` 创建或更新 `task-download` 下载卡，保留 `style_writeback` 和 `comment_writeback` 摘要 (`frontend/stores/chatStore.ts:1536`)。

### URL And Conversation Flow

1. `useUrlParams()` 使用 `useSearchParams()` 读取 `tender_lx`、`purchase_method`、`fund_lx`、`tenderno` (`frontend/hooks/useUrlParams.ts:66`)。
2. `parseTenderUrlParams()` 只按 `purchase_method` 判定前端 `TenderType` (`frontend/utils/tenderTypeMapper.ts:205`)。
3. `TenderPageContent` 对 `gngk` 使用 tenderno + `tender_lx` + `fund_lx` 查找会话，避免不同子类型复用同一 draft (`frontend/app/tender/page.tsx:78`, `frontend/stores/chatStore.ts:870`)。
4. `syncBrowserUrlToConversation()` 和 `chatStore.syncUrlToCurrentConversation()` 维护 canonical query (`frontend/utils/tenderTypeMapper.ts:72`, `frontend/stores/chatStore.ts:2375`)。

### Generate Payload Flow

1. 表单 wrapper 只传入 `tenderType`，具体 UI 复用 `TenderFormShared` (`frontend/components/forms/XjcgTenderForm.tsx`, `frontend/components/forms/GngkTenderForm.tsx`, `frontend/components/forms/GjgkTenderForm.tsx`)。
2. 模板文件使用 `fileType="template"` 上传，技术参数文件使用 `fileType="params"` 上传 (`frontend/components/forms/TenderFormShared.tsx:1737`, `frontend/components/forms/TenderFormShared.tsx:1753`)。
3. `convertXjcgFormToApiRequest()`、`convertGngkFormToApiRequest()`、`convertGjgkFormToApiRequest()` 生成后端 payload (`frontend/lib/formDataConverter.ts:117`, `frontend/lib/formDataConverter.ts:193`, `frontend/lib/formDataConverter.ts:225`)。
4. `gngk` 后端 `form_type` 由 `resolveGngkFormType()` 按 `tender_lx + fund_lx + ifzgcg` 分派；工程类和服务类进入 `gngk_fw_*` form type (`frontend/lib/gngkFormType.ts:18`)。

### Agent Run And Chat Flow

1. `ChatInput` 解析 `$rewrite` / `/rewrite` 前缀，或通过加号菜单选择上传文件 rewrite (`frontend/components/chat/ChatInput.tsx:37`, `frontend/components/chat/ChatInput.tsx:482`)。
2. `ChatPanel` 构造 `AgentRunStreamRequest`，包含模型、消息、`selected_skills` 和 `context_snapshot` (`frontend/components/chat/ChatPanel.tsx:393`, `frontend/components/chat/ChatPanel.tsx:423`)。
3. `streamAgentRun()` 以 NDJSON 调用 `/api/agent/runs/stream` (`frontend/lib/api.ts:589`)。
4. `run_started`、`thinking_stage`、`tool_call` 更新 thinking card 或普通 AI 消息；`needs_input` 不创建后台 task (`frontend/components/chat/ChatPanel.tsx:553`)。
5. 只有 `task_accepted` 调用 `startTask()` 并进入任务/SSE 体系 (`frontend/components/chat/ChatPanel.tsx:559`)。

### Upload Rewrite Flow

1. `ChatInput` 的隐藏文件输入只接受 `.doc` / `.docx` (`frontend/components/chat/ChatInput.tsx:308`)。
2. `ChatPanel.handleRewriteFileSelect()` 调用 `uploadFile(file, 'rewrite_source')`，把返回文件写入 conversation draft 的 `rewrite_file`，并设置 `selected_skills: ['rewrite']` (`frontend/components/chat/ChatPanel.tsx:338`)。
3. `buildAgentRunContextSnapshot()` 把 `rewrite_available`、`uploaded_files` 和 `rewrite_context` 放入 agent run context (`frontend/components/chat/ChatPanel.tsx:123`)。
4. `resolveRewriteFormType()` 为上传 rewrite 计算后端 `form_type`，`gngk` 继续复用 `resolveGngkFormType()` (`frontend/components/chat/ChatPanel.tsx:162`)。
5. rewrite task 完成后，`ChatPanel` 用下载卡产物回写 draft 的 `rewrite_file`，让下一轮 rewrite 基于最新文档 (`frontend/components/chat/ChatPanel.tsx:955`)。

### Task SSE And Artifact Flow

1. `createSSEConnection()` 注册 `connected`、`log`、`llm`、`progress`、`agent_step`、`status`、`error`、`done`、`heartbeat` named events (`frontend/lib/sse.ts:77`, `frontend/lib/sse.ts:193`)。
2. `useChatSSE()` 在连接前查询 `getTaskStatus()`，queued 不连 SSE，terminal 直接终态收敛 (`frontend/hooks/useChatSSE.ts:667`, `frontend/hooks/useChatSSE.ts:710`)。
3. `log` / `llm` / `agent_step` / `progress` 更新 `chatStreamStore` 和 task summary (`frontend/hooks/useChatSSE.ts:371`, `frontend/hooks/useChatSSE.ts:399`, `frontend/hooks/useChatSSE.ts:441`, `frontend/hooks/useChatSSE.ts:488`)。
4. `done` / `error` 关闭连接并调用 `completeTask()` / `failTask()` / `cancelTask()` (`frontend/hooks/useChatSSE.ts:530`, `frontend/hooks/useChatSSE.ts:568`)。
5. `MessageList` 按 `message.metadata.messageKind` 渲染任务日志、AI 正文、agent-step、下载卡或 thinking card (`frontend/components/chat/MessageList.tsx`)。

### Template Candidate Flow

1. `TenderFormShared` 用招标编号和项目名维护候选缓存，并调用 `fetchTemplateCandidates()` (`frontend/components/forms/TenderFormShared.tsx:1378`, `frontend/lib/api.ts:734`)。
2. 候选选择使用 `selectTemplateCandidate()`，后端返回 selected file 后写入模板上传槽 (`frontend/components/forms/TenderFormShared.tsx:1485`, `frontend/lib/api.ts:748`)。
3. 候选模板下载 URL 必须由 `getTemplateCandidateDownloadUrl()` 生成项目内代理 URL (`frontend/lib/api.ts:757`, `frontend/components/forms/TemplateCandidateDialog.tsx:62`)。

### Comment Supplement Flow

1. `TaskDownloadMessage` 只对 `taskKind === 'generate'` 显示补充批注入口 (`frontend/components/chat/TaskDownloadMessage.tsx:15`)。
2. `ChatPanel.handleCommentSupplement()` 从下载卡读取 `metadata.outputFile`，调用 `createCommentSupplementTask()` (`frontend/components/chat/ChatPanel.tsx:847`, `frontend/lib/api.ts:814`)。
3. `comment_supplement` 复用 task summary、SSE、agent-step 和下载卡，不引入第二套任务流 (`frontend/hooks/useChatSSE.ts:175`)。

**State Management:**
- `chatStore` 是持久化主状态，storage name 为 `chat-storage`，持久化 `conversations`、`currentConversationId`、`selectedTenderType`、`conversationDrafts`、`taskSummaries`、`unreadConversationResults` (`frontend/stores/chatStore.ts:994`, `frontend/stores/chatStore.ts:2408`)。
- `chatStreamStore` 是运行时内存状态，保存 `logs`、`aiText`、`agentSteps`、progress 和 `lastEventId` (`frontend/stores/chatStreamStore.ts:5`)。
- `chatTaskSessionStore` 只持久化 task resume 元数据，storage name 为 `chat-task-session-storage` (`frontend/stores/chatTaskSessionStore.ts:16`, `frontend/stores/chatTaskSessionStore.ts:43`)。
- `historyStore` 和 `useAppStore` 存在，但工作台主流程以 `chatStore` 为准 (`frontend/stores/historyStore.ts`, `frontend/stores/useAppStore.ts`)。

## Key Abstractions

**`TenderType`:**
- 职责： 前端 UI 类型，取值为 `xjcg`、`gngk`、`gjgk`。
- Examples: `frontend/types/index.ts`, `frontend/components/chat/tenderFormRegistry.ts`, `frontend/utils/tenderTypeMapper.ts`
- Pattern: UI type 与后端 `GenerateRequest.form_type` 分离；新增招标类型要同步 registry、converter、URL mapper、类型和测试。

**`GenerateRequest`:**
- 职责： 初次生成任务 payload。
- Examples: `frontend/types/api.ts`, `frontend/lib/formDataConverter.ts`
- Pattern: converter 负责默认值、文件路径提取、generate-only 字段和 `gngk` form type 分派。

**`ConversationFormDraft`:**
- 职责： 会话级表单草稿、上传文件、生成字段、rewrite 文件、一次性 skill 和 pending rewrite 恢复状态。
- Examples: `frontend/stores/chatStore.ts`, `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/chat/ChatPanel.tsx`
- Pattern: draft 是表单恢复、URL 同步和 agent run context 的共享来源。

**`TaskMessageGroupIds`:**
- 职责： 一个 `task_id` 对应 `task-log`、`task-content`、`task-download` 三类消息。
- Examples: `frontend/stores/chatStore.ts`, `frontend/components/chat/MessageList.tsx`
- Pattern: 任务消息由 store 方法维护，组件不要手写 message group。

**`agent-step` message:**
- 职责： 智能体过程卡，展示 `content_agent`、`comment_agent` 和 rewrite 过程。
- Examples: `frontend/types/chat.ts`, `frontend/types/api.ts`, `frontend/stores/chatStore.ts`, `frontend/components/chat/TaskContentMessage.tsx`
- Pattern: 运行中快照在 `chatStreamStore.agentSteps`，完成态 upsert 到 conversation messages。

**`AgentThinkingCardState`:**
- 职责： agent run 创建任务前的过程卡。
- Examples: `frontend/lib/agentThinking.ts`, `frontend/components/chat/AgentThinkingMessage.tsx`, `frontend/types/chat.ts`
- Pattern: 只展示前置流状态；后台任务创建后进度交给 task/SSE 卡。

## Entry Points

**Root Page:**
- Location: `frontend/app/page.tsx`
- Triggers: 用户访问 `/`。
- Responsibilities: 重定向到 `/tender`。

**Workbench Page:**
- Location: `frontend/app/tender/page.tsx`
- Triggers: 用户访问 `/tender` 或带查询参数的深链。
- Responsibilities: 三栏 UI、URL 参数处理、会话创建、招标数据预取、conversation heartbeat。

**Generate Task Entry:**
- Location: `frontend/components/chat/FormPanel.tsx`
- Triggers: 招标表单提交。
- Responsibilities: 通过 converter 生成 `GenerateRequest`、创建 generate task、启动任务消息组和 task summary。

**Agent Run Entry:**
- Location: `frontend/components/chat/ChatPanel.tsx`
- Triggers: 右侧聊天输入发送普通消息、`/rewrite`、上传 Word 文件 rewrite。
- Responsibilities: 构造 agent run context、处理 NDJSON event、在 `task_accepted` 后接入 task/SSE 状态机。

**API Entry:**
- Location: `frontend/lib/api.ts`
- Triggers: 表单提交、聊天发送、上传、下载、模板候选、任务状态/heartbeat。
- Responsibilities: 构造请求、解析 wrapped/unwrapped response、抛出 `ApiError`、解析 NDJSON agent run。

**SSE Entry:**
- Location: `frontend/hooks/useChatSSE.ts`
- Triggers: 任务创建、恢复或进入 running 后绑定 `task_id`。
- Responsibilities: 状态确认、连接 SSE、映射事件、终态收敛。

## Architectural Constraints

- **Threading:** 浏览器单线程 React 渲染；异步 `fetch`、`EventSource`、timer、focus、pageshow、online 和 visibility 事件驱动任务状态。
- **Global state:** Zustand stores 是模块级 singleton，见 `frontend/stores/chatStore.ts`、`frontend/stores/chatStreamStore.ts`、`frontend/stores/chatTaskSessionStore.ts`、`frontend/stores/historyStore.ts`、`frontend/stores/useAppStore.ts`。
- **Circular imports:** `frontend/types/` 保持无运行时副作用；修改 `stores/types/lib` 边界时避免让类型层反向依赖组件或 store runtime。
- **API boundary:** 新增后端请求放到 `frontend/lib/api.ts`；组件负责用户交互和调用 API helper，不实现协议解析。
- **Generate-only fields:** `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 只属于 generate 请求和会话 draft，不进入 rewrite request、skill state 或 prompt surface。
- **GNGK dispatch:** `gngk` 后端 `form_type` 分派集中到 `frontend/lib/gngkFormType.ts`，generate 和上传文件 rewrite 复用同一 helper。
- **Agent run:** `POST /api/agent/runs/stream` 是右侧聊天唯一流式入口；rewrite 通过 agent run 接受任务，不使用第二套任务状态机。
- **SSE contract:** 新增 SSE event 要同步 `frontend/types/api.ts`、`frontend/lib/sse.ts` named event 注册、`frontend/hooks/useChatSSE.ts` 解析和相关测试。
- **Sensitive data:** `.env`、token、真实客户原文、私有路径和 traceback 不进入文档、日志、测试夹具或最终回复。

## Anti-Patterns

### 组件内实现后端请求协议

**What happens:** 在组件里写裸 `fetch`、手工解析 API error、手工拼后端 host。
**Why it's wrong:** 绕过 `ApiError`、base URL resolver、Next rewrite、测试 mock 和统一错误口径。
**Do this instead:** 新请求放入 `frontend/lib/api.ts`，类型同步 `frontend/types/api.ts`，组件只调用 helper。

### 直接访问外部模板候选 URL

**What happens:** 组件拿候选记录的外部文件 URL 直接作为下载地址。
**Why it's wrong:** 绕过后端模板候选代理和可审计下载边界。
**Do this instead:** 使用 `getTemplateCandidateDownloadUrl()`，候选选择走 `selectTemplateCandidate()` (`frontend/lib/api.ts`)。

### 绕过 `resolveGngkFormType()`

**What happens:** 在 `ChatPanel`、converter 或表单组件里手写 `gngk_hw_*` / `gngk_fw_*` 分派。
**Why it's wrong:** generate 与上传文件 rewrite 可能进入不同后端 graph。
**Do this instead:** 只修改 `frontend/lib/gngkFormType.ts`，调用点继续复用 helper，并同步 `frontend/__tests__/unit/lib/test_form_data_converter.test.ts` 和 `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`。

### 手工 patch URL 参数

**What happens:** 组件直接改单个 query 参数或直接调用 history API 构造 URL。
**Why it's wrong:** canonical URL、会话身份和 deep-link 恢复会漂移。
**Do this instead:** 使用 `buildCanonicalSearchParams()`、`syncBrowserUrlToConversation()` 和 `chatStore.syncUrlToCurrentConversation()` (`frontend/utils/tenderTypeMapper.ts`, `frontend/stores/chatStore.ts`)。

### 把 agent run 当成任务状态

**What happens:** `run_started`、`thinking_stage` 或 `needs_input` 直接创建 task summary、SSE 连接或下载卡。
**Why it's wrong:** agent run 是任务创建前置流，后台任务只有后端接受后才存在。
**Do this instead:** 只有 `task_accepted` 触发 `chatStore.startTask()`；其他 agent run 事件只更新普通消息或 thinking card (`frontend/components/chat/ChatPanel.tsx`)。

### 在前端暴露后端私有运行细节

**What happens:** 把审计日志路径、完整下载路径、traceback、完整客户原文或检索 JSON 暴露到 UI 或前端 store。
**Why it's wrong:** 违反 agent run 和检索审计的白名单边界，增加敏感信息泄露风险。
**Do this instead:** 只消费 scrub 后的摘要字段和公开任务状态，类型定义放在 `frontend/types/api.ts`。

## Error Handling

**Strategy:** API 层统一转换为 `ApiError`，任务层通过状态确认、SSE 终态、heartbeat 和本地中断态收敛 UI。

**Patterns:**
- `frontend/lib/api.ts` 从 HTTP status、wrapped `success: false`、嵌套 `detail` 和 network failure 提取 message/code/status。
- `frontend/hooks/useChatSSE.ts` 先 `getTaskStatus()`，再连接 SSE；terminal 或 missing task 直接收敛。
- `frontend/hooks/useCurrentConversationTaskStatus.ts` 轮询当前任务，`TASK_NOT_FOUND` 或 404 调用 `discardStaleTask()`。
- `frontend/hooks/useTaskHeartbeat.ts` 对活跃 task 发 heartbeat，终态回调给 `FormPanel` 做补拉收敛。
- `frontend/app/tender/page.tsx` 用 conversation heartbeat 检测后端 `instance_id` 变化，并调用 `handleBackendRestart()`。
- UI 组件展示用户可读错误；下载失败路径在 `frontend/components/chat/ChatPanel.tsx` 使用 alert + console 错误。

## Cross-Cutting Concerns

**Logging:** 用户可见任务日志经 `TaskLogMessage` 渲染；排障日志使用 `console`，主要在 `frontend/lib/sse.ts`、`frontend/components/chat/ChatPanel.tsx`、`frontend/components/chat/FormPanel.tsx`。

**Validation:** TypeScript strict、ESLint、Jest 单测、Playwright E2E；表单提交前在 `TenderFormShared` 做必填、文件和插入锚点检查，后端仍是最终契约校验方。

**Authentication:** 前端未检测到认证层；`sessionStorage` 会话只表示浏览器工作台状态，不表示用户身份或权限。

**Styling:** UI 使用 Tailwind utility class、CSS variables 和 `lucide-react` 图标，组件样式主要内联在 TSX 中；共享 class helper 是 `frontend/lib/utils.ts`。

**外部 API 隔离：** 招标详情、模板候选、模板下载、Word COM、LLM 和检索运行时都在后端封装；前端只消费项目内 `/api/*`。

---

*Architecture analysis: 2026-06-18*
