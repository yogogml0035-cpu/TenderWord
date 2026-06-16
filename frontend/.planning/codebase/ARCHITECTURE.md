<!-- refreshed: 2026-06-16 -->
# 前端架构事实地图

**分析日期：** 2026-06-16

**范围：** `frontend/` 前端子项目、前端配置、`README.md`、现有 `frontend/.planning/codebase/` 文档。未读取 `frontend/.env.local`、`backend/.env`、`.npmrc` 或任何真实密钥文件。

## 系统总览

```text
┌─────────────────────────────────────────────────────────────┐
│                    Next.js App Router                        │
│      `frontend/app/page.tsx`, `frontend/app/tender/page.tsx`  │
└───────────────┬─────────────────────────────┬───────────────┘
                │                             │
                ▼                             ▼
┌───────────────────────────────┐ ┌───────────────────────────┐
│ 三栏招标工作台 UI              │ │ URL / hydration / heartbeat │
│ `frontend/components/chat/`    │ │ `frontend/hooks/`           │
│ `frontend/components/forms/`   │ │ `frontend/app/tender/page.tsx` │
└───────────────┬───────────────┘ └──────────────┬────────────┘
                │                                │
                ▼                                ▼
┌─────────────────────────────────────────────────────────────┐
│                  Zustand 会话、任务、stream 状态              │
│                  `frontend/stores/`                          │
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

前端是 TenderWord 的浏览器工作台，负责招标类型选择、URL 深链、会话和草稿、招标信息预取、模板候选选择、文件上传、生成任务创建、聊天式 agent run、上传文件 rewrite、补充批注、SSE 进度、智能体过程卡和任务产物下载展示。浏览器端不直接执行 Word COM、LLM、检索或文件系统写入，这些能力都由后端 `/api/*` 封装。

## 组件职责

| 组件 | 职责 | 文件 |
|-----------|----------------|------|
| App Router 根入口 | `/` 进入工作台 | `frontend/app/page.tsx` |
| 工作台页面 | 三栏布局、URL 参数建会话、招标数据预取、会话 heartbeat、后端重启收敛 | `frontend/app/tender/page.tsx` |
| 类型侧栏 | 招标类型分组、会话选择、创建、重命名、删除和 URL 同步入口 | `frontend/components/chat/TenderTypeSidebar.tsx` |
| 表单面板 | 挂载当前 tender form、创建 generate task、绑定当前任务状态、取消任务 | `frontend/components/chat/FormPanel.tsx` |
| 聊天面板 | agent run、rewrite、上传文件 rewrite、补充批注、下载、取消、重试 | `frontend/components/chat/ChatPanel.tsx` |
| 聊天输入 | 普通消息输入、`/rewrite` 能力选择、上传文件 rewrite 文件选择 | `frontend/components/chat/ChatInput.tsx` |
| 消息列表 | 普通消息、任务日志、AI 正文、智能体过程卡、下载卡分派渲染 | `frontend/components/chat/MessageList.tsx` |
| 下载卡 | 任务产物展示、下载按钮、generate 产物的补充批注入口 | `frontend/components/chat/TaskDownloadMessage.tsx` |
| 共享表单 | 招标信息、模板/参数上传、模板候选、插入锚点、生成模式、批注和样式回填 | `frontend/components/forms/TenderFormShared.tsx` |
| 表单注册表 | `TenderType` 到显示名、表单组件、生成转换器的映射 | `frontend/components/chat/tenderFormRegistry.ts` |
| API client | JSON、上传、下载、NDJSON agent run、任务、模板候选 API helper | `frontend/lib/api.ts` |
| SSE runtime | `EventSource` 包装、named events、重连、heartbeat、last event id 去重 | `frontend/lib/sse.ts` |
| 任务 SSE hook | 任务状态确认、SSE 事件到 stream/store/messages 的映射 | `frontend/hooks/useChatSSE.ts` |
| 主会话 store | 会话、草稿、任务摘要、任务消息组、URL 同步、后端重启收敛 | `frontend/stores/chatStore.ts` |
| Stream store | 运行中日志、AI 文本、agent step 快照和进度 | `frontend/stores/chatStreamStore.ts` |
| URL mapper | URL 参数解析、`TenderType` 判定、canonical query 构造 | `frontend/utils/tenderTypeMapper.ts` |
| API 类型 | 后端 payload、任务、agent run、SSE、错误码和模板候选类型 | `frontend/types/api.ts` |

## 模式概览

**总体：** Next.js App Router + 客户端工作台 + Zustand 状态层 + 统一 API/SSE 边界。

**关键特征：**
- 页面层只组合路由、三栏 UI 和启动副作用；长期业务状态放在 `frontend/stores/`，I/O 边界放在 `frontend/lib/` 与 `frontend/hooks/`。
- 后端请求集中到 `frontend/lib/api.ts`；组件可以触发动作，但不自己实现后端请求协议，也不直接访问外部模板候选 URL。
- 会话、草稿、任务摘要和未读结果持久化到 `sessionStorage`；SSE stream runtime 保持内存态；last event id resume 信息单独存在 `frontend/stores/chatTaskSessionStore.ts`。
- `TenderType` 是前端 UI 类型；后端 `GenerateRequest.form_type` 由 `frontend/lib/formDataConverter.ts` 与 `frontend/lib/gngkFormType.ts` 生成。
- 任务链路以 `task_id` 为主键，SSE、任务消息组、下载卡、补充批注和上传 rewrite 产物续写都围绕 task summary 收敛。

## 分层

**路由层：**
- 用途：定义页面入口、metadata、工作台页面和全局样式。
- 位置：`frontend/app/`
- 包含：`layout.tsx`、`page.tsx`、`tender/page.tsx`、`globals.css`。
- 依赖：Next.js、React、workspace components、hooks、stores。
- 使用方：浏览器访问 `/` 和 `/tender`。

**工作台 UI 层：**
- 用途：展示三栏招标操作界面、聊天消息、表单、上传、下载和任务状态。
- 位置：`frontend/components/chat/`、`frontend/components/forms/`、`frontend/components/layout/`
- 包含：`ChatPanel`、`FormPanel`、`MessageList`、`TaskLogMessage`、`TaskContentMessage`、`TaskDownloadMessage`、`TenderFormShared`、`FileUploader`、`TemplateCandidateDialog`。
- 依赖：`frontend/stores/`、`frontend/hooks/`、`frontend/lib/api.ts`、`frontend/types/`。
- 使用方：`frontend/app/tender/page.tsx`。

**状态层：**
- 用途：保存会话、草稿、任务摘要、任务消息分组、运行中 stream、历史和局部 UI 状态。
- 位置：`frontend/stores/`
- 包含：`chatStore.ts`、`chatStreamStore.ts`、`chatTaskSessionStore.ts`、`historyStore.ts`、`useAppStore.ts`。
- 依赖：Zustand、`frontend/types/`、纯 helper。
- 使用方：页面、聊天组件、表单组件、任务 hooks。

**集成层：**
- 用途：后端 API、SSE、NDJSON、上传下载、表单 payload 转换、URL canonical 化。
- 位置：`frontend/lib/`、`frontend/hooks/`、`frontend/utils/`
- 包含：`api.ts`、`apiBaseUrl.ts`、`sse.ts`、`formDataConverter.ts`、`gngkFormType.ts`、`tenderFetch.ts`、`useChatSSE.ts`、`tenderTypeMapper.ts`。
- 依赖：浏览器 `fetch`、`EventSource`、`URL`、`FormData` APIs 和 `frontend/types/`。
- 使用方：工作台 UI 和 stores。

**类型层：**
- 用途：定义跨层契约和类型守卫。
- 位置：`frontend/types/`
- 包含：`api.ts`、`chat.ts`、`index.ts`。
- 依赖：TypeScript 类型系统。
- 使用方：全前端，尤其是 API client、stores、hooks 和组件 props。

## 数据流

### `/tender` 深链与会话启动

1. `useUrlParams()` 从 `useSearchParams()` 解析 `tender_lx`、`purchase_method`、`fund_lx`、`tenderno`（`frontend/hooks/useUrlParams.ts:66`）。
2. `parseTenderUrlParams()` 由 URL 参数判定前端 `TenderType`，判型只依赖 `purchase_method`（`frontend/utils/tenderTypeMapper.ts:205`）。
3. `TenderPageContent` hydration 后选择 tender type，并按 tenderno/类型查找或创建 conversation（`frontend/app/tender/page.tsx:34`）。
4. `gngk` 会话用 tenderno + `tender_lx` + `fund_lx` 做身份匹配（`frontend/app/tender/page.tsx:78`、`frontend/stores/chatStore.ts:981`）。
5. 深链参数写入 conversation draft；`TenderFormShared` 以 `draft > URL > default` 初始化 `tender_lx`、`fund_lx` 和表单状态（`frontend/components/forms/TenderFormShared.tsx:632`、`frontend/components/forms/TenderFormShared.tsx:679`）。
6. `syncBrowserUrlToConversation()` 与 `chatStore.syncUrlToCurrentConversation()` 维护 canonical URL（`frontend/utils/tenderTypeMapper.ts:72`、`frontend/stores/chatStore.ts:2375`）。

### 生成任务

1. `TenderFormShared` 校验招标编号、招标信息、模板文件、技术参数文件和插入锚点，组装 `BaseTenderFormData`（`frontend/components/forms/TenderFormShared.tsx:1544`）。
2. `FormPanel` 通过 `tenderFormConverterMap` 把当前表单转成 `GenerateRequest` 并附加 `conversation_id`（`frontend/components/chat/FormPanel.tsx:387`）。
3. `formDataConverter.ts` 写入 `file_paths.template`、`file_paths.tender_params`、`generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 和 `model`（`frontend/lib/formDataConverter.ts:117`、`frontend/lib/formDataConverter.ts:193`、`frontend/lib/formDataConverter.ts:225`）。
4. `gngk` 后端 `form_type` 由 `resolveGngkFormType()` 按 `tender_lx + fund_lx + ifzgcg` 分派；工程类和服务类都进入 `gngk_fw_*` form type（`frontend/lib/gngkFormType.ts:18`）。
5. `createGenerateTask()` 调用 `/api/generate`（`frontend/lib/api.ts:808`），`chatStore.startTask()` 建立 task summary、active task 和消息组（`frontend/components/chat/FormPanel.tsx:392`、`frontend/stores/chatStore.ts:1202`）。
6. `useCurrentConversationTaskStatus()` 轮询当前任务状态和排队进度；`useTaskHeartbeat()` 对活跃 task 发 heartbeat（`frontend/hooks/useCurrentConversationTaskStatus.ts:88`、`frontend/hooks/useTaskHeartbeat.ts:16`）。
7. `useChatSSE()` 在任务进入 running 后连接 `/api/stream/{taskId}`，处理 `log`、`llm`、`agent_step`、`progress`、`done`、`error`（`frontend/hooks/useChatSSE.ts:622`、`frontend/hooks/useChatSSE.ts:766`）。
8. 终态由 `chatStore.completeTask()` 更新日志/正文卡并创建或更新 `task-download` 下载卡（`frontend/stores/chatStore.ts:1536`）。

### Agent Run 与普通聊天

1. `ChatPanel` 从当前 conversation、draft、聊天输入、模型和选中 skill 构造 `AgentRunStreamRequest`（`frontend/components/chat/ChatPanel.tsx:393`）。
2. `buildAgentRunContextSnapshot()` 把已有下载产物可 rewrite 状态、上传文件和 `rewrite_context` 放入 agent run context（`frontend/components/chat/ChatPanel.tsx:123`）。
3. `streamAgentRun()` 以 NDJSON 方式调用 `/api/agent/runs/stream`（`frontend/lib/api.ts:590`）。
4. `run_started`、`thinking_stage`、`tool_call` 更新前置思考卡或普通 AI 消息；`needs_input` 只追加用户可读提示，不创建后端 task（`frontend/components/chat/ChatPanel.tsx:553`、`frontend/components/chat/ChatPanel.tsx:608`）。
5. 只有 `task_accepted` 触发 `startTask()` 并进入任务/SSE 体系；synthetic task 只用于前端展示，不进入真实任务跟踪（`frontend/components/chat/ChatPanel.tsx:559`）。

### 上传文件 Rewrite

1. `ChatInput` 的隐藏文件输入只接受 `.doc`、`.docx`，文件选择失败时在输入区展示本地提示（`frontend/components/chat/ChatInput.tsx:275`、`frontend/components/chat/ChatInput.tsx:303`）。
2. `ChatPanel.handleRewriteFileSelect()` 调用 `uploadFile(file, 'rewrite_source')`，把返回文件写入 conversation draft 的 `rewrite_file`，并一次性选择 `selected_skills: ['rewrite']`（`frontend/components/chat/ChatPanel.tsx:338`）。
3. 发送时若 draft 有 `rewrite_file`，`selected_skills` 固定为 `['rewrite']`，context 的 `uploaded_files` 带 `file_path` 和 `file_name`（`frontend/components/chat/ChatPanel.tsx:417`、`frontend/components/chat/ChatPanel.tsx:131`）。
4. 上传文件 rewrite 的 `rewrite_context.form_type` 通过 `resolveRewriteFormType()` 生成，`gngk` 继续复用 `resolveGngkFormType()`（`frontend/components/chat/ChatPanel.tsx:162`）。
5. 后端接受 rewrite task 后，`ChatPanel` 保存 `pending_rewrite_prompt` 和 `pending_rewrite_task_id`；rewrite 完成后用下载卡产物回写 draft 的 `rewrite_file`，让下一轮 rewrite 基于最新文档（`frontend/components/chat/ChatPanel.tsx:581`、`frontend/components/chat/ChatPanel.tsx:951`）。

### Artifact / 任务产物展示

1. `useChatSSE()` 从 `done` event 或 `getTaskStatus()` 提取 `output_file`、`file_name`、`style_writeback`、`comment_writeback`（`frontend/hooks/useChatSSE.ts:237`、`frontend/hooks/useChatSSE.ts:530`）。
2. `chatStore.completeTask()` 将文本内容写入 `task-content` 或 `agent-step`，将文件产物写入 `task-download` metadata 的 `outputFile` 和 `fileName`（`frontend/stores/chatStore.ts:1568`、`frontend/stores/chatStore.ts:1589`）。
3. `MessageList` 根据 `message.metadata.messageKind` 分派到 `TaskLogMessage`、`TaskContentMessage`、`TaskDownloadMessage` 或 `AgentThinkingMessage`（`frontend/components/chat/MessageList.tsx:306`）。
4. `TaskContentMessage` 展示普通 AI 内容、`content_agent` 过程、`comment_agent` 过程和复制动作（`frontend/components/chat/TaskContentMessage.tsx:369`）。
5. `TaskDownloadMessage` 展示文件名、下载按钮、批注写回警告和 generate 产物的“补充批注”按钮（`frontend/components/chat/TaskDownloadMessage.tsx:15`）。
6. `ChatPanel.handleDownload()` 使用 `downloadFile()` 拉取 blob 并触发浏览器下载（`frontend/components/chat/ChatPanel.tsx:830`、`frontend/lib/api.ts:899`）。

### 补充批注

1. `TaskDownloadMessage` 只对 `taskKind === 'generate'` 的下载卡显示“补充批注”（`frontend/components/chat/TaskDownloadMessage.tsx:24`、`frontend/components/chat/TaskDownloadMessage.tsx:82`）。
2. `ChatPanel.handleCommentSupplement()` 从下载卡读取 `metadata.outputFile`，调用 `createCommentSupplementTask()`（`frontend/components/chat/ChatPanel.tsx:847`、`frontend/lib/api.ts:815`）。
3. `comment_supplement` 复用 task summary、SSE、下载卡；`comment_agent` 过程通过 `agent_step` 和 `TaskContentMessage` 展示（`frontend/hooks/useChatSSE.ts:119`、`frontend/components/chat/TaskContentMessage.tsx:380`）。

### 模板候选

1. `TenderFormShared` 按招标编号和项目名维护模板候选缓存（`frontend/components/forms/TenderFormShared.tsx:1378`）。
2. `fetchTemplateCandidates()` 调用 `/api/template-candidates`，`selectTemplateCandidate()` 调用 `/api/template-candidates/select`（`frontend/lib/api.ts:735`、`frontend/lib/api.ts:749`）。
3. `getTemplateCandidateDownloadUrl()` 生成项目内 `/api/template-candidates/download` 代理 URL（`frontend/lib/api.ts:758`）。
4. `TemplateCandidateDialog` 渲染候选表格、不可选状态、刷新、选择和候选模板下载代理链接（`frontend/components/forms/TemplateCandidateDialog.tsx:62`、`frontend/components/forms/TemplateCandidateDialog.tsx:171`）。

**状态管理：**
- `chatStore` 是持久化主状态，storage name 是 `chat-storage`，持久化目标是 `sessionStorage`（`frontend/stores/chatStore.ts:994`、`frontend/stores/chatStore.ts:2408`）。
- `chatStreamStore` 是运行时内存状态，保存 `logs`、`aiText`、`agentSteps`、progress 和 last event id（`frontend/stores/chatStreamStore.ts:5`）。
- `chatTaskSessionStore` 只持久化 task resume 元数据，storage name 是 `chat-task-session-storage`（`frontend/stores/chatTaskSessionStore.ts:16`、`frontend/stores/chatTaskSessionStore.ts:43`）。
- running task 恢复前先查询后端状态；404 / `TASK_NOT_FOUND` 由 `discardStaleTask()` 或本地中断态收敛（`frontend/hooks/useChatSSE.ts:735`、`frontend/hooks/useCurrentConversationTaskStatus.ts:197`）。

## 核心抽象

**`TenderType`：**
- 用途：前端 UI 类型，取值为 `xjcg`、`gngk`、`gjgk`。
- 示例：`frontend/types/index.ts`、`frontend/components/chat/tenderFormRegistry.ts`。
- 模式：UI type 与后端 `GenerateRequest.form_type` 分离；新增招标类型要同步 registry、converter、URL mapper 和 tests。

**`GenerateRequest`：**
- 用途：初次生成任务 payload。
- 示例：`frontend/types/api.ts`、`frontend/lib/formDataConverter.ts`。
- 模式：converter 负责默认值、文件路径提取、generate-only 字段和 `gngk` form type 分派。

**`ConversationFormDraft`：**
- 用途：会话级表单草稿、上传文件、生成字段、rewrite 文件、一次性 skill 和 pending rewrite 恢复状态。
- 示例：`frontend/stores/chatStore.ts`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/components/chat/ChatPanel.tsx`。
- 模式：draft 是表单恢复、URL 同步和 agent run context 的共享来源。

**`TaskMessageGroupIds`：**
- 用途：一个 `task_id` 对应 `task-log`、`task-content`、`task-download` 三类消息。
- 示例：`frontend/stores/chatStore.ts`、`frontend/components/chat/MessageList.tsx`。
- 模式：任务消息由 store 方法维护，组件不手写 message group。

**`agent-step` message：**
- 用途：智能体过程卡，展示 `content_agent`、`comment_agent` 和 rewrite 过程。
- 示例：`frontend/types/chat.ts`、`frontend/types/api.ts`、`frontend/stores/chatStore.ts`、`frontend/components/chat/TaskContentMessage.tsx`。
- 模式：运行中快照在 `chatStreamStore.agentSteps`，完成态 upsert 到 conversation messages。

**`AgentThinkingCardState`：**
- 用途：agent run 创建任务前的“任务上下文助手”过程卡。
- 示例：`frontend/lib/agentThinking.ts`、`frontend/components/chat/AgentThinkingMessage.tsx`、`frontend/types/chat.ts`。
- 模式：只展示前置流状态；后台任务创建后进度交给 task/SSE 卡。

## 入口点

**浏览器入口：**
- 位置：`frontend/app/page.tsx`
- 触发：用户访问 `/`。
- 职责：重定向到 `/tender`。

**工作台入口：**
- 位置：`frontend/app/tender/page.tsx`
- 触发：用户访问 `/tender` 或带查询参数的深链。
- 职责：三栏 UI、URL 参数处理、会话创建、招标数据预取、会话 heartbeat。

**API 入口：**
- 位置：`frontend/lib/api.ts`
- 触发：表单提交、聊天发送、上传、下载、模板候选、任务状态/heartbeat。
- 职责：构造请求、解析 wrapped/unwrapped response、抛出 `ApiError`、解析 NDJSON agent run。

**SSE 入口：**
- 位置：`frontend/hooks/useChatSSE.ts`
- 触发：任务创建、恢复或进入 running 后绑定 `task_id`。
- 职责：状态确认、连接 SSE、映射事件、终态收敛。

**URL 入口：**
- 位置：`frontend/utils/tenderTypeMapper.ts`
- 触发：深链加载、类型切换、会话切换、draft 同步。
- 职责：`purchase_method` 到 `TenderType` 映射、canonical query 构造、浏览器 URL 替换。

## 架构约束

- **线程模型：** 浏览器单线程 React 渲染；异步 `fetch`、`EventSource`、timer、focus、pageshow、online 和 visibility 事件驱动任务状态。
- **全局状态：** Zustand stores 是模块级 singleton，见 `frontend/stores/chatStore.ts`、`frontend/stores/chatStreamStore.ts`、`frontend/stores/chatTaskSessionStore.ts`、`frontend/stores/historyStore.ts`、`frontend/stores/useAppStore.ts`。
- **循环导入：** `frontend/types/` 保持无运行时副作用；修改 `stores/types/lib` 边界时避免让类型层反向依赖组件或 store runtime。
- **API 边界：** 新增后端请求放到 `frontend/lib/api.ts`；组件负责用户交互和调用 API helper，不实现协议解析。
- **Generate-only 字段：** `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 只属于 generate 请求和会话 draft，不进入 rewrite request、skill state 或 prompt surface。
- **GNGK 分派：** `gngk` 后端 `form_type` 分派集中到 `frontend/lib/gngkFormType.ts`，generate 和上传文件 rewrite 复用同一 helper。
- **Agent run：** `POST /api/agent/runs/stream` 是右侧聊天唯一流式入口；rewrite 通过 agent run 接受任务，不使用第二套任务状态机。
- **SSE 契约：** 新增 SSE event 要同步 `frontend/types/api.ts`、`frontend/lib/sse.ts` named event 注册、`frontend/hooks/useChatSSE.ts` 解析和相关测试。
- **敏感数据：** `.env`、token、真实客户原文、私有路径和 traceback 不进入文档、日志、测试夹具或最终回复。

## 反模式

### 组件内实现后端请求协议

**问题形态：** 在组件里写裸 `fetch`、手工解析 API error、手工拼后端 host。
**风险原因：** 绕过 `ApiError`、base URL resolver、Next rewrite、测试 mock 和统一错误口径。
**正确做法：** 新请求放入 `frontend/lib/api.ts`，类型同步 `frontend/types/api.ts`，组件只调用 helper。

### 直接访问外部模板候选 URL

**问题形态：** 组件拿候选记录的外部文件 URL 直接作为下载地址。
**风险原因：** 绕过后端模板候选代理和可审计下载边界。
**正确做法：** 继续使用 `getTemplateCandidateDownloadUrl()`，候选选择走 `selectTemplateCandidate()`（`frontend/lib/api.ts`、`frontend/components/forms/TemplateCandidateDialog.tsx`）。

### 绕过 `resolveGngkFormType()`

**问题形态：** 在 `ChatPanel`、converter 或表单组件里手写 `gngk_hw_*` / `gngk_fw_*` 分派。
**风险原因：** generate 与上传文件 rewrite 可能进入不同后端 graph。
**正确做法：** 只修改 `frontend/lib/gngkFormType.ts`，调用点保持复用 helper，并同步 `frontend/__tests__/unit/lib/test_form_data_converter.test.ts` 和 `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`。

### 手工 patch URL 参数

**问题形态：** 组件直接改单个 query 参数或直接调用 history API 构造 URL。
**风险原因：** canonical URL、会话身份和 deep-link 恢复会漂移。
**正确做法：** 使用 `buildCanonicalSearchParams()`、`syncBrowserUrlToConversation()` 和 `chatStore.syncUrlToCurrentConversation()`（`frontend/utils/tenderTypeMapper.ts`、`frontend/stores/chatStore.ts`）。

### 把 agent run 当成任务状态

**问题形态：** `run_started`、`thinking_stage` 或 `needs_input` 直接创建 task summary、SSE 连接或下载卡。
**风险原因：** agent run 是任务创建前置流，后台任务只有后端接受后才存在。
**正确做法：** 只有 `task_accepted` 触发 `chatStore.startTask()`；其他 agent run 事件只更新普通消息或思考卡（`frontend/components/chat/ChatPanel.tsx`）。

### 在前端暴露后端私有运行细节

**问题形态：** 把审计日志路径、完整下载路径、traceback、完整客户原文或检索 JSON 暴露到 UI 或前端 store。
**风险原因：** 违反 agent run 和检索审计的白名单边界，增加敏感信息泄露风险。
**正确做法：** 只消费 scrub 后的摘要字段和公开任务状态，类型定义放在 `frontend/types/api.ts`。

## 错误处理

**策略：** API 层统一转换为 `ApiError`，任务层通过状态确认、SSE 终态、heartbeat 和本地中断态收敛 UI。

**模式：**
- `frontend/lib/api.ts` 从 HTTP status、wrapped `success: false`、嵌套 `detail` 和 network failure 提取 message/code/status。
- `frontend/hooks/useChatSSE.ts` 先 `getTaskStatus()`，再连接 SSE；terminal 或 missing task 直接收敛。
- `frontend/hooks/useCurrentConversationTaskStatus.ts` 轮询当前任务，`TASK_NOT_FOUND` 或 404 调用 `discardStaleTask()`。
- `frontend/hooks/useTaskHeartbeat.ts` 对活跃 task 发 heartbeat，终态回调给 `FormPanel` 做补拉收敛。
- `frontend/app/tender/page.tsx` 用 conversation heartbeat 检测后端 `instance_id` 变化，并调用 `handleBackendRestart()`。
- UI 组件展示用户可读错误；下载失败路径在 `frontend/components/chat/ChatPanel.tsx` 使用 alert + console 错误。

## 横切关注点

**日志：** 用户可见任务日志经 `TaskLogMessage` 渲染；排障日志使用 `console`，主要在 `frontend/lib/sse.ts`、`frontend/components/chat/ChatPanel.tsx`、`frontend/components/chat/FormPanel.tsx`。

**校验：** TypeScript strict、ESLint、Jest 单测、Playwright E2E；表单提交前在 `TenderFormShared` 做必填、文件和插入锚点检查，后端仍是最终契约校验方。

**认证：** 前端未检测到认证层；`sessionStorage` 会话只表示浏览器工作台状态，不表示用户身份或权限。

**样式：** UI 使用 Tailwind utility class、CSS variables 和 `lucide-react` 图标，组件样式主要内联在 TSX 中；共享 class helper 是 `frontend/lib/utils.ts`。

**外部 API 隔离：** 招标详情、模板候选、模板下载、Word COM、LLM 和检索运行时都在后端封装；前端只消费项目内 `/api/*`。

---

*架构分析：2026-06-16*
