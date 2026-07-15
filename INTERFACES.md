# TenderWord 接口边界

**生成日期：** 2026-07-15

本文件是根级**系统级接口边界文档**，记录 TenderWord 当前已确认的跨系统接口边界、跨系统调用关系、任务排查建议和可扩展集成文档入口。具体模型和行为以代码真源为准，并参考 2026-07-15 刷新的 `backend/.planning/codebase/` 与 `frontend/.planning/codebase/` 事实层。

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
| **Tender type（UI 层）** | `xjcg` / `gngk` / `gjgk`（`frontend/types/index.ts`），由 `purchase_method` 判定（`5`→`xjcg`、`2`→`gngk`、`0`→`gjgk`）。 | 改 UI 类型同步 `tenderFormRegistry`、converter、URL mapper、类型和测试。 |
| **Form type（`GenerateRequest.form_type`）** | `xjcg_tender`、`gngk_hw_zc_tender`、`gngk_hw_cz_tender`、`gngk_fw_zc_tender`、`gngk_fw_cz_tender`、`gjgk_tender`（`backend/models/generate.py`）。 | 新增/改类型同步前端 UI 类型、后端 `FormType`、`GRAPH_REGISTRY`、graph/state/node、anchor config 和测试。 |
| **运行态 `tender_type` / family** | graph state 用 `form_type.value.replace("_tender","")` 去后缀；`get_tender_type_family()` 把所有 `gngk_*` 归并为 `gngk`。 | family 行为族改动集中在 `backend/config/tender_config.py`。 |
| **gngk 分派** | `gngk` 在前端是单一 UI 类型，提交后端时由共享 helper `frontend/lib/gngkFormType.ts` 的 `resolveGngkFormType({ tender_lx, fund_lx, ifzgcg })` 分派到具体 form type。两个调用点都走该 helper：generate 经 `formDataConverter.ts`，上传文件 rewrite 经 `ChatPanel.tsx`（`resolveRewriteFormType`）。 | 不能绕开 helper 单独改调用点；分派规则变化同步两端测试。 |
| **generate-only 字段** | `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 只出现在 `GenerateRequest` 和生成 draft（`TenderFormShared.tsx`）。 | 不得进入 rewrite 请求模型（`AgentRunStreamRequest` / `AgentRunRewriteContextSnapshot`）、skill state 或 prompt surface。 |
| **rewrite_source** | 上传文件 rewrite 前端用 `rewrite_source` 文件类型（`uploadFile(file,'rewrite_source')`），后端 task skill state 用 `rewrite_source="uploaded_file"` 路由并穿过 LangGraph schema。 | 不要恢复旧 edit 入口或第二套任务链路。 |

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
- `generation_mode` 默认 `workflow`（走 `generate_polished_text`），`agent` 走公共 `content_agent`，只影响初次生成节点选择；`comment_generation_mode` 默认 `on`，`off` 时跳过 AI 批注生成。
- `content_verify_agent` 审核结果只保留真实需修复 findings；无问题 / 无需修改折叠为 `[]`，前端过程卡不应把空审核项当真实问题。
- content agent 正文把技术参数结构化表里的 `[[TABLE:<id>]]` 当作内部写回入口交给后端写回层处理；占位符识别在 `backend/agents/generation/table_placeholder_utils.py`，按 sidecar 恢复/丢弃在 `backend/helper/word_helper/text_parsing.py`，`table_id` 字符集需与 `backend/util/word_util/table_models.py` 一致；verify agent 不再把缺失占位符单独当 finding。

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
- `agent_step` 是智能体生成过程事件，允许断线重放和前端过程卡展示，但不替代 `done` / `error` 终态。`comment_supplement` 任务复用同一 SSE 通道，`comment_agent` 过程卡仍通过 `agent_step` 展示。

### Agent Run、聊天与 Rewrite（NDJSON 回流）

| 项 | 当前边界 |
| --- | --- |
| 前端调用方 | `frontend/components/chat/ChatPanel.tsx` |
| API client | `frontend/lib/api.ts` 中的 `streamAgentRun()` / `streamNdjson()` |
| 后端路由 | `backend/api/agent.py` 中的 `POST /api/agent/runs/stream` |
| 路由 service | `backend/services/agent_run_service.py` |
| Agent / tool runtime | `backend/agents/task_context_assistant/` |
| 后续 task runtime | `backend/graphs/skill_graph.py`、`backend/skills/rewrite/` |

- `POST /api/agent/runs/stream` 是右侧聊天**唯一流式入口**，返回 NDJSON agent run 事件。后端编排真源是 `agent_run_service.py`（客观不可执行 preflight、NDJSON 事件映射、审计落盘）；NDJSON 行序列化复用 `backend/services/chat_stream_service.py` 的 `to_ndjson_line()`，不在调用方各自手写 JSON 行。
- agent run 必须先流出 `run_started` 和 `thinking_stage: understand completed`，再由 task-context assistant 决定 `needs_input`（追问）或经 `create_rewrite_task_tool` 创建 rewrite 任务（`task_accepted`）。
- `task_accepted` 只负责把 agent run 收敛为"已创建任务"，agent run 即结束；后续排队、`RewriteSkillGraph` 执行、SSE、取消和下载继续沿用既有任务主链路，**不在 agent run 里复制第二套任务状态机**。
- task-context assistant 只允许受控 `rewrite` skill（`TASK_CONTEXT_ASSISTANT_ALLOWED_SKILLS=("rewrite",)`）、只读摘要工具（`read_current_conversation_summary_tool` / `read_current_task_public_summary_tool`），并通过 `CompositeBackend` 分隔 `/skills/`、`/scratch/`、`/workspace/`。
- NDJSON event shape 变化必须同步 `frontend/types/api.ts`、`api.ts` 的 `parseAgentRunEvent()` 和 `ChatPanel`。`selected_skills`、`context_snapshot.uploaded_files` 和 `context_snapshot.rewrite_context` 变化同步 `backend/models/agent_run.py`、`frontend/types/api.ts`、`frontend/stores/chatStore.ts` 和 `ChatPanel`。
- **显式 `$rewrite` / `/rewrite` 和上传 Word 文件都归入 rewrite**：上传文件 rewrite 前端用 `rewrite_source` 文件类型，`context_snapshot.uploaded_files` 提供文件摘要，`context_snapshot.rewrite_context` 提供当前页面 `form_type`、锚点、`tender_lx`、`fund_source_lx` 和可选招标数据快照。
- 上传文件 rewrite 必须有非空用户重写指令、文件路径、完整锚点、`tender_lx`、`fund_source_lx`；`tender_data_snapshot` 只是可选快照，缺招标数据不阻断。缺必需条件只返回 `needs_input`，不自动猜测文档类型或锚点。rewrite 完成后前端用 SSE `done.output_file` 回写文件卡，下一轮 rewrite 基于最新输出；用户删文件卡后回到会话 rewrite history。
- `/api/edit`、edit skill、edit task kind、`create_edit_task_tool` 已删除；旧调用表现为 404，不做历史会话迁移。
- agent run 审计日志只写白名单结构化字段并 scrub token、`.env`、私有绝对路径、完整客户原文和 traceback；公共摘要工具不暴露完整结果或下载路径。

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

- 前端 URL 驱动查数要把必要 URL 参数写入 draft，再由表单初始化读取；外部接口细节不应泄露到前端组件。
- 外部接口返回未支持的 `purchase_method` 时，后端仍返回 `data` 与原始 `type`，并通过 `warning` 提示前端显示黄色"当前采购方式暂不支持"；前端不得把未知采购方式自动映射到现有表单类型或自动改写当前页面类型按钮和生成 graph。

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
- AI 排序契约只返回后端生成的 `row_index` 列表，不能要求前端用项目名称反查候选。
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
| **LLM provider** | OpenAI-compatible streaming：DeepSeek / Qwen-DashScope / Doubao-ARK（可选 LangSmith tracing）。统一 model factory 在 `backend/agents/generation/model_factory.py`，超时取 `LLM_STREAM_TIMEOUT_SECONDS`。provider key/base URL/model 配置在 `backend/config/settings.py`。 | `backend/util/common_util/llm_stream_utils.py`、`backend/agents/generation/`、`backend/agents/comments/`、`backend/services/chat_stream_service.py` |
| **Word COM** | 仅存在于后端；前端无直接入口。 | `backend/util/word_util/`（COM 生命周期）、`backend/helper/word_helper/`（业务）、`backend/nodes/`（graph node）、`backend/graphs/base_graph.py`（锁/进度）、`backend/task/task_queue_manager.py`（队列） |
| **招标详情 API** | 外部接口经后端代理。 | `TENDER_DATA_API_URL` → `backend/util/common_util/fetch_tender_data.py` |
| **模板候选 API** | 外部列表/下载经后端代理 + 白名单。 | `TEMPLATE_CANDIDATE_API_URL` → `backend/util/common_util/template_candidates.py` |
| **批注 bad case 检索** | 后端 prompt 增强正式运行时，不是对前端开放的 API。 | `backend/retrieval/`（Qdrant + embedding，失败降级 BM25） |

retrieval 系统级边界（已确认）：

- 正式接入点只包括 `generate_comments`、自主生成模式 `comment_agent` 和 `comment_supplement` 的 prompt 增强；rewrite 和 `comment_generation_mode=off` 不触发检索。
- hybrid 失败降级到 `bm25_only`，检索失败、无命中或坏文件不阻塞批注生成。
- retrieval JSON 只作为后端审计文件落盘，检索状态、日志路径和命中详情**不进入 SSE、下载卡或 `agent_step`**。

## 2. 未证实或当前不存在的接口

下列能力当前源文档未确认，若后续新增需先建立代码真源，再同步本文件和对应 `.planning/codebase/`：

- 当前源文档**未确认**稳定登录、用户认证、鉴权中间件或权限接口（前后端均无）。
- 当前源文档**未确认**外部关系数据库、ORM、migration、Redis、独立 cache service 或对象存储（任务/SSE/会话历史/retrieval cache 均为进程内状态，重启不恢复）。
- 当前源文档**未确认**第三方入站 webhook。
- 当前源文档**未确认**生产托管配置、`vercel.json`/`Dockerfile`/`docker-compose` 或 CI workflow 文件（`.github/workflows/` 未检测到）。

## 3. 任务排查建议

按修改类型给出排查路径（完整阅读顺序见 `coding_maps/SYSTEM_MAP.md`）：

- **接口返回异常：** 先看 `frontend/lib/api.ts` 的 `ApiError` 包装（HTTP status / wrapped `success:false` / 嵌套 `detail` / network failure），再看对应 `backend/api/` route 和 `backend/models/`。
- **SSE 卡住：** 先区分任务是否还存在、队列是否运行、后端是否发出 `error` / `done`，再看 `backend/core/sse_manager.py` 和 `frontend/hooks/useChatSSE.ts`；`agent_step` 不显示时还要检查 `frontend/lib/sse.ts` 是否监听 named event，补充批注还要确认任务类型是 `comment_supplement` 且过程卡来自 `comment_agent`。
- **gngk 类型不对：** 同时检查 URL 参数、draft、`frontend/lib/gngkFormType.ts`、`formDataConverter.ts`、`ChatPanel.tsx` 上传文件 rewrite 调用点、后端 `FormType` 和 `GRAPH_REGISTRY`。
- **rewrite/agent run 不创建任务：** 确认是否缺必需条件（非空重写指令、文件路径、完整锚点、`tender_lx`、`fund_source_lx`）只返回了 `needs_input`；确认只在 `task_accepted` 后才进入任务/SSE 链路；确认 NDJSON 行是否复用 `to_ndjson_line()`。
- **模板候选不可选：** 检查 `year`、`blocked_reason`、后端归一化、AI `row_index` 重排和前端选择按钮状态；确认未直接访问外部 URL。
- **Word 写回异常：** 先看任务队列、graph 锁（`CrossProcessFileLock`）、protected fields、paragraph boundary helper，再看类型专属 node；确认改动未绕过队列、graph 锁、取消检查和进度包装。
- **上传文件 rewrite Word 冲突：** 确认仍保持单次 Word 删除（`extract_rewrite_context -> rewrite_text -> delete_section -> update_word`），避免 `delete_section` 执行两次并与 `update_word` 并发抢 Word COM。
- **content agent 表格异常：** 确认 `[[TABLE:<id>]]` 占位符只交给后端写回层处理，`table_id` 字符集与 `backend/util/word_util/table_models.py` 一致，verify agent 仍只对真实参数差异产出 findings。

## 4. 可扩展集成文档入口

跨项目接口、协作关系的更细文档入口：

- **跨子项目系统地图：** `coding_maps/SYSTEM_MAP.md`（跨层调用链与数据流、后端到前端接口边界总表、按任务分类阅读指南、集成风险检查清单、验证入口）。
- **后端内部集成：** `backend/.planning/codebase/INTEGRATIONS.md`（LLM provider 调用参数、retrieval 细节、env 配置键名、监控与可观测性）。
- **前端内部集成：** `frontend/.planning/codebase/INTEGRATIONS.md`（API helper 全清单、SSE/NDJSON runtime、浏览器存储、模型选择）。
- **接口运行时规则：** `docs/interfaces-runtime.md`、`docs/backend.md`、`docs/frontend.md`。
- **长期知识包：** `asset/shared_runtime_word_skill_knowledge_pack.md`（运行时 / Word skill / SSE 透传 / 批注样式回写）、`asset/tender_type_identity_session_knowledge_pack.md`（类型 identity / URL 判型 / 会话）、`asset/template_candidate_pipeline_knowledge_pack.md`（模板候选管线）。
- **知识包索引：** `asset/README.md`。

---

*接口边界文档：2026-06-29*
