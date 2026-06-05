<!-- refreshed: 2026-06-05 -->
# 前端架构事实地图

**分析日期：** 2026-06-05

**范围：** `frontend/`，并在启动、验证和 API 边界上参考根级 `AGENTS.md`、`README.md` 与 `scripts/`。

## 系统总览

```text
Next.js App Router
  -> / 与 /tender 页面
  -> 三栏工作台：类型侧栏 / 表单 / 聊天任务
  -> Zustand sessionStorage 持久化
  -> 统一 API client + SSE runtime
  -> FastAPI /api
```

前端是 TenderWord 的浏览器工作台。它负责招标类型选择、URL 深链、会话和草稿、文件上传、模板候选弹窗、生成任务创建、智能体生成方式选择、agent run 任务上下文助手、rewrite/补充批注任务创建、SSE 进度与智能体过程卡展示和下载入口。

## 主要层次

| 层 | 职责 | 关键路径 |
| --- | --- | --- |
| 路由层 | App Router 页面边界、工作台组合、URL 参数接入 | `frontend/app/` |
| 工作台 UI | 类型侧栏、表单面板、聊天面板、消息列表、任务消息 | `frontend/components/chat/` |
| 表单层 | 各招标类型表单、共享字段、上传、模板候选、锚点、生成风格 | `frontend/components/forms/` |
| 状态层 | 会话、草稿、任务摘要、stream runtime、历史、侧栏状态 | `frontend/stores/` |
| API / SSE 层 | JSON、上传、下载、NDJSON、SSE URL、EventSource wrapper、任务心跳 | `frontend/lib/`, `frontend/hooks/` |
| 类型与映射层 | 前端 TenderType、API 类型、聊天类型、URL canonical 化 | `frontend/types/`, `frontend/utils/` |
| 测试层 | Jest 单元/集成测试与 Playwright E2E | `frontend/__tests__/`, `frontend/e2e/` |

## 关键运行链路

### `/tender` 深链与会话启动

1. `frontend/hooks/useUrlParams.ts` 从 URL 解析 `tender_lx`、`purchase_method`、`fund_lx`、`tenderno`。
2. `frontend/utils/tenderTypeMapper.ts` 只用 `purchase_method` 判定前端 `TenderType`。
3. `frontend/app/tender/page.tsx` hydration 后选择或创建会话。
4. `gngk` 会话按 `tenderType + tenderno + tender_lx + fund_lx` 精确匹配。
5. URL 参数先写入 draft，再由 `TenderFormShared` 按 `draft > URL > default` 初始化。
6. `syncBrowserUrlToConversation()` 与 store 层 `syncUrlToCurrentConversation()` 维护 canonical URL。

### 生成任务

1. `TenderFormShared` 收集招标数据、模板文件、技术参数文件、模板候选结果、插入锚点、生成风格、生成方式、批注生成开关和样式回填模式。
2. `FormPanel` 通过 `tenderFormRegistry` 获取表单组件和转换器。
3. `frontend/lib/formDataConverter.ts` 把前端类型转换为后端 `GenerateRequest`，只发送 `file_paths.template` 与 `file_paths.tender_params`，并把缺省 `generation_mode` / `comment_generation_mode` 分别归一为 `workflow` / `on`。
4. `gngk` 由 `frontend/lib/gngkFormType.ts` 根据 `tender_lx + fund_lx + ifzgcg` 分派到四套后端 form type；工程类当前复用服务链路。
5. `frontend/lib/api.ts` 调用 `createGenerateTask()`。
6. `chatStore.startTask()` 创建任务消息组和 task summary。
7. `useCurrentConversationTaskStatus()` 查询队列/运行状态，`useChatSSE()` 连接任务 SSE。
8. SSE `log`、`llm`、`progress`、`agent_step`、`done`、`error` 进入 `chatStreamStore` 和任务消息；`agent_step` 完成事件持久化为 `agent-step` 过程卡，运行中快照留在临时 stream。
9. 任务完成后 `TaskDownloadMessage` 展示下载入口，下载仍经 `frontend/lib/api.ts`。

### Agent run、rewrite 与上传文件修改

- 右侧聊天使用 `streamAgentRun()` 调用 `/api/agent/runs/stream` 并解析 NDJSON agent run 事件。
- 当前可创建后台任务的 skill 是 `rewrite`；agent run 返回 `needs_input` 时只追加普通 AI 提示，不进入任务/SSE 链路。
- 上传待改 Word 文件使用 `uploadFile(file, 'rewrite_source')`，文件写入会话 draft 的 `rewrite_file`，并自动选择 rewrite skill。
- 上传文件 rewrite 的 `form_type` 在 `ChatPanel` 中按当前页面类型和 draft 调用 `resolveGngkFormType()`，必须与生成链路共用 `frontend/lib/gngkFormType.ts`。
- `selected_skills` 是一次性能力选择；发送后清空。存在 `rewrite_file` 时隐式选择 rewrite，只有 `task_accepted` 才进入后台任务/SSE/下载链路。
- `chat_input` 在消息受理时立即清空；中断恢复使用 `pending_rewrite_prompt` / `pending_rewrite_task_id`。

### 补充批注

- 初次生成完成后的下载卡可触发补充批注，入口在 `TaskDownloadMessage` 经 `MessageList` 回调到 `ChatPanel`。
- `ChatPanel` 调用 `createCommentSupplementTask()`，只提交当前会话 id、当前下载文件路径和模型。
- `comment_supplement` 任务复用任务状态、SSE 和下载消息；`comment_agent` 过程卡通过 `agent_step` 展示。
- rewrite 和补充批注任务自己的下载卡不显示再次补充批注动作，避免重复基于衍生副本创建任务。

### 模板候选

- `TenderFormShared` 打开 `TemplateCandidateDialog`。
- 候选列表、选择和下载 URL 都通过 `frontend/lib/api.ts` 的 `/api/template-candidates*` helper。
- 前端只展示后端返回的 `selectable` 与 `blocked_reason`，不直接请求外部候选接口或文件 URL。
- 选择成功后，后端返回的 clean draft / origin tender 文件写回表单 draft。

## 核心抽象

- `TenderType`：前端 UI 类型，仅有 `xjcg`、`gngk`、`gjgk`。
- `GenerateRequest` / `AgentRunStreamRequest`：前端镜像后端生成任务和 agent run payload，位于 `frontend/types/api.ts`。
- `ConversationFormDraft`：每个会话的表单、文件、锚点、`generation_mode`、聊天输入和 pending 恢复状态。
- `TaskMessageGroupIds`：一个 task id 对应 log/content/download 三类任务消息；智能体 `agent-step` 过程卡不纳入该三卡分组。
- `TaskKind`：任务类型包含 `generate`、`rewrite`、`comment_supplement`；补充批注复用任务消息组和独立 `agent-step` 过程卡。
- `chatStreamStore`：运行中任务的 transient logs、AI 文本、agent step 快照、进度、当前节点和 `lastEventId`。
- `buildCanonicalSearchParams()`：会话身份到浏览器 URL 的唯一构造入口。
- `tenderFormRegistry`：TenderType 到显示名、表单组件和 generate converter 的注册表。

## 架构约束

- 组件不直接裸写后端 `fetch`；统一通过 `frontend/lib/api.ts`。
- JSON 错误统一收敛为 `ApiError`，UI 至少展示 message。
- URL canonical 化统一走 `frontend/utils/tenderTypeMapper.ts` 和 store helper。
- 会话、草稿和任务恢复语义继续使用 `sessionStorage`。
- 从 `sessionStorage` 恢复 running task 前必须先查任务状态，404 / `TASK_NOT_FOUND` 收敛为本地中断态。
- 新增 SSE 事件类型必须同步前端 `types/api.ts`、`frontend/lib/sse.ts` named event、`useChatSSE` 和测试。
- 类型 identity 或 `form_type` 分派变化必须同步 `gngkFormType.ts`、`formDataConverter.ts`、`ChatPanel.tsx` 的上传文件 rewrite 上下文、`tenderTypeMapper.ts`、注册表、store 和测试。

## 反模式

- 在组件中直接调用后端 URL 或外部模板候选 URL。
- 手工 patch 单个 query 参数导致 canonical URL 与会话身份漂移。
- 绕过 `gngkFormType.ts`，只在表单转换器或只在 `ChatPanel` 上传文件 rewrite 上下文里修改 gngk form type 分派。
- 直接 append 任务消息，绕过 `chatStore` 的 task group 方法。
- 把 pending rewrite prompt 当成正常发送后的延迟清空机制。
- 让用户态 SSE UI 展示候选打分、淘汰阈值等排障细节。
- 把智能体运行中的高频 `agent_step` 快照直接写入持久化会话消息，导致 sessionStorage 与渲染压力放大。

## 错误处理

- `frontend/lib/api.ts` 将 HTTP / wrapped error 解析为 `ApiError`。
- 表单、模板弹窗、聊天面板和任务消息展示用户可读错误。
- `useTaskHeartbeat`、`useCurrentConversationTaskStatus` 和 `useChatSSE` 负责处理 terminal / missing task。
- 后端重启通过会话心跳检测，并由 `chatStore.handleBackendRestart()` 收敛本地 running task。
- 下载失败当前在 `ChatPanel` 中提示用户，并保留 console 错误用于排障。

## 横切关注点

- 样式：Tailwind 4，主题与全局样式在 `frontend/app/globals.css`。
- 图标：`lucide-react` 已作为依赖。
- 测试：Jest 使用 jsdom，Playwright baseURL 是 `http://localhost:8502`。
- 认证：当前前端未检测到稳定登录或 auth header。

---

*前端架构分析：2026-06-05*
