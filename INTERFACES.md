# TenderWord 接口边界

**生成日期：** 2026-07-18

本文件是根级**系统级接口边界文档**，记录 TenderWord 当前已确认的跨系统接口边界、跨系统调用关系、任务排查建议和可扩展集成文档入口。具体模型和行为以代码真源为准，并参考 2026-07-18 刷新的 `backend/.planning/codebase/` 与 `frontend/.planning/codebase/` 事实层。

> 分层定位：本文件承接**跨项目接口与协作**。子系统内部集成（如后端 LLM provider 调用细节、前端 store 内部结构）留在各自 `.planning/codebase/INTEGRATIONS.md`；按任务的完整阅读指南在 `coding_maps/SYSTEM_MAP.md`。本文件不复制底层实现细节。

## 1. 已确认接口边界

### API 前缀与前端调用入口

- 后端真实 API 前缀是 `/api`，FastAPI router 注册在 `backend/main.py`。
- 根级健康检查端点是 `/health`、`/health/ready` 和 `/health/live`，**不挂 `/api` 前缀**；它们只表达应用进程层状态。注意 `/health/ready` 的 `upload_dir_accessible` 当前固定为 `True`，不代表 Word COM / LLM / 外部 HTTP 真实可用。
- 前端所有后端调用统一经由 `frontend/lib/api.ts`。JSON 请求走 `request<T>()` / `api.get/post/put/delete` 封装；流式、上传和下载使用其内专用 helper；产品源码中后端 `fetch(` 集中于 `api.ts`，组件层不写裸 `fetch`。
- 前端基础 URL 由 `frontend/lib/apiBaseUrl.ts` 解析 `NEXT_PUBLIC_API_URL`（支持逗号分隔多候选，无配置时用 `http://localhost:8000`）；Next rewrites 在 `frontend/next.config.ts`，把 `/api/:path*` rewrite 到 `resolveApiBaseUrl()` 结果，并将候选 hostname 纳入 `allowedDevOrigins`。修改 `NEXT_PUBLIC_API_URL` 时需同时验证浏览器 base URL、Next rewrite 目标和开发期 allowed origin。

### 跨层枚举与关键约定（系统级契约）

| 契约 | 当前边界 | 同步要求 |
| --- | --- | --- |
| **Task type（`TaskKind`）** | 跨层枚举 `generate` / `rewrite` / `comment_supplement`，定义在 `frontend/types/api.ts`，被 `parseTaskKind`、SSE/agent 事件解析和 `chatStore` 共享。 | 新增任务类型必须同步后端 `TaskKind`、前端 union、SSE 终态、下载卡和会话结果语义。 |
| **Task status** | `queued` / `running` / `completed` / `failed` / `cancelled`。 | 状态字段变化同步后端模型、前端类型、store task summary 和任务 UI。 |
| **Tender type（UI 层）** | `xjcg` / `gngk` / `gjgk`（`frontend/types/index.ts`），由 `purchase_method` 判定（`5`→`xjcg`、`2`→`gngk`、`0`→`gjgk`）；`tender_lx`/`fund_lx` 不参与顶层 UI 判型，但参与 `gngk` 会话 identity 与 form 分派。 | 改 UI 类型同步 `tenderFormRegistry`、converter、URL mapper、类型和测试。 |
| **Form type（`GenerateRequest.form_type`）** | `xjcg_tender`、`gngk_hw_zc_tender`、`gngk_hw_cz_tender`、`gngk_fw_zc_tender`、`gngk_fw_cz_tender`、`gjgk_tender`（`backend/models/generate.py`）。 | 新增/改类型同步前端 UI 类型、后端 `FormType`、`GRAPH_REGISTRY`、graph/state/node、anchor config 和测试。 |
| **运行态 `tender_type` / family** | graph state 用 `form_type.value.replace("_tender","")` 去后缀；`get_tender_type_family()` 把所有 `gngk_*` 归并为 `gngk`。 | family 行为族改动集中在 `backend/config/tender_config.py`。 |
| **gngk 分派** | `gngk` 在前端是单一 UI 类型，提交后端时由共享 helper `frontend/lib/gngkFormType.ts` 的 `resolveGngkFormType({ tender_lx, fund_lx, ifzgcg })` 分派。两个调用点：generate 经 `formDataConverter.ts`，上传文件 rewrite 经 `ChatPanel.tsx`（`resolveRewriteFormType`）。工程类（`tender_lx` 1/2）当前复用服务链路 `gngk_fw_*`（产品临时策略）。 | 不能绕开 helper 单独改调用点；拆独立 graph 时两端同步。 |
| **generate-only 字段** | `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 只出现在 `GenerateRequest` 和生成 draft（`TenderFormShared.tsx`）。 | 不得进入 rewrite 请求模型（`AgentRunStreamRequest` / `AgentRunRewriteContextSnapshot`）、skill state 或 prompt surface。 |
| **rewrite_source** | 上传文件 rewrite 前端用 `rewrite_source` 文件类型（`uploadFile(file,'rewrite_source')`），后端 task skill state 用 `rewrite_source="uploaded_file"` 路由并穿过 LangGraph schema。前端 `FileType` 另含 `template` / `params` / `qualification`。 | 不要恢复旧 edit 入口或第二套任务链路。 |
| **批注职责** | 技术参数差异更正批注仅由 generate 主干的 `annotate_corrections` 产出；合规批注由 `comment_agent` / `generate_comments` 产出；`comment_agent` 不得生成“原技术参数为…现改为…”类差异批注。编号/项目符号/展示壳变化不得生成事实更正；重要性标识规范化（`*/※→★`、`△/Δ→▲`）可保留。 | 改对齐规则、句式门禁或写回顺序时同步后端节点/测试与 `docs/backend.md`；不要把编号隔离散落到 writeback 层。 |
| **批注写回顺序与开关** | `update_word` 先写 `correction_comments` 再写普通 `polished_comments`。`comment_generation_mode=off` / `suppress_ai_comment_writeback` 只跳过普通 AI 批注，不跳过更正批注。标准写回默认跳过已有批注重叠锚点；`comment_agent` 显式允许同锚点追加。 | 改写回语义时同步 comment writeback helper、comment agent 调用方、任务结果/SSE `done` 中的 writeback 摘要与测试。 |

### 生成任务

| 项 | 当前边界 |
| --- | --- |
| 前端调用方 | `frontend/components/chat/FormPanel.tsx` |
| 请求转换 | `frontend/lib/formDataConverter.ts`（按 `tenderFormConverterMap` 选择） |
| API client | `frontend/lib/api.ts` 中的 `createGenerateTask()` |
| 后端路由 | `backend/api/generate.py` 中的 `POST /api/generate` |
| 后端模型 | `backend/models/generate.py` 中的 `GenerateRequest` / `FormType` |
| 后端 service | `backend/services/document_service.py` |
| 运行时 | `backend/task/task_queue_manager.py`、`backend/graphs/base_graph.py` |

同步要求：

- `GenerateRequest.file_paths` 当前只接受 `template` 与 `tender_params`；后端初始 state 只装配 `template_path` + `tender_param_paths`，不要重新引入旧文件槽位。
- `GenerateRequest.form_type` 变化必须同步 `frontend/types/api.ts`、`frontend/lib/formDataConverter.ts` 和 `backend/models/generate.py`；`gngk` 分派变化还必须同步 `frontend/lib/gngkFormType.ts`。
- `generation_mode` 默认 `workflow`（走 `generate_polished_text`），`agent` 走公共 `content_agent`，只影响初次生成节点选择；`comment_generation_mode` 默认 `on`，`off` 时跳过**普通** AI 批注生成与 bad case 检索，不关闭更正批注。
- 初次生成共享主干在正文确定后接入 **`annotate_corrections`（仅 generate；`RewriteSkillGraph` 不接入）**：条款标识规范化 + 可确定事实差异的更正批注候选；再进入普通批注分支与 `update_word`。
- `content_verify_agent` 审核结果只保留真实需修复 findings；无问题 / 无需修改折叠为 `[]`。
- content agent 正文把技术参数结构化表里的 `[[TABLE:<id>]]` 当作内部写回入口交给后端写回层；占位符识别与 sidecar 恢复语义在后端统一维护，不进入前端 API/SSE 契约。
- 注意：`GET /api/generate/{task_id}` 完成态返回 shape 与 `GET /api/tasks/{task_id}` / SSE `done` 不同源；完整结果优先走任务查询或 SSE 终态。

### 任务状态、取消与心跳

| 项 | 当前边界 |
| --- | --- |
| API client | `frontend/lib/api.ts` 中的 `getTaskStatus()`、`getTaskList()`、`cancelTask()`、`sendTaskHeartbeat()` |
| 后端路由 | `backend/api/tasks.py` |
| 后端 service | `backend/services/task_service.py` |
| 队列真源 | `backend/task/task_queue_manager.py` |
| 前端轮询 | `frontend/hooks/useCurrentConversationTaskStatus.ts` |
| 前端心跳 | `frontend/hooks/useTaskHeartbeat.ts` |

同步要求：

- 任务状态字段变化必须同步 `backend/models/task.py`、`frontend/types/api.ts`、store task summary 和任务 UI。
- 从 `sessionStorage` 恢复 running task 前，前端必须先查任务状态；404 / `TASK_NOT_FOUND` 收敛成本地中断态，避免直接连接已不存在的 SSE。
- 后端 `instance_id` 变化时，前端需收敛本地 running task 状态。

### 任务 SSE

| 项 | 当前边界 |
| --- | --- |
| 后端路由 | `backend/api/stream.py` 中的 `GET /api/stream/{task_id}`（及 `/status`） |
| 后端 manager | `backend/core/sse_manager.py` |
| 日志桥接 | `backend/util/log_util/sse_log_handler.py` |
| 前端 URL helper | `frontend/lib/api.ts` 中的 `getTaskStreamUrl()` |
| 前端 runtime | `frontend/lib/sse.ts` |
| 前端映射 | `frontend/hooks/useChatSSE.ts` |
| 前端类型 | `frontend/types/api.ts` |

- 后端 SSE event enum：`log`、`llm`、`progress`、`node_start`、`node_complete`、`agent_step`、`done`、`error`、`heartbeat`。
- 前端 named events：`connected`、`log`、`llm`、`progress`、`agent_step`、`status`、`error`、`done`、`heartbeat`。注意 `connected`、`status` 是前端连接/映射层事件，不是后端真实事件；`node_start`、`node_complete` 是后端事件但不在前端 named event 列表中。
- 新增 SSE 事件必须同步后端模型、事件发送、前端 union 类型、`frontend/lib/sse.ts` named event 注册、`useChatSSE` 解析和测试。
- 任务失败必须最终表现为 `error` 或 `done`，不能让 SSE 静默中断。
- `comment_writeback_*` 和 `style_writeback_*` 摘要属于任务结果契约，不得在 state、任务结果或 `done` 事件中丢失。
- `agent_step` 是智能体过程事件，允许断线重放和前端过程卡展示，但不替代 `done` / `error` 终态。`comment_supplement` 任务复用同一 SSE 通道。
- retrieval 命中详情 / 检索 JSON **不进入** SSE、下载卡或 `agent_step`。

### Agent Run、聊天与 Rewrite（NDJSON 回流）

| 项 | 当前边界 |
| --- | --- |
| 前端调用方 | `frontend/components/chat/ChatPanel.tsx` |
| API client | `frontend/lib/api.ts` 中的 `streamAgentRun()` / `streamNdjson()` |
| 后端路由 | `backend/api/agent.py` 中的 `POST /api/agent/runs/stream` |
| 路由 service | `backend/services/agent_run_service.py` |
| Agent / tool runtime | `backend/agents/task_context_assistant/` |
| 后续 task runtime | `backend/graphs/skill_graph.py`（显式 `RewriteSkillGraph`）、`backend/skills/rewrite/` |

- `POST /api/agent/runs/stream` 是右侧聊天**唯一流式入口**，返回 NDJSON agent run 事件。后端编排真源是 `agent_run_service.py`；NDJSON 行序列化复用 `backend/services/chat_stream_service.py` 的 `to_ndjson_line()`。
- agent run 必须先流出 `run_started` 和 `thinking_stage`，再决定 `needs_input`（追问，**不创建任务**）或经 `create_rewrite_task_tool` 创建 rewrite 任务（`task_accepted`）。
- `task_accepted` 后 agent run 即结束；后续排队、**显式 `RewriteSkillGraph`** 执行、SSE、取消和下载继续沿用既有任务主链路，不在 agent run 里复制第二套任务状态机。
- `RewriteSkillGraph` **不接入** `annotate_corrections`；rewrite 不触发 bad case retrieval。
- task-context assistant 只允许受控 `rewrite` skill 与只读摘要工具；审计日志只写 scrub 后白名单字段。
- NDJSON event shape 变化必须同步 `frontend/types/api.ts`、`parseAgentRunEvent()` 和 `ChatPanel`。当前事件：`run_started`、`thinking_stage`、`tool_call`、`task_accepted`、`needs_input`、`done`、`error`；未知事件在前端 parser 白名单外静默丢弃。
- 显式 `$rewrite` / `/rewrite` 和上传 Word 文件都归入 rewrite：上传文件用 `rewrite_source` 文件类型；`context_snapshot.rewrite_context` 提供 `form_type`、锚点、`tender_lx`、`fund_source_lx` 和可选招标数据快照，**不含** generate-only 字段。
- 上传文件 rewrite 必须有非空用户重写指令、文件路径、完整锚点、`tender_lx`、`fund_source_lx`；`tender_data_snapshot` 可选，缺招标数据不阻断。
- `/api/edit`、edit skill、edit task kind 已删除；不要恢复 `SkillGraph.for_skill + TaskSkillWorkflow` 元数据驱动框架。

### 补充批注任务

| 项 | 当前边界 |
| --- | --- |
| 前端触发 | `frontend/components/chat/TaskDownloadMessage.tsx`、`frontend/components/chat/MessageList.tsx`、`frontend/components/chat/ChatPanel.tsx` |
| API client | `frontend/lib/api.ts` 中的 `createCommentSupplementTask()` |
| 后端路由 | `backend/api/comment_supplement.py` 中的 `POST /api/comment-supplement` |
| 后端 service | `DocumentService.create_comment_supplement_task()` |
| Graph | `backend/graphs/comment_supplement_graph.py` |
| 共享节点 / 运行时 | `backend/nodes/common_word_nodes/comment_supplement.py`、`backend/nodes/common_word_nodes/comment_agent.py`、`backend/agents/comments/` |

同步要求：

- 补充批注只从**初次生成**下载卡触发（`taskKind === 'generate'`）；rewrite 和 comment_supplement 下载卡不应再显示补充批注动作。
- 请求只携带当前会话、当前下载文件路径和模型；后端负责校验 latest `rewrite_state`、`polished_text` 和 source file 是否仍是当前最新文档。
- 成功后必须更新会话 latest `rewrite_state.prepared_doc_path`，让后续 rewrite 基于补充批注后的副本。
- 批注写回统一收敛到共享 writeback helper；差异批注仍只由 generate 的 `annotate_corrections` 产出，本链路只做合规批注增强。
- `TaskKind`、任务状态、SSE `done` payload、下载消息和 `agent_step` 过程卡变化必须同步前后端类型与测试。

### 招标详情查询

| 项 | 当前边界 |
| --- | --- |
| 前端调用方 | `frontend/lib/tenderFetch.ts`、`frontend/app/tender/page.tsx`、`frontend/components/forms/TenderFormShared.tsx` |
| API client | `frontend/lib/api.ts` 中的 `fetchTenderDataWithType()` / `fetchTenderData()` |
| 后端路由 | `backend/api/tender.py` 中的 `GET /api/tender/{tender_no}` |
| 后端工具 | `backend/util/common_util/fetch_tender_data.py` |
| 外部配置 | `backend/config/settings.py` 中的 `TENDER_DATA_API_URL` |

同步要求：

- 外部接口细节不应泄露到前端组件；未知 `purchase_method` 时后端返回 `data` 与原始 `type` 并 `warning`；前端不得把未知采购方式自动映射到现有表单类型。

### 上传与下载

| 项 | 当前边界 |
| --- | --- |
| 上传 client | `frontend/lib/api.ts` 中的 `uploadFile()`、`uploadFiles()` |
| 上传 UI | `frontend/components/forms/FileUploader.tsx`、`ChatPanel` 中的上传文件 rewrite |
| 上传路由 | `backend/api/upload.py`（`POST /api/upload`、`POST /api/upload/multiple`） |
| 下载 client | `frontend/lib/api.ts` 中的 `downloadFile()`、`getDownloadUrl()` |
| 下载路由 | `backend/api/download.py`（`GET /api/download/{file_path:path}`） |
| 存储 helper | `backend/util/common_util/upload_storage.py` |

同步要求：

- 前端不直接访问本地文件系统或云存储；历史侧栏也用相对 `/api/download/...` 链接经 Next rewrite 代理。
- 后端下载路径必须继续受 `settings.UPLOAD_DIR` containment 校验。

### 模板候选

| 项 | 当前边界 |
| --- | --- |
| 前端调用方 | `frontend/components/forms/TenderFormShared.tsx`、`frontend/components/forms/TemplateCandidateDialog.tsx` |
| API client | `frontend/lib/api.ts` 中的 `fetchTemplateCandidates()`、`selectTemplateCandidate()`、`getTemplateCandidateDownloadUrl()` |
| 后端路由 | `backend/api/template_candidates.py` |
| 后端工具 | `backend/util/common_util/template_candidates.py` |
| 排序 service | `backend/services/template_candidate_ranking_service.py` |
| Prompt | `backend/prompts/template_candidate_ranking_prompt.py` |
| 外部配置 | `TEMPLATE_CANDIDATE_API_URL`、`TEMPLATE_CANDIDATE_ALLOWED_HOSTS` |

同步要求：

- 前端只调用项目内 `/api/template-candidates*`，不得直接访问外部候选接口或外部文件 URL。
- 外部列表请求、下载代理、落盘和文件名清洗统一由后端处理；外部下载链接受 `TEMPLATE_CANDIDATE_ALLOWED_HOSTS` 白名单约束。
- AI 排序契约只返回后端生成的 `row_index` 列表。
- `year < 2025` 或非法年份的模板不可选择，只允许下载参考。

### 会话心跳

| 项 | 当前边界 |
| --- | --- |
| 前端调用方 | `frontend/app/tender/page.tsx` |
| API client | `frontend/lib/api.ts` 中的 `sendConversationHeartbeat()` |
| 后端路由 | `backend/api/conversations.py`（`POST /api/conversations/{conversation_id}/heartbeat`） |
| 后端 service | `backend/services/conversation_service.py` |

同步要求：

- 浏览器地址栏必须始终反映当前会话身份。
- 后端实例变化时，前端需要收敛本地 running task 状态，避免旧快照误连。

### 外部集成边界（系统级）

| 集成 | 边界 | 后端入口 |
| --- | --- | --- |
| **LLM provider** | OpenAI-compatible streaming：DeepSeek / Qwen-DashScope / Doubao-ARK（可选 LangSmith）。超时取 `LLM_STREAM_TIMEOUT_SECONDS`。 | `backend/util/common_util/llm_stream_utils.py`、`backend/agents/generation/`、`backend/agents/comments/`、`backend/services/chat_stream_service.py` |
| **Word COM** | 仅存在于后端；前端无直接入口。必须经任务队列 + graph 锁 + 取消检查 + 进度包装。 | `backend/util/word_util/`、`backend/helper/word_helper/`、`backend/nodes/`、`backend/graphs/base_graph.py`、`backend/task/task_queue_manager.py` |
| **招标详情 API** | 外部接口经后端代理。 | `TENDER_DATA_API_URL` → `backend/util/common_util/fetch_tender_data.py` |
| **模板候选 API** | 外部列表/下载经后端代理 + 白名单。 | `TEMPLATE_CANDIDATE_API_URL` → `backend/util/common_util/template_candidates.py` |
| **批注 bad case 检索** | 后端 prompt 增强正式运行时，不是对前端开放的 API。 | `backend/retrieval/`（Qdrant + embedding，失败降级 BM25） |

retrieval 系统级边界（已确认）：

- 正式接入点只包括 `generate_comments`、自主生成模式 `comment_agent` 和 `comment_supplement` 的 prompt 增强；rewrite 和 `comment_generation_mode=off` 不触发检索。
- hybrid 失败降级到 `bm25_only`；检索失败、无命中或坏文件不阻塞批注生成。
- retrieval JSON 只作为后端审计文件落盘，检索状态、日志路径和命中详情**不进入 SSE、下载卡或 `agent_step`**。

## 2. 未证实或当前不存在的接口

下列能力当前源文档未确认，若后续新增需先建立代码真源，再同步本文件和对应 `.planning/codebase/`：

- 当前源文档**未确认**稳定登录、用户认证、鉴权中间件或权限接口（前后端均无）。
- 当前源文档**未确认**外部关系数据库、ORM、migration、Redis、独立 cache service 或对象存储（任务/SSE/会话历史/retrieval cache 均为进程内状态，重启不恢复）。
- 当前源文档**未确认**第三方入站 webhook。
- 当前源文档**未确认**生产托管配置、`vercel.json`/`Dockerfile`/`docker-compose` 或 CI workflow 文件（`.github/workflows/` 未检测到）。

## 3. 任务排查建议

按修改类型给出排查路径（完整阅读顺序见 `coding_maps/SYSTEM_MAP.md`）：

- **接口返回异常：** 先看 `frontend/lib/api.ts` 的 `ApiError` 包装，再看对应 `backend/api/` route 和 `backend/models/`。
- **SSE 卡住：** 先区分任务是否还存在、队列是否运行、后端是否发出 `error` / `done`，再看 `backend/core/sse_manager.py` 和 `frontend/hooks/useChatSSE.ts`；注意前端刷新后可能强制从起点回放 SSE。
- **gngk 类型不对：** 同时检查 URL 参数、draft、`frontend/lib/gngkFormType.ts`、`formDataConverter.ts`、`ChatPanel.tsx` 上传文件 rewrite 调用点、后端 `FormType` 和 `GRAPH_REGISTRY`；工程类是否仍按临时策略复用 `gngk_fw_*`。
- **rewrite/agent run 不创建任务：** 确认是否缺必需条件只返回了 `needs_input`；确认只在 `task_accepted` 后才进入任务/SSE 链路；确认未把 generate-only 字段塞进 agent run payload。
- **更正批注 / 编号隔离异常：** 确认改动在 generate 主干的 `annotate_corrections`，而非 rewrite 或 writeback 层；编号/展示壳是否被误标为事实更正；`update_word` 是否仍先写更正批注；`comment_generation_mode=off` 是否误关更正批注。
- **同锚点批注重复或漏写：** 区分标准写回默认跳过重叠锚点与 `comment_agent` 显式允许同锚点追加。
- **模板候选不可选：** 检查 `year`、`blocked_reason`、AI `row_index` 重排和前端选择按钮状态；确认未直接访问外部 URL。
- **Word 写回异常：** 先看任务队列、graph 锁、protected fields、paragraph boundary helper，再看类型专属 node；确认未绕过队列、graph 锁、取消检查和进度包装。
- **上传文件 rewrite Word 冲突：** 确认仍保持单次 Word 删除分支语义，避免 `delete_section` 执行两次并与 `update_word` 并发抢 COM。
- **content agent 表格异常：** 确认 `[[TABLE:<id>]]` 只交给后端写回层处理，不把占位符当用户可见正文或手绘 Markdown 表。

## 4. 可扩展集成文档入口

跨项目接口、协作关系的更细文档入口：

- **跨子项目系统地图：** `coding_maps/SYSTEM_MAP.md`（跨层调用链与数据流、后端到前端接口边界总表、按任务分类阅读指南、集成风险检查清单、验证入口）。
- **后端内部集成：** `backend/.planning/codebase/INTEGRATIONS.md`（LLM provider 调用参数、retrieval 细节、env 配置键名、监控与可观测性）。
- **前端内部集成：** `frontend/.planning/codebase/INTEGRATIONS.md`（API helper 全清单、SSE/NDJSON runtime、浏览器存储、模型选择）。
- **接口运行时规则：** `docs/interfaces-runtime.md`、`docs/backend.md`、`docs/frontend.md`。
- **长期知识包：** `asset/shared_runtime_word_skill_knowledge_pack.md`（运行时 / Word skill / SSE 透传 / 批注样式回写）、`asset/tender_type_identity_session_knowledge_pack.md`（类型 identity / URL 判型 / 会话）、`asset/template_candidate_pipeline_knowledge_pack.md`（模板候选管线）。
- **知识包索引：** `asset/README.md`。

---

*接口边界文档：2026-07-18*
