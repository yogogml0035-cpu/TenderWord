# 前端风险事实地图

**分析日期：** 2026-07-15

**范围：** `frontend/` 前端风险事实地图。必要时引用后端契约源文件来说明前后端同步边界；未读取 `frontend/.env.local`、`frontend/.npmrc` 或任何凭据文件内容。密钥、token、本机私有路径与完整客户原文不得写入本文档。

## 技术债

**核心文件职责密集：**
- 问题： 会话、任务、SSE、表单、聊天、API 和 rewrite 的关键行为集中在少数大文件中。当前实现体量较大的文件包括 `frontend/stores/chatStore.ts`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/components/chat/ChatPanel.tsx`、`frontend/lib/api.ts`、`frontend/hooks/useChatSSE.ts`、`frontend/components/chat/FormPanel.tsx`、`frontend/types/api.ts`。
- 相关文件： `frontend/stores/chatStore.ts`, `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/chat/ChatPanel.tsx`, `frontend/lib/api.ts`, `frontend/hooks/useChatSSE.ts`, `frontend/components/chat/FormPanel.tsx`, `frontend/types/api.ts`
- 影响： 小改动容易同时影响 URL 深链、会话草稿、任务消息、agent run、上传文件 rewrite、SSE 终态、下载卡和补充批注。
- 修复方向： 新增分支优先提取纯 helper 到 `frontend/lib/` 或 `frontend/utils/`，并补窄测试；不要在功能修复中做目录洗牌或大范围拆分。

**前后端 API shape 手写镜像（类型漂移高风险）：**
- 问题： 前端 `frontend/types/api.ts` 与 `frontend/lib/api.ts` 手写镜像后端 Pydantic 模型；后端 `backend/models/generate.py`、`backend/models/task.py`、`backend/models/agent_run.py`、`backend/models/sse.py` 是接口字段和枚举的源头。未检测到从后端 schema 自动生成前端类型的流程。
- 相关文件： `frontend/types/api.ts`, `frontend/lib/api.ts`, `frontend/lib/formDataConverter.ts`, `backend/models/generate.py`, `backend/models/task.py`, `backend/models/agent_run.py`, `backend/models/sse.py`
- 影响： 字段名、枚举、响应包装或 SSE/NDJSON event 只改一端会造成前端解析失败、后端 422、任务卡状态错误或下载卡缺失。`parseAgentRunEvent()` 对 `model`/`runtime`/event 名做白名单，未知 event 静默丢弃，漂移更难在 UI 上立刻暴露。
- 修复方向： 修改 `GenerateRequest`、`AgentRunStreamRequest`、`TaskKind`、`TaskStatus`、SSE `done/error/agent_step` 时同步前端类型、API client、转换器、UI 处理和测试；优先考虑生成式 contract 或跨端契约测试。

**直接 fetch 边界靠约定维护（已确认零残留）：**
- 问题： 本次审计 grep 确认 `frontend/app`、`frontend/components`、`frontend/hooks`、`frontend/stores` 目录下无裸 `fetch()` / `new EventSource()`；所有后端请求集中在 `frontend/lib/api.ts`（`request()`、`streamNdjson()`、`fetchTenderDataWithType()`、`downloadFile()`），SSE 连接集中在 `frontend/lib/sse.ts`。但代码中没有 lint 规则阻止后续在组件或 hooks 层新增裸调用。
- 相关文件： `frontend/lib/api.ts`, `frontend/lib/apiBaseUrl.ts`, `frontend/lib/sse.ts`, `frontend/eslint.config.mjs`
- 影响： 裸 `fetch()` 会绕过 `resolveApiBaseUrl()`、统一 `ApiError`、FormData 头处理、NDJSON parser、下载 URL 编码和测试 mock 入口；组件直接 `new EventSource()` 会绕过 SSE 重连/心跳/`seenEventIds` 去重。
- 修复方向： 新后端请求必须先加到 `frontend/lib/api.ts`，SSE 必须走 `createSSEConnection()`；必要时补 ESLint 规则约束组件层不写裸 `fetch()` 和 `EventSource()`。

**generate-only 字段边界容易被误用：**
- 问题： `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 只属于初次 generate 请求；上传文件 rewrite 的 agent run 请求只应携带 `selected_skills`、`uploaded_files`（经 `context_snapshot`）和 `rewrite_context`。`AgentRunStreamRequest` 不包含上述 generate-only 字段。
- 相关文件： `frontend/types/api.ts`, `frontend/lib/formDataConverter.ts`, `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/chat/ChatPanel.tsx`, `backend/models/generate.py`, `backend/models/agent_run.py`
- 影响： 把 generate-only 字段放进 rewrite 请求会污染 rewrite 语义，且后端 agent run 请求模型使用 `extra="forbid"`，多余字段会直接触发接口失败。
- 修复方向： generate 字段只改 `GenerateRequest` 链路；rewrite 能力只改 `AgentRunStreamRequest` 与 `AgentRunContextSnapshot` 明确存在的字段；不要把 generate-only 字段塞进 `context_snapshot` 或任何 skill state / prompt surface。

**`gngk` form type 分派是共享业务规则（双调用方一致，工程类仍为临时复用）：**
- 问题： `gngk` 在前端是 UI 类型，提交到后端需要由 `tender_lx + fund_lx + ifzgcg` 分派到具体 `form_type`。`frontend/lib/gngkFormType.ts` 的 `resolveGngkFormType()` 被两条链路共同调用：generate 在 `formDataConverter.ts`，rewrite 在 `ChatPanel.tsx` 的 `resolveRewriteFormType()`。工程类（`tender_lx === 1 || 2`）当前复用服务链路 `gngk_fw_*`。
- 相关文件： `frontend/lib/gngkFormType.ts`, `frontend/lib/formDataConverter.ts`, `frontend/components/chat/ChatPanel.tsx`, `frontend/utils/tenderTypeMapper.ts`, `backend/models/generate.py`
- 影响： 分派规则集中但带临时注释；若新增独立工程 graph 而只改一端调用方或只改后端，会导致同一页面 generate 与 rewrite 落到不同 graph，或 422。rewrite 在 `tender_lx`/`fund_lx` 不完整时返回 `null` 并省略 `form_type`，依赖 agent run `needs_input`，若 UI 草稿未同步 URL 子类型会放大缺参率。
- 修复方向： 分派规则只通过 `frontend/lib/gngkFormType.ts` 修改；改动时同步 `frontend/__tests__/unit/lib/test_form_data_converter.test.ts`、`frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx` 和后端对应 graph/service 测试。

**招标详情拉取逻辑已抽到独立 helper：**
- 问题： `frontend/lib/tenderFetch.ts` 封装了 `fetchTenderDataWithType()` 的调用、`gjgk` 项目编号归一化、draft 同步与 loading/error/warning 状态机。
- 相关文件： `frontend/lib/tenderFetch.ts`, `frontend/lib/api.ts`, `frontend/components/forms/TenderFormShared.tsx`
- 影响： 招标号前缀剥离、`project_number` 归一化和 warning 回填的真相源在 `tenderFetch.ts` + `api.ts`；若组件层重新内联会重复实现归一化和状态机。
- 修复方向： 新增招标详情相关 UI 行为优先复用 `syncTenderDataDraft()`、`createTenderFetchState()`、`resolveTenderFetchState()`。

**通用 SSE hook 与业务 SSE hook 并存：**
- 问题： `frontend/hooks/useSSE.ts` 提供通用 `useTaskProgress()`，实际聊天任务进度走 `frontend/hooks/useChatSSE.ts`，两者对事件 payload 和任务终态的处理粒度不同。
- 相关文件： `frontend/hooks/useSSE.ts`, `frontend/hooks/useChatSSE.ts`, `frontend/lib/sse.ts`, `frontend/stores/chatStreamStore.ts`, `frontend/stores/chatTaskSessionStore.ts`
- 影响： 新页面误接 `useTaskProgress()` 可能只得到通用进度，不会更新聊天消息组、下载卡、agent step 卡、session replay 和后端重启中断状态。
- 修复方向： 工作台任务优先复用 `useChatSSE()`；通用 hook 只用于不需要会话消息副作用的只读监控场景。

**未使用组件与历史 UI 债务：**
- 问题： 任务展示已拆成 `TaskLogMessage` / `TaskContentMessage` / `TaskDownloadMessage` / `AgentThinkingMessage`（由 `MessageList` 装配），但旧版双栏消息组件仍保留：
  - `frontend/components/chat/DualColumnMessage.tsx`：仅被单测 `test_dual_column_message.test.tsx` 引用，生产路径无 import。
  - `frontend/components/chat/NewChatPopup.tsx`：生产路径无 import。
  - `frontend/components/chat/Skeleton.tsx` 中的 `DualColumnSkeleton` / `PageSkeleton` / `MessageSkeleton` 等：无生产引用，与已废弃双栏布局耦合。
- 相关文件： `frontend/components/chat/DualColumnMessage.tsx`, `frontend/components/chat/NewChatPopup.tsx`, `frontend/components/chat/Skeleton.tsx`, `frontend/components/chat/MessageList.tsx`, `frontend/__tests__/unit/components/chat/test_dual_column_message.test.tsx`
- 影响： 新成员可能误改死代码；单测给人“仍在使用”的假象；与当前 task 消息模型漂移后更容易静默腐烂。
- 修复方向： 确认无回滚计划后删除死组件及对应单测，或在组件顶部标注废弃并禁止新功能依赖；不要在未确认前用 DualColumn 再接生产路径。

## 已知问题

**全局主色 hover token 重复定义：**
- Symptoms: `frontend/app/globals.css` 的 `:root` 中 `--primary-hover` 被定义两次（先 `#2563eb` 后 `#e04343`），后定义值覆盖前定义值；`--color-primary-hover` 继续引用被覆盖后的变量。
- 相关文件： `frontend/app/globals.css`
- Trigger: 使用 `var(--primary-hover)` 或 Tailwind theme token `--color-primary-hover` 的样式会拿到后定义值。
- Workaround: 修改视觉 token 前先清理重复变量，并检查引用 `--color-primary-hover` 的 UI。

**FileUploader 对拖拽文件类型只靠后端兜底：**
- Symptoms: `frontend/components/forms/FileUploader.tsx` 的 `validateFile()` 只校验大小，`accept` 主要影响文件选择器提示；拖拽路径没有前端扩展名或 MIME 校验。
- 相关文件： `frontend/components/forms/FileUploader.tsx`, `frontend/__tests__/unit/components/forms/test_file_uploader.test.tsx`, `backend/util/common_util/upload_storage.py`
- Trigger: 用户拖入非预期扩展名文件时，前端会发起上传请求，由后端返回类型错误。
- Workaround: 后端 `upload_storage` 继续作为最终文件类型和大小防线；前端如需更早提示，应在 `FileUploader` 增加扩展名校验并补单测。

**刷新后仅有 lastEventId 时强制全量 SSE 回放：**
- Symptoms: `useChatSSE` hydrate 时若 `chatStreamStore` 内存流为空（刷新后必然为空），会把连接的 `lastEventId` 置为 `null`，即使 `chat-task-session-storage` 里仍存有该 task 的 `lastEventId`。单测 `replays from the beginning after refresh when only lastEventId is persisted` 明确固化此行为。
- 相关文件： `frontend/hooks/useChatSSE.ts`, `frontend/stores/chatTaskSessionStore.ts`, `frontend/stores/chatStreamStore.ts`, `frontend/lib/sse.ts`
- Trigger: 用户刷新页面时任务仍在 `running`，sessionStorage 仅恢复消息摘要与 session `lastEventId`，内存 stream 丢失。
- Workaround: 当前依赖后端 SSE 从起点回放 + 客户端 `seenEventIds`；长任务会放大首屏回放成本。若要做“从 lastEventId 续订”，必须同时恢复或可重建 stream 快照，否则 UI 会缺日志/进度。

## 安全注意事项

**前端没有认证和授权边界：**
- 风险： `sessionStorage` 会话、conversation id、task id、task heartbeat 和草稿状态都不是身份凭据，不能用于权限判断。
- 相关文件： `frontend/stores/chatStore.ts`, `frontend/stores/chatTaskSessionStore.ts`, `frontend/stores/historyStore.ts`, `frontend/lib/api.ts`, `backend/api/tasks.py`, `backend/api/download.py`
- Current mitigation: `frontend/lib/api.ts` 未注入稳定 `Authorization` header；任务访问、文件下载、路径校验和权限判断必须由后端控制。
- Recommendations: 新增认证时同步 API client、路由守卫、错误处理、后端鉴权、E2E 和接口文档；不要在前端会话 id 上建立安全判断。

**模板候选 URL 必须继续由后端代理：**
- 风险： UI 直接请求外部候选文件 URL 会绕过后端白名单、年份规则、文件名清洗、下载代理和落盘逻辑。
- 相关文件： `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/forms/TemplateCandidateDialog.tsx`, `frontend/lib/api.ts`, `backend/api/template_candidates.py`
- Current mitigation: 前端通过 `fetchTemplateCandidates()`、`selectTemplateCandidate()`、`getTemplateCandidateDownloadUrl()` 访问 `/api/template-candidates*`，外部 `file_url` 仅作为后端 download 端点 query 参数透传，组件不直接 fetch 该 URL。
- Recommendations: 候选列表、选择和下载继续走项目内 API；不要在组件内直接请求后端返回的外部文件 URL。

**Agent run 可见信息必须保持最小化：**
- 风险： 前端发送 `message`、`uploaded_files`、`rewrite_context` 后，后端 agent run 日志和摘要若处理不当，可能暴露完整用户原文、私有路径、traceback 或下载路径。
- 相关文件： `frontend/components/chat/ChatPanel.tsx`, `frontend/types/api.ts`, `backend/models/agent_run.py`, `backend/agents/task_context_assistant/logging.py`, `backend/agents/task_context_assistant/tools.py`
- Current mitigation: `AgentRunContextSnapshot` 是受控上下文快照，后端请求模型 `extra="forbid"`。
- Recommendations: 新增 agent run event、tool summary 或前端日志时只记录白名单结构字段，不记录完整客户原文、真实密钥、完整本机路径、traceback 或下载 URL。

**环境和凭据文件存在但不能进入长期文档（密钥不入前端文档）：**
- 风险： `frontend/.env.local`、`frontend/.npmrc` 可能存在；这些文件可能包含本机配置或包管理认证信息。
- 相关文件： `frontend/.env.local`, `frontend/.env.local.example`, `frontend/.npmrc`
- Current mitigation: 本轮与历史审计只记录文件存在性，不读取、不摘录内容；`CONCERNS.md` / 其它 `.planning` 文档禁止写入真实 token、密钥或客户原文。
- Recommendations: 文档、测试夹具、E2E 截图说明和最终回复不得写入 `.env` 内容、token、私有凭据或真实客户原文；示例只使用占位符键名。

## 性能瓶颈

**浏览器会话和任务消息存储会随对话增长：**
- 问题： 会话、草稿、任务摘要、消息组和未读结果持久化到浏览器 `sessionStorage`；运行中 stream 快照另存在内存 store。
- 相关文件： `frontend/stores/chatStore.ts`, `frontend/stores/chatStreamStore.ts`, `frontend/stores/chatTaskSessionStore.ts`
- Cause: 前端以浏览器会话为恢复边界，没有服务端分页聊天历史。
- 改进路径： 扩展多会话或长任务前，先定义消息截断、任务摘要保留和 storage 上限测试；不要把运行中 `chatStreamStore` 的完整快照持久化到 `chatStore`。

**SSE 高事件流会放大内存和重放成本：**
- 问题： `frontend/lib/sse.ts` 为每条连接保留 `seenEventIds` 去重，上限 5000（`MAX_SEEN_EVENT_IDS`）；`frontend/hooks/useChatSSE.ts` 把日志、AI 文本、进度和 agent step 写入 `chatStreamStore`。刷新后全量回放会再次灌入内存。
- 相关文件： `frontend/lib/sse.ts`, `frontend/hooks/useChatSSE.ts`, `frontend/stores/chatStreamStore.ts`, `backend/core/sse_manager.py`, `backend/api/stream.py`
- Cause: 断线重连、Last-Event-ID 回放、过程卡实时展示都依赖运行时缓存。
- 改进路径： 新增高频 SSE event 前定义采样、压缩或摘要策略，并补长流重连测试。

**大组件渲染路径缺少虚拟化：**
- 问题： `frontend/components/chat/MessageList.tsx`、`frontend/components/chat/TaskContentMessage.tsx`、`frontend/components/forms/TenderFormShared.tsx` 直接渲染消息、agent step、表单区和候选列表，没有列表虚拟化层。
- 相关文件： `frontend/components/chat/MessageList.tsx`, `frontend/components/chat/TaskContentMessage.tsx`, `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/forms/TemplateCandidateDialog.tsx`
- Cause: 当前 UI 面向单工作台会话，依赖本地状态直接渲染。
- 改进路径： 引入长消息、长候选或多轮 agent step 前先加性能测试和滚动行为测试，再考虑虚拟化或分页。

**模板候选缓存只在组件状态内：**
- 问题： 模板候选以招标号和项目名为 key 缓存在 `TenderFormShared` 组件状态中，不跨会话、跨页面或刷新持久化。
- 相关文件： `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/forms/TemplateCandidateDialog.tsx`
- Cause: 候选列表依赖当前招标编号、项目名和后端重排策略。
- 改进路径： 如需跨会话缓存，先定义失效规则、刷新按钮行为和后端候选策略，再改缓存层。

## 脆弱区域

**SSE 重连与 task resume（高优先级）：**
- 相关文件： `frontend/lib/sse.ts`, `frontend/hooks/useSSE.ts`, `frontend/hooks/useChatSSE.ts`, `frontend/hooks/useTaskHeartbeat.ts`, `frontend/components/chat/FormPanel.tsx`, `frontend/stores/chatStore.ts`, `frontend/stores/chatStreamStore.ts`, `frontend/stores/chatTaskSessionStore.ts`, `backend/api/stream.py`
- 脆弱点：
  - 连接层：`createSSEConnection()` 支持 `autoReconnect`、指数退避（默认 `reconnectDelay=1000`、`multiplier=1.5`、`maxReconnectDelay=30000`、`maxReconnectAttempts=5`）、`heartbeatTimeout`、`lastEventId` query 回放与 `seenEventIds`（上限 5000）去重。
  - 业务层：`useChatSSE` 在 `FormPanel` 挂载，先 `getTaskStatus()` hydrate；`queued` 不连 SSE；终态走 `finalizeFromTaskStatus`；`running` 才 `connectRunningTask()`。
  - 业务重连参数：`autoReconnect: true`、`heartbeatTimeout: 45000`；`done`/`error`/heartbeat 超时/status fallback/`TASK_NOT_FOUND`/`cancel` noop 均可触发终态收口。
  - 同一 task id 同时存在于 `conversations`、`activeTaskIds`、`taskMessageMap`、`taskSummaries`、`chatStreamStore`、`chatTaskSessionStore`；清理不同步会产生幽灵任务或重复下载卡。
  - **Resume 语义分裂**：内存 stream 非空时可用 stream/session 的 `lastEventId` 续订；刷新后 stream 空则强制 `lastEventId=null` 全量回放（见已知问题）。
- 安全修改： 新增终态或重连分支时必须同时清理三类 store，并补 `useChatSSE`、heartbeat、取消和 stale task 测试；不要在组件层自建第二套 EventSource。
- 测试覆盖： `frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`, `frontend/__tests__/unit/hooks/test_use_task_heartbeat.test.tsx`, `frontend/__tests__/unit/stores/test_chat_store_task_messages.test.ts`, `frontend/e2e/test_url_conversation.spec.ts`

**sessionStorage 状态一致性（高优先级）：**
- 相关文件： `frontend/stores/chatStore.ts`, `frontend/stores/chatTaskSessionStore.ts`, `frontend/stores/chatStreamStore.ts`, `frontend/stores/historyStore.ts`, `frontend/app/tender/page.tsx`
- 脆弱点：
  - `chat-storage` partialize 只持久化：`conversations`、`currentConversationId`、`selectedTenderType`、`conversationDrafts`、`taskSummaries`、`unreadConversationResults`。**不持久化** `activeTaskIds`、`taskMessageMap`、`isLoading`、`error`。
  - `chat-task-session-storage` 持久化各 task 的 `lastEventId`；`chatStreamStore` **仅内存**，刷新即丢。
  - 刷新后：消息里可能仍是 `status: 'generating'`，`taskSummaries` 可能仍是 `queued/running`，但 `activeTaskIds` 为空，需靠 `getActiveTaskIdsFromState()` 从 `currentTaskId` + summary 推导，再经 `useChatSSE`/`useCurrentConversationTaskStatus`/`useTaskHeartbeat` 与后端对齐。
  - 后端实例切换：`tender/page.tsx` 通过 conversation heartbeat 检测 `instance_id` 变化后调用 `handleBackendRestart()`，打断 in-flight 任务并清空 stream/session；与 sessionStorage 中“未终态消息”交互复杂，易漏 draft 的 `pending_rewrite_*`。
  - 多 tab 同 origin 共享 `sessionStorage` 时可能互相覆盖 store 快照（浏览器语义下同一会话标签页共享，行为依赖浏览器实现）。
- 安全修改： 改 partialize 前先列清“可恢复 / 必须重拉 / 仅内存”三类字段；终态路径必须同时清理 stream、task session 与 summary；补 hydration 与 backend restart 测试。
- 测试覆盖： `frontend/__tests__/unit/stores/test_session_persistence.test.ts`, `frontend/__tests__/unit/stores/test_chat_store_task_messages.test.ts`, `frontend/e2e/test_url_conversation.spec.ts`

**form_type / gngk 分派错误风险（高优先级）：**
- 相关文件： `frontend/lib/gngkFormType.ts`, `frontend/lib/formDataConverter.ts`, `frontend/components/chat/ChatPanel.tsx`, `frontend/utils/tenderTypeMapper.ts`, `frontend/app/tender/page.tsx`
- 脆弱点：
  - UI `TenderType` 只有 `xjcg|gngk|gjgk`；后端 `form_type` 含四套 gngk 细分 + xjcg/gjgk。
  - generate 与 rewrite 虽共用 `resolveGngkFormType`，但 rewrite 额外要求 draft 已有合法 `tender_lx`/`fund_lx`，否则省略 `form_type`。
  - URL 深链对 gngk 用 `tenderno + tender_lx + fund_lx` 做会话 identity；与表单内手动切换标的/资金后的 draft 可能短暂不一致。
  - 工程类复用 `gngk_fw_*` 是产品临时策略，后端一旦拆 graph 而前端未改 helper，会产生系统性错派。
- 安全修改： 只改 `gngkFormType.ts`；URL 构造只走 `tenderTypeMapper`；改动同步 converter、ChatPanel、单测与 E2E。
- 测试覆盖： `frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`, `frontend/__tests__/unit/lib/test_form_data_converter.test.ts`, `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`

**上传 rewrite / agent run 边界（高优先级）：**
- 相关文件： `frontend/components/chat/ChatPanel.tsx`, `frontend/components/chat/ChatInput.tsx`, `frontend/stores/chatStore.ts`, `frontend/types/api.ts`, `frontend/lib/api.ts`, `backend/models/agent_run.py`, `backend/nodes/skills_nodes/rewrite_nodes.py`
- 脆弱点：
  - 上传：`uploadFile(file, 'rewrite_source')` 写入 draft `rewrite_file`，并强制 `selected_skills: ['rewrite']`；**不要**复用 generate 的 template/params 文件槽。
  - 前置流：`streamAgentRun` → NDJSON（`run_started` / `thinking_stage` / `tool_call` / `needs_input` / `task_accepted` / `done` / `error`）；只有 `task_accepted` 才 `startTask` 进入后台 task/SSE/下载卡。
  - `needs_input` 与非任务 `done` 只是聊天消息，不得当作任务终态。
  - 合成 task id（fake runtime）可展示卡片但不得进入 `activeTaskIds` 真跟踪。
  - generate-only 字段不得进入 agent run payload；单测已断言 `not.toHaveProperty('generation_mode')` 等。
  - 不要恢复旧 edit 入口或第二套 rewrite 任务链路；rewrite 由显式 agent run + 后端 `RewriteSkillGraph` 承载。
- 安全修改： 改 agent run event 同步 parser、类型、UI；改上传只动 rewrite_source 链路；缺 `form_type`/锚点/`tender_lx`/`fund_source_lx` 时依赖 `needs_input`。
- 测试覆盖： `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`, `frontend/e2e/test_agent_run_chat_panel.spec.ts`

**Generate 提交状态机：**
- 相关文件： `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/chat/FormPanel.tsx`, `frontend/lib/formDataConverter.ts`, `frontend/lib/api.ts`, `frontend/stores/chatStore.ts`
- 脆弱点： 表单提交先构造 `GenerateRequest`，再调用 `/api/generate`，随后补拉 `getTaskStatus()` 获取排队摘要；UI busy、取消按钮、任务消息组和 SSE 连接依赖这些步骤按序发生。
- 安全修改： 修改提交字段时同步 converter、`createGenerateTask()`、`startTask()`、`useChatSSE()` 和任务卡测试；不要在表单组件中直接拼接后端 URL。
- 测试覆盖： `frontend/__tests__/unit/lib/test_form_data_converter.test.ts`, `frontend/__tests__/unit/components/forms/test_tender_form_shared.test.tsx`, `frontend/__tests__/unit/components/chat/test_form_panel.test.tsx`, `frontend/e2e/test_generation_mode_agent.spec.ts`

**Agent run NDJSON 前置流：**
- 相关文件： `frontend/lib/api.ts`, `frontend/components/chat/ChatPanel.tsx`, `frontend/lib/agentThinking.ts`, `frontend/types/api.ts`, `backend/api/agent.py`, `backend/models/agent_run.py`
- 脆弱点： `parseAgentRunEvent()` 白名单校验失败时静默丢弃；UI 可能卡在 thinking 态直到超时或用户重试。不要在 agent run 内复制第二套任务状态机。
- 安全修改： 新增 NDJSON event 同步 parser、类型、UI 和测试。
- 测试覆盖： `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`, `frontend/__tests__/unit/components/chat/test_agent_thinking_message.test.tsx`, `frontend/e2e/test_agent_run_chat_panel.spec.ts`

**URL、draft 和招标类型 identity：**
- 相关文件： `frontend/app/tender/page.tsx`, `frontend/hooks/useUrlParams.ts`, `frontend/utils/tenderTypeMapper.ts`, `frontend/stores/chatStore.ts`, `frontend/components/forms/TenderFormShared.tsx`
- 脆弱点： 页面启动状态由 URL 参数、会话 draft、招标详情预取和 `gngk` 子类型共同决定；`gngk` 的 `tender_lx`/`fund_lx` 是 UI 子状态，不直接决定顶层 `TenderType`。
- 安全修改： URL 构造只走 `tenderTypeMapper`；深链参数先写入 draft；改动同步 URL、store 和 E2E。
- 测试覆盖： `frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`, `frontend/__tests__/unit/stores/test_chat_store_conversation_scope.test.ts`, `frontend/e2e/test_url_conversation.spec.ts`

**补充批注下载卡规则：**
- 相关文件： `frontend/components/chat/TaskDownloadMessage.tsx`, `frontend/components/chat/MessageList.tsx`, `frontend/components/chat/ChatPanel.tsx`, `frontend/lib/api.ts`, `backend/api/comment_supplement.py`
- 脆弱点： 补充批注从 generate 下载卡触发；rewrite 和 comment_supplement 下载卡继续显示补充批注动作会产生衍生文件重复任务。
- 安全修改： 保持 `taskKind === 'generate'` 才允许补充批注；请求只携带当前会话、当前 output file 和模型。
- 测试覆盖： `frontend/__tests__/unit/components/chat/test_message_list.test.tsx`, `frontend/e2e/test_comment_supplement.spec.ts`

## 扩展边界

**浏览器 session 不是多设备会话系统：**
- 当前能力： `chatStore` 与 `chatTaskSessionStore` 使用浏览器 `sessionStorage` 保存当前浏览器会话状态。
- 限制： 刷新同一浏览器 session 可以恢复部分状态；跨设备、跨浏览器或长期历史恢复没有稳定前端能力；`activeTaskIds` 与 stream 不跨刷新。
- 扩展路径： 接入服务端会话列表前先定义 `backend/api/conversations.py` 的 API shape，再更新 `frontend/lib/api.ts`、store hydration 和测试。

**前端 E2E 不能验证真实 Word COM 闭环：**
- 当前能力： `frontend/e2e/` 通过 `page.route()` mock 后端，验证 URL、表单、上传、SSE、agent run、补充批注和任务卡 UI。
- 限制： 不能验证真实 Windows Python、pywin32、Word/WPS COM、LangGraph、graph 锁、取消检查、文件写回和下载文件内容。
- 扩展路径： 发布验收需要在后端 Windows + Word/WPS COM 环境执行；前端只验证请求、状态、SSE 和下载入口。

**SSE 重放窗口和客户端去重有限：**
- 当前能力： `seenEventIds` 上限 5000，重连默认 5 次、指数退避；后端支持 `lastEventId` 回放。
- 限制： 超长任务、高频日志和多轮 agent step 会放大前后端事件缓存与重放成本；刷新场景当前刻意全量回放。
- 扩展路径： 增加高频事件前先设计摘要 event 或分页查询，避免把完整过程都塞进 SSE。

**CI 自动化未检测到：**
- 当前能力： 仓库未检测到 `.github/workflows/`。
- 限制： `npm run lint`、`npm run type-check`、`npm run test`、`npm run test:e2e` 和文档校验是否执行取决于人工或外部流水线。
- 扩展路径： 建立 CI 时按前端包边界运行 `frontend/package.json` 的脚本，并保留文档变更的 `git diff --check`。

## 高风险依赖

**Windows/WSL 原生依赖不能混用：**
- 风险： Next、SWC、Tailwind、Playwright 和相关原生包依赖平台二进制，Windows 与 WSL 复用同一 `node_modules` 容易失败。
- 影响： `npm run dev`、`npm run build`、`npm run test:e2e` 可能因平台二进制不匹配失败。
- 迁移建议： Windows 使用 `frontend/node_modules/`；WSL 使用独立 Linux 安装目录；不要提交或复制 `node_modules` 作为修复。

**Next.js 16 / React 19 / Jest 29 组合对测试环境敏感：**
- 风险： `frontend/jest.config.ts` 依赖 `next/jest`、`jest-environment-jsdom`、`frontend/polyfills.js` 和 `frontend/jest.setup.js`；升级 ESM 包或浏览器 API polyfill 容易触发测试环境问题。
- 影响： 单测可能在 `fetch`、`EventSource`、`TextEncoder`、stream polyfill 或 JSX transform 上失败。
- 迁移建议： 依赖变更后运行 `npm run type-check`、`npm run test`，重点检查 jest 配置与 polyfill。

**Playwright 依赖本机浏览器/端口假设：**
- 风险： `frontend/playwright.config.ts` 默认使用 `http://localhost:8502`，非 CI 时倾向系统 Chrome，webServer 运行 `npm run dev -- --webpack`。
- 影响： 本机已有服务、Chrome 渠道缺失或端口冲突会影响 E2E 稳定性。
- 迁移建议： E2E 调试时明确端口和浏览器渠道；CI 中使用 Playwright 自带浏览器并保持 `workers: 1`。

## 缺失的关键能力

**自动契约同步未检测到：**
- 问题： 未检测到从后端 Pydantic schema 自动生成 `frontend/types/api.ts` 的流程。
- Blocks: 前后端字段漂移只能靠人工同步、单测 mock 和 E2E mock 暴露。

**稳定认证/权限 UI 未检测到：**
- 问题： 未检测到登录页、认证 provider、JWT 注入、OAuth SDK 或路由守卫。
- Blocks: 前端不能判断用户身份、租户或授权范围；相关能力必须由后端或新增认证层定义。

**生产监控/错误上报未检测到：**
- 问题： 未检测到 Sentry、Datadog、OpenTelemetry、PostHog、Google Analytics 或 Firebase 等前端监控 SDK。
- Blocks: 生产端错误追踪依赖部署平台、浏览器 console 或后端日志；前端代码内没有统一上报边界。

**自动视觉回归未检测到：**
- 问题： `frontend/e2e/` 中存在 `page.screenshot()` 人工证据输出，但未检测到 `toHaveScreenshot()`、baseline 截图断言或视觉 diff 阈值。
- Blocks: 布局、颜色 token、按钮文案溢出和移动端重排只能靠人工截图审查或普通 DOM 断言发现。

## 测试覆盖缺口

**真实 Word COM 生成闭环：**
- 未覆盖测试： 真实后端、任务队列、LangGraph、Word/WPS COM、文件写回、下载文件内容和补充批注写回。
- 相关文件： `frontend/e2e/`, `frontend/__tests__/`, `backend/api/generate.py`, `backend/services/document_service.py`
- 风险： 前端测试通过不代表 Word 输出正确。
- Priority: High

**跨端契约缺少统一 contract 测试：**
- 未覆盖测试： `backend/models/generate.py`、`backend/models/agent_run.py`、`backend/models/sse.py` 与 `frontend/types/api.ts` 的自动一致性。
- 相关文件： `frontend/types/api.ts`, `frontend/lib/api.ts`, `backend/models/generate.py`, `backend/models/agent_run.py`, `backend/models/sse.py`
- 风险： 字段或枚举漂移可能只在运行时 422、SSE 解析失败或 mock 不匹配时暴露。
- Priority: High

**SSE resume 在“有 lastEventId 无 stream 快照”场景的产品策略未单测产品意图变更：**
- 未覆盖测试： 若未来改为“刷新后从 lastEventId 续订且 UI 不缺日志”，当前实现与单测会直接冲突；缺少长任务刷新后回放耗时/内存压力测试。
- 相关文件： `frontend/hooks/useChatSSE.ts`, `frontend/lib/sse.ts`, `frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`
- 风险： 误改 resume 策略会导致重复事件、缺卡或首屏卡顿。
- Priority: High

**视觉回归只保存截图，不做自动 diff：**
- 未覆盖测试： 工作台三列布局、状态 overlay、agent step 卡、rewrite 文件卡、模板候选弹窗、移动端文本溢出的自动视觉比较。
- 相关文件： `frontend/e2e/`, `frontend/playwright.config.ts`
- 风险： 颜色 token、排版或响应式布局退化不会让 E2E 失败。
- Priority: Medium

**文件上传前端类型校验缺口：**
- 未覆盖测试： 非 `.doc`/`.docx` 文件通过拖拽进入 `FileUploader` 时的前端拦截行为。
- 相关文件： `frontend/components/forms/FileUploader.tsx`, `frontend/__tests__/unit/components/forms/test_file_uploader.test.tsx`
- 风险： 用户只能在后端错误后得到反馈。
- Priority: Medium

**直接 fetch / EventSource 边界缺少静态测试：**
- 未覆盖测试： 组件/hooks/stores 层禁止裸 `fetch()` 与 `new EventSource()` 的 ESLint 或静态扫描。
- 相关文件： `frontend/lib/api.ts`, `frontend/lib/sse.ts`, `frontend/eslint.config.mjs`
- 风险： 新功能可能绕过 API client / SSE helper。
- Priority: Medium

**未使用组件缺少清理门禁：**
- 未覆盖测试： 生产 bundle 是否仍打包 `DualColumnMessage`/`NewChatPopup` 等死代码；依赖图或 lint unused export 未强制。
- 相关文件： `frontend/components/chat/DualColumnMessage.tsx`, `frontend/components/chat/NewChatPopup.tsx`, `frontend/components/chat/Skeleton.tsx`
- 风险： 死代码与测试继续维护成本上升。
- Priority: Medium

**长流和大消息性能缺少压力测试：**
- 未覆盖测试： 超过数千 SSE event、多轮 content/comment agent step、大段 AI 文本、长会话消息列表和 sessionStorage 上限。
- 相关文件： `frontend/lib/sse.ts`, `frontend/hooks/useChatSSE.ts`, `frontend/stores/chatStreamStore.ts`, `frontend/stores/chatStore.ts`, `frontend/components/chat/MessageList.tsx`
- 风险： 长任务可能出现内存增长、重连变慢、渲染卡顿或 storage 写入失败。
- Priority: Medium

**模板候选真实外部策略组合：**
- 未覆盖测试： 外部候选 API、后端 allowed host、AI ranking、非法年份、下载代理失败和选择落盘失败的真实组合。
- 相关文件： `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/forms/TemplateCandidateDialog.tsx`, `frontend/lib/api.ts`, `backend/api/template_candidates.py`
- 风险： mock 通过但真实候选策略变化后 UI 回填不一致。
- Priority: Medium

**Agent run 日志脱敏回归：**
- 未覆盖测试： 前端 `message`、`uploaded_files.file_path`、`rewrite_context` 与后端 agent run audit summary 的端到端脱敏验证。
- 相关文件： `frontend/components/chat/ChatPanel.tsx`, `frontend/lib/api.ts`, `backend/agents/task_context_assistant/logging.py`
- 风险： 新增事件或工具摘要时可能把真实路径、token、traceback 或完整用户原文写入日志和公共摘要。
- Priority: Medium

---

*前端风险分析：2026-07-15*
