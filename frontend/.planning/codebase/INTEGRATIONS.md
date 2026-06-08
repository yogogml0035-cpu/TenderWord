# 前端外部集成事实地图

**分析日期：** 2026-06-08

**范围：** 仅 `frontend/` 对后端 API、浏览器运行时、本地存储、文件上传下载、SSE/NDJSON、测试工具和开发服务器的集成边界。未读取 `frontend/.env.local`、`frontend/.env.local.example`、`frontend/.npmrc` 或任何真实凭据文件内容。

## API 与外部服务

**TenderWord 后端 API：**
- 服务用途：招标数据查询、模板候选、文件上传、生成任务、补充批注任务、任务状态、任务取消、心跳、下载和 agent run。
- SDK/Client：无第三方 SDK；统一使用 `fetch` 封装在 `frontend/lib/api.ts`。
- 认证：未检测到稳定认证 header、JWT 注入、登录 provider 或权限 SDK；`frontend/lib/api.ts` 不注入 auth。
- 基础 URL：`frontend/lib/apiBaseUrl.ts` 解析 `NEXT_PUBLIC_API_URL`，无配置时使用 `http://localhost:8000` 或按浏览器 hostname 推导 `:8000`。
- 开发代理：`frontend/next.config.ts` 将 `/api/:path*` rewrite 到后端 API base URL，并把 `NEXT_PUBLIC_API_URL` 候选 hostname 纳入 `allowedDevOrigins`。

**后端 API endpoints：**
- 招标查询：`GET /api/tender/{tender_no}`，helper 为 `fetchTenderDataWithType()` / `fetchTenderData()`，见 `frontend/lib/api.ts`、`frontend/lib/tenderFetch.ts`。
- 模板候选：`GET /api/template-candidates`、`POST /api/template-candidates/select`、`GET /api/template-candidates/download`，helper 位于 `frontend/lib/api.ts`。
- 文件上传：`POST /api/upload`、`POST /api/upload/multiple`，使用 `FormData`，见 `frontend/lib/api.ts`、`frontend/components/forms/FileUploader.tsx`。
- 任务创建：`POST /api/generate`、`POST /api/comment-supplement`，见 `frontend/lib/api.ts`。
- 任务管理：`GET /api/tasks/{taskId}`、`DELETE /api/tasks/{taskId}`、`POST /api/tasks/{taskId}/heartbeat`、`GET /api/tasks`，见 `frontend/lib/api.ts`。
- 会话心跳：`POST /api/conversations/{conversationId}/heartbeat`，见 `frontend/lib/api.ts`。
- 文件下载：`GET /api/download/{file_path}`，helper 为 `downloadFile()` / `getDownloadUrl()`，见 `frontend/lib/api.ts`。

**前置智能体 NDJSON：**
- 服务用途：聊天输入先经任务上下文助手判定 rewrite 能力、需求补充和任务创建。
- 入口：`streamAgentRun()` 调用 `/api/agent/runs/stream`，见 `frontend/lib/api.ts`、`frontend/components/chat/ChatPanel.tsx`。
- 事件类型：`run_started`、`thinking_stage`、`tool_call`、`task_accepted`、`needs_input`、`done`、`error`，类型位于 `frontend/types/api.ts`。
- 任务边界：`task_accepted` 进入 task summary、SSE、取消和下载链路；`needs_input` 与非任务 `done` 更新聊天消息或思考卡。

**任务 SSE：**
- 服务用途：生成、rewrite、补充批注任务的实时日志、进度、LLM 文本、agent step、终态和 heartbeat。
- 入口：`getTaskStreamUrl()`、`createSSEConnection()`、`useSSE()`、`useChatSSE()`，见 `frontend/lib/api.ts`、`frontend/lib/sse.ts`、`frontend/hooks/useSSE.ts`、`frontend/hooks/useChatSSE.ts`。
- 运行时：`frontend/lib/sse.ts` 包装浏览器 `EventSource`，支持 heartbeat timeout、`lastEventId`、事件去重和重连。
- 命名事件：`connected`、`log`、`llm`、`progress`、`agent_step`、`status`、`error`、`done`、`heartbeat`。

**模板候选：**
- 服务用途：获取可选模板候选、选择候选、通过后端代理下载候选文件。
- UI：`frontend/components/forms/TemplateCandidateDialog.tsx`。
- 表单接入：`frontend/components/forms/TenderFormShared.tsx`。
- API 辅助函数：`fetchTemplateCandidates()`、`selectTemplateCandidate()`、`getTemplateCandidateDownloadUrl()`，见 `frontend/lib/api.ts`。
- 约束：前端只消费后端返回的候选、ranking、`selectable` 和 `blocked_reason`；不得直接访问外部模板候选 URL。

## 数据存储

**数据库：**
- 前端未直接连接数据库。
- 后端任务、文件、模板候选和会话心跳数据都通过 `frontend/lib/api.ts` 访问。

**浏览器存储：**
- `chat-storage` - `frontend/stores/chatStore.ts` 使用 Zustand persist + `sessionStorage` 保存会话、草稿、任务摘要、任务消息映射和未读结果。
- `chat-task-session-storage` - `frontend/stores/chatTaskSessionStore.ts` 使用 Zustand persist + `sessionStorage` 保存 task id 与 last event id。
- `tender-history-storage` - `frontend/stores/historyStore.ts` 使用 Zustand persist + `sessionStorage` 保存最近历史条目。
- `tender-app-storage` - `frontend/stores/useAppStore.ts` 使用 Zustand persist 保存 sidebar 状态；该文件未显式设置 `sessionStorage` adapter，按 Zustand 默认 storage 行为处理。

**临时运行态：**
- `frontend/stores/chatStreamStore.ts` 是内存 store，不持久化完整 stream payload。
- 运行中的 `agent_step` 快照位于 `chatStreamStore.agentSteps`；完成展示由 `frontend/stores/chatStore.ts` 写入会话消息。

**文件存储：**
- 浏览器不直接访问本地文件系统或云存储。
- 上传经 `uploadFile()` / `uploadFiles()` 发送 `FormData` 到 `/api/upload` 或 `/api/upload/multiple`，见 `frontend/lib/api.ts`。
- 下载经 `downloadFile()` / `getDownloadUrl()` 访问 `/api/download/{file_path}`；模板候选下载经 `/api/template-candidates/download`，见 `frontend/lib/api.ts`。

**缓存：**
- `frontend/components/forms/TenderFormShared.tsx` 在组件生命周期内按招标编号和项目名缓存模板候选结果。
- `frontend/next.config.ts` 对生产静态资源使用 immutable cache，对其他路径使用 `no-store`。

## 认证与身份

**认证提供方：**
- 未检测到登录页、认证 provider、JWT 注入、OAuth SDK 或权限 UI。
- 前端 API helper 不设置 `Authorization` header，见 `frontend/lib/api.ts`。

**会话身份：**
- 前端会话 identity 是浏览器本地 conversation id、任务 id、招标类型、招标编号和 `gngk` 子类型组合，不是安全身份。
- `gngk` 类型分派依赖 `tender_lx + fund_lx + ifzgcg`，共享 helper 位于 `frontend/lib/gngkFormType.ts`，根级约束见 `docs/frontend.md`、`docs/interfaces-runtime.md`。

## 监控与可观测性

**错误追踪：**
- 未检测到 Sentry、Datadog、OpenTelemetry、PostHog、Google Analytics 或其他前端监控 SDK。

**日志：**
- 用户可见任务日志、正文和下载卡由 `frontend/components/chat/TaskLogMessage.tsx`、`frontend/components/chat/TaskContentMessage.tsx`、`frontend/components/chat/TaskDownloadMessage.tsx` 展示。
- 排障日志使用 `console.log` / `console.warn` / `console.error`，主要见 `frontend/lib/sse.ts`、`frontend/components/chat/ChatPanel.tsx`、`frontend/components/chat/FormPanel.tsx`。
- E2E 证据由 Playwright 失败截图、视频和 trace 支持，配置见 `frontend/playwright.config.ts`。

## CI/CD 与部署

**部署托管：**
- `frontend/` 内未检测到 Vercel、Docker、Netlify 等明确前端部署配置。
- Next.js dev/start 端口固定为 `8502`，见 `frontend/package.json`。

**CI 流水线：**
- 当前仓库未检测到 `.github/workflows/` workflow 文件。
- `frontend/playwright.config.ts` 在测试运行时可启动 `npm run dev -- --webpack`，`CI` 环境下启用 forbidOnly、retry 和单 worker。

## 环境配置

**必需环境变量：**
- `NEXT_PUBLIC_API_URL` - 可选；配置后影响浏览器 API base URL、Next rewrite 目标和开发期 allowed origins。

**测试环境变量：**
- `CI` - 影响 Playwright forbidOnly、retries、workers 和 server reuse，见 `frontend/playwright.config.ts`。
- `PLAYWRIGHT_USE_SYSTEM_CHROME` - 非 CI 环境下控制是否使用系统 Chrome channel，见 `frontend/playwright.config.ts`。

**密钥位置：**
- `frontend/.env.local` 文件存在，作为本地环境配置；不得读取内容或写入文档。
- `frontend/.env.local.example` 文件存在，作为示例环境文件；本次未读取内容。
- `frontend/.npmrc` 文件存在；本次未读取内容。

## Webhook 与回调

**入站：**
- 前端没有自定义后端回调 endpoint；未检测到 `frontend/app/api/` route。

**出站：**
- JSON / upload / download：由 `frontend/lib/api.ts` 发起。
- SSE：由 `frontend/lib/sse.ts` 发起 `EventSource` 连接。
- NDJSON：由 `streamNdjson()` 发起 fetch stream，见 `frontend/lib/api.ts`。
- 裸 `fetch(` 只出现在 `frontend/lib/api.ts`；组件层不直接调用后端 fetch。

## 集成修改规则

- 新后端接口必须同步 `frontend/types/api.ts`、`frontend/lib/api.ts` 和相关测试。
- 新 SSE 事件必须同步 `frontend/types/api.ts` 的事件类型、`frontend/lib/sse.ts` named event 注册、`frontend/hooks/useChatSSE.ts` 映射和 hook/store 测试。
- `generation_style`、`generation_mode`、`comment_generation_mode` 和 `style_writeback_mode` 是 generate-only 字段，不得进入 rewrite 请求模型、skill state 或 prompt surface；根级规则见 `docs/frontend.md`、`docs/interfaces-runtime.md`。
- 上传文件 rewrite 使用 `fileType: 'rewrite_source'` 和 `rewrite_context`；不要恢复旧 edit 入口或新建第二套任务链路。
- 模板候选外部 URL 必须继续通过后端 API 代理，不得从组件直接请求。

---

*前端集成分析：2026-06-08*
