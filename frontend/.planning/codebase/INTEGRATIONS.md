# 前端外部集成事实地图

**分析日期：** 2026-06-16

**范围：** 仅 `frontend/` 对后端 API、SSE、NDJSON、浏览器运行时、本地存储、上传下载、模板候选、agent run 前置流、测试工具和开发服务器的集成边界。`frontend/.env.local`、`frontend/.env.local.example` 和 `frontend/.npmrc` 文件存在；内容不读取，不写入事实文档。

## API 与外部服务

**TenderWord 后端 API：**
- 服务用途：招标数据查询、模板候选、文件上传、生成任务、补充批注任务、任务状态、任务取消、心跳、下载、agent run 前置流和任务 SSE。
- SDK/Client：无第三方 SDK；JSON、上传、下载和 NDJSON 主入口统一封装在 `frontend/lib/api.ts`。
- 认证：未检测到登录 provider、JWT 注入、OAuth SDK 或稳定 `Authorization` header；`frontend/lib/api.ts` 不注入 auth。
- 基础 URL：`frontend/lib/apiBaseUrl.ts` 解析 `NEXT_PUBLIC_API_URL`，无配置时使用 `http://localhost:8000`，浏览器环境还会按当前 hostname 推导 `:8000` 后端地址。
- 开发代理：`frontend/next.config.ts` 将 `/api/:path*` rewrite 到后端 API base URL，并将 `NEXT_PUBLIC_API_URL` 候选 hostname 纳入 `allowedDevOrigins`。
- Next route：`frontend/app/api/` 未检测到；前端自身不实现 API route。

**后端 API endpoints：**
- 招标查询：`GET /api/tender/{tender_no}`，helper 为 `fetchTenderDataWithType()` / `fetchTenderData()`，见 `frontend/lib/api.ts`、`frontend/lib/tenderFetch.ts`。
- 模板候选列表：`GET /api/template-candidates`，helper 为 `fetchTemplateCandidates()`，见 `frontend/lib/api.ts`、`frontend/components/forms/TenderFormShared.tsx`。
- 模板候选选择：`POST /api/template-candidates/select`，helper 为 `selectTemplateCandidate()`，见 `frontend/lib/api.ts`。
- 模板候选下载代理：`GET /api/template-candidates/download`，helper 为 `getTemplateCandidateDownloadUrl()`，见 `frontend/lib/api.ts`、`frontend/components/forms/TemplateCandidateDialog.tsx`。
- 文件上传：`POST /api/upload`、`POST /api/upload/multiple`，使用 `FormData`，见 `frontend/lib/api.ts`、`frontend/components/forms/FileUploader.tsx`。
- 生成任务创建：`POST /api/generate`，helper 为 `createGenerateTask()`，见 `frontend/lib/api.ts`、`frontend/components/chat/FormPanel.tsx`。
- 补充批注任务创建：`POST /api/comment-supplement`，helper 为 `createCommentSupplementTask()`，见 `frontend/lib/api.ts`、`frontend/components/chat/ChatPanel.tsx`。
- 任务状态与列表：`GET /api/tasks/{taskId}`、`GET /api/tasks`，见 `frontend/lib/api.ts`。
- 任务取消：`DELETE /api/tasks/{taskId}`，helper 为 `cancelTask()`，见 `frontend/lib/api.ts`。
- 任务心跳：`POST /api/tasks/{taskId}/heartbeat`，helper 为 `sendTaskHeartbeat()`，见 `frontend/hooks/useTaskHeartbeat.ts`。
- 会话心跳：`POST /api/conversations/{conversationId}/heartbeat`，helper 为 `sendConversationHeartbeat()`，见 `frontend/app/tender/page.tsx`。
- 文件下载：`GET /api/download/{file_path}`，helper 为 `downloadFile()` / `getDownloadUrl()`，见 `frontend/lib/api.ts`；`frontend/components/layout/Sidebar.tsx` 也使用相对 `href="/api/download/..."` 交给 Next rewrite 代理。

**Agent run 前置流：**
- 服务用途：右侧聊天输入先经任务上下文助手判定 rewrite 能力、需求补充和任务创建。
- 入口：`streamAgentRun()` 调用 `POST /api/agent/runs/stream`，见 `frontend/lib/api.ts`、`frontend/components/chat/ChatPanel.tsx`。
- 协议：`streamNdjson()` 使用 `fetch` 读取 NDJSON response body，每行 JSON 由 `parseAgentRunEvent()` 过滤为类型化事件，见 `frontend/lib/api.ts`。
- 请求字段：`conversation_id`、`message`、`model`、`selected_skills`、`context_snapshot`，类型为 `AgentRunStreamRequest`，见 `frontend/types/api.ts`。
- 技能范围：`AgentSkill` 当前只有 `rewrite`；`selected_skills` 在 `frontend/stores/chatStore.ts` 中归一化为最多一个技能，消息发出后清空。
- 上传文件 rewrite：`frontend/components/chat/ChatPanel.tsx` 使用 `uploadFile(file, 'rewrite_source')`，再把 `uploaded_files` 与 `rewrite_context` 放入 `context_snapshot`。
- 事件类型：`run_started`、`thinking_stage`、`tool_call`、`task_accepted`、`needs_input`、`done`、`error`，类型位于 `frontend/types/api.ts`。
- 任务边界：`task_accepted` 进入 task summary、SSE、取消和下载链路；`needs_input` 与非任务 `done` 只更新聊天消息，不创建后台任务。

**任务 SSE：**
- 服务用途：生成、rewrite、补充批注任务的实时日志、进度、LLM 文本、agent step、终态和 heartbeat。
- 入口：`getTaskStreamUrl()`、`createSSEConnection()`、`useSSE()`、`useChatSSE()`，见 `frontend/lib/api.ts`、`frontend/lib/sse.ts`、`frontend/hooks/useSSE.ts`、`frontend/hooks/useChatSSE.ts`。
- 运行时：`frontend/lib/sse.ts` 包装浏览器 `EventSource`，支持 `lastEventId` query 参数、事件去重、heartbeat timeout 和重连。
- 命名事件：`connected`、`log`、`llm`、`progress`、`agent_step`、`status`、`error`、`done`、`heartbeat`。
- 状态映射：`frontend/hooks/useChatSSE.ts` 将 SSE 事件写入 `frontend/stores/chatStreamStore.ts` 和 `frontend/stores/chatStore.ts`，并在终态后清理 `frontend/stores/chatTaskSessionStore.ts`。

**模板候选：**
- 服务用途：获取可选模板候选、选择候选、通过后端代理下载候选文件。
- UI：`frontend/components/forms/TemplateCandidateDialog.tsx`。
- 表单接入：`frontend/components/forms/TenderFormShared.tsx`。
- API 辅助函数：`fetchTemplateCandidates()`、`selectTemplateCandidate()`、`getTemplateCandidateDownloadUrl()`，见 `frontend/lib/api.ts`。
- 缓存：`frontend/components/forms/TenderFormShared.tsx` 使用 `buildTemplateCandidateCacheKey(tenderNo, projectName)` 在组件状态内缓存候选与 ranking。
- 约束：前端只消费后端返回的候选、ranking、`selectable` 和 `blocked_reason`；不得直接访问外部模板候选 URL。

## 数据存储

**数据库：**
- 前端未直接连接数据库。
- 招标数据、任务数据、上传文件、模板候选和会话心跳都通过 `frontend/lib/api.ts` 或相对 `/api/download/...` 链路访问后端。

**浏览器存储：**
- `chat-storage` - `frontend/stores/chatStore.ts` 使用 Zustand persist + `sessionStorage` 保存会话、草稿、任务摘要和未读结果。
- `chat-task-session-storage` - `frontend/stores/chatTaskSessionStore.ts` 使用 Zustand persist + `sessionStorage` 保存 task id 与 last event id。
- `tender-history-storage` - `frontend/stores/historyStore.ts` 使用 Zustand persist + `sessionStorage` 保存最近历史条目。
- `tender-app-storage` - `frontend/stores/useAppStore.ts` 使用 Zustand persist，未显式指定 storage adapter；只 partialize `sidebarOpen`。
- `frontend/stores/chatStreamStore.ts` 是内存 store，不持久化完整 stream payload。

**文件存储：**
- 浏览器不直接访问本地文件系统、对象存储或云盘。
- 上传经 `uploadFile()` / `uploadFiles()` 发送 `FormData` 到 `/api/upload` 或 `/api/upload/multiple`，见 `frontend/lib/api.ts`。
- 生成产物下载经 `downloadFile()` / `getDownloadUrl()` 或相对 `/api/download/...` 链接访问后端下载代理。
- 模板候选下载经 `/api/template-candidates/download`，见 `frontend/lib/api.ts`。

**缓存：**
- 模板候选组件状态缓存位于 `frontend/components/forms/TenderFormShared.tsx`。
- 生产静态资源 header 位于 `frontend/next.config.ts`：`/_next/static/:path*` 使用 immutable cache，其他路径使用 `no-store`。

## 认证与身份

**认证提供方：**
- 未检测到登录页、认证 provider、JWT 注入、OAuth SDK 或权限 UI。
- `frontend/lib/api.ts` 不设置 `Authorization` header。

**会话身份：**
- 前端会话 identity 是浏览器本地 conversation id、task id、招标类型、招标编号和 `gngk` 子类型组合，不是安全身份。
- `gngk` 后端 form type 分派依赖 `tender_lx + fund_lx + ifzgcg`，共享 helper 位于 `frontend/lib/gngkFormType.ts`。
- URL canonical 化和会话恢复由 `frontend/utils/tenderTypeMapper.ts`、`frontend/hooks/useUrlParams.ts`、`frontend/stores/chatStore.ts` 和 `frontend/app/tender/page.tsx` 协作。

## 监控与可观测性

**错误追踪：**
- 未检测到 Sentry、Datadog、OpenTelemetry、PostHog、Google Analytics、Firebase 或其他前端监控 SDK。

**日志：**
- 用户可见任务日志、正文、agent step 和下载卡由 `frontend/components/chat/TaskLogMessage.tsx`、`frontend/components/chat/TaskContentMessage.tsx`、`frontend/components/chat/AgentThinkingMessage.tsx`、`frontend/components/chat/TaskDownloadMessage.tsx` 展示。
- 排障日志使用 `console.log` / `console.warn` / `console.error`，主要见 `frontend/lib/sse.ts`、`frontend/components/chat/ChatPanel.tsx`、`frontend/components/chat/FormPanel.tsx`。
- E2E 证据由 Playwright 失败截图、视频和 trace 支持，配置见 `frontend/playwright.config.ts`。

## CI/CD 与部署

**托管：**
- `frontend/` 顶层未检测到 `vercel.json`、`Dockerfile`、`docker-compose*.yml` 或 `netlify.toml`。
- Next.js dev/start 端口固定为 `8502`，见 `frontend/package.json`。

**CI 流水线：**
- 仓库级 `.github/workflows/` 未检测到。
- `frontend/playwright.config.ts` 在 E2E 运行时可启动 `npm run dev -- --webpack`；`CI` 环境下启用 forbidOnly、retry 和单 worker。

## 环境配置

**必需环境变量：**
- 无必须前端密钥变量。
- `NEXT_PUBLIC_API_URL` 是可选配置；配置后影响浏览器 API base URL、Next rewrite 目标和开发期 allowed origins。

**测试环境变量：**
- `CI` - 影响 Playwright forbidOnly、retries、workers 和 server reuse，见 `frontend/playwright.config.ts`。
- `PLAYWRIGHT_USE_SYSTEM_CHROME` - 非 CI 环境下控制是否使用系统 Chrome channel，见 `frontend/playwright.config.ts`。

**密钥位置：**
- `frontend/.env.local` 文件存在，作为本地环境配置；内容不读取。
- `frontend/.env.local.example` 文件存在，作为示例环境文件；内容不读取。
- `frontend/.npmrc` 文件存在；内容不读取。

## Webhook 与回调

**入站：**
- 前端没有自定义后端回调 endpoint；`frontend/app/api/` 未检测到。

**出站：**
- JSON / upload / binary download / NDJSON：由 `frontend/lib/api.ts` 发起。
- 任务 SSE：由 `frontend/lib/sse.ts` 发起 `EventSource` 连接。
- 历史下载链接：`frontend/components/layout/Sidebar.tsx` 使用相对 `/api/download/...` 链接。
- 裸 `fetch(` 在产品源码中集中于 `frontend/lib/api.ts`；组件层不直接裸 `fetch` 调用后端。

## 集成修改规则

- 新后端接口必须同步 `frontend/types/api.ts`、`frontend/lib/api.ts` 和相关测试。
- 新 SSE 事件必须同步后端事件模型/发送方、`frontend/types/api.ts` union 类型、`frontend/lib/sse.ts` named event 注册、`frontend/hooks/useChatSSE.ts` 映射和 hook/store 测试。
- 新 agent run NDJSON 事件必须同步 `frontend/types/api.ts`、`frontend/lib/api.ts` 的 `parseAgentRunEvent()` 和 `frontend/components/chat/ChatPanel.tsx` 事件处理。
- `generation_style`、`generation_mode`、`comment_generation_mode` 和 `style_writeback_mode` 是 generate-only 字段，不得进入 rewrite 请求模型、skill state 或 prompt surface。
- 上传文件 rewrite 使用 `fileType: 'rewrite_source'`，并通过 `uploaded_files` + `rewrite_context` 向 agent run 提供上下文；不要恢复旧 edit 入口或创建第二套任务链路。
- `gngk` 提交和上传文件 rewrite 都必须走 `frontend/lib/gngkFormType.ts` 分派到后端 form type。
- 模板候选外部 URL 必须继续通过后端 API 代理，不得从组件直接请求。

---

*前端集成分析：2026-06-16*
