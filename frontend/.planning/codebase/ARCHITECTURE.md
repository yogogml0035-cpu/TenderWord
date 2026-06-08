<!-- refreshed: 2026-06-08 -->
# 前端架构事实地图

**分析日期：** 2026-06-08

**范围：** 仅 `frontend/` 子项目。依据当前源码、配置、测试和项目级 skill 索引刷新；未读取 `.env.local`、`.env.local.example`、`.npmrc` 或任何真实凭据。

## 系统总览

```text
┌─────────────────────────────────────────────────────────────┐
│                    Next.js App Router                       │
│         `frontend/app/page.tsx`, `frontend/app/tender/page.tsx` │
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
│                  Zustand 会话/任务/stream 状态               │
│                  `frontend/stores/`                          │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│ API client / SSE / NDJSON / 表单转换 / URL 映射              │
│ `frontend/lib/`, `frontend/utils/`, `frontend/types/`        │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│ TenderWord FastAPI 后端 `/api/*` 与浏览器 runtime            │
│ `frontend/next.config.ts`, `frontend/lib/api.ts`             │
└─────────────────────────────────────────────────────────────┘
```

前端是 TenderWord 的浏览器工作台。它负责招标类型选择、URL 深链、会话草稿、招标数据预取、模板候选选择、文件上传、生成任务创建、聊天式 rewrite 前置流、补充批注任务、SSE 进度展示、智能体过程卡和下载入口。

## 组件职责

| Component | Responsibility | File |
|-----------|----------------|------|
| App Router 根入口 | `/` 重定向到 `/tender` | `frontend/app/page.tsx` |
| 工作台页面 | 三栏布局、URL 参数建会话、招标数据预取、会话心跳和后端重启检测 | `frontend/app/tender/page.tsx` |
| 类型侧栏 | 招标类型分组、会话选择、创建、重命名、删除和 URL 同步 | `frontend/components/chat/TenderTypeSidebar.tsx` |
| 表单面板 | 挂载当前 tender form、创建 generate task、绑定任务状态和 SSE | `frontend/components/chat/FormPanel.tsx` |
| 聊天面板 | agent run、rewrite、上传 rewrite 文件、补充批注、取消、下载 | `frontend/components/chat/ChatPanel.tsx` |
| 共享表单 | 模板/参数上传、模板候选、锚点、生成方式、批注开关、样式回填和 draft 同步 | `frontend/components/forms/TenderFormShared.tsx` |
| 表单注册表 | `TenderType` 到显示名、表单组件、生成转换器的映射 | `frontend/components/chat/tenderFormRegistry.ts` |
| API client | JSON、上传、下载、NDJSON、agent run、任务和模板候选 API helper | `frontend/lib/api.ts` |
| SSE runtime | EventSource 包装、named events、重连、heartbeat、last event id | `frontend/lib/sse.ts` |
| 任务 SSE hook | 任务状态确认、SSE 事件到 stream/store/messages 的映射 | `frontend/hooks/useChatSSE.ts` |
| 主会话 store | 会话、草稿、任务摘要、任务消息组、URL 同步、后端重启收敛 | `frontend/stores/chatStore.ts` |
| Stream store | 运行中日志、AI 文本、agent step 快照和进度 | `frontend/stores/chatStreamStore.ts` |
| URL mapper | URL 参数解析、TenderType 判定、canonical query 构造 | `frontend/utils/tenderTypeMapper.ts` |
| API 类型 | 后端 payload、任务、agent run、SSE 和错误码类型 | `frontend/types/api.ts` |

## 模式概览

**Overall:** Next.js App Router + 客户端工作台 + Zustand 状态层 + 统一 API/SSE 边界。

**Key Characteristics:**
- 页面层只负责路由、三栏组合和启动副作用；业务状态集中在 stores、hooks、lib helpers。
- 所有后端请求统一走 `frontend/lib/api.ts`，组件不直接拼后端 URL。
- 会话和草稿以 `sessionStorage` 为主要持久化介质；stream runtime 不持久化。
- `TenderType` 是前端 UI 类型，后端 `form_type` 通过 converter/helper 再分派。
- 任务链路以 task id 为主键，SSE、任务消息组、下载卡和补充批注围绕 task summary 收敛。

## 分层

**路由层：**
- 用途：定义页面入口、元数据和工作台容器。
- Location: `frontend/app/`
- 包含：`layout.tsx`、`page.tsx`、`tender/page.tsx`、`globals.css`。
- Depends on: Next.js、React、workspace components、hooks、stores。
- Used by: 浏览器访问 `/` 和 `/tender`。

**工作台 UI 层：**
- 用途：展示三栏招标操作界面、聊天消息、表单、上传、下载和状态。
- Location: `frontend/components/chat/`、`frontend/components/forms/`、`frontend/components/layout/`
- 包含：`ChatPanel`、`FormPanel`、`MessageList`、`TenderFormShared`、`FileUploader`、`TemplateCandidateDialog` 等。
- Depends on: stores、hooks、`frontend/lib/api.ts` helper、`frontend/types/`。
- Used by: `frontend/app/tender/page.tsx`。

**状态层：**
- 用途：保存会话、草稿、任务摘要、任务消息分组、stream runtime、历史和 UI 状态。
- Location: `frontend/stores/`
- 包含：`chatStore.ts`、`chatStreamStore.ts`、`chatTaskSessionStore.ts`、`historyStore.ts`、`useAppStore.ts`。
- Depends on: Zustand、类型、部分纯 helper。
- Used by: 页面、聊天组件、表单组件、任务 hooks。

**集成层：**
- 用途：后端 API、SSE、NDJSON、上传下载、表单 payload 转换、URL canonical 化。
- Location: `frontend/lib/`、`frontend/hooks/`、`frontend/utils/`
- 包含：`api.ts`、`sse.ts`、`formDataConverter.ts`、`gngkFormType.ts`、`tenderFetch.ts`、`useChatSSE.ts`、`tenderTypeMapper.ts`。
- Depends on: 浏览器 fetch/EventSource/URL APIs、`frontend/types/`。
- Used by: 工作台 UI 和 stores。

**类型层：**
- 用途：定义跨层契约和类型守卫。
- Location: `frontend/types/`
- 包含：`api.ts`、`chat.ts`、`index.ts`。
- Depends on: TypeScript 类型系统；`types/chat.ts` 类型引用 `types/api.ts`。
- Used by: 全前端。

## 数据流

### `/tender` 深链与会话启动

1. `useUrlParams()` 从 `useSearchParams()` 解析 `tender_lx`、`purchase_method`、`fund_lx`、`tenderno`（`frontend/hooks/useUrlParams.ts`）。
2. `parseTenderUrlParams()` 由 URL 参数判定前端 `TenderType`（`frontend/utils/tenderTypeMapper.ts`）。
3. `TenderPageContent` hydration 后选择 tender type，并按 tenderno/类型查找或创建 conversation（`frontend/app/tender/page.tsx`）。
4. `gngk` 使用 tenderno + `tender_lx` + `fund_lx` 精确匹配会话（`frontend/stores/chatStore.ts`）。
5. 深链参数先写入 conversation draft，再由 `TenderFormShared` 以 `draft > URL > default` 初始化表单（`frontend/components/forms/TenderFormShared.tsx`）。
6. `syncBrowserUrlToConversation()` 和 `syncUrlToCurrentConversation()` 维护 canonical URL（`frontend/utils/tenderTypeMapper.ts`、`frontend/stores/chatStore.ts`）。

### 生成任务

1. `TenderFormShared` 收集招标数据、模板文件、技术参数文件、锚点、生成风格、生成模式、批注生成开关和样式回填模式（`frontend/components/forms/TenderFormShared.tsx`）。
2. `FormPanel` 从 `tenderFormRegistry` 获取当前类型表单组件和 converter（`frontend/components/chat/FormPanel.tsx`、`frontend/components/chat/tenderFormRegistry.ts`）。
3. `formDataConverter.ts` 将表单数据转成 `GenerateRequest`，文件只进入 `file_paths.template` 和 `file_paths.tender_params`（`frontend/lib/formDataConverter.ts`）。
4. `gngk` 后端 `form_type` 由 `resolveGngkFormType()` 根据 `tender_lx + fund_lx + ifzgcg` 分派（`frontend/lib/gngkFormType.ts`）。
5. `createGenerateTask()` 调用 `/api/generate`（`frontend/lib/api.ts`）。
6. `chatStore.startTask()` 建立 task summary 和 task message group（`frontend/stores/chatStore.ts`）。
7. `useCurrentConversationTaskStatus()` 查任务队列/运行状态，`useChatSSE()` 连接 `/api/stream/{taskId}`（`frontend/hooks/useCurrentConversationTaskStatus.ts`、`frontend/hooks/useChatSSE.ts`）。
8. SSE `log`、`llm`、`progress`、`agent_step`、`done`、`error` 更新 `chatStreamStore` 和任务消息；终态产生下载卡（`frontend/hooks/useChatSSE.ts`、`frontend/stores/chatStore.ts`）。

### Agent run 与上传文件 rewrite

1. `ChatPanel` 从聊天输入、draft、rewrite 文件和选中 skill 构造 `AgentRunStreamRequest`（`frontend/components/chat/ChatPanel.tsx`）。
2. 上传待改 Word 文件时调用 `uploadFile(file, 'rewrite_source')`，并写入 draft 的 `rewrite_file` 和一次性 `selected_skills: ['rewrite']`（`frontend/components/chat/ChatPanel.tsx`）。
3. `streamAgentRun()` 解析 `/api/agent/runs/stream` NDJSON（`frontend/lib/api.ts`）。
4. `task_accepted` 后才调用 `startTask()` 并进入 SSE；`needs_input` 只追加普通 AI 提示（`frontend/components/chat/ChatPanel.tsx`）。
5. 上传文件 rewrite 的 `rewrite_context.form_type` 继续调用 `resolveGngkFormType()`，保持与生成链路一致（`frontend/components/chat/ChatPanel.tsx`、`frontend/lib/gngkFormType.ts`）。

### 补充批注

1. 初次生成下载卡触发补充批注动作，入口由 `TaskDownloadMessage` 到 `MessageList` 再回调 `ChatPanel`（`frontend/components/chat/TaskDownloadMessage.tsx`、`frontend/components/chat/MessageList.tsx`、`frontend/components/chat/ChatPanel.tsx`）。
2. `createCommentSupplementTask()` 调用 `/api/comment-supplement`，payload 只包含会话 id、当前源文件和模型（`frontend/lib/api.ts`）。
3. `comment_supplement` 复用任务状态、SSE、下载消息；`comment_agent` 过程卡通过 `agent_step` 展示（`frontend/hooks/useChatSSE.ts`）。
4. rewrite 和 comment_supplement 的下载卡不继续暴露补充批注动作，避免对衍生文件重复创建补充任务。

**State Management:**
- `chatStore` 是持久化主状态；`chatStreamStore` 是运行时内存状态；`chatTaskSessionStore` 只保留 task resume 元数据。
- running task 恢复前必须先查询后端状态；404 / `TASK_NOT_FOUND` 收敛成本地中断或失败态。

## 核心抽象

**`TenderType`：**
- 用途：前端 UI 类型，当前只有 `xjcg`、`gngk`、`gjgk`。
- Examples: `frontend/types/index.ts`、`frontend/components/chat/tenderFormRegistry.ts`。
- Pattern: UI type 与后端 form type 分离。

**`GenerateRequest`：**
- 用途：初次生成任务 payload。
- Examples: `frontend/types/api.ts`、`frontend/lib/formDataConverter.ts`。
- Pattern: converter 负责默认值、文件路径提取和 `gngk` form type 分派。

**`ConversationFormDraft`：**
- 用途：会话级表单草稿、上传文件、生成字段、rewrite 文件、一次性 skill 和 pending 恢复状态。
- Examples: `frontend/stores/chatStore.ts`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/components/chat/ChatPanel.tsx`。
- Pattern: draft 是表单恢复和 agent run 上下文的共享来源。

**`TaskMessageGroupIds`：**
- 用途：一个 task id 对应 log/content/download 三类任务消息。
- Examples: `frontend/stores/chatStore.ts`。
- Pattern: 任务消息由 store 方法维护，不在组件中手写 group。

**`agent-step` message：**
- 用途：完成态智能体过程卡。
- Examples: `frontend/types/chat.ts`、`frontend/hooks/useChatSSE.ts`、`frontend/components/chat/AgentThinkingMessage.tsx`。
- Pattern: 运行中快照在 `chatStreamStore`，完成态 upsert 到 `chatStore.conversations`，不纳入旧三卡分组。

## 入口点

**浏览器入口：**
- Location: `frontend/app/page.tsx`
- Triggers: 用户访问 `/`。
- Responsibilities: 重定向到 `/tender`。

**工作台入口：**
- Location: `frontend/app/tender/page.tsx`
- Triggers: 用户访问 `/tender` 或带查询参数的深链。
- Responsibilities: 三栏 UI、URL 参数处理、会话创建、招标数据预取、会话心跳。

**API 入口：**
- Location: `frontend/lib/api.ts`
- Triggers: 表单提交、聊天发送、上传、下载、模板候选、任务状态/心跳。
- Responsibilities: 构造请求、解析 wrapped/unwrapped response、抛出 `ApiError`、解析 NDJSON agent run。

**SSE 入口：**
- Location: `frontend/hooks/useChatSSE.ts`
- Triggers: 任务创建或恢复后绑定 task id。
- Responsibilities: 状态确认、连接 SSE、映射事件、终态收敛。

## 架构约束

- **Threading:** 浏览器单线程 React 渲染；异步 fetch/EventSource/timer 驱动任务状态。
- **Global state:** Zustand stores 是模块级 singleton，见 `frontend/stores/chatStore.ts`、`frontend/stores/chatStreamStore.ts`、`frontend/stores/chatTaskSessionStore.ts`、`frontend/stores/historyStore.ts`、`frontend/stores/useAppStore.ts`。
- **Circular imports:** 当前未确认循环依赖；修改 stores/types/lib 边界时保持 `types/` 无运行时副作用。
- **API boundary:** 组件不得直接裸写后端 `fetch` 或外部模板候选 URL；统一经 `frontend/lib/api.ts`。
- **Generate-only fields:** `generation_mode`、`comment_generation_mode`、`style_writeback_mode` 只属于 generate 请求，不进入 rewrite request、skill state 或 prompt surface。
- **GNGK dispatch:** `gngk` 后端 `form_type` 分派必须集中到 `frontend/lib/gngkFormType.ts`。

## 反模式

### 组件直接请求后端或外部候选 URL

**What happens:** 在组件里拼 `/api/...`、后端主机或模板候选文件 URL。
**Why it's wrong:** 绕过 `ApiError`、base URL resolver、rewrite、测试 mock 和后端模板候选安全规则。
**Do this instead:** 新请求放入 `frontend/lib/api.ts`，模板候选继续使用 `fetchTemplateCandidates()`、`selectTemplateCandidate()`、`getTemplateCandidateDownloadUrl()`。

### 绕过 `resolveGngkFormType()`

**What happens:** 在 `ChatPanel`、converter 或表单组件里手写 `gngk_hw_*` / `gngk_fw_*` 分派。
**Why it's wrong:** generate 与上传文件 rewrite 可能进入不同后端 graph。
**Do this instead:** 只修改 `frontend/lib/gngkFormType.ts`，调用点保持复用 helper，并同步 `frontend/__tests__/unit/lib/test_form_data_converter.test.ts` 和 `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`。

### 手工 patch URL 参数

**What happens:** 组件直接改单个 query 参数或直接调用 history API 构造 URL。
**Why it's wrong:** canonical URL、会话身份和 deep-link 恢复会漂移。
**Do this instead:** 使用 `buildCanonicalSearchParams()`、`syncBrowserUrlToConversation()` 和 `chatStore.syncUrlToCurrentConversation()`。

### 把 agent run 当成任务状态

**What happens:** `run_started`、`thinking_stage` 或 `needs_input` 直接创建 task summary 或下载卡。
**Why it's wrong:** agent run 只是任务创建前置流，后台任务只有后端接受后才存在。
**Do this instead:** 只有 `task_accepted` 触发 `chatStore.startTask()`；其他 agent run 事件只更新普通消息或思考卡。

## 错误处理

**Strategy:** API 层统一转换为 `ApiError`，任务层通过状态确认、SSE 终态、心跳和本地中断态收敛 UI。

**模式：**
- `frontend/lib/api.ts` 从 HTTP status、wrapped `success: false`、嵌套 `detail` 和 network failure 提取 message/code/status。
- `frontend/hooks/useChatSSE.ts` 先 `getTaskStatus()`，再连接 SSE；terminal 或 missing task 直接收敛。
- `frontend/app/tender/page.tsx` 用会话 heartbeat 检测后端 instance id 变化，并调用 `handleBackendRestart()`。
- UI 组件展示用户可读错误；下载失败当前仍使用 alert + console 错误。

## 横切关注点

**Logging:** 用户可见任务日志经 task message 渲染；排障日志使用 console，主要在 `frontend/lib/sse.ts`、`frontend/components/chat/ChatPanel.tsx`、`frontend/components/chat/FormPanel.tsx`。

**Validation:** TypeScript strict、Jest 单测、Playwright mock E2E；表单提交前在 `TenderFormShared` 做基本必填/文件检查，后端仍是最终契约校验方。

**认证：** 当前未检测到前端认证层；不要把 `sessionStorage` 会话当成用户身份或权限。

---

*前端架构分析：2026-06-08*
