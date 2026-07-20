# TenderWord 系统地图

**生成日期：** 2026-07-21

本文件是仓库级系统地图，用于帮助后续开发先判断“该看哪里、跨层如何协作、哪些边界不能破坏”。它基于 **2026-07-21** 刷新的子项目事实文档（`backend/.planning/codebase/` 与 `frontend/.planning/codebase/`，对照提交 `e748f16d1a2b253c766008f1a060e3ebba9b2f85`）和根级 `AGENTS.md`、`ARCHITECTURE.md`、`INTERFACES.md`，并参考 `asset/` 知识包与 `docs/` 边界摘要。不替代代码真源、不替代根级文档的执行红线，也不替代子项目事实文档。子项目实现细节请直接看对应 `.planning/codebase/`，本地图只保留系统层。

## 系统目的与仓库形态

TenderWord 是前后端分离的招标文档生成、修改、补充批注和模板复用系统。完整运行依赖 Windows + Word COM：前端是浏览器工作台，负责会话、表单、任务进度和文件交互；后端是 FastAPI + LangGraph + Word COM 执行端，负责 API、任务队列、SSE/NDJSON、LangGraph 工作流、LLM/智能体调用、模板候选代理、招标详情代理、批注 bad case 检索和 Word 文件生成/写回。

核心闭环：

```text
浏览器 / Next.js 工作台
  -> FastAPI /api
  -> TaskQueueManager 任务队列 + SSE
  -> LangGraph tender / rewrite skill / comment_supplement 工作流
  -> Prompt Layer + OpenAI-compatible LLM provider / DeepAgents content_agent / LangChain comment_agent
  -> Word COM 文档操作（写回受 graph 锁、取消检查和进度包装保护）
  -> 生成文件 / 任务结果 / 下载
```

系统完整能力依赖 Windows + Word COM。前端可在 WSL/Linux Node 环境运行，但后端 Word 自动化必须使用 Windows Python、`pywin32` 和本机 Word/WPS COM。无 COM 环境只能覆盖 API shape、service、prompt、retrieval、agent guard 和 helper 纯逻辑。后端开发端口 **8000**，前端 **8502**。

仓库形态（系统层稳定目录）：

| 目录 | 稳定职责 |
| --- | --- |
| `backend/` | FastAPI `/api`、任务队列、SSE/NDJSON、LangGraph、智能体、Prompt Layer、Word COM、外部代理、retrieval、上传下载。 |
| `frontend/` | Next.js 工作台、类型/URL/会话、generate/agent run/rewrite/补充批注 UI、SSE 过程卡、上传下载、模板候选弹窗。 |
| `asset/` | 长期知识包（运行时/Word skill、类型 identity/会话、模板候选）。 |
| `coding_maps/` | 跨子项目系统地图（本文件）。 |
| `docs/` | 工作流向事实说明（`backend.md`、`frontend.md`、`interfaces-runtime.md`、`knowledge-validation.md`）。 |
| `scripts/` | 启动脚本（Windows / WSL 协作入口）。 |

长期业务规则和跨主题回归风险沉淀在 `asset/`，索引是 `asset/README.md`；首次安装和启动入口在 `README.md`。

## 子项目职责表

| 子项目 | 职责 | 关键技术栈 | 事实文档 |
| --- | --- | --- | --- |
| `backend/` | FastAPI `/api`、任务队列、SSE、NDJSON agent run、LangGraph 工作流、DeepAgents/LangChain 智能体、Prompt Layer、Word COM 写回、模板候选代理、招标详情代理、批注 bad case retrieval、上传下载。 | Python 3.12、FastAPI、Uvicorn、Pydantic v2、LangGraph、LangChain、DeepAgents、`pywin32`/Word COM、OpenAI-compatible streaming（DeepSeek/Qwen/Doubao）、Qdrant/embedding（可降级 BM25）。 | `backend/.planning/codebase/` |
| `frontend/` | Next.js 三栏工作台、招标类型表单与 URL 判型、会话/草稿/任务摘要持久化、generate 任务创建、agent run、上传文件 rewrite、补充批注、SSE/agent-step 过程卡、上传下载、模板候选弹窗。 | Next.js 16、React 19、Zustand 5、TypeScript 5、Tailwind 4、Jest、Playwright；包管理器固定 npm，端口 8502；Node `>=20.9.0`。 | `frontend/.planning/codebase/` |
| `asset/` | 跨多轮需求复用的同步面、边界与回归风险；不替代代码真源。 | 三份 topic 知识包 + `asset/README.md` 索引。 | `asset/README.md` |

**可独立维护性：** 前端仅通过 `/api/*` 契约耦合后端；后端内部 service/graph/node/helper 重构只要契约不变即可。前后端均未检测到强制认证层。

## 跨子项目调用链与数据流

### 生成任务主链路（generate）

1. 用户进入 `/tender`，`frontend/app/tender/page.tsx` 解析 URL 参数、建立或选择会话，并按需预取招标数据。
2. `frontend/components/forms/TenderFormShared.tsx` 以 `draft > URL > default` 初始化，收集招标数据、模板文件（`fileType="template"`）、技术参数文件（`fileType="params"`）、模板候选、插入锚点、generate-only 字段（`generation_style` / `generation_mode` / `comment_generation_mode` / `style_writeback_mode`）和模型。
3. `frontend/components/chat/FormPanel.tsx` 经 `tenderFormConverterMap[conversation.tenderType]` 选择转换器。
4. `frontend/lib/formDataConverter.ts` 把前端 `TenderType` 转为后端 `GenerateRequest`，只提交 `file_paths.template` 与 `file_paths.tender_params`；其中 `gngk` 后端 `form_type` 由共享 helper `frontend/lib/gngkFormType.ts`（`resolveGngkFormType`）按 `tender_lx + fund_lx + ifzgcg` 分派。工程类（`tender_lx` 1/2）当前复用服务链路 `gngk_fw_*`（产品临时策略）。
5. `frontend/lib/api.ts` 的 `createGenerateTask()` 调用 `POST /api/generate`。
6. `backend/api/generate.py` 委派 `backend/services/document_service.py`；`DocumentService` 从 `GRAPH_REGISTRY`（6 种 form type）选 graph，`_build_initial_state()` 装配初始 state（只写 `template_path` + `tender_param_paths`，以及 generate-only 字段），`_submit_graph_task()` 提交 `TaskQueueManager`。
7. `backend/graphs/base_graph.py` 的 `StandardTenderWorkflowGraph` 执行共享主干：
   - `prepare_template -> extract_tender_params`
   - 并行 Word 操作子图与生成分支
   - `generation_mode_gate`：`workflow` → `generate_polished_text`，`agent` → 公共 `content_agent`
   - 两路正文汇合到共享 **`annotate_corrections`（仅首次 generate 接入；`RewriteSkillGraph` / `CommentSupplementGraph` 不接入）**：先规范条款标识（如 `△/Δ→▲`、`*/※→★`），再按技术参数与最终正文比较，仅对可确定事实变化产出固定句式更正批注；**编号/项目符号/展示壳变化不得生成事实更正批注**（编号隔离）
   - 再按 `comment_generation_mode` 决定普通批注分支，`update_word` 写回
   - `update_word` **先写 `correction_comments` 再写普通 `polished_comments`**；`comment_generation_mode=off` / `suppress_ai_comment_writeback` **只跳过普通 AI 批注，不跳过更正批注**
   - 最后按 `generation_mode=agent && comment_generation_mode=on` 决定是否进入公共 `comment_agent`
8. Word 业务逻辑经 `backend/helper/word_helper/` 和 `backend/util/word_util/`；prompt 经 `backend/prompts/`；正文智能体在 `backend/agents/generation/`，批注智能体在 `backend/agents/comments/`。
9. `generation_mode=agent` 路径中，技术参数结构化表以 `[[TABLE:<id>]]` 作为内部写回入口；占位符识别在 `backend/agents/generation/table_placeholder_utils.py`，按 sidecar 恢复/丢弃在 `backend/helper/word_helper/text_parsing.py`，`table_id` 字符集与 `backend/util/word_util/table_models.py` 一致。`content_verify_agent` 只保留真实需修复 findings，无问题折叠为 `[]`。
10. `DocumentService` 收敛 output file、file size、model、style/comment writeback 摘要，通过 `TaskQueueManager` + `SSEManager` 推送 `done` 或 `error`；前端经 `useChatSSE.ts` 更新任务消息、智能体过程卡和下载入口。

### 任务状态、SSE 与下载回流

- 前端任务创建/查询/取消/心跳/下载统一经 `frontend/lib/api.ts`（`getTaskStatus`、`getTaskList`、`cancelTask`、`sendTaskHeartbeat`、`getTaskStreamUrl`、`downloadFile`、`getDownloadUrl`）。
- 后端任务生命周期在 `backend/task/task_queue_manager.py`（公平锁、进度、取消、心跳、清理），API 展示在 `backend/api/tasks.py` 和 `backend/services/task_service.py`。
- SSE 后端入口是 `backend/api/stream.py`（`GET /api/stream/{task_id}` 及 `/status`），事件缓冲/重放/threadsafe 调度在 `backend/core/sse_manager.py`，日志桥接在 `backend/util/log_util/sse_log_handler.py`；后端 SSE event enum 含 `log`、`llm`、`progress`、`node_start`、`node_complete`、`agent_step`、`done`、`error`、`heartbeat`。
- 前端 SSE runtime 是 `frontend/lib/sse.ts`（包装 `EventSource`，注册 named events：`connected`、`log`、`llm`、`progress`、`agent_step`、`status`、`error`、`done`、`heartbeat`）；事件到 UI 的映射是 `frontend/hooks/useChatSSE.ts`。注意 `connected`、`status` 是前端连接/映射层事件，不是后端真实事件；`node_start`、`node_complete` 是后端事件但不在前端 named event 列表中。
- 从 `sessionStorage` 恢复 running task 前必须先查任务状态；404 / `TASK_NOT_FOUND` 收敛成本地中断态。刷新后内存 `chatStreamStore` 为空时，当前实现会强制从起点回放 SSE（即使 session 仍有 `lastEventId`）。
- 下载由 `backend/api/download.py`（受 `UPLOAD_DIR` containment 校验）保护；历史侧栏用相对 `/api/download/...` 链接经 Next rewrite 代理。
- 根级 `/health`、`/health/ready`、`/health/live` 只代表应用进程层状态；`/health/ready` 的 `upload_dir_accessible` 当前固定为 `True`，不代表 Word COM / LLM / 外部 HTTP 真实可用。
- 注意：`GET /api/generate/{task_id}` 完成态返回 shape 与 `GET /api/tasks/{task_id}` / SSE `done` 不同源；完整结果优先走任务查询或 SSE 终态，不要把 generate 查询当唯一结果源。

### 任务上下文助手 / Rewrite（NDJSON 回流 + RewriteSkillGraph）

- 右侧聊天统一从 `frontend/components/chat/ChatPanel.tsx` 经 `streamAgentRun()` 调用 `POST /api/agent/runs/stream`，返回 NDJSON agent run 事件。
- 后端编排真源是 `backend/services/agent_run_service.py`（客观不可执行 preflight、NDJSON 事件映射和审计落盘）；NDJSON 行序列化复用 `backend/services/chat_stream_service.py` 的 `to_ndjson_line()`。
- agent run 必须先流出 `run_started` 和 `thinking_stage: understand completed`，再由 task-context assistant 决定 `needs_input`（追问）或经 `create_rewrite_task_tool` 创建 rewrite 任务（`task_accepted`）。
- task-context assistant 运行时在 `backend/agents/task_context_assistant/`：只允许受控 `rewrite` skill（`TASK_CONTEXT_ASSISTANT_ALLOWED_SKILLS=("rewrite",)`）、只读摘要工具，并通过 `CompositeBackend` 分隔 `/skills/`、`/scratch/`、`/workspace/`。
- `task_accepted` 后 agent run 即结束；后续排队、**显式 `RewriteSkillGraph`** 执行、SSE、取消和下载继续沿用既有任务主链路，不在 agent run 里复制第二套任务状态机。
- `RewriteSkillGraph`（`backend/graphs/skill_graph.py`）显式 6 节点 + 条件边：`resolve_rewrite_target` →（`uploaded_file` 时）`extract_rewrite_context` → `rewrite_text` / 可选 `get_rewrite_comments` → `delete_section` → 汇合 `update_word`。分支判定在 `backend/skills/rewrite/scripts/runtime.py`（`select_resolve_branch` / `select_comment_branch`，按 `rewrite_source` / `source_document_path` 分派）。删除与写回经 `dispatch_tender_aware_*` 按类型路由。
- 上传 Word 文件后的修改统一归入 rewrite：前端用 `rewrite_source` 文件类型（`uploadFile(file, 'rewrite_source')`），`context_snapshot.uploaded_files` 提供文件摘要，`context_snapshot.rewrite_context` 提供当前页面 `form_type`、锚点、`tender_lx`、`fund_source_lx` 和可选招标数据快照；后端 task skill state 用 `rewrite_source="uploaded_file"` 路由。
- 上传文件 rewrite 必须有非空用户重写指令、文件路径、完整锚点、`tender_lx`、`fund_source_lx`；`tender_data_snapshot` 只是可选快照，缺招标数据不阻断。缺必需条件只返回 `needs_input`。rewrite 完成后前端用 SSE `done.output_file` 回写文件卡，下一轮 rewrite 基于最新输出。
- 上传文件 rewrite 的 task graph 必须保持**单次 Word 删除**语义（`extract_rewrite_context -> rewrite_text -> delete_section -> update_word`），避免 `delete_section` 执行两次并与 `update_word` 并发抢 COM。
- `/api/edit`、edit skill、edit task kind、`create_edit_task_tool` 已删除；旧调用表现为 404，不做历史会话迁移。不要恢复 `SkillGraph.for_skill + TaskSkillWorkflow` 元数据驱动框架。
- agent run 审计日志只写白名单结构化字段并 scrub；只读工具只返回 rewrite 可用性、公共进度和摘要。

### 补充批注任务（comment_supplement）

- 仅从初次 generate 下载卡触发（`TaskDownloadMessage` 对 `taskKind === 'generate'` 显示入口）；rewrite 和 comment_supplement 下载卡不再显示该动作。
- `frontend/lib/api.ts` 的 `createCommentSupplementTask()` 调用 `POST /api/comment-supplement`；请求只携带会话、当前下载文件路径和模型。
- `DocumentService.create_comment_supplement_task()` 校验 `conversation_id`、`source_file`、latest `rewrite_state`、`polished_text` 和当前文件是否仍是会话 latest 文档后，提交 `CommentSupplementGraph`（`prepare_comment_supplement -> comment_agent -> finalize_comment_supplement`）。
- 复制当前文档副本，调用 `backend/agents/comments/` 的 `comment_agent` 生成/校验/写回批注；批注写回统一收敛到 `backend/nodes/common_word_nodes/comment_writeback.py::write_polished_comments()`。
- **同锚点写回语义：** 标准写回默认 `allow_existing_comments=False`（跳过已有批注重叠锚点）；`comment_agent` 显式 `allow_existing_comments=True` 允许同锚点追加。
- 职责隔离：技术参数差异批注只由 `annotate_corrections` 产出；`comment_agent` 不得生成“原技术参数为…现改为…”类差异批注。
- 完成后更新会话 latest `rewrite_state.prepared_doc_path`，后续 rewrite 基于补充批注后的副本。复用同一 SSE / `agent_step` 过程卡 / 下载链路。

### 模板候选

- 前端只调用项目内 `/api/template-candidates*` helper（`fetchTemplateCandidates`、`selectTemplateCandidate`、`getTemplateCandidateDownloadUrl`）。
- 模板候选 UI 在 `frontend/components/forms/TemplateCandidateDialog.tsx`，表单回填在 `frontend/components/forms/TenderFormShared.tsx`（组件状态内按 `tenderNo + projectName` 缓存候选与 ranking）。
- 后端代理、下载、选择、落盘在 `backend/api/template_candidates.py` 和 `backend/util/common_util/template_candidates.py`（外部下载链接受 `TEMPLATE_CANDIDATE_ALLOWED_HOSTS` 白名单约束）。
- AI 重排在 `backend/services/template_candidate_ranking_service.py`，prompt 在 `backend/prompts/template_candidate_ranking_prompt.py`；排序契约只返回后端生成的 `row_index` 列表。`year < 2025` 或非法年份的模板不可选择，只允许下载参考。

### 招标详情查询

- 前端经 `frontend/lib/tenderFetch.ts` + `fetchTenderDataWithType()` 调用 `GET /api/tender/{tender_no}`。
- 后端经 `backend/util/common_util/fetch_tender_data.py` 代理外部 `TENDER_DATA_API_URL`。
- 外部返回未支持的 `purchase_method` 时，后端仍返回 `data` 与原始 `type`，并通过 `warning` 提示；前端不得把未知采购方式自动映射到现有表单类型。

## 后端到前端的接口边界

接口字段以代码真源为准：`backend/api/`、`backend/models/`、`frontend/lib/api.ts`、`frontend/types/api.ts`。跨端规则沉淀在 `docs/interfaces-runtime.md` 与 `INTERFACES.md`。

| 边界 | 前端入口 | 后端入口 | 关键同步要求 |
| --- | --- | --- | --- |
| API client | `frontend/lib/api.ts` | `backend/api/`（全部 `/api` 前缀） | API shape 变化同步 `frontend/types/api.ts`、后端 `backend/models/` 和测试。 |
| 本地 API 代理 | `frontend/lib/apiBaseUrl.ts`、`frontend/next.config.ts` | `backend/main.py` | `NEXT_PUBLIC_API_URL`（可逗号分隔多候选）同时影响浏览器 base URL、Next rewrite 目标和开发期 `allowedDevOrigins`。 |
| 招标类型身份 | `frontend/types/index.ts`、`frontend/utils/tenderTypeMapper.ts`、`frontend/lib/gngkFormType.ts`、`frontend/lib/formDataConverter.ts`、`frontend/components/chat/ChatPanel.tsx` | `backend/models/generate.py`、`backend/config/tender_config.py`、`backend/services/document_service.py`、`backend/graphs/` | 新增/改类型同步前端 UI 类型、后端 `FormType`、URL、graph/state/node、anchor 和测试。 |
| 会话和 URL | `frontend/stores/chatStore.ts`、`frontend/utils/tenderTypeMapper.ts`、`frontend/hooks/useUrlParams.ts`、`frontend/app/tender/page.tsx` | `backend/api/conversations.py`、`backend/services/conversation_service.py` | 地址栏始终反映当前会话身份；后端 `instance_id` 变化时前端收敛本地 running task。 |
| 任务与 SSE | `frontend/hooks/useChatSSE.ts`、`frontend/lib/sse.ts`、`frontend/stores/*` | `backend/api/stream.py`、`backend/core/sse_manager.py`、`backend/models/sse.py`、`backend/task/task_queue_manager.py` | 新增 SSE 事件同步后端 `SSEEventType`、前端 union、`sse.ts` named event、`useChatSSE` 解析和测试。 |
| Agent run / rewrite | `frontend/components/chat/ChatPanel.tsx`、`frontend/lib/api.ts`、`frontend/types/api.ts` | `backend/api/agent.py`、`backend/services/agent_run_service.py`、`backend/agents/task_context_assistant/`、`backend/graphs/skill_graph.py` | `task_accepted` 后交既有 task/SSE 链路；`needs_input` 不创建后台任务；NDJSON 行复用 `to_ndjson_line()`。 |
| 补充批注 | `frontend/components/chat/TaskDownloadMessage.tsx`、`frontend/components/chat/MessageList.tsx`、`frontend/lib/api.ts` | `backend/api/comment_supplement.py`、`backend/services/document_service.py`、`backend/graphs/comment_supplement_graph.py` | 成功后更新 latest `rewrite_state.prepared_doc_path`；同步 `TaskKind`、SSE `done`、下载卡语义。 |
| 招标详情 | `frontend/lib/tenderFetch.ts`、`frontend/lib/api.ts` | `backend/api/tender.py`、`backend/util/common_util/fetch_tender_data.py` | 外部接口细节不泄露到前端组件；未知采购方式只 warning。 |
| Word 运行时 | 无前端直接入口 | `backend/graphs/`、`backend/nodes/`、`backend/helper/word_helper/`、`backend/util/word_util/` | 前端不触碰 COM；后端新增 graph/node/tool 不得绕过队列、graph 锁、取消检查和进度包装。 |
| Prompt / LLM / 智能体 | 无前端直接入口 | `backend/prompts/`、`backend/agents/generation/`、`backend/agents/comments/`、`backend/util/common_util/llm_stream_utils.py`、`backend/agents/generation/model_factory.py` | prompt 渲染、智能体协议、超时、解析和结构校验集中维护；新增 LLM provider 同步 `settings.py`、`MODEL_CONFIGS`、model factory。 |
| 模板候选 | `frontend/components/forms/TemplateCandidateDialog.tsx`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/lib/api.ts` | `backend/api/template_candidates.py` | 前端不得直接调用外部候选接口或外部文件 URL。 |
| 上传 / 下载 | `frontend/lib/api.ts`、`frontend/components/forms/FileUploader.tsx` | `backend/api/upload.py`、`backend/api/download.py`、`backend/util/common_util/upload_storage.py` | 下载路径 containment；上传扩展名/大小校验。 |

### 跨层枚举与关键约定

- **Task type（`TaskKind`）：** 跨层枚举 `generate` / `rewrite` / `comment_supplement`，定义在 `frontend/types/api.ts`，被 `parseTaskKind`、SSE/agent 事件解析和 `chatStore` 共享。新增任务类型必须同步后端 `TaskKind`、前端 union、SSE 终态、下载卡和会话结果语义。
- **Task status：** `queued` / `running` / `completed` / `failed` / `cancelled`。
- **Tender type（UI）：** 前端 `xjcg` / `gngk` / `gjgk`（`frontend/types/index.ts`），由 `purchase_method` 判定（`5→xjcg`、`2→gngk`、`0→gjgk`）；`tender_lx`/`fund_lx` 不参与前端 UI 顶层判型，但参与 `gngk` 会话 identity 与 form 分派。
- **Form type（`GenerateRequest.form_type`）：** `xjcg_tender`、`gngk_hw_zc_tender`、`gngk_hw_cz_tender`、`gngk_fw_zc_tender`、`gngk_fw_cz_tender`、`gjgk_tender`（`backend/models/generate.py`）。
- **运行态 `tender_type` / family：** graph state 用 `form_type.value.replace("_tender", "")` 去后缀；`get_tender_type_family()` 把所有 `gngk_*` 归并为 `gngk`。
- **gngk 分派：** `gngk` 在前端是单一 UI 类型，提交后端时必须由 `frontend/lib/gngkFormType.ts` 的 `resolveGngkFormType({ tender_lx, fund_lx, ifzgcg })` 分派。两个调用点都走该 helper：generate 经 `formDataConverter.ts`，上传文件 rewrite 经 `ChatPanel.tsx`（`resolveRewriteFormType`）。不能绕开 helper 单独改调用点。
- **generate-only 字段：** `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 只出现在 `GenerateRequest` 和生成 draft（`TenderFormShared.tsx`），不得进入 rewrite 请求模型（`AgentRunStreamRequest` / `AgentRunRewriteContextSnapshot`）、skill state 或 prompt surface。注意：后端 `TaskSkillGraphState` 结构上继承了 generate base state 字段面（技术债），运行时仍不得主动填入或从 generate state 整包拷贝。
- **rewrite_source：** 上传文件 rewrite 前端用 `rewrite_source` 文件类型；后端 task skill state 用 `rewrite_source="uploaded_file"` 标记来源并穿过 LangGraph schema。前端 `FileType` 另含 `template` / `params` / `qualification`。
- **Agent run NDJSON 事件：** `run_started`、`thinking_stage`、`tool_call`、`task_accepted`、`needs_input`、`done`、`error`；未知事件在前端 parser 白名单外静默丢弃。

## 共享状态、存储、运行时与外部集成边界

以下边界均已被源文档确认；尚未确认的能力见“当前源文档未确认”。

- **前端持久化：** 会话、草稿、任务摘要、未读结果用 `sessionStorage`（`chatStore.ts` → `chat-storage`）；task resume 元数据在 `chatTaskSessionStore.ts`（`chat-task-session-storage`）；最近历史在 `historyStore.ts`（`tender-history-storage`）；`useAppStore.ts`（`tender-app-storage`，Zustand 默认 `localStorage`）只存 `sidebarOpen`。
- **前端运行时态：** 活跃 SSE 文本、日志、进度、当前节点、未完成 agent step 快照是内存态，在 `chatStreamStore.ts`，不持久化完整 stream payload。
- **后端状态：** 任务、取消事件、任务结果、SSE event buffer、conversation rewrite history、retrieval runtime cache 当前是进程内状态，服务重启不恢复。
- **后端文件存储：** 上传文件、模板选择结果、生成产物、下载文件位于 `settings.UPLOAD_DIR`；content agent workspace 在 `backend/context_log/content_agent_workspace/`，comment agent audit 在 `backend/context_log/comment_agent_audit/`，agent run audit JSONL 在 `backend/logs/`，进度/执行/prompt/skill audit/SSE 日志由 `backend/util/log_util/` 管理（启动时清理，`backend/logs` 上限约 200MB）。
- **数据库：** 当前源文档未确认外部关系数据库、ORM、migration、Redis、独立 cache service 或对象存储。
- **外部集成：** LLM provider（DeepSeek / Qwen-DashScope / Doubao-ARK，均 OpenAI-compatible streaming，可选 LangSmith）、招标详情接口、模板候选接口、Word COM、批注 bad case retrieval（Qdrant + embedding，失败降级 BM25）。
- **retrieval 边界：** `backend/retrieval/` 是批注 prompt 增强正式运行时，正式接入点只包括 `generate_comments`、自主生成模式 `comment_agent` 和 `comment_supplement`；rewrite 和 `comment_generation_mode=off` 不触发检索。hybrid 失败降级到 `bm25_only`；检索状态、日志路径或命中详情**不进入** SSE、下载卡或 `agent_step`。
- **认证：** 前后端均未检测到强制认证/鉴权层或稳定 `Authorization` header；`conversation_id` / `user_session_id` / `task_id` 只用于运行态连续性，不是安全身份。
- **本地运行环境：** Windows 完整闭环（Windows Python 3.12 + `pywin32` + Word/WPS COM + `backend/.env` + 可写 `UPLOAD_DIR`）；WSL 场景下前端可在 Linux Node 运行，后端 Word 自动化仍需 Windows COM。
- **生产托管 / CI：** 当前源文档未确认稳定生产托管配置、`vercel.json`/`Dockerfile`/`docker-compose` 或仓库级 CI workflow（`.github/workflows/` 未检测到）。

## 子项目依赖与归属规则

- 前端所有后端请求统一走 `frontend/lib/api.ts`；组件不写裸 `fetch`，也不直接访问外部模板候选 URL。该约定当前主要靠评审和测试维护，没有专门 lint 规则兜底。
- 后端跨包导入统一用 `backend.*` 包绝对路径；API router 保持薄入口，业务编排放 service / graph / node / helper。
- Word COM 是稀缺临界资源：新增 Word 能力不得在 API route、service、前端或随意脚本中直接操作 COM，必须经 `DocumentService` → `TaskQueueManager`（公平锁 `wait_for_turn`）→ graph 锁（`CrossProcessFileLock` + `msvcrt.locking`）→ 节点取消检查 → 进度包装 → `backend/util/word_util/`（`com_lock()`）。
- 初次生成用 `StandardTenderWorkflowGraph` 共享主干，类型差异通过 graph class attribute（`STATE_CLS` / `NODE_*` / `get_word_operation_steps()` / `get_post_update_steps()`）绑定，不复制 `build_graph()`；`generation_mode` / `comment_generation_mode` / `comment_agent` / `annotate_corrections` 分流只在基类实现。
- rewrite 用显式 `RewriteSkillGraph`，图结构真源在 `backend/graphs/skill_graph.py`，分支判定集中在 `backend/skills/rewrite/scripts/runtime.py`；不要恢复 `SkillGraph.for_skill + TaskSkillWorkflow` 元数据驱动框架。
- 批注写回统一收敛到 `write_polished_comments`；差异批注归 `annotate_corrections`，合规批注归 `comment_agent`。
- Prompt Layer 只做渲染与机器契约解析，不承载 SSE、COM 或 session state。
- 子项目事实变化应先更新对应 `.planning/codebase/`；长期边界进入 `asset/`；影响多数未来需求的规则上提到 `AGENTS.md`。本 skill 只输出 `coding_maps/SYSTEM_MAP.md`，不改根级导航文档。

## 按任务分类的阅读指南

### 后端业务、API、存储、runner 修改

先读：

- `AGENTS.md`
- `docs/backend.md`
- `backend/.planning/codebase/ARCHITECTURE.md`
- `backend/.planning/codebase/STRUCTURE.md`
- `backend/.planning/codebase/INTEGRATIONS.md`
- `backend/.planning/codebase/CONVENTIONS.md`
- 风险面：`backend/.planning/codebase/CONCERNS.md`

再按任务读取：

- 任务与队列：`backend/task/task_queue_manager.py`、`backend/services/document_service.py`
- 任务上下文助手 / rewrite：`backend/api/agent.py`、`backend/services/agent_run_service.py`、`backend/agents/task_context_assistant/`、`backend/graphs/skill_graph.py`、`backend/skills/rewrite/`
- SSE：`backend/core/sse_manager.py`、`backend/api/stream.py`、`backend/models/sse.py`
- 补充批注：`backend/api/comment_supplement.py`、`backend/graphs/comment_supplement_graph.py`、`backend/nodes/common_word_nodes/comment_supplement.py`、`backend/agents/comments/`
- 更正批注 / 编号隔离：`backend/nodes/common_word_nodes/annotate_corrections.py`、`backend/helper/word_helper/clause_marker_normalize.py`、`backend/nodes/common_word_nodes/comment_writeback.py`
- 特殊字形 / 自动编号抽取：`backend/util/word_util/word_extraction_utils.py`、`backend/util/word_util/word_symbol_tokens.py`、`backend/helper/word_helper/content_ops.py`
- 字段替换长度门禁：`backend/nodes/common_word_nodes/replace_content.py`（`WORD_FIND_TEXT_MAX_LEN`）、`backend/nodes/common_word_nodes/get_replacements_core.py`
- Prompt / skill / 智能体：`backend/prompts/`、`backend/skills/`、`backend/agents/generation/`、`backend/agents/comments/`
- 检索：`backend/retrieval/`
- Word 业务：`asset/shared_runtime_word_skill_knowledge_pack.md`

### 前端工作区、状态、上传、产物、SSE 修改

先读：

- `AGENTS.md`
- `docs/frontend.md`
- `frontend/.planning/codebase/ARCHITECTURE.md`
- `frontend/.planning/codebase/STRUCTURE.md`
- `frontend/.planning/codebase/INTEGRATIONS.md`
- `frontend/.planning/codebase/CONVENTIONS.md`
- `frontend/.planning/codebase/TESTING.md`
- 风险面：`frontend/.planning/codebase/CONCERNS.md`

再按任务读取：

- 类型身份与会话：`asset/tender_type_identity_session_knowledge_pack.md`
- API client：`frontend/lib/api.ts`
- URL 映射：`frontend/utils/tenderTypeMapper.ts`、`frontend/hooks/useUrlParams.ts`
- 表单：`frontend/components/forms/TenderFormShared.tsx`、`frontend/components/forms/tenderFormConfig.ts`
- 聊天任务：`frontend/components/chat/ChatPanel.tsx`、`frontend/components/chat/FormPanel.tsx`
- Agent run：`frontend/lib/api.ts`、`frontend/types/api.ts`、`frontend/components/chat/ChatPanel.tsx`、`frontend/lib/agentThinking.ts`
- 智能体过程卡：`frontend/hooks/useChatSSE.ts`、`frontend/stores/chatStore.ts`、`frontend/stores/chatStreamStore.ts`、`frontend/components/chat/TaskContentMessage.tsx`
- 补充批注动作：`frontend/components/chat/TaskDownloadMessage.tsx`、`frontend/components/chat/MessageList.tsx`

### 跨系统接口修改

必须同时读：

- `docs/interfaces-runtime.md`
- `INTERFACES.md`
- `backend/models/`
- `backend/api/`
- `frontend/types/api.ts`
- `frontend/lib/api.ts`
- 相关前后端测试

接口变更不能只改一侧。

### 视觉或 UX 修改

先读：

- `frontend/.planning/codebase/ARCHITECTURE.md`
- `frontend/.planning/codebase/CONVENTIONS.md`
- `frontend/.planning/codebase/TESTING.md`

涉及真实浏览器交互、页面跳转、会话恢复、模板弹窗或任务进度展示时，最终回归入口是 `frontend/e2e/test_*.spec.ts` 和 `npm run test:e2e`（当前 E2E 覆盖 home、URL/conversation、表单上传槽、agent run chat panel、补充批注、generation_mode=agent）。注意 `DualColumnMessage` / `NewChatPopup` / 部分 Skeleton 当前未接入主流程。

### 领域流程或报告生成修改

先读：

- `asset/shared_runtime_word_skill_knowledge_pack.md`（generate / rewrite / comment_supplement 运行时、Word skill、SSE 透传、批注/样式回写）
- `asset/tender_type_identity_session_knowledge_pack.md`（类型 identity、graph/state/node/replacement 收敛）
- `asset/template_candidate_pipeline_knowledge_pack.md`（模板候选与智能抽取）
- `backend/.planning/codebase/ARCHITECTURE.md`（数据流与关键抽象）
- 对应 graph / node / helper / converter / `gngkFormType` 和测试

### 模板候选修改

先读：

- `asset/template_candidate_pipeline_knowledge_pack.md`
- `backend/.planning/codebase/INTEGRATIONS.md`
- `frontend/.planning/codebase/INTEGRATIONS.md`

重点同步：`backend/api/template_candidates.py`、`backend/util/common_util/template_candidates.py`、`backend/services/template_candidate_ranking_service.py`、`frontend/lib/api.ts`、`frontend/components/forms/TemplateCandidateDialog.tsx`、`frontend/components/forms/TenderFormShared.tsx`。

### 批注写回 / 编号隔离 / 更正批注修改

先读：

- `asset/shared_runtime_word_skill_knowledge_pack.md`
- `backend/.planning/codebase/CONCERNS.md`（近期风险：编号隔离与同锚点写回）
- `docs/backend.md`（`annotate_corrections` 与写回顺序）

重点同步：

- `backend/nodes/common_word_nodes/annotate_corrections.py`
- `backend/nodes/common_word_nodes/comment_writeback.py`
- `backend/nodes/common_word_nodes/comment_agent.py`
- `backend/agents/comments/`
- 对应测试：`backend/tests/nodes/test_annotate_corrections.py`、`test_comment_writeback.py`、`backend/tests/agents/test_comment_agent.py`

## 集成风险检查清单

- API 形状变化是否同步后端模型、前端类型、API client 和测试（前后端类型为手写镜像，无自动生成）。
- 前端新增请求是否仍经过 API client；当前没有 lint 规则自动阻止组件或 hooks 写裸 `fetch`，评审时要人工检查。
- `gngk` 的 `tender_lx + fund_lx + ifzgcg` 分派是否集中在 `frontend/lib/gngkFormType.ts`，且 `formDataConverter.ts`（generate）与 `ChatPanel.tsx`（rewrite）是否都调用该 helper；工程类复用 `gngk_fw_*` 若拆独立 graph 是否两端同步。
- 生成文件契约是否仍是 `template + tender_params`，后端初始 state 是否只装配 `template_path + tender_param_paths`。
- `generation_style` / `generation_mode` / `comment_generation_mode` / `style_writeback_mode` 是否仍为 generate-only，没有进入 rewrite 请求模型、skill state 或 prompt surface；是否未从 generate state 整包拷贝到 `TaskSkillGraphState`。
- 上传文件 rewrite 是否仍用前端 `rewrite_source` 文件类型，并在后端 task skill state 中通过 `rewrite_source="uploaded_file"` 路由；是否未恢复旧 edit 入口。
- 上传文件 rewrite 是否保持单次 Word 删除（`extract_rewrite_context -> rewrite_text -> delete_section -> update_word` 分支语义），避免 `delete_section` 执行两次并与 `update_word` 并发抢 Word COM。
- 新增/修改 SSE 事件是否同步后端 `SSEEventType`、前端 union、`frontend/lib/sse.ts` named event、`useChatSSE` 和测试；是否区分后端真实事件与前端 `connected` / `status` 包装/映射事件。
- 新增/修改任务类型是否同步 `TaskKind`、任务状态、SSE `done` payload、下载卡和会话结果语义。
- Agent run 是否只在 `task_accepted` 后启动后台任务；NDJSON 行是否复用 `to_ndjson_line()`；agent run 审计/摘要工具是否仍只暴露 scrub 后白名单字段。
- Word COM 相关改动是否仍经过任务队列、graph 锁、取消检查和进度包装。
- Prompt、LLM 流式、`content_agent` 或 `comment_agent` 改动是否复用 `LLM_STREAM_TIMEOUT_SECONDS`，并保留 Prompt Layer 与智能体协议边界；content agent draft/revision/final 是否接入统一 sanitizer。
- `content_verify_agent` 是否只输出真实需修复 findings，并把“无问题 / 无需修改”折叠为 `[]`；audit 是否保持合法 JSON 数组形状。
- content agent 正文是否把 `[[TABLE:<id>]]` 作为内部写回入口交给后端写回层处理；占位符识别、sidecar 恢复/丢弃和 `table_id` 字符集是否与 `backend/util/word_util/table_models.py` 一致。
- **`annotate_corrections` 编号隔离：** 编号/项目符号/展示壳变化是否不生成事实更正批注；重要性标识 `*/※→★`、`△/Δ→▲` 是否仍生成/保留；是否未把编号隔离逻辑散落到 writeback 层。
- **批注写回同锚点：** 标准写回是否仍默认跳过重叠锚点；`comment_agent` 是否显式 `allow_existing_comments=True`；差异批注是否仍只由 annotate 产出。
- **特殊字形 / 自动编号：** 抽取是否仍产出 `[[WORD_SYMBOL:...]]` 或可见 Unicode 而非静默丢弃；`extract_text_with_list_numbers` 是否仍恢复 List 编号；写回字体恢复失败是否 fail-fast。
- **Find 256：** 替换查找串超长是否跳过并记日志，而非强行 COM Find。
- `update_word` 是否仍先写更正批注再写普通批注；`comment_generation_mode=off` 是否不关闭更正批注。
- `backend/retrieval/` 改动是否仍限制在批注 prompt 增强边界内，不进入 rewrite 或 `comment_generation_mode=off`；检索状态/日志路径/命中详情不进入 SSE、下载卡或 `agent_step`。
- 模板候选改动是否仍由后端代理外部列表、文件下载和 `TEMPLATE_CANDIDATE_ALLOWED_HOSTS` 白名单校验；AI 排序是否只返回 `row_index`。
- 前端 running task 恢复是否先查任务状态（404 / `TASK_NOT_FOUND` 收敛成本地中断态），避免直接连接已不存在的 SSE。
- 文件下载是否仍受 `settings.UPLOAD_DIR` containment 校验。
- 任务结果 / SSE `done` 是否仍透传 `comment_writeback_*` 与 `style_writeback_*` 摘要。

## 验证入口

- 后端常规验证：在 `backend/` 运行 `.\.venv\Scripts\python.exe -m pytest tests -v`（pytest + pytest-asyncio，async 测试需显式 `@pytest.mark.asyncio`）。当前约 **87** 个 `test_*.py`（2026-07-21 fact doc）。
- 后端 Word 闭环验证：必须回到 Windows + Word/WPS COM 环境；无 COM 环境只能覆盖 API shape、service、prompt、retrieval、agent guard 和 helper 纯逻辑。诊断脚本：`backend/scripts/diagnose_word.py`（不得作为业务写回旁路）。
- 前端常规验证：在 `frontend/` 运行 `npm run lint`、`npm run type-check`、`npm run test`（Jest；约 **31** 个 unit 文件）。
- 前端 E2E：在 `frontend/` 运行 `npm run test:e2e`（Playwright；**6** 个 spec：home、URL/conversation、表单上传槽、agent run chat panel、补充批注、generation_mode=agent）。
- 文档型变更：根目录运行 `git diff --check`，并扫描文档中的密钥/token 模式；仅文档变更不需要跑代码测试或 E2E。

本次系统地图是文档层产物；具体功能验证仍以受影响代码路径的测试要求为准。

## 当前源文档未确认

下列能力当前源文档未确认，若后续新增需先建立代码真源，再同步本文件和对应 `.planning/codebase/`：

- 稳定登录、用户认证、鉴权中间件或权限接口（前后端均无）。
- 外部关系数据库、ORM、migration、Redis、独立 cache service 或对象存储。
- 第三方入站 webhook。
- 生产托管配置、`vercel.json` / `Dockerfile` / `docker-compose` 或仓库级 CI workflow。

## 源文档索引

本轮综合使用的源文档：

- 根级：`AGENTS.md`、`ARCHITECTURE.md`、`INTERFACES.md`、`README.md`（导航）
- 工作流文档：`docs/backend.md`、`docs/frontend.md`、`docs/interfaces-runtime.md`、`docs/knowledge-validation.md`（边界摘要）
- 后端事实层（2026-07-21）：`backend/.planning/codebase/ARCHITECTURE.md`、`STRUCTURE.md`、`INTEGRATIONS.md`、`STACK.md`、`CONVENTIONS.md`、`TESTING.md`、`CONCERNS.md`
- 前端事实层（2026-07-21）：`frontend/.planning/codebase/ARCHITECTURE.md`、`STRUCTURE.md`、`INTEGRATIONS.md`、`STACK.md`、`CONVENTIONS.md`、`TESTING.md`、`CONCERNS.md`
- 知识包：`asset/README.md`、`asset/shared_runtime_word_skill_knowledge_pack.md`、`asset/tender_type_identity_session_knowledge_pack.md`、`asset/template_candidate_pipeline_knowledge_pack.md`
- 刷新基线：本文件为 2026-07-21 全量刷新版（对照提交 `e748f16d`）；在保留仍正确的系统层结论基础上，按当日前后端 fact docs 改写过时结论
