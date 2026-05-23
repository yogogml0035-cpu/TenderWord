# 前端集成事实地图

**分析日期：** 2026-05-23

**范围：** `frontend/` 对后端 API、浏览器运行时、存储、测试工具和本地启动环境的集成边界。

## 后端 API

- 前端后端调用统一经由 `frontend/lib/api.ts`。
- API base URL 由 `frontend/lib/apiBaseUrl.ts` 解析。
- Next dev rewrites 在 `frontend/next.config.ts` 中把 `/api/:path*` 代理到后端。
- JSON 请求走 `request<T>()` / `api.get/post/put/delete`。
- 上传、下载、NDJSON、SSE URL 使用 `frontend/lib/api.ts` 的专用 helper。

关键 helper 包括：

- `createGenerateTask()`
- `createEditTask()`
- `getTaskStatus()`
- `getTaskList()`
- `cancelTask()`
- `sendTaskHeartbeat()`
- `streamUserMessage()`
- `uploadFile()` / `uploadFiles()`
- `downloadFile()` / `getDownloadUrl()`
- `fetchTemplateCandidates()`
- `selectTemplateCandidate()`
- `getTemplateCandidateDownloadUrl()`
- `sendConversationHeartbeat()`

## SSE 与 NDJSON

- 任务 SSE URL 由 `getTaskStreamUrl()` 构造。
- `frontend/lib/sse.ts` 包装 `EventSource`，支持 heartbeat timeout、last event id、去重和重连。
- `frontend/hooks/useChatSSE.ts` 把后端 SSE 事件映射到 `chatStreamStore` 与 `chatStore`。
- 用户流式聊天/rewrite 通过 `streamUserMessage()` 解析 NDJSON。

## 浏览器存储

- `chatStore`、`chatTaskSessionStore`、`historyStore`、`useAppStore` 使用 `sessionStorage`。
- `chatStreamStore` 是内存态，不持久化完整 stream payload。
- 浏览器地址栏必须与当前会话身份同步，canonical URL 走 `tenderTypeMapper`。

## 文件与下载

- 浏览器不直接访问本地文件系统。
- 文件上传通过 `FormData` 发往后端 upload API。
- 下载通过后端 download API 或模板候选代理下载 URL。
- 模板候选外部文件 URL 不应在前端直接请求。

## 模板候选

- UI：`frontend/components/forms/TemplateCandidateDialog.tsx`。
- 表单回填：`frontend/components/forms/TenderFormShared.tsx`。
- 类型：`frontend/types/api.ts` 的 `TemplateCandidate*`。
- 前端只展示后端返回的候选、ranking summary、可选状态和 blocked reason。
- 年份和白名单等安全规则由后端执行，前端只按后端结果禁用选择。

## 认证与身份

- 当前前端没有稳定登录入口或 auth header。
- 会话身份是浏览器本地 conversation identity，不是用户认证身份。
- 如果后续增加认证，需要同步 `frontend/lib/api.ts`、错误处理、路由守卫、测试和 `INTERFACES.md`。

## 监控与日志

- 用户可见任务日志通过 `TaskLogMessage` 渲染。
- 前端排障日志主要是 `console.error` / `console.warn`。
- 当前未确认外部前端监控或 APM。

## CI/CD 与 E2E

- Playwright config 会自动启动 `npm run dev`，baseURL 为 `http://localhost:8502`。
- E2E 主要用于不依赖真实 Word COM 的浏览器契约；真实生成链路需要后端和 Word COM 环境。
- 当前未确认稳定 CI workflow 文件。

## 环境配置

- `.env.local` 用于前端本地环境，示例为 `frontend/.env.local.example`。
- `NEXT_PUBLIC_API_URL` 可配置后端地址；若缺省，base URL resolver 会按当前浏览器位置推导。
- 文档不得记录私有 URL、token 或客户样例内容。

## 集成风险

- API shape 变化必须同步 `frontend/types/api.ts`、`frontend/lib/api.ts`、后端模型和测试。
- SSE 事件变化必须同步事件类型、解析、store 映射和测试。
- gngk form type 分派必须同步 `formDataConverter.ts` 与 `ChatPanel.tsx`。
- URL 参数变化必须同步 `tenderTypeMapper.ts`、store、页面启动和 E2E。
- 模板候选改动不能绕过后端代理。

---

*前端集成分析：2026-05-23*
