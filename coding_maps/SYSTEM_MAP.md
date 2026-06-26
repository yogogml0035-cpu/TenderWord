# TenderWord 系统地图

**生成日期：** 2026-06-25

本文件是仓库级系统地图，用于帮助后续开发先判断“该看哪里、跨层如何协作、哪些边界不能破坏”。它基于 2026-06-25 刷新的子项目事实文档，不替代代码真源、不替代根级 `AGENTS.md` 的执行红线，也不替代 `backend/.planning/codebase/` 和 `frontend/.planning/codebase/` 的子系统事实文档。

## 系统目的与仓库形态

TenderWord 是前后端分离的招标文档生成、修改、补充批注和模板复用系统。完整运行依赖 Windows + Word COM：前端负责会话、表单、任务进度和文件交互，后端负责 API、任务队列、LangGraph 工作流、LLM/智能体调用、模板候选代理和 Word 文件生成。

| 子项目 | 职责 | 事实文档 |
| --- | --- | --- |
| `backend/` | FastAPI API、任务队列、SSE、LangGraph、补充批注图、任务上下文助手 agent run、Prompt Layer、DeepAgents content_agent、LangChain comment_agent、Word COM、模板候选代理、上传与下载。 | `backend/.planning/codebase/` |
| `frontend/` | Next.js 工作台、招标类型表单、会话与 URL 身份、agent run 上下文、任务 SSE / agent-step 展示、补充批注动作、模板候选弹窗、上传下载交互。 | `frontend/.planning/codebase/` |

长期业务规则和跨主题回归风险沉淀在 `asset/`，当前索引是 `asset/README.md`。首次安装和启动入口保留在 `README.md`。

## 跨子项目主链路

### 生成任务

1. 用户进入 `/tender`，`frontend/app/tender/page.tsx` 解析 URL 参数并恢复或创建会话。
2. `frontend/components/forms/TenderFormShared.tsx` 收集招标数据、模板文件、技术参数文件、模板候选、插入锚点、`generation_mode` 和 `comment_generation_mode`。
3. `frontend/components/chat/FormPanel.tsx` 通过 `tenderFormRegistry` 选择转换器。
4. `frontend/lib/formDataConverter.ts` 把前端 `TenderType` 转换为后端 `GenerateRequest`，并只提交 `file_paths.template` 与 `file_paths.tender_params`；其中 `gngk` 后端 `form_type` 由共享 helper `frontend/lib/gngkFormType.ts` 根据 `tender_lx + fund_lx + ifzgcg` 解析。
5. `frontend/lib/api.ts` 调用 `POST /api/generate`。
6. `backend/api/generate.py` 校验请求并交给 `backend/services/document_service.py`。
7. `DocumentService` 选择 `GRAPH_REGISTRY`，构造初始 state，并提交到 `backend/task/task_queue_manager.py`。
8. `backend/graphs/base_graph.py` 执行共享 LangGraph 工作流，类型 graph 绑定具体 node；`generation_mode=workflow` 走 `generate_polished_text`，`generation_mode=agent` 走公共 `content_agent`。
9. Word 业务逻辑通过 `backend/helper/word_helper/` 和 `backend/util/word_util/` 执行，LLM prompt 通过 `backend/prompts/` 渲染；正文智能体运行时在 `backend/agents/generation/`，批注智能体运行时在 `backend/agents/comments/`。
10. `generation_mode=agent` 路径中，技术参数里的结构化表以 `[[TABLE:<id>]]` 作为内部写回入口；`backend/agents/generation/table_placeholder_utils.py` 负责占位符识别与 `table_id` 字符集，`backend/helper/word_helper/text_parsing.py` 负责按 sidecar 恢复真实表格或静默丢弃不可恢复的投影表。verify agent 不再把缺失占位符单独当 finding，也不要求最终正文原样保留占位符。
11. 后端写入任务结果并推送 `agent_step` / `done` / `error` SSE，前端通过 `frontend/hooks/useChatSSE.ts` 更新任务消息、智能体过程卡和下载入口。

### 任务状态、SSE 与下载

- 前端任务创建、查询、取消、心跳、下载统一通过 `frontend/lib/api.ts`。
- 后端任务生命周期在 `backend/task/task_queue_manager.py`，API 展示在 `backend/api/tasks.py` 和 `backend/services/task_service.py`。
- SSE 后端入口是 `backend/api/stream.py`，事件缓冲和重放在 `backend/core/sse_manager.py`，进度日志桥接在 `backend/util/log_util/sse_log_handler.py`；后端事件枚举含 `node_start` / `node_complete`。
- 前端 SSE runtime 是 `frontend/lib/sse.ts`，任务事件到 UI 的映射是 `frontend/hooks/useChatSSE.ts`；`connected` / `status` 属于前端连接和任务映射层事件，`agent_step` 必须在 runtime 层注册 named event。
- 下载由 `backend/api/download.py` 和上传存储 helper 保护，前端使用 `downloadFile()` / `getDownloadUrl()`。
- 根级 `/health*` 端点只适合作为后端进程探测；Word COM 真实生成能力仍要用 Windows 环境诊断或实际任务验证。

### 任务上下文助手与 rewrite

- 右侧聊天统一从 `frontend/components/chat/ChatPanel.tsx` 发起，通过 `frontend/lib/api.ts` 调用 `POST /api/agent/runs/stream`。
- 后端 `backend/api/agent.py` 返回 NDJSON agent run 事件，编排真源是 `backend/services/agent_run_service.py`；NDJSON 行序列化复用 service 层共享辅助。这里负责显式 `selected_skills`、自然语言兜底、guard、`needs_input`、`task_accepted` 和 JSONL 审计日志。
- task-context assistant 运行时与 tool 真源在 `backend/agents/task_context_assistant/`：它只暴露受控 rewrite skill、受控上下文读取工具、公共摘要工具，以及复用 `DocumentService.create_rewrite_task()` 的 `create_rewrite_task_tool`。
- rewrite 真正进入队列后，仍走既有 task runtime：声明和 guide 在 `backend/skills/rewrite/`，执行图在 `backend/graphs/skill_graph.py`（显式 `RewriteSkillGraph`），后续 SSE、取消、下载和结果卡继续复用同一任务主链路。
- 上传 Word 文件后的修改统一走 rewrite：前端上传文件类型是 `rewrite_source`，agent run payload 由 `uploaded_files` 提供文件摘要、由 `context_snapshot.rewrite_context` 提供当前页面 `form_type`、锚点、`tender_lx`、`fund_source_lx` 和可选招标数据快照；后端 task skill state 内部用 `rewrite_source="uploaded_file"` 标记上传来源。
- `/api/edit`、edit skill 和 edit task kind 已删除；不要把旧 edit 入口重新写回前端或后端文档。
- agent run 审计日志只写白名单结构化字段并 scrub token、`.env`、私有绝对路径和 traceback；只读工具只返回 rewrite 可用性、公共进度和摘要，不暴露完整结果或下载路径。

### 补充批注任务

- 初次生成下载卡在前端触发补充批注，入口从 `TaskDownloadMessage` 经 `MessageList` 回到 `ChatPanel`。
- `frontend/lib/api.ts` 调用 `POST /api/comment-supplement` 创建 `comment_supplement` 任务。
- 后端 `DocumentService` 校验当前会话 latest `rewrite_state`、`polished_text` 和 source file 后，提交 `CommentSupplementGraph`。
- `CommentSupplementGraph` 复制当前文档副本，调用 `backend/agents/comments/` 的 `comment_agent` 生成/校验/写回补充批注，完成后更新会话 latest `rewrite_state.prepared_doc_path` 并通过同一 SSE / 下载链路返回结果。
- rewrite 和 comment_supplement 下载卡不应再次显示补充批注动作。
- 生成/批注 agent 的 workspace 与审计日志共享后端日志命名清洗辅助；新增 agent workspace 不应各自复制文件名规则。

### 模板候选

- 前端只调用项目内 `/api/template-candidates*` helper。
- 模板候选 UI 在 `frontend/components/forms/TemplateCandidateDialog.tsx`，表单回填在 `frontend/components/forms/TenderFormShared.tsx`。
- 后端代理、下载、选择、落盘在 `backend/api/template_candidates.py` 和 `backend/util/common_util/template_candidates.py`。
- AI 重排在 `backend/services/template_candidate_ranking_service.py`，prompt 在 `backend/prompts/template_candidate_ranking_prompt.py`。
- 外部下载链接必须继续受后端白名单约束，前端不得绕过后端直接请求外部模板文件。

## 接口边界

| 边界 | 前端入口 | 后端入口 | 同步要求 |
| --- | --- | --- | --- |
| API client | `frontend/lib/api.ts` | `backend/api/` | API 形状变化时同步 `frontend/types/api.ts`、后端 `backend/models/` 和测试。 |
| 本地 API 代理 | `frontend/lib/apiBaseUrl.ts`, `frontend/next.config.ts` | `backend/main.py` | `NEXT_PUBLIC_API_URL` 会影响 API base URL、Next rewrite 和开发期 allowed origin，修改时需一起验证。 |
| 招标类型身份 | `frontend/types/index.ts`, `frontend/utils/tenderTypeMapper.ts`, `frontend/lib/gngkFormType.ts`, `frontend/lib/formDataConverter.ts` | `backend/models/generate.py`, `backend/config/tender_config.py`, `backend/services/document_service.py` | 新增或修改类型必须同步前端 UI 类型、后端 `form_type`、URL、graph/state/node、anchor 和测试。 |
| 会话和 URL | `frontend/stores/chatStore.ts`, `frontend/utils/tenderTypeMapper.ts` | `backend/api/conversations.py`, `backend/services/conversation_service.py` | 地址栏、会话身份、任务恢复和后端心跳需保持一致。 |
| 任务与 SSE | `frontend/hooks/useChatSSE.ts`, `frontend/lib/sse.ts`, `frontend/stores/*` | `backend/api/stream.py`, `backend/core/sse_manager.py`, `backend/task/task_queue_manager.py` | 新增 SSE 事件必须同步后端模型、前端 named event、类型、解析和测试。 |
| Agent run / rewrite | `frontend/components/chat/ChatPanel.tsx`, `frontend/lib/api.ts` | `backend/api/agent.py`, `backend/services/agent_run_service.py`, `backend/agents/task_context_assistant/` | `task_accepted` 后交给既有 task / SSE 链路；`needs_input` 不创建后台任务。 |
| Word 运行时 | 无前端直接入口 | `backend/graphs/`, `backend/nodes/`, `backend/helper/word_helper/`, `backend/util/word_util/` | 前端不得触碰 COM；后端新增 graph/node/tool 不得绕过队列、锁、取消检查和进度包装。 |
| Prompt / LLM / 智能体 | 无前端直接入口 | `backend/prompts/`, `backend/agents/generation/`, `backend/agents/comments/`, `backend/util/common_util/llm_stream_utils.py` | prompt 渲染、智能体协议、超时、解析和结构校验要集中维护。 |
| 模板候选 | `frontend/components/forms/TemplateCandidateDialog.tsx`, `frontend/lib/api.ts` | `backend/api/template_candidates.py` | 前端不得直接调用外部候选接口或外部文件 URL。 |

## 状态、存储与运行时

- 前端会话、草稿、任务摘要和历史状态使用 `sessionStorage`，主要由 `frontend/stores/chatStore.ts`、`frontend/stores/historyStore.ts` 和 `frontend/stores/chatTaskSessionStore.ts` 持久化。
- 前端活跃 SSE 文本、日志、进度、当前节点和未完成 agent step 快照是内存态，位于 `frontend/stores/chatStreamStore.ts`；完成态 `agent-step` 过程卡进入 `chatStore.conversations`。
- 后端任务、会话和 SSE 事件当前是进程内状态；上传、下载、生成文档、prompt log 和运行日志是本地文件。
- 后端没有已确认的外部数据库；外部集成主要是 LLM provider、招标详情接口、模板候选接口、Word COM，以及批注 bad case retrieval。`backend/retrieval/` 已是 `generate_comments`、自主生成模式 `comment_agent` 和 `comment_supplement` 的正式 prompt 增强运行时；向量配置可用时使用 Qdrant/embedding，hybrid 失败会降级到 `bm25_only`，检索失败不阻塞批注生成。
- 本地完整运行的关键环境是 Windows + Word COM；WSL 场景下前端可在 Linux Node 运行，后端仍需要 Windows Python 和 Word COM。

## 按任务分类的阅读指南

### 后端 API、任务或 graph 修改

先读：

- `AGENTS.md`
- `docs/backend.md`
- `backend/.planning/codebase/ARCHITECTURE.md`
- `backend/.planning/codebase/STRUCTURE.md`
- `backend/.planning/codebase/INTEGRATIONS.md`
- `backend/.planning/codebase/CONVENTIONS.md`

再按任务读取：

- 任务与队列：`backend/task/task_queue_manager.py`、`backend/services/document_service.py`
- 任务上下文助手：`backend/api/agent.py`、`backend/services/agent_run_service.py`、`backend/agents/task_context_assistant/`
- SSE：`backend/core/sse_manager.py`、`backend/api/stream.py`
- 补充批注：`backend/api/comment_supplement.py`、`backend/graphs/comment_supplement_graph.py`、`backend/nodes/common_word_nodes/comment_supplement.py`、`backend/agents/comments/`
- Prompt / skill / 智能体：`backend/prompts/`、`backend/skills/`、`backend/agents/generation/`、`backend/agents/comments/`
- Word 业务：`asset/shared_runtime_word_skill_knowledge_pack.md`

### 前端表单、会话、URL 或任务展示修改

先读：

- `AGENTS.md`
- `docs/frontend.md`
- `frontend/.planning/codebase/ARCHITECTURE.md`
- `frontend/.planning/codebase/STRUCTURE.md`
- `frontend/.planning/codebase/CONVENTIONS.md`
- `frontend/.planning/codebase/TESTING.md`

再按任务读取：

- 类型身份与会话：`asset/tender_type_identity_session_knowledge_pack.md`
- API client：`frontend/lib/api.ts`
- URL 映射：`frontend/utils/tenderTypeMapper.ts`
- 表单：`frontend/components/forms/TenderFormShared.tsx`
- 聊天任务：`frontend/components/chat/ChatPanel.tsx`、`frontend/components/chat/FormPanel.tsx`
- Agent run：`frontend/lib/api.ts`、`frontend/types/api.ts`、`frontend/components/chat/ChatPanel.tsx`
- 智能体过程卡：`frontend/hooks/useChatSSE.ts`、`frontend/stores/chatStore.ts`、`frontend/stores/chatStreamStore.ts`、`frontend/components/chat/TaskContentMessage.tsx`
- 补充批注动作：`frontend/components/chat/TaskDownloadMessage.tsx`、`frontend/components/chat/MessageList.tsx`、`frontend/components/chat/ChatPanel.tsx`

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

### 模板候选修改

先读：

- `asset/template_candidate_pipeline_knowledge_pack.md`
- `backend/.planning/codebase/INTEGRATIONS.md`
- `frontend/.planning/codebase/INTEGRATIONS.md`

重点同步：

- `backend/api/template_candidates.py`
- `backend/util/common_util/template_candidates.py`
- `backend/services/template_candidate_ranking_service.py`
- `frontend/lib/api.ts`
- `frontend/components/forms/TemplateCandidateDialog.tsx`
- `frontend/components/forms/TenderFormShared.tsx`

### 视觉或 UX 修改

先读：

- `frontend/.planning/codebase/ARCHITECTURE.md`
- `frontend/.planning/codebase/CONVENTIONS.md`
- `frontend/.planning/codebase/TESTING.md`

涉及真实浏览器交互、页面跳转、会话恢复、模板弹窗或任务进度展示时，最终回归入口应是 `frontend/e2e/test_*.spec.ts` 和 `npm run test:e2e`。

## 集成风险检查清单

- API 形状变化是否同步后端模型、前端类型、API client 和测试。
- 前端新增请求是否仍经过 API client；当前没有 lint 规则自动阻止组件或 hooks 写裸 `fetch`，评审时要人工检查。
- `gngk` 的 `tender_lx + fund_lx + ifzgcg` 分派是否集中在 `frontend/lib/gngkFormType.ts`，且 `formDataConverter.ts` 与 `ChatPanel.tsx` 是否都调用该 helper。
- 生成文件契约是否仍是 `template + tender_params`，后端初始 state 是否只装配 `template_path + tender_param_paths`。
- 上传文件 rewrite 是否仍使用前端 `rewrite_source` 文件类型，并在后端 task skill state 中通过 `rewrite_source="uploaded_file"` 路由。
- `comment_generation_mode` 是否只影响初次生成批注分支，且没有进入 rewrite 请求模型或 skill state。
- 新增或修改 SSE 事件是否同步后端事件模型、前端事件 union、`frontend/lib/sse.ts` named event、`useChatSSE` 和测试。
- 新增或修改任务类型是否同步 `TaskKind`、任务状态、SSE `done` payload、下载卡和会话结果语义。
- Agent run 是否只在 `task_accepted` 后启动后台任务，且没有复制 task/SSE/下载状态机。
- agent run 审计日志和摘要工具是否仍只暴露 scrub 后白名单字段。
- Word COM 相关改动是否仍然经过任务队列、graph 锁、取消检查和进度包装。
- Prompt、LLM 流式、`content_agent` 或 `comment_agent` 改动是否复用 `LLM_STREAM_TIMEOUT_SECONDS`，并保留 Prompt Layer 与智能体协议边界。
- `backend/retrieval/` 改动是否仍限制在批注 prompt 增强边界内：只接入 `generate_comments`、自主生成模式 `comment_agent` 和 `comment_supplement`，不进入 rewrite 或 `comment_generation_mode=off`；检索状态、日志路径和命中详情不进入 SSE、下载卡或 `agent_step`。
- `content_verify_agent` 是否只输出真实需修复 findings，并把“无问题 / 无需修改”的无效审核项折叠为 `[]`。
- content agent 生成的正文是否把 `[[TABLE:<id>]]` 作为内部写回入口交给后端写回层处理，verify agent 是否仍只对真实参数差异产出 findings；占位符识别、sidecar 恢复和 `table_id` 字符集是否与 `backend/util/word_util/table_models.py` 一致。
- 模板候选改动是否仍由后端代理外部列表、文件下载和白名单校验。
- 前端 running task 恢复是否先查任务状态，避免直接连接已不存在的 SSE。
- 文档引用的路径、命令、端口和目录是否仍真实存在。

## 验证入口

- 后端常规验证：在 `backend/` 运行 `\.\.venv\Scripts\python.exe -m pytest tests -v`。
- 前端常规验证：在 `frontend/` 运行 `npm run lint`、`npm run type-check`、相关 `npm run test`。
- 前端 E2E：在 `frontend/` 运行 `npm run test:e2e`。
- 文档型变更：根目录运行 `git diff --check`，并扫描文档中的密钥/token 模式。

本次系统地图是文档层产物；具体功能验证仍以受影响代码路径的测试要求为准。

## 源文档索引

- `AGENTS.md`
- `README.md`
- `ARCHITECTURE.md`
- `INTERFACES.md`
- `docs/backend.md`
- `docs/frontend.md`
- `docs/interfaces-runtime.md`
- `docs/knowledge-validation.md`
- `backend/.planning/codebase/ARCHITECTURE.md`
- `backend/.planning/codebase/INTEGRATIONS.md`
- `backend/.planning/codebase/STRUCTURE.md`
- `backend/.planning/codebase/TESTING.md`
- `backend/.planning/codebase/CONVENTIONS.md`
- `backend/.planning/codebase/CONCERNS.md`
- `backend/.planning/codebase/STACK.md`
- `frontend/.planning/codebase/ARCHITECTURE.md`
- `frontend/.planning/codebase/INTEGRATIONS.md`
- `frontend/.planning/codebase/STRUCTURE.md`
- `frontend/.planning/codebase/TESTING.md`
- `frontend/.planning/codebase/CONVENTIONS.md`
- `frontend/.planning/codebase/CONCERNS.md`
- `frontend/.planning/codebase/STACK.md`
- `asset/README.md`
- `asset/shared_runtime_word_skill_knowledge_pack.md`
- `asset/template_candidate_pipeline_knowledge_pack.md`
- `asset/tender_type_identity_session_knowledge_pack.md`
