# 前端外部集成事实地图

**分析日期：** 2026-07-21

**范围：** 仅 `frontend/` 对后端 API、SSE、NDJSON、浏览器运行时、本地存储、上传下载、模板候选、agent run 前置流、测试工具与开发服务器的集成边界。只记录 `frontend/.env.local.example` 中的配置键名；不读取 `.env.local` 真实值。

**对照提交：** `e748f16d1a2b253c766008f1a060e3ebba9b2f85`（映射时仓库 HEAD 与该提交一致）。

## API 与外部服务

**TenderWord 后端 API：**
- 服务用途：招标数据查询、模板候选、文件上传、生成任务、补充批注任务、任务状态、任务列表、任务取消、心跳、下载、agent run 前置流与任务 SSE。
- SDK/Client：无第三方 HTTP SDK；JSON、上传、下载、NDJSON 与 SSE URL 主入口统一封装在 `frontend/lib/api.ts`。所有后端请求必须走该 API client；组件层不写裸 `fetch`，也不直接访问外部模板候选 URL。
- 认证：未检测到登录 provider、JWT 注入、OAuth SDK 或稳定 `Authorization` header；`frontend/lib/api.ts` 不注入 auth。
- 基础 URL：`frontend/lib/apiBaseUrl.ts` 解析 `NEXT_PUBLIC_API_URL`（逗号分隔多候选），无配置时使用 `http://localhost:8000`；浏览器环境会按当前 hostname 推导 `:8000` 后端地址，并与配置候选按 host 别名（`localhost` / `127.0.0.1` 互通）优先匹配。
- 开发代理：`frontend/next.config.ts` 将 `/api/:path*` rewrite 到 `resolveApiBaseUrl()` 结果，并将 `NEXT_PUBLIC_API_URL` 候选 hostname 纳入 `allowedDevOrigins`。
- Next route：`frontend/app/api/` 不存在；前端自身不实现 API route。
- 产品源码中的后端 `fetch(` 仅出现在 `frontend/lib/api.ts`（内部 `request`、`streamNdjson`、`fetchTenderDataWithType`、`downloadFile`）；组件与 hooks 通过导出 helper 间接调用。

**后端 API endpoints：**
- 招标查询：`GET /api/tender/{tender_no}` — `fetchTenderDataWithType()` / `fetchTenderData()`，见 `frontend/lib/api.ts`、`frontend/lib/tenderFetch.ts`。`gjgk` 会规范化 `project_number`（去招标编号前缀）。
- 模板候选列表：`GET /api/template-candidates` — `fetchTemplateCandidates()`，见 `frontend/lib/api.ts`、`frontend/components/forms/TenderFormShared.tsx`。
- 模板候选选择：`POST /api/template-candidates/select` — `selectTemplateCandidate()`，见 `frontend/lib/api.ts`。
- 模板候选下载代理：`GET /api/template-candidates/download` — `getTemplateCandidateDownloadUrl()`，见 `frontend/lib/api.ts`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/components/forms/TemplateCandidateDialog.tsx`。
- 文件上传：`POST /api/upload`、`POST /api/upload/multiple`（`FormData`）— `uploadFile()` / `uploadFiles()`，见 `frontend/lib/api.ts`、`frontend/components/forms/FileUploader.tsx`。`FileType`：`template` | `rewrite_source` | `params` | `qualification`（`frontend/types/api.ts`）。
- 生成任务创建：`POST /api/generate` — `createGenerateTask()`，见 `frontend/lib/api.ts`、`frontend/components/chat/FormPanel.tsx`。
- 补充批注任务创建：`POST /api/comment-supplement` — `createCommentSupplementTask()`，见 `frontend/lib/api.ts`、`frontend/components/chat/ChatPanel.tsx`。
- 任务状态：`GET /api/tasks/{taskId}` — `getTaskStatus()`，见 `frontend/lib/api.ts`、`frontend/hooks/useCurrentConversationTaskStatus.ts`、`frontend/hooks/useChatSSE.ts`。
- 任务列表：`GET /api/tasks` — `getTaskList()`（可选 `status` / `page` / `page_size` / `user_session_id`），见 `frontend/lib/api.ts`、`frontend/hooks/useLatestActiveTaskSummary.ts`。
- 任务取消：`DELETE /api/tasks/{taskId}` — `cancelTask()`；对 `TASK_CANNOT_CANCEL` 做 noop 成功返回，见 `frontend/lib/api.ts`、`frontend/components/chat/FormPanel.tsx`、`frontend/components/chat/ChatPanel.tsx`。
- 任务心跳：`POST /api/tasks/{taskId}/heartbeat` — `sendTaskHeartbeat()`，见 `frontend/lib/api.ts`、`frontend/hooks/useTaskHeartbeat.ts`（默认间隔 5s）。
- 会话心跳：`POST /api/conversations/{conversationId}/heartbeat` — `sendConversationHeartbeat()`，见 `frontend/lib/api.ts`、`frontend/app/tender/page.tsx`。
- 文件下载：`GET /api/download/{file_path}` — `downloadFile()` / `getDownloadUrl()`，见 `frontend/lib/api.ts`、`frontend/components/chat/ChatPanel.tsx`；`frontend/components/layout/Sidebar.tsx` 使用相对 `href="/api/download/..."` 交给 Next rewrite 代理。
- 任务 SSE：`GET /api/stream/{taskId}` — `getTaskStreamUrl()`，见 `frontend/lib/api.ts`、`frontend/lib/sse.ts`；hooks 侧用路径 `/api/stream/${taskId}` 经 `createSSEConnection()` 拼 base URL。

**Agent run 前置流：**
- 服务用途：右侧聊天输入先经任务上下文助手判定 rewrite 能力、需求补充与任务创建。
- 入口：`streamAgentRun()` → `POST /api/agent/runs/stream`，见 `frontend/lib/api.ts`、`frontend/components/chat/ChatPanel.tsx`。
- 协议：底层 `streamNdjson()` 使用 `fetch` 读取 NDJSON response body，每行 JSON 由 `parseAgentRunEvent()` 过滤为类型化事件。
- 请求字段：`conversation_id`、`message`、`model`、`selected_skills`、`context_snapshot`（`AgentRunStreamRequest`，`frontend/types/api.ts`）。
- 技能范围：`AgentSkill` 当前只有 `rewrite`；`selected_skills` 在 `frontend/stores/chatStore.ts` 与 `frontend/components/chat/ChatPanel.tsx` 中归一化为最多一个技能，消息发出后清空。
- 上传文件 rewrite：`ChatPanel.tsx` 使用 `uploadFile(file, 'rewrite_source')`，再把 `uploaded_files` 与 `rewrite_context` 放入 `context_snapshot`（`buildAgentRunContextSnapshot` / `buildAgentRunRewriteContext`）。
- 事件类型：`run_started`、`thinking_stage`、`tool_call`、`task_accepted`、`needs_input`、`done`、`error`（`frontend/types/api.ts` + `parseAgentRunEvent()`）。
- 任务边界：`task_accepted` 进入 task summary、SSE、取消与下载链路；`needs_input` 与非任务 `done` 只更新聊天消息，不创建后台任务。
- 思考展示：`frontend/lib/agentThinking.ts` 将 agent run 事件折叠为 UI 可消费的 thinking 状态；`AgentThinkingMessage.tsx` 展示。

**任务 SSE：**
- 服务用途：生成、rewrite、补充批注任务的实时日志、进度、LLM 文本、agent step、终态与 heartbeat。
- 入口：`getTaskStreamUrl()`、`createSSEConnection()`、`useSSE()`、`useChatSSE()`，见 `frontend/lib/api.ts`、`frontend/lib/sse.ts`、`frontend/hooks/useSSE.ts`、`frontend/hooks/useChatSSE.ts`。
- 运行时：`frontend/lib/sse.ts` 包装浏览器 `EventSource`，支持 `lastEventId` query、事件去重（`seenEventIds`，上限 5000）、heartbeat timeout 与可选指数退避重连（默认 `autoReconnect: false`）。
- 命名事件：`connected`、`log`、`llm`、`progress`、`agent_step`、`status`、`error`、`done`、`heartbeat`（`sse.ts` 中显式 `addEventListener`）。
- 状态映射：`useChatSSE.ts` 写入 `chatStreamStore` / `chatStore`，终态后清理 `chatTaskSessionStore`；必要时回退 `getTaskStatus()`。`useChatSSE` / `useSSE` 默认 `heartbeatTimeout: 45000`。

**模板候选：**
- 服务用途：获取可选模板候选、选择候选、通过后端代理下载候选文件。
- UI：`frontend/components/forms/TemplateCandidateDialog.tsx`。
- 表单接入：`frontend/components/forms/TenderFormShared.tsx`（组件内 `buildTemplateCandidateCacheKey(tenderNo, projectName)` 缓存候选与 ranking）。
- API：`fetchTemplateCandidates()`、`selectTemplateCandidate()`、`getTemplateCandidateDownloadUrl()`。
- 约束：前端只消费后端返回的候选、ranking、`selectable` 与 `blocked_reason`；不得直接访问外部模板候选 URL。外部下载必须走 `/api/template-candidates/download`。

**模型选择：**
- UI 选项：`deepseek`、`qwen`、`doubao`，定义在 `frontend/components/forms/ModelSelector.tsx` 的 `MODEL_OPTIONS`；聊天侧复用见 `frontend/components/chat/ChatModelPicker.tsx`。
- 前端职责：仅把模型枚举传给 `GenerateRequest`、`CommentSupplementTaskRequest` 或 `AgentRunStreamRequest`。
- Provider 密钥与真实 LLM 调用不在前端；前端不保存 provider key。

## 跨层约定（task type / tender type / form type）

- `TaskKind`：`generate` / `rewrite` / `comment_supplement`（`frontend/types/api.ts`），由 `parseTaskKind`、SSE/agent 事件解析、`chatStore` 共享。
- `TaskStatus`：`queued` / `running` / `completed` / `failed` / `cancelled`。
- `TenderType`（UI）：`xjcg` / `gngk` / `gjgk`；URL canonical 见 `frontend/utils/tenderTypeMapper.ts`，与 `useUrlParams`、`chatStore`、`app/tender/page.tsx` 协作。
- `gngk` 在前端是 UI 类型；提交后端时由 `frontend/lib/gngkFormType.ts` 的 `resolveGngkFormType({ tender_lx, fund_lx, ifzgcg })` 分派到 `form_type`：`gngk_hw_zc_tender` / `gngk_hw_cz_tender` / `gngk_fw_zc_tender` / `gngk_fw_cz_tender`。规则：工程类（`tender_lx` 1/2）当前复用服务链路；否则按 `fund_lx` 与 `ifzgcg !== 2` 区分采购/服务。
- 调用方：generate 经 `frontend/lib/formDataConverter.ts`（`convertGngkFormToApiRequest`）；rewrite 经 `frontend/components/chat/ChatPanel.tsx`（`resolveRewriteFormType` → `resolveGngkFormType`）。`xjcg`→`xjcg_tender`、`gjgk`→`gjgk_tender` 为直接映射。
- Generate-only 字段：`generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 仅属于 `GenerateRequest` / 表单 draft，不得进入 rewrite / agent skill surface。

## 数据存储

**数据库：**
- 前端未直接连接数据库。招标数据、任务、上传文件、模板候选与会话心跳均经 `frontend/lib/api.ts` 或相对 `/api/download/...` 访问后端。

**浏览器存储：**
- `chat-storage` — `chatStore.ts`：Zustand `persist` + `sessionStorage`（会话、草稿、任务摘要、未读结果）。
- `chat-task-session-storage` — `chatTaskSessionStore.ts`：`sessionStorage`（task id 与 last event id）。
- `tender-history-storage` — `historyStore.ts`：`sessionStorage`（最近历史）。
- `tender-app-storage` — `useAppStore.ts`：默认 `localStorage`；`partialize` 仅 `sidebarOpen`。
- `chatStreamStore.ts` — 内存 store，不持久化完整 stream payload。

**文件存储：**
- 浏览器不直接访问本地文件系统、对象存储或云盘。
- 上传：`uploadFile()` / `uploadFiles()` → `/api/upload` 或 `/api/upload/multiple`。
- 生成产物下载：`downloadFile()` / `getDownloadUrl()` 或相对 `/api/download/...`（`Sidebar.tsx`）。
- 模板候选下载：`/api/template-candidates/download`（`TemplateCandidateDialog.tsx` 等）。

**缓存：**
- 模板候选组件状态缓存：`TenderFormShared.tsx`。
- 生产静态资源 header：`next.config.ts`（`/_next/static` immutable；其他路径 `no-store`）。

## 认证与身份

**认证提供方：**
- 未检测到登录页、认证 provider、JWT 注入、OAuth SDK 或权限 UI。
- `frontend/lib/api.ts` 不设置 `Authorization` header。

**会话身份：**
- 前端会话 identity 是浏览器本地 conversation id、task id、招标类型、招标编号与 `gngk` 子类型组合，不是安全身份。
- `gngk` 后端 form type 分派依赖 `tender_lx + fund_lx + ifzgcg`（`gngkFormType.ts`）。
- URL canonical 与会话恢复：`tenderTypeMapper.ts`、`useUrlParams.ts`、`chatStore.ts`、`app/tender/page.tsx`。

## 监控与可观测性

**错误追踪：**
- 未检测到 Sentry、Datadog、OpenTelemetry、PostHog、Google Analytics、Firebase 或其他前端监控 SDK。

**日志：**
- 用户可见任务日志 / 正文 / agent step / 下载卡：`TaskLogMessage.tsx`、`TaskContentMessage.tsx`、`AgentThinkingMessage.tsx`、`TaskDownloadMessage.tsx`。
- 排障：`console.log` / `console.warn` / `console.error`，主要见 `frontend/lib/sse.ts`、`ChatPanel.tsx`、`FormPanel.tsx`。
- E2E 证据：Playwright 失败截图、视频、trace（`playwright.config.ts`）。

## CI/CD 与部署

**托管：**
- `frontend/` 顶层未检测到 `vercel.json`、`Dockerfile`、`docker-compose*.yml` 或 `netlify.toml`。
- Next.js dev/start 端口固定 `8502`（`package.json`）。

**CI 流水线：**
- 仓库级 `.github/workflows/` 未检测到。
- Playwright 可启动 `npm run dev -- --webpack`；`CI` 下 forbidOnly、retry、单 worker，且不复用已运行 server。

## 环境配置

**必需 env vars：**
- 无必须前端密钥变量。
- `NEXT_PUBLIC_API_URL` 可选（逗号分隔多候选）；影响浏览器 API base URL、Next rewrite 目标与开发期 allowed origins。键名见 `frontend/.env.local.example`。

**测试 env vars：**
- `CI` — Playwright forbidOnly / retries / workers / server reuse。
- `PLAYWRIGHT_USE_SYSTEM_CHROME` — 非 CI 是否使用系统 Chrome（默认开，`'0'` 关）。

**密钥位置：**
- 可存在 `frontend/.env.local`；内容不读取、不写入知识包。
- `frontend/.env.local.example` 仅记录 `NEXT_PUBLIC_API_URL` 键名与多候选示例格式。

## Webhook 与回调

**入站：**
- 前端没有自定义后端回调 endpoint；`frontend/app/api/` 不存在。

**出站：**
- JSON / upload / binary download / NDJSON：`frontend/lib/api.ts`。
- 任务 SSE：`frontend/lib/sse.ts` 的 `EventSource`。
- 历史下载链接：`Sidebar.tsx` 相对 `/api/download/...`。
- 产品源码后端 `fetch(` 集中于 `frontend/lib/api.ts`；组件层不直接裸 `fetch` 后端。

## 集成修改规则

- 新后端接口必须同步 `frontend/types/api.ts`、`frontend/lib/api.ts` 与相关测试。
- 新 SSE 事件必须同步后端事件模型/发送方、`frontend/types/api.ts` union、`frontend/lib/sse.ts` named event 注册、`frontend/hooks/useChatSSE.ts` 映射与 hook/store 测试。
- 新 agent run NDJSON 事件必须同步 `frontend/types/api.ts`、`parseAgentRunEvent()` 与 `ChatPanel.tsx` 事件处理。
- `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 是 generate-only 字段，仅出现在 `GenerateRequest`（`formDataConverter.ts`）与生成表单 draft（`TenderFormShared.tsx` / `chatStore.ts`）；不得进入 rewrite 请求模型（`AgentRunStreamRequest` / `AgentRunRewriteContextSnapshot`）、skill state 或 prompt surface。
- 上传文件 rewrite 使用 `fileType: 'rewrite_source'`，经 `uploaded_files` + `rewrite_context` 进入 agent run；不要恢复旧 edit 入口或第二套任务链路。
- `gngk` 提交与上传文件 rewrite 的 `form_type` 都必须走 `gngkFormType.ts`（generate 经 `formDataConverter.ts`，rewrite 经 `ChatPanel.tsx`）。
- 模板候选外部 URL 必须继续通过后端 API 代理，不得从组件直接请求。

---

*前端集成分析：2026-07-21*
