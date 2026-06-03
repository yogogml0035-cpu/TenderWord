# TenderWord 接口边界

**生成日期：** 2026-06-02

本文件记录 TenderWord 当前已确认的系统级接口边界。具体模型和行为以 `backend/api/`、`backend/models/`、`frontend/types/api.ts` 和 `frontend/lib/api.ts` 为准。

## 已确认接口边界

### API 前缀与前端调用入口

- 后端真实 API 前缀是 `/api`，FastAPI router 注册在 `backend/main.py`。
- 前端所有后端调用统一经由 `frontend/lib/api.ts`。
- JSON 请求走 `request<T>()` / `api.get/post/put/delete` 封装。
- 流式、上传和下载使用 `frontend/lib/api.ts` 内的专用 helper。
- 前端基础 URL 由 `frontend/lib/apiBaseUrl.ts` 解析，Next rewrites 在 `frontend/next.config.ts`。

### 生成任务

| 项 | 当前边界 |
| --- | --- |
| 前端调用方 | `frontend/components/chat/FormPanel.tsx` |
| 请求转换 | `frontend/lib/formDataConverter.ts` |
| API client | `frontend/lib/api.ts` 中的 `createGenerateTask()` |
| 后端路由 | `backend/api/generate.py` 中的 `POST /api/generate` |
| 后端模型 | `backend/models/generate.py` 中的 `GenerateRequest` / `FormType` |
| 后端 service | `backend/services/document_service.py` |
| 运行时 | `backend/task/task_queue_manager.py`, `backend/graphs/base_graph.py` |

同步要求：
- `GenerateRequest.file_paths` 当前只接受 `template` 与 `tender_params`；生成节点只消费 `template_path` 与 `tender_param_paths`，不要重新引入旧文件槽位。
- `GenerateRequest.form_type` 变化必须同步 `frontend/types/api.ts`、`frontend/lib/formDataConverter.ts` 和 `backend/models/generate.py`；`gngk` 分派变化还必须同步 `frontend/lib/gngkFormType.ts`。
- `generation_mode` 是 generate-only 字段，默认 `workflow`；`agent` 只影响初次生成节点选择，不进入 rewrite 请求模型、skill state 或 prompt surface。
- `comment_generation_mode` 是 generate-only 字段，默认 `on`；`off` 时 workflow 与 agent 生成都跳过 AI 批注生成，不进入 rewrite 链路。
- `content_verify_agent` 的审核结果只保留真实需修复 findings；无问题 / 无需修改会折叠为 `[]`，前端过程卡不应把这类空审核项当成真实问题展示。
- `gngk` 的后端分派依赖 `tender_lx + fund_lx + ifzgcg`，共享真源是 `frontend/lib/gngkFormType.ts`；generate 由 `formDataConverter.ts` 调用该 helper，上传文件 rewrite 由 `ChatPanel.tsx` 调用该 helper，不能绕开 helper 单独改调用点。

### 任务状态、取消与心跳

| 项 | 当前边界 |
| --- | --- |
| API client | `frontend/lib/api.ts` 中的 `getTaskStatus()`, `getTaskList()`, `cancelTask()`, `sendTaskHeartbeat()` |
| 后端路由 | `backend/api/tasks.py` |
| 后端 service | `backend/services/task_service.py` |
| 队列真源 | `backend/task/task_queue_manager.py` |
| 前端轮询 | `frontend/hooks/useCurrentConversationTaskStatus.ts` |
| 前端心跳 | `frontend/hooks/useTaskHeartbeat.ts` |

同步要求：
- 任务状态字段变化必须同步 `backend/models/task.py`、`frontend/types/api.ts`、store task summary 和任务 UI。
- 从 `sessionStorage` 恢复 running task 前，前端必须先查任务状态；404 / `TASK_NOT_FOUND` 收敛成本地中断态。

### 任务 SSE

| 项 | 当前边界 |
| --- | --- |
| 后端路由 | `backend/api/stream.py` 中的 `GET /api/stream/{task_id}` |
| 后端 manager | `backend/core/sse_manager.py` |
| 日志桥接 | `backend/util/log_util/sse_log_handler.py` |
| 前端 URL helper | `frontend/lib/api.ts` 中的 `getTaskStreamUrl()` |
| 前端 runtime | `frontend/lib/sse.ts` |
| 前端映射 | `frontend/hooks/useChatSSE.ts` |
| 前端类型 | `frontend/types/api.ts` |

已确认前端事件类型包括 `connected`、`log`、`llm`、`progress`、`agent_step`、`status`、`error`、`done`、`heartbeat`。

同步要求：
- 新增 SSE 事件类型必须同步后端模型、事件发送、前端 union 类型、`frontend/lib/sse.ts` named event 注册、`useChatSSE` 解析和测试。
- 任务失败必须最终表现为 `error` 或 `done`，不能让 SSE 静默中断。
- `comment_writeback_*` 和 `style_writeback_*` 摘要属于任务结果契约，不得在 state、任务结果或 `done` 事件中丢失。
- `agent_step` 是智能体生成过程事件，允许断线重放和前端过程卡展示，但不替代 `done` / `error` 终态。
- `comment_supplement` 任务复用同一 SSE 通道，`comment_agent` 过程卡仍通过 `agent_step` 展示。

### Agent Run、聊天与任务创建

| 项 | 当前边界 |
| --- | --- |
| 前端调用方 | `frontend/components/chat/ChatPanel.tsx` |
| API client | `frontend/lib/api.ts` 中的 `streamAgentRun()` / `streamNdjson()` |
| 后端路由 | `backend/api/agent.py` 中的 `POST /api/agent/runs/stream` |
| 路由 service | `backend/services/agent_run_service.py` |
| Agent / tool runtime | `backend/agents/task_context_assistant/` |
| 后续 task runtime | `backend/graphs/skill_graph.py`, `backend/graphs/task_skill_workflows.py`, `backend/skills/rewrite/` |

同步要求：
- NDJSON event shape 变化必须同步 `frontend/types/api.ts` 和 `ChatPanel`。
- `selected_skills`、`context_snapshot.uploaded_files` 和 `context_snapshot.rewrite_context` 变化必须同步 `backend/models/agent_run.py`、`frontend/types/api.ts`、`frontend/stores/chatStore.ts` 和 `ChatPanel`。
- `task_accepted` 只负责把 agent run 收敛为“已创建任务”；后续排队、SSE、取消、下载和结果卡仍沿用既有 task / stream 契约，不能在 agent run 自己复制第二套任务状态机。
- `generation_style` 和 `generation_mode` 是 generate-only 字段，不得透传进 rewrite 请求模型、skill state 或 prompt surface。

### Rewrite 任务

| 项 | 当前边界 |
| --- | --- |
| 前端调用方 | 当前右侧聊天通过 `frontend/components/chat/ChatPanel.tsx` 走 `streamAgentRun()`；显式 `$rewrite` / `/rewrite` 和上传 Word 文件都归入 rewrite |
| 上传 helper | `frontend/lib/api.ts` 中的 `uploadFile()` |
| API client | `frontend/lib/api.ts` 中的 `streamAgentRun()`；后台任务由 agent run tool 创建 |
| 后端路由 | `backend/api/agent.py` 中的 `POST /api/agent/runs/stream` |
| 后端 service | `AgentRunService`, `DocumentService.create_rewrite_task()` |
| Skill runtime | `backend/skills/rewrite/`, `backend/graphs/skill_graph.py` |

同步要求：
- `/api/edit`、edit skill、edit task kind 和 `create_edit_task_tool` 已删除；旧调用表现为 404，不做历史会话迁移。
- 上传 Word 文件 rewrite 必须带非空用户重写指令、当前页面 `form_type`、完整锚点、`tender_lx`、`fund_source_lx` 和 `tender_data_snapshot`；缺条件时返回 `needs_input`，不自动猜测文档类型或锚点。
- 上传文件链路优先于会话 rewrite history；rewrite 完成后前端用 SSE `done.output_file` 更新输入框文件卡，后续 rewrite 继续修改最新输出文件。用户删除文件卡后清空上传链路，后续 rewrite 回到会话生成 / 重写历史。

### 补充批注任务

| 项 | 当前边界 |
| --- | --- |
| 前端触发 | `frontend/components/chat/TaskDownloadMessage.tsx`, `frontend/components/chat/MessageList.tsx`, `frontend/components/chat/ChatPanel.tsx` |
| API client | `frontend/lib/api.ts` 中的 `createCommentSupplementTask()` |
| 后端路由 | `backend/api/comment_supplement.py` 中的 `POST /api/comment-supplement` |
| 后端 service | `DocumentService.create_comment_supplement_task()` |
| Graph | `backend/graphs/comment_supplement_graph.py` |
| 共享节点 / 运行时 | `backend/nodes/common_word_nodes/comment_supplement.py`, `backend/nodes/common_word_nodes/comment_agent.py`, `backend/agents/comments/` |

同步要求：
- 补充批注只从初次生成下载卡触发；rewrite 和 comment_supplement 下载卡不应再显示补充批注动作。
- 请求只携带当前会话、当前下载文件路径和模型；后端负责校验 latest `rewrite_state`、`polished_text` 和 source file 是否仍是当前最新文档。
- 成功后必须更新会话 latest `rewrite_state.prepared_doc_path`，让后续 rewrite 基于补充批注后的副本。
- `TaskKind`、任务状态、SSE `done` payload、下载消息和 `agent_step` 过程卡变化必须同步前后端类型与测试。

### 招标详情查询

| 项 | 当前边界 |
| --- | --- |
| 前端调用方 | `frontend/lib/tenderFetch.ts`, `frontend/app/tender/page.tsx`, `frontend/components/forms/TenderFormShared.tsx` |
| API client | `frontend/lib/api.ts` 中的 `fetchTenderDataWithType()` / `fetchTenderData()` |
| 后端路由 | `backend/api/tender.py` 中的 `GET /api/tender/{tender_no}` |
| 后端工具 | `backend/util/common_util/fetch_tender_data.py` |
| 外部配置 | `backend/config/settings.py` 中的 `TENDER_DATA_API_URL` |

同步要求：
- 前端 URL 驱动查数要把必要 URL 参数写入 draft，再由表单初始化读取。
- 外部接口细节不应泄露到前端组件。
- 外部接口返回未支持的 `purchase_method` 时，后端仍返回 `data` 与原始 `type`，并通过 `warning` 提示前端显示黄色“当前采购方式暂不支持”；前端不得把未知采购方式自动映射到现有表单类型，也不得用未知类型自动改写当前页面的类型按钮和生成 graph。

### 上传与下载

| 项 | 当前边界 |
| --- | --- |
| 上传 client | `frontend/lib/api.ts` 中的 `uploadFile()`, `uploadFiles()` |
| 上传 UI | `frontend/components/forms/FileUploader.tsx`, `ChatPanel` 中的上传文件 rewrite |
| 上传路由 | `backend/api/upload.py` |
| 下载 client | `frontend/lib/api.ts` 中的 `downloadFile()`, `getDownloadUrl()` |
| 下载路由 | `backend/api/download.py` |
| 存储 helper | `backend/util/common_util/upload_storage.py` |

同步要求：
- 前端不直接访问本地文件系统或云存储。
- 后端下载路径必须继续受存储 helper 和路径安全规则约束。

### 模板候选

| 项 | 当前边界 |
| --- | --- |
| 前端调用方 | `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/forms/TemplateCandidateDialog.tsx` |
| API client | `frontend/lib/api.ts` 中的 `fetchTemplateCandidates()`, `selectTemplateCandidate()`, `getTemplateCandidateDownloadUrl()` |
| 后端路由 | `backend/api/template_candidates.py` |
| 后端工具 | `backend/util/common_util/template_candidates.py` |
| 排序 service | `backend/services/template_candidate_ranking_service.py` |
| Prompt | `backend/prompts/template_candidate_ranking_prompt.py` |
| 外部配置 | `TEMPLATE_CANDIDATE_API_URL`, `TEMPLATE_CANDIDATE_ALLOWED_HOSTS` |

同步要求：
- 前端只调用项目内 `/api/template-candidates*`。
- 外部列表请求、下载代理、落盘和文件名清洗统一由后端处理。
- AI 排序契约只返回后端生成的 `row_index` 列表，不能要求前端用项目名称反查候选。
- `year < 2025` 或非法年份的模板不可选择，只允许下载参考。

### 会话心跳

| 项 | 当前边界 |
| --- | --- |
| 前端调用方 | `frontend/app/tender/page.tsx` |
| API client | `frontend/lib/api.ts` 中的 `sendConversationHeartbeat()` |
| 后端路由 | `backend/api/conversations.py` |
| 后端 service | `backend/services/conversation_service.py` |

同步要求：
- 浏览器地址栏必须始终反映当前会话身份。
- 后端实例变化时，前端需要收敛本地 running task 状态，避免旧快照误连。

## 类型身份接口

当前有三层身份：

- 前端 UI 类型：`xjcg`、`gngk`、`gjgk`，定义在 `frontend/types/index.ts`。
- 后端 `FormType`：`xjcg_tender`、`gngk_hw_zc_tender`、`gngk_hw_cz_tender`、`gngk_fw_zc_tender`、`gngk_fw_cz_tender`、`gjgk_tender`，定义在 `backend/models/generate.py`。
- 运行态 `tender_type` / family：后端 graph、prompt、replacement 和公共节点会用 family 收敛公开招标差异。

关键同步点：

- `frontend/lib/formDataConverter.ts`
- `frontend/lib/gngkFormType.ts`
- `frontend/components/chat/ChatPanel.tsx`
- `frontend/utils/tenderTypeMapper.ts`
- `frontend/components/chat/tenderFormRegistry.ts`
- `backend/models/generate.py`
- `backend/config/tender_config.py`
- `backend/services/document_service.py`
- `backend/graphs/`
- `backend/states/`

新增招标类型或修改 `gngk` 子类型分派时，必须同步上述两端映射和测试。

当前 `gngk_hw_cz_tender` 是 direct-replace 首次生成类型：后端 `GngkHwCzTenderGraph` 显式绑定财政货物 delete/update 节点，锚点和 content mode 真源位于 `backend/config/tender_config.py`。这不改变前端仍以单一 `gngk` UI 类型承载公开招标的现实。

## 外部集成边界

### LLM 服务商

后端通过 OpenAI-compatible streaming client 调用 DeepSeek、Doubao / Volcengine ARK 和 Qwen / DashScope。调用封装集中在 `backend/util/common_util/llm_stream_utils.py` 和相关服务。初次生成的 `generation_mode=agent` 通过 `backend/agents/generation/` 调用 DeepAgents content agent；批注增强和补充批注通过 `backend/agents/comments/` 调用 `comment_agent`，模型配置仍复用后端 settings。

关键设置位于 `backend/config/settings.py`，包括 provider key、base URL、model、`LLM_STREAM_TIMEOUT_SECONDS` 和模板候选重排 provider。

### Word COM

Word COM 只存在于后端：

- 低层 COM 生命周期：`backend/util/word_util/`
- 业务 helper：`backend/helper/word_helper/`
- graph node：`backend/nodes/`
- graph 锁和进度包装：`backend/graphs/base_graph.py`
- 任务队列：`backend/task/task_queue_manager.py`

新增 Word 能力不得在 API route、service、前端或随意脚本中直接写 pywin32 / COM 调用。

### 外部招标详情与模板 API

- 招标详情：`TENDER_DATA_API_URL` -> `backend/util/common_util/fetch_tender_data.py`。
- 模板候选：`TEMPLATE_CANDIDATE_API_URL` -> `backend/util/common_util/template_candidates.py`。
- 模板下载：必须经过 `TEMPLATE_CANDIDATE_ALLOWED_HOSTS` 和 `validate_template_download_url()`。

## 未证实或当前不存在的接口

- 当前源文档未确认稳定登录、用户认证或权限接口。
- 当前源文档未确认外部数据库、Redis、队列服务或对象存储。
- 当前源文档未确认第三方入站 webhook。
- 当前源文档未确认部署平台或 CI workflow 文件。

这些能力若后续新增，需要先建立代码真源，再同步本文件和对应 `.planning/codebase/` 文档。

## 排查建议

- 接口返回异常：先看 `frontend/lib/api.ts` 的 `ApiError` 包装，再看对应 `backend/api/` route 和 `backend/models/`。
- SSE 卡住：先区分任务是否还存在、队列是否运行、后端是否发出 `error` / `done`，再看 `backend/core/sse_manager.py` 和 `frontend/hooks/useChatSSE.ts`；`agent_step` 不显示时还要检查 `frontend/lib/sse.ts` 是否监听 named event，补充批注还要确认任务类型是 `comment_supplement` 且过程卡来自 `comment_agent`。
- `gngk` 类型不对：同时检查 URL 参数、draft、`gngkFormType`、`formDataConverter`、`ChatPanel` 上传文件 rewrite 调用点、后端 `FormType` 和 `GRAPH_REGISTRY`。
- 模板候选不可选：检查 `year`、blocked reason、后端归一化、AI row_index 重排和前端选择按钮状态。
- Word 写回异常：先看任务队列、graph 锁、protected fields、paragraph boundary helper，再看类型专属 node。
