# 前端集成事实地图

**分析日期：** 2026-06-08

**范围：** 仅 `frontend/` 对后端 API、浏览器运行时、本地存储、文件上传下载、SSE/NDJSON、测试工具和开发服务器的集成边界。未读取 `.env.local`、`.env.local.example`、`.npmrc` 或任何真实凭据。

## API 与外部服务

**TenderWord 后端 API：**
- 服务用途：招标数据查询、模板候选、文件上传、生成任务、补充批注任务、任务状态、心跳、下载、agent run。
- SDK/Client：无第三方 SDK；统一使用 `fetch` 封装在 `frontend/lib/api.ts`。
- Auth：未检测到稳定认证 header 或登录凭据；当前 API helper 不注入 auth。
- Base URL：由 `frontend/lib/apiBaseUrl.ts` 解析 `NEXT_PUBLIC_API_URL`，无配置时使用本机后端默认值或按当前浏览器 hostname 推导。
- 开发代理：`frontend/next.config.ts` 将 `/api/:path*` rewrite 到后端 API base URL。

**Agent Run NDJSON：**
- 服务用途：聊天输入先经任务上下文助手判定 rewrite 能力、需求补充和任务创建。
- 入口：`streamAgentRun()` 调用 `/api/agent/runs/stream`，见 `frontend/lib/api.ts`。
- 事件类型：`run_started`、`thinking_stage`、`tool_call`、`task_accepted`、`needs_input`、`done`、`error`，类型位于 `frontend/types/api.ts`。
- 后台任务边界：只有 `task_accepted` 进入 task summary、SSE、取消和下载链路；`needs_input` 与非任务 `done` 只更新聊天消息或思考卡。

**任务 SSE：**
- 服务用途：生成、rewrite、补充批注任务的实时日志、进度、LLM 文本、agent step、终态。
- 入口：`getTaskStreamUrl()` 和 `useChatSSE()`，见 `frontend/lib/api.ts`、`frontend/hooks/useChatSSE.ts`。
- Runtime：`frontend/lib/sse.ts` 包装浏览器 `EventSource`，支持 heartbeat timeout、`lastEventId`、事件去重和重连。
- Named events：底层显式注册 `connected`、`log`、`llm`、`progress`、`agent_step`、`status`、`error`、`done`、`heartbeat`。

**模板候选：**
- 服务用途：获取可选模板候选、选择候选、通过后端代理下载候选文件。
- UI：`frontend/components/forms/TemplateCandidateDialog.tsx`。
- 表单接入：`frontend/components/forms/TenderFormShared.tsx`。
- API helper：`fetchTemplateCandidates()`、`selectTemplateCandidate()`、`getTemplateCandidateDownloadUrl()`，见 `frontend/lib/api.ts`。
- 约束：前端只展示后端返回的候选、ranking、`selectable` 和 `blocked_reason`；不得直接访问外部模板候选 URL。

## 数据存储

**浏览器本地状态：**
- `chat-storage` - `frontend/stores/chatStore.ts` 使用 Zustand persist + `sessionStorage` 保存会话、草稿、任务摘要、任务消息映射和未读结果。
- `chat-task-session-storage` - `frontend/stores/chatTaskSessionStore.ts` 使用 `sessionStorage` 保存 task id 与 last event id。
- `tender-history-storage` - `frontend/stores/historyStore.ts` 使用 `sessionStorage` 保存历史条目。
- `tender-app-storage` - `frontend/stores/useAppStore.ts` 持久化部分 UI 状态；当前文件使用 Zustand persist，但未显式设置 `sessionStorage` adapter，按 Zustand 默认存储行为处理。

**Transient runtime：**
- `frontend/stores/chatStreamStore.ts` 是内存 store，不持久化完整 stream payload。
- 运行中的 `agent_step` 快照只留在 `chatStreamStore.agentSteps`；完成态再由 `chatStore.upsertAgentStepMessage()` 持久化为会话消息。

**数据库：**
- 前端未直接连接数据库。
- 后端任务、文件和会话心跳数据通过 API 访问；前端文档不记录后端内部连接信息。

**File Storage：**
- 浏览器不直接访问本地文件系统。
- 上传经 `uploadFile()` / `uploadFiles()` 发送 `FormData` 到 `/api/upload` 或 `/api/upload/multiple`。
- 下载经 `downloadFile()` / `getDownloadUrl()` 访问 `/api/download/{file_path}`，模板候选下载经 `/api/template-candidates/download`。

**Caching：**
- 模板候选在 `TenderFormShared` 内按招标编号和项目名缓存当前组件生命周期结果。
- Next 生产 header 对静态资源使用 immutable cache，对其他路径 no-store，见 `frontend/next.config.ts`。

## 认证与身份

**认证提供方：**
- 未检测到登录页、认证 provider、JWT 注入或权限 UI。

**前端会话身份：**
- 会话 identity 是浏览器本地 conversation id 和 `TenderType`/招标编号/`gngk` 子类型组合，不是安全身份。
- `gngk` 会话匹配使用 `tenderType + tenderno + tender_lx + fund_lx`，实现见 `frontend/app/tender/page.tsx`、`frontend/stores/chatStore.ts`。

## 监控与可观测性

**错误追踪：**
- 未检测到 Sentry、Datadog、OpenTelemetry 等前端监控 SDK。

**Logs：**
- 用户可见任务日志通过 `TaskLogMessage`、`TaskContentMessage`、`TaskDownloadMessage` 展示，组件位于 `frontend/components/chat/`。
- 排障日志使用 `console.error` / `console.log`，主要见 `frontend/lib/sse.ts`、`frontend/components/chat/ChatPanel.tsx`、`frontend/components/chat/FormPanel.tsx`。
- E2E 中会收集浏览器 console 作为验证证据，见 `frontend/e2e/test_comment_supplement.spec.ts`、`frontend/e2e/test_generation_mode_agent.spec.ts`。

## CI/CD 与部署

**Hosting：**
- `frontend/` 内未检测到 Vercel、Docker、GitHub Actions 等明确部署配置。
- Next.js dev/start 端口固定为 `8502`，见 `frontend/package.json`。

**CI Pipeline：**
- 当前 `frontend/` 范围未检测到 CI workflow 文件。
- Playwright config 在本地或 CI 下可自动启动 `npm run dev -- --webpack`，见 `frontend/playwright.config.ts`。

## 环境配置

**必要环境变量：**
- `NEXT_PUBLIC_API_URL` - 可选；配置后影响浏览器 API base URL、Next rewrite 目标和开发期 allowed origins。

**凭据文件位置：**
- `frontend/.env.local` 文件存在，作为本地环境配置；不得读取内容或写入文档。
- `frontend/.env.local.example` 文件存在，作为示例环境文件；本次未读取内容。
- `frontend/.npmrc` 文件存在；本次未读取内容。

## Webhook 与回调

**Incoming：**
- 前端没有自定义后端回调 endpoint；Next App Router 中未检测到 `frontend/app/api/` route。

**Outgoing：**
- JSON / upload / download：由 `frontend/lib/api.ts` 发起。
- SSE：由 `frontend/lib/sse.ts` 发起 `EventSource` 连接。
- NDJSON：由 `streamNdjson()` 发起 fetch stream。

## 集成修改规则

- 新后端接口必须同步 `frontend/types/api.ts` 和 `frontend/lib/api.ts`，并补 `frontend/__tests__/unit/lib/test_api.test.ts`。
- 新 SSE 事件必须同步 `frontend/types/api.ts` 的事件 union、`frontend/lib/sse.ts` named event 注册、`frontend/hooks/useChatSSE.ts` 映射和相关 hook/store 测试。
- `generation_mode`、`comment_generation_mode`、`style_writeback_mode` 是初次生成字段；rewrite 的 agent run 上下文不得透传这些字段。
- 上传文件 rewrite 使用 `fileType: 'rewrite_source'` 和 `rewrite_context`；不要恢复旧 edit 入口或新建第二套任务链路。
- 模板候选外部 URL 必须继续通过后端 API 代理，不得从组件直接请求。

---

*前端集成分析：2026-06-08*
