# 前端架构事实地图

**分析日期：** 2026-07-15

**范围：** `frontend/` 子项目。分析覆盖 App Router 工作台、API client、hooks、Zustand 状态流、上传、generate/rewrite/comment_supplement UI 边界、SSE 与目录分层。未读取 `.env`、`.env.*`、`.npmrc`、凭据或真实密钥文件。

## 系统总览

```text
┌─────────────────────────────────────────────────────────────┐
│                    Next.js App Router                        │
│      `frontend/app/page.tsx`, `frontend/app/tender/page.tsx`  │
└───────────────┬─────────────────────────────────┬───────────┘
                │                                 │
                ▼                                 ▼
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

组件层（`frontend/components/`）不写裸 `fetch`，也不直接访问外部模板候选 URL；所有后端请求统一经 `frontend/lib/api.ts`（及内部 SSE/NDJSON helper）。

## 组件职责

| Component | Responsibility | File |
|-----------|----------------|------|
| Root route | `/` 重定向到 `/tender` | `frontend/app/page.tsx` |
| Workbench page | 三栏布局、URL 参数建会话、招标数据预取、conversation heartbeat、后端重启收敛 | `frontend/app/tender/page.tsx` |
| Tender type sidebar | 招标类型分组、会话选择/创建/重命名/删除、类型切换时同步 URL | `frontend/components/chat/TenderTypeSidebar.tsx` |
| Form panel | 挂载当前招标表单、创建 generate task、绑定 SSE/heartbeat/任务状态、取消任务 | `frontend/components/chat/FormPanel.tsx` |
| Chat panel | 右侧聊天、agent run、上传文件 rewrite、补充批注、下载、取消和重试 | `frontend/components/chat/ChatPanel.tsx` |
| Chat input | 普通消息输入、`/rewrite` skill、上传文件 rewrite 文件选择、模型选择 | `frontend/components/chat/ChatInput.tsx` |
| Chat model picker | 聊天输入区的模型下拉，复用 `ModelSelector` 的 `MODEL_OPTIONS` | `frontend/components/chat/ChatModelPicker.tsx` |
| Message list | 按 `messageKind` 分派普通消息、任务日志、AI 正文、agent-step、下载卡和 thinking card | `frontend/components/chat/MessageList.tsx` |
| Task content card | 展示普通 AI 正文、rewrite 正文、`content_agent` 和 `comment_agent` 过程 | `frontend/components/chat/TaskContentMessage.tsx` |
| Task download card | 展示下载入口、批注写回警告、generate 产物的补充批注按钮 | `frontend/components/chat/TaskDownloadMessage.tsx` |
| Dual column message | 左进度日志 / 右 AI 内容的双列消息卡（含复制、下载、重试）；当前未接入主消息分派 | `frontend/components/chat/DualColumnMessage.tsx` |
| New chat popup | 类型侧栏的悬浮"新建对话/最近对话"弹窗，含重命名/删除右键菜单；当前未接入侧栏 | `frontend/components/chat/NewChatPopup.tsx` |
| Skeleton | shimmer 占位与页面/消息/双列骨架组件；当前未接入主流程 | `frontend/components/chat/Skeleton.tsx` |
| Shared tender form | 招标信息、模板/参数上传、模板候选、插入锚点、生成模式和 draft 同步 | `frontend/components/forms/TenderFormShared.tsx` |
| Form registry | `TenderType` 到显示名、表单组件、converter 的映射 | `frontend/components/chat/tenderFormRegistry.ts` |
| Layout shell | 通用 Header/Sidebar/History/MainLayout；**不**被 `/tender` 工作台使用 | `frontend/components/layout/` |
| API client | JSON、上传、下载、NDJSON agent run、任务、模板候选 API helper | `frontend/lib/api.ts` |
| SSE runtime | `EventSource` 包装、named events、重连、heartbeat、last event id 去重 | `frontend/lib/sse.ts` |
| SSE hook 层 | `useSSE` 封装 `createSSEConnection` 生命周期；`useChatSSE` 把事件映射到 store/messages | `frontend/hooks/useSSE.ts`, `frontend/hooks/useChatSSE.ts` |
| Main chat store | 会话、草稿、任务摘要、任务消息组、URL 同步、后端重启收敛 | `frontend/stores/chatStore.ts` |
| Stream store | 运行中日志、AI 文本、agent step 快照、进度和 last event id | `frontend/stores/chatStreamStore.ts` |
| URL mapper | URL 参数解析、`TenderType` 判定、canonical query 构造 | `frontend/utils/tenderTypeMapper.ts` |
| API types | 后端 payload、任务、agent run、SSE、错误码和模板候选类型 | `frontend/types/api.ts` |

## 核心模式

**Overall:** Next.js App Router + 客户端工作台 + Zustand 状态层 + 统一 API/SSE 边界。

**Key Characteristics:**
- 页面层只组合路由、三栏 UI 和启动副作用；长期业务状态放在 `frontend/stores/`。
- 后端请求集中到 `frontend/lib/api.ts`；组件调用 helper，不在组件内实现请求协议或裸 `fetch`（`frontend/components/` 与 `frontend/stores/` 中无 `fetch(` 调用）。
- `TenderType`（`xjcg`/`gngk`/`gjgk`）是前端 **UI 类型**；后端 `GenerateRequest.form_type` 由 `frontend/lib/formDataConverter.ts` 和 `frontend/lib/gngkFormType.ts` 在提交时生成。`gngk` 不是后端 form type。
- 任务链路以 `task_id` 为主键，SSE、任务消息组、下载卡、补充批注和 rewrite 产物续写都围绕 task summary 收敛。
- 会话、草稿、任务摘要和未读结果持久化到 `sessionStorage`；SSE stream runtime 是内存态，task resume metadata 单独持久化。
- `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 是 **generate-only** 字段：属于 `GenerateRequest` 与会话 draft 表单状态，不进入 agent run rewrite 的 `context_snapshot.rewrite_context`、也不出现在 `ChatPanel` 的 rewrite 请求构造中。

## 分层结构

**Route Layer:**
- 职责： 定义页面入口、metadata、全局样式和 `/tender` 工作台页面。
- Location: `frontend/app/`
- 包含： `layout.tsx`、`page.tsx`、`tender/page.tsx`、`globals.css`。
- Depends on: Next.js、React、workspace components、hooks、stores。
- Used by: 浏览器访问 `/` 和 `/tender`。

**Workbench UI Layer:**
- 职责： 展示三栏招标操作界面、聊天消息、表单、上传、下载和任务状态。
- Location: `frontend/components/chat/`、`frontend/components/forms/`、`frontend/components/layout/`
- 包含： `ChatPanel`、`ChatInput`、`ChatModelPicker`、`FormPanel`、`MessageList`、`TaskLogMessage`、`TaskContentMessage`、`TaskDownloadMessage`、`TenderFormShared`、`FileUploader`、`TemplateCandidateDialog`。
- Depends on: `frontend/stores/`、`frontend/hooks/`、`frontend/lib/api.ts`、`frontend/types/`。
- Used by: `frontend/app/tender/page.tsx` 直接挂载 chat 三栏；`layout/` 为通用壳，当前未被 workbench 路由引用。

**State Layer:**
- 职责： 保存会话、草稿、任务摘要、任务消息分组、运行中 stream、历史和局部 UI 状态。
- Location: `frontend/stores/`
- 包含： `chatStore.ts`、`chatStreamStore.ts`、`chatTaskSessionStore.ts`、`historyStore.ts`、`useAppStore.ts`。
- Depends on: Zustand、`frontend/types/`、纯 helper。
- Used by: 页面、聊天组件、表单组件、任务 hooks；`historyStore`/`useAppStore` 主要服务 `components/layout/`。

**Integration Layer:**
- 职责： 后端 API、SSE、NDJSON、上传下载、表单 payload 转换、URL canonical 化。
- Location: `frontend/lib/`、`frontend/hooks/`、`frontend/utils/`
- 包含： `api.ts`、`apiBaseUrl.ts`、`sse.ts`、`formDataConverter.ts`、`gngkFormType.ts`、`tenderFetch.ts`、`agentThinking.ts`、`chat-utils.ts`、`useSSE.ts`、`useChatSSE.ts`、`tenderTypeMapper.ts`。
- Depends on: 浏览器 `fetch`、`EventSource`、`URL`、`FormData` APIs 和 `frontend/types/`。
- Used by: 工作台 UI 和 stores。

**Type Layer:**
- 职责： 定义跨层契约和类型守卫。
- Location: `frontend/types/`
- 包含： `api.ts`、`chat.ts`、`index.ts`、`jest-dom.d.ts`。
- Depends on: TypeScript 类型系统。
- Used by: API client、stores、hooks、组件 props 和测试。

## 数据流

### 初次生成主链路

1. `/` 通过 `redirect('/tender')` 进入工作台 (`frontend/app/page.tsx`)。
2. `TenderPageContent` 解析 URL、建立或选择 conversation，并按需预取招标数据 (`frontend/app/tender/page.tsx`)。
3. 三栏布局：`TenderTypeSidebar` | `FormPanel` | `ChatPanel`，CSS grid 为 `grid-cols-[auto_minmax(0,2fr)_minmax(0,3fr)]`。
4. `TenderFormShared` 以 `draft > URL > default` 初始化表单状态、文件状态、生成模式和插入锚点。
5. `TenderFormShared` 校验招标编号、招标信息、模板文件、技术参数文件和插入锚点，组装 `BaseTenderFormData`。
6. `FormPanel` 使用 `tenderFormConverterMap[conversation.tenderType]` 生成 `GenerateRequest` 并附加 `conversation_id`。
7. `createGenerateTask()` 调用 `/api/generate`；`chatStore.startTask()` 建立任务摘要和消息组。
8. `useCurrentConversationTaskStatus()`、`useTaskHeartbeat()` 和 `useChatSSE()` 同步 queue/running/terminal 状态。
9. `chatStore.completeTask()` 创建或更新 `task-download` 下载卡，保留 `style_writeback` 和 `comment_writeback` 摘要。

### URL 与会话链路

1. `useUrlParams()` 使用 `useSearchParams()` 读取 `tender_lx`、`purchase_method`、`fund_lx`、`tenderno`。
2. `getTenderTypeFromParams()` 只按 `purchase_method` 判定前端 `TenderType`（`0`→`gjgk`、`2`→`gngk`、`5`→`xjcg`）；`tender_lx`/`fund_lx` 不参与前端 UI 判型。
3. `TenderPageContent` 对 `gngk` 使用 tenderno + `tender_lx` + `fund_lx` 查找会话（`findGngkConversationByIdentity`），避免不同子类型复用同一 draft。
4. `syncBrowserUrlToConversation()` 和 `chatStore.syncUrlToCurrentConversation()` 维护 canonical query。

### 生成请求载荷链路

1. 表单 wrapper 只传入 `tenderType`，具体 UI 复用 `TenderFormShared`（`XjcgTenderForm` / `GngkTenderForm` / `GjgkTenderForm`）。
2. 模板文件使用 `fileType="template"` 上传，技术参数文件使用 `fileType="params"` 上传。
3. `convertXjcgFormToApiRequest()` → `form_type: 'xjcg_tender'`；`convertGjgkFormToApiRequest()` → `form_type: 'gjgk_tender'`；`convertGngkFormToApiRequest()` 调用 `resolveGngkFormType()`。
4. 三个 converter 均写入 generate-only 字段：`generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode`。
5. **`gngk` UI 类型分派：** `resolveGngkFormType({ tender_lx, fund_lx, ifzgcg })`：
   - 工程类（`tender_lx` 1/2）先复用服务链路：`gngk_fw_cz_tender` / `gngk_fw_zc_tender`；
   - 货物类按 `fund_lx` + `ifzgcg` 分 `gngk_hw_cz_tender` / `gngk_hw_zc_tender`。

### Agent Run 与聊天链路

1. `ChatInput` 解析 `$rewrite` / `/rewrite` 前缀，或通过加号菜单选择上传文件 rewrite。
2. `ChatPanel` 构造 `AgentRunStreamRequest`：`conversation_id`、`message`、`model`、`selected_skills`、`context_snapshot`。
3. `streamAgentRun()` 以 NDJSON 调用 `/api/agent/runs/stream`。
4. `run_started`、`thinking_stage`、`tool_call` 更新 thinking card 或普通 AI 消息；`needs_input`/`done`/`error` 只更新普通消息，不创建后台 task。
5. 只有 `task_accepted` 调用 `startTask()` 并进入任务/SSE 体系。

### 上传文件 Rewrite 链路

1. `ChatInput` 的隐藏文件输入只接受 `.doc` / `.docx`。
2. `ChatPanel.handleRewriteFileSelect()` 调用 `uploadFile(file, 'rewrite_source')`，把返回文件写入 conversation draft 的 `rewrite_file`，并设置 `selected_skills: ['rewrite']`。
3. `buildAgentRunContextSnapshot()` 放入 `rewrite_available`、`uploaded_files` 和可选 `rewrite_context`。
4. `rewrite_context` 字段仅含：`form_type`、`insertion_config`、`tender_lx`、`fund_source_lx`、`tender_data_snapshot`（见 `AgentRunRewriteContextSnapshot`）。**不含** `generation_style` / `generation_mode` / `comment_generation_mode` / `style_writeback_mode`。
5. `resolveRewriteFormType()` 为上传 rewrite 计算后端 `form_type`；`gngk` 继续复用 `resolveGngkFormType()`。
6. rewrite task 完成后，`ChatPanel` 通过 `pending_rewrite_task_id` 监听终态，用下载卡产物回写 draft 的 `rewrite_file`，让下一轮 rewrite 基于最新文档。

### 任务 SSE 与产物流转

1. SSE 调用链：`useChatSSE` → `useSSE` → `createSSEConnection`。
2. `createSSEConnection()` 注册 `connected`、`log`、`llm`、`progress`、`agent_step`、`status`、`error`、`done`、`heartbeat` named events。
3. `useChatSSE()` 在连接前查询 `getTaskStatus()`，queued 不连 SSE，terminal 直接终态收敛。
4. `log` / `llm` / `agent_step` / `progress` 更新 `chatStreamStore` 和 task summary。
5. `done` / `error` 关闭连接并调用 `completeTask()` / `failTask()` / `cancelTask()`。
6. `MessageList` 按 `message.metadata.messageKind` 渲染 `task-log`、`task-content`、`agent-step`、`task-download` 或 thinking card，其余为普通消息。

### 模板候选链路

1. `TenderFormShared` 用招标编号和项目名维护候选缓存，并调用 `fetchTemplateCandidates()`。
2. 候选选择使用 `selectTemplateCandidate()`，后端返回 selected file 后写入模板上传槽。
3. 候选模板下载 URL 必须由 `getTemplateCandidateDownloadUrl()` 生成项目内代理 URL。

### 补充批注链路

1. `TaskDownloadMessage` 只对 `taskKind === 'generate'` 显示补充批注入口。
2. `ChatPanel.handleCommentSupplement()` 从下载卡读取 `metadata.outputFile`，调用 `createCommentSupplementTask()`（`/api/comment-supplement`）。
3. `comment_supplement` 复用 task summary、SSE、agent-step 和下载卡，不引入第二套任务流。

**状态管理：**
- `chatStore` 是持久化主状态，storage name 为 `chat-storage`，持久化 `conversations`、`currentConversationId`、`selectedTenderType`、`conversationDrafts`、`taskSummaries`、`unreadConversationResults`。
- `chatStreamStore` 是运行时内存状态，保存 `logs`、`aiText`、`agentSteps`、progress 和 `lastEventId`。
- `chatTaskSessionStore` 只持久化 task resume 元数据，storage name 为 `chat-task-session-storage`。
- `historyStore`（`tender-history-storage`）与 `useAppStore`（`tender-app-storage`，仅 persist `sidebarOpen`）存在，但工作台主流程以 `chatStore` 为准；layout 侧栏会消费 history/app store。

## 关键抽象

**`TenderType`:**
- 职责： 前端 UI 类型，取值为 `xjcg`、`gngk`、`gjgk`。
- Examples: `frontend/types/index.ts`, `frontend/components/chat/tenderFormRegistry.ts`, `frontend/utils/tenderTypeMapper.ts`
- Pattern: UI type 与后端 `GenerateRequest.form_type` 分离；`gngk` 提交时再分派具体 form type。新增招标类型要同步 registry、converter、URL mapper、类型和测试。

**`GenerateRequest`:**
- 职责： 初次生成任务 payload。
- Examples: `frontend/types/api.ts`, `frontend/lib/formDataConverter.ts`
- Pattern: converter 负责默认值、文件路径提取、generate-only 字段和 `gngk` form type 分派。

**`FileType`:**
- 职责： 上传接口 `file_type` 参数。
- Values: `template` | `rewrite_source` | `params` | `qualification`
- Pattern: 表单模板/参数用 `template`/`params`；聊天上传 rewrite 源文档用 `rewrite_source`。

**`ConversationFormDraft`:**
- 职责： 会话级表单草稿、上传文件、生成字段、rewrite 文件、一次性 skill、pending rewrite 恢复状态和模型。
- Examples: `frontend/stores/chatStore.ts`, `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/chat/ChatPanel.tsx`
- Pattern: draft 是表单恢复、URL 同步和 agent run context 的共享来源；generate-only 字段可存在 draft 中供表单恢复，但不进入 rewrite 请求体。

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
- Pattern: 只展示前置流状态；后台任务创建后进度交给 task/SSE 卡。rewrite skill 会抑制 thinking card。

**`AgentRunRewriteContextSnapshot`:**
- 职责： 上传文件 rewrite / rewrite skill 的上下文快照。
- Fields: `form_type?`、`insertion_config?`、`tender_lx?`、`fund_source_lx?`、`tender_data_snapshot?`
- Pattern: 与 `GenerateRequest` 共享 form_type 分派，但刻意不携带 generation_* 字段。

## 入口清单

**Root Page:**
- Location: `frontend/app/page.tsx`
- Triggers: 用户访问 `/`。
- Responsibilities: 重定向到 `/tender`。

**Workbench Page:**
- Location: `frontend/app/tender/page.tsx`
- Triggers: 用户访问 `/tender` 或带查询参数的深链。
- Responsibilities: 三栏 UI、URL 参数处理、会话创建、招标数据预取、conversation heartbeat（30s + focus/pageshow/online/visibility）。

**Generate Task Entry:**
- Location: `frontend/components/chat/FormPanel.tsx`
- Triggers: 招标表单提交。
- Responsibilities: 通过 converter 生成 `GenerateRequest`、创建 generate task、启动任务消息组和 task summary；绑定 `useChatSSE` / `useTaskHeartbeat` / `useCurrentConversationTaskStatus`。

**Agent Run Entry:**
- Location: `frontend/components/chat/ChatPanel.tsx`
- Triggers: 右侧聊天输入发送普通消息、`/rewrite`、上传 Word 文件 rewrite。
- Responsibilities: 构造 agent run context、处理 NDJSON event、在 `task_accepted` 后接入 task/SSE 状态机。

**API Entry:**
- Location: `frontend/lib/api.ts`
- Triggers: 表单提交、聊天发送、上传、下载、模板候选、任务状态/heartbeat。
- Responsibilities: 构造请求、解析 wrapped/unwrapped response、抛出 `ApiError`、解析 NDJSON agent run。

**SSE Entry:**
- Location: `frontend/hooks/useChatSSE.ts`（底层 `frontend/lib/sse.ts`，封装层 `frontend/hooks/useSSE.ts`）
- Triggers: 任务创建、恢复或进入 running 后绑定 `task_id`。
- Responsibilities: 状态确认、连接 SSE、映射事件、终态收敛。

## 架构约束

- **Threading:** 浏览器单线程 React 渲染；异步 `fetch`、`EventSource`、timer、focus、pageshow、online 和 visibility 事件驱动任务状态。
- **Global state:** Zustand stores 是模块级 singleton，见 `frontend/stores/chatStore.ts`、`frontend/stores/chatStreamStore.ts`、`frontend/stores/chatTaskSessionStore.ts`、`frontend/stores/historyStore.ts`、`frontend/stores/useAppStore.ts`。
- **Circular imports:** `frontend/types/` 保持无运行时副作用；修改 `stores/types/lib` 边界时避免让类型层反向依赖组件或 store runtime。
- **API boundary:** 新增后端请求放到 `frontend/lib/api.ts`；组件负责用户交互和调用 API helper，不实现协议解析或裸 `fetch`。
- **Generate-only fields:** `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 只属于 generate 请求和会话 draft，不进入 rewrite request、skill state 或 prompt surface。
- **GNGK dispatch:** `gngk` 是 UI 类型；后端 `form_type` 分派集中到 `frontend/lib/gngkFormType.ts`，generate 与上传文件 rewrite 复用同一 helper。
- **Rewrite upload:** 源文档 `file_type` 必须为 `rewrite_source`；产物通过 `pending_rewrite_task_id` 回写 draft，不另开任务状态机。
- **Agent run:** `POST /api/agent/runs/stream` 是右侧聊天唯一流式入口；rewrite 通过 agent run 接受任务，不使用第二套任务状态机。
- **SSE contract:** 新增 SSE event 要同步 `frontend/types/api.ts`、`frontend/lib/sse.ts` named event 注册、`frontend/hooks/useChatSSE.ts` 解析和相关测试。
- **Sensitive data:** `.env`、token、真实客户原文、私有路径和 traceback 不进入文档、日志、测试夹具或最终回复。

## 反模式

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
**Do this instead:** 只修改 `frontend/lib/gngkFormType.ts`，调用点继续复用 helper，并同步相关单测。

### 把 `gngk` 当作后端 form_type

**What happens:** 直接把 UI `TenderType` 字符串 `gngk` 提交给后端。
**Why it's wrong:** 后端只认 `gngk_hw_*` / `gngk_fw_*` 等具体 form type。
**Do this instead:** UI 保持 `gngk`；提交时经 converter / `resolveRewriteFormType` → `resolveGngkFormType`。

### 把 generation_* 塞进 rewrite

**What happens:** 在 `AgentRunStreamRequest` 或 `rewrite_context` 中附带 `generation_mode` 等字段。
**Why it's wrong:** 违反 generate-only 契约，污染 rewrite skill state。
**Do this instead:** 这些字段仅经 `formDataConverter` 进入 `GenerateRequest`。

### 手工 patch URL 参数

**What happens:** 组件直接改单个 query 参数或直接调用 history API 构造 URL。
**Why it's wrong:** canonical URL、会话身份和 deep-link 恢复会漂移。
**Do this instead:** 使用 `buildCanonicalSearchParams()`、`syncBrowserUrlToConversation()` 和 `chatStore.syncUrlToCurrentConversation()`。

### 把 agent run 当成任务状态

**What happens:** `run_started`、`thinking_stage` 或 `needs_input` 直接创建 task summary、SSE 连接或下载卡。
**Why it's wrong:** agent run 是任务创建前置流，后台任务只有后端接受后才存在。
**Do this instead:** 只有 `task_accepted` 触发 `chatStore.startTask()`；其他 agent run 事件只更新普通消息或 thinking card。

### 在前端暴露后端私有运行细节

**What happens:** 把审计日志路径、完整下载路径、traceback、完整客户原文或检索 JSON 暴露到 UI 或前端 store。
**Why it's wrong:** 违反 agent run 和检索审计的白名单边界，增加敏感信息泄露风险。
**Do this instead:** 只消费 scrub 后的摘要字段和公开任务状态，类型定义放在 `frontend/types/api.ts`。

## 错误处理

**Strategy:** API 层统一转换为 `ApiError`，任务层通过状态确认、SSE 终态、heartbeat 和本地中断态收敛 UI。

**Patterns:**
- `frontend/lib/api.ts` 从 HTTP status、wrapped `success: false`、嵌套 `detail` 和 network failure 提取 message/code/status。
- `frontend/hooks/useChatSSE.ts` 先 `getTaskStatus()`，再连接 SSE；terminal 或 missing task 直接收敛。
- `frontend/hooks/useCurrentConversationTaskStatus.ts` 轮询当前任务，`TASK_NOT_FOUND` 或 404 调用 `discardStaleTask()`。
- `frontend/hooks/useTaskHeartbeat.ts` 对活跃 task 发 heartbeat，终态回调给 `FormPanel` 做补拉收敛。
- `frontend/app/tender/page.tsx` 用 conversation heartbeat 检测后端 `instance_id` 变化，并调用 `handleBackendRestart()`。
- UI 组件展示用户可读错误；下载失败路径在 `ChatPanel` 使用 alert + console 错误。

## 横切关注点

**Logging:** 用户可见任务日志经 `TaskLogMessage` 渲染；排障日志使用 `console`，主要在 `frontend/lib/sse.ts`、`frontend/components/chat/ChatPanel.tsx`、`frontend/components/chat/FormPanel.tsx`。

**Validation:** TypeScript strict、ESLint、Jest 单测、Playwright E2E；表单提交前在 `TenderFormShared` 做必填、文件和插入锚点检查，后端仍是最终契约校验方。

**Authentication:** 前端未检测到认证层；`sessionStorage` 会话只表示浏览器工作台状态，不表示用户身份或权限。

**Styling:** UI 使用 Tailwind utility class、CSS variables 和 `lucide-react` 图标，组件样式主要内联在 TSX 中；共享 class helper 是 `frontend/lib/utils.ts`。

**外部 API 隔离：** 招标详情、模板候选、模板下载、Word COM、LLM 和检索运行时都在后端封装；前端只消费项目内 `/api/*`（经 Next rewrite 代理）。

**运行端口：** 前端开发服默认 `8502`（`npm run dev`）；后端 API 经 `NEXT_PUBLIC_API_URL` / `apiBaseUrl` 解析，Next rewrite 转发 `/api/:path*`。

---

*前端架构分析：2026-07-15*
