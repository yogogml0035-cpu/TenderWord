# 后端架构事实地图

**分析日期：** 2026-06-25

**范围：** 仅覆盖 `backend/` 子项目。`backend/.env` 文件存在，但不得读取、摘录或把其中任何值写入文档、日志、测试夹具或回复。

## 系统总览

```text
┌─────────────────────────────────────────────────────────────┐
│                       FastAPI 应用入口                       │
│                       `backend/main.py`                      │
├───────────────┬────────────────┬────────────────────────────┤
│ API routers   │ Pydantic models │ startup / CORS / health    │
│ `backend/api` │ `backend/models`│ `backend/main.py`           │
└───────┬───────┴────────┬───────┴───────────────┬────────────┘
        │                │                       │
        ▼                ▼                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Service 编排与进程内运行态                 │
│ `backend/services/`, `backend/task/`, `backend/core/`         │
│ DocumentService / TaskQueueManager / SSEManager / AgentRun   │
└───────────────┬───────────────────────┬─────────────────────┘
                │                       │
                ▼                       ▼
┌───────────────────────────────┐   ┌─────────────────────────┐
│ LangGraph 工作流与 state       │   │ Agent / Prompt / LLM     │
│ `backend/graphs/`             │   │ `backend/agents/`        │
│ `backend/states/`             │   │ `backend/prompts/`       │
└───────────────┬───────────────┘   └─────────────┬───────────┘
                │                                 │
                ▼                                 ▼
┌───────────────────────────────┐   ┌─────────────────────────┐
│ Word 节点、业务 helper、COM 工具 │   │ Retrieval / 外部 HTTP     │
│ `backend/nodes/`              │   │ `backend/retrieval/`     │
│ `backend/helper/word_helper/` │   │ `backend/util/common_util/`│
│ `backend/util/word_util/`     │   │                         │
└───────────────┬───────────────┴─────────────┬────────────────┘
                │                             │
                ▼                             ▼
┌─────────────────────────────────────────────────────────────┐
│ 本地上传/生成文件、运行日志、agent workspace、外部 LLM/接口/Word │
│ `settings.UPLOAD_DIR`, `backend/logs/`, `backend/context_log/` │
└─────────────────────────────────────────────────────────────┘
```

后端是 TenderWord 的 FastAPI + LangGraph + Word COM 执行端，负责招标详情代理、模板候选代理、上传下载、初次生成、rewrite、补充批注、任务队列、SSE、LLM/agent 调用、bad case retrieval 和 Word 文件写回。完整 Word 闭环必须运行在 Windows Python、`pywin32`、本机 Word/WPS COM 环境中；无 COM 环境只能验证纯逻辑、API 契约和非写回分支。

## 组件职责

| Component | Responsibility | File |
|-----------|----------------|------|
| FastAPI app | 创建应用、注册 `/api` routers、配置 CORS、绑定 startup/shutdown、提供 health endpoints | `backend/main.py:143`, `backend/main.py:176`, `backend/main.py:199` |
| API routers | 保持薄入口，解析 HTTP/SSE/NDJSON 请求并委派 service 或 util | `backend/api/generate.py:51`, `backend/api/agent.py:19`, `backend/api/stream.py:23`, `backend/api/tasks.py:36` |
| Pydantic models | 定义 generate、task、SSE、agent run、tender、upload、template candidate 的 API/runtime shape | `backend/models/generate.py:117`, `backend/models/task.py:17`, `backend/models/sse.py:17`, `backend/models/agent_run.py:92` |
| Settings | 从环境变量和 `backend/.env` 加载 LLM、上传、外部接口、锁、日志、SSE、任务配置 | `backend/config/settings.py:24` |
| Tender config | 集中管理招标类型锚点、字号、content mode、受保护字段 profile 和 family 归并 | `backend/config/tender_config.py:20`, `backend/config/tender_config.py:142` |
| DocumentService | 选择 graph、构建初始 state、创建任务、提交后台线程、执行 graph、收敛 task result 与 SSE 终态 | `backend/services/document_service.py:400`, `backend/services/document_service.py:430`, `backend/services/document_service.py:709`, `backend/services/document_service.py:991` |
| TaskQueueManager | 管理进程内任务队列、状态、心跳、取消、后台清理、公平锁、进度和 worker future | `backend/task/task_queue_manager.py:169`, `backend/task/task_queue_manager.py:281`, `backend/task/task_queue_manager.py:682`, `backend/task/task_queue_manager.py:756` |
| SSEManager | 管理 SSE client、事件缓存、断线重连、heartbeat 和后台线程到主事件循环的 threadsafe 调度 | `backend/core/sse_manager.py:44`, `backend/core/sse_manager.py:99`, `backend/core/sse_manager.py:305`, `backend/core/sse_manager.py:395` |
| BaseGraph | 提供跨进程文件锁、节点进度包装、取消检查、同步/异步执行包装 | `backend/graphs/base_graph.py:53`, `backend/graphs/base_graph.py:272`, `backend/graphs/base_graph.py:309`, `backend/graphs/base_graph.py:661` |
| StandardTenderWorkflowGraph | 初次生成的共享 LangGraph 主干，维护 Word 子图、`generation_mode`、批注分支和写回分支 | `backend/graphs/base_graph.py:438`, `backend/graphs/base_graph.py:491` |
| Tender graph classes | 按招标类型绑定差异节点，复用标准生成主干 | `backend/graphs/xjcg_tender_graph.py`, `backend/graphs/gngk_hw_zc_tender_graph.py`, `backend/graphs/gjgk_tender_graph.py` |
| RewriteSkillGraph | 显式声明 rewrite 节点顺序、普通边和条件分支 | `backend/graphs/skill_graph.py:31`, `backend/graphs/skill_graph.py:54`, `backend/graphs/skill_graph.py:63` |
| CommentSupplementGraph | 独立补充批注 graph，复用任务队列、SSE、锁、`comment_agent` 写回 | `backend/graphs/comment_supplement_graph.py:19`, `backend/graphs/comment_supplement_graph.py:35` |
| Word nodes | 承载模板准备、抽参、删除、替换、正文生成、批注生成、rewrite 上下文和写回节点 | `backend/nodes/common_word_nodes/`, `backend/nodes/skills_nodes/`, `backend/nodes/gngk_word_nodes/`, `backend/nodes/gjgk_word_nodes/` |
| Word helper | 承载段落边界、正文操作、删除、cleanup、样式回填、受保护字段、range 等业务 helper | `backend/helper/word_helper/` |
| Word util | 承载 COM lock/retry、Word app 生命周期、锚点工具、文档检查、常量和诊断 | `backend/util/word_util/word_com_manager.py:100`, `backend/util/word_util/word_application_util.py:132` |
| Generation agents | `generation_mode=agent` 的 DeepAgents 主/子智能体、workspace、协议校验和 `agent_step` | `backend/agents/generation/content_agents.py`, `backend/nodes/common_word_nodes/content_agent_generate.py` |
| Comment agents | 批注候选生成/校验/修复、工具门禁、Word 写回和审计 | `backend/agents/comments/comment_agent.py`, `backend/nodes/common_word_nodes/comment_agent.py` |
| Task context assistant | 右侧 agent run 前置流，只用受控上下文和白名单工具创建 rewrite 任务 | `backend/services/agent_run_service.py`, `backend/agents/task_context_assistant/tools.py`, `backend/agents/task_context_assistant/factory.py` |
| Prompt layer | 只做 prompt 渲染和机器契约解析，不承载副作用、SSE、COM 或 session state | `backend/prompts/` |
| Retrieval layer | 为批注生成注入 bad case prompt context，hybrid 失败时降级 | `backend/retrieval/comment_bad_case_runtime.py`, `backend/retrieval/hybrid.py`, `backend/retrieval/qdrant_store.py` |

## 核心模式

**Overall:** FastAPI 薄入口 + Service 编排 + 进程内任务队列 + LangGraph 工作流 + Word COM 临界资源串行化。

**Key Characteristics:**
- API route 只做 HTTP 边界处理；业务编排进入 `backend/services/`，graph/node/helper 承担实际生成与写回。
- 初次生成使用 `StandardTenderWorkflowGraph` 共享主干；类型差异通过 graph class attribute 绑定节点。
- rewrite 使用 `RewriteSkillGraph` 显式 graph；不要恢复 `SkillGraph.for_skill + TaskSkillWorkflow` 元数据驱动框架。
- Word COM 写入必须经过 `DocumentService`、`TaskQueueManager`、graph 锁、节点取消检查、进度包装和 `backend/util/word_util/`。
- Agent run 只负责任务创建前置流；后台 task、SSE、取消、下载仍沿用 task/SSE/download 链路。
- 子项目 `.planning/codebase/` 是事实层；根级 `AGENTS.md`、`ARCHITECTURE.md`、`INTERFACES.md` 只做导航和跨项目边界。项目内规则来源包括 `.agents/skills/ai-coding-first/SKILL.md`、`.agents/skills/agents-map/SKILL.md`、`.agents/skills/gsd-map-codebase/SKILL.md`。

## 分层结构

**API 层:**
- 职责： 暴露 HTTP、SSE、NDJSON 入口，转换为 service 调用。
- Location: `backend/api/`
- 包含： `generate.py`, `agent.py`, `comment_supplement.py`, `tasks.py`, `stream.py`, `upload.py`, `download.py`, `tender.py`, `template_candidates.py`, `conversations.py`
- Depends on: `backend/models/`, `backend/services/`, `backend/util/common_util/`
- Used by: 前端 API client、浏览器 SSE、agent run UI 和本地调试。

**模型与配置层:**
- 职责： 保存 API shape、runtime state shape、配置和招标类型规则。
- Location: `backend/models/`, `backend/states/`, `backend/config/`
- 包含： Pydantic models、TypedDict graph states、Settings、TenderAnchorConfig、ProtectedFieldProfile。
- Depends on: Pydantic、`pydantic-settings`、环境变量、`backend/.env`。
- Used by: API、service、graph、nodes、SSE、task queue、frontend 类型同步。

**Service 层:**
- 职责： 封装业务编排，避免 route 直接操作 graph、任务队列、agent 或 Word。
- Location: `backend/services/`
- 包含： `DocumentService`, `TaskService`, `ConversationService`, `AgentRunService`, `TemplateCandidateRankingService`, chat stream helpers。
- Depends on: models、graphs、task queue、SSE、agents、prompts、common util。
- Used by: `backend/api/`。

**Task/SSE 运行态层:**
- 职责： 管理长任务生命周期、排队、公平执行、取消、心跳、进度和事件推送。
- Location: `backend/task/`, `backend/core/`
- 包含： `TaskQueueManager`, `Task`, `TaskProgress`, `SSEManager`, event cache。
- Depends on: settings、models、log util。
- Used by: `DocumentService`, `TaskService`, `SSELogHandler`, `stream.py`。

**Graph/Node 层:**
- 职责： 用 LangGraph 编排 generate、rewrite、comment supplement，并用 state 在节点间传递数据。
- Location: `backend/graphs/`, `backend/nodes/`, `backend/states/`
- 包含： 标准 graph、类型 graph、skill graph、补充批注 graph、共享 Word 节点、类型专属节点、skill 节点。
- Depends on: Word helper/util、agents、prompts、retrieval、task queue。
- Used by: `DocumentService`。

**Word 操作层:**
- 职责： 执行 Word 文件复制、打开、抽取、删除、替换、样式回填、批注写回、保存和关闭。
- Location: `backend/nodes/`, `backend/helper/word_helper/`, `backend/util/word_util/`
- 包含： 业务 helper 和 COM 技术 helper。
- Depends on: pywin32/COM、Word/WPS、本地文件、tender config。
- Used by: graph nodes 和 `backend/scripts/diagnose_word.py`。

**Agent/Prompt/LLM 层:**
- 职责： 渲染 prompt、调用 OpenAI-compatible LLM、执行 DeepAgents/LangChain agent、产出结构化过程事件。
- Location: `backend/agents/`, `backend/prompts/`, `backend/skills/`, `backend/util/common_util/llm_stream_utils.py`
- 包含： content agent、comment agent、task context assistant、rewrite skill、LLM stream util。
- Depends on: settings、LangChain、DeepAgents、OpenAI-compatible SDK。
- Used by: graph nodes、agent run service、template candidate ranking。

**Retrieval 层:**
- 职责： 为批注生成提供 bad case context，向量能力不可用时降级。
- Location: `backend/retrieval/`
- 包含： bad case loader、BM25、Qdrant store、embedding client、hybrid merge、runtime cache。
- Depends on: `backend/retrieval/bad_cases/`, Qdrant, embedding API, env。
- Used by: `backend/nodes/common_word_nodes/generate_comments.py`, `backend/nodes/common_word_nodes/comment_agent.py`。

## 数据流

### 初次生成主链路

1. `POST /api/generate` 进入 `create_generate_task()`，请求模型是 `GenerateRequest` (`backend/api/generate.py:51`, `backend/models/generate.py:117`)。
2. `DocumentService.create_task()` 使用 `request.form_type.value` 从 `GRAPH_REGISTRY` 选择 graph (`backend/services/document_service.py:430`, `backend/services/document_service.py:216`)。
3. `_build_initial_state()` 将 tender data、文件路径、锚点、`generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 写入初次 generate state (`backend/services/document_service.py:902`)。
4. `_submit_graph_task()` 调用 `TaskQueueManager.add_task()` 并把 `_run_graph()` 提交到后台线程池 (`backend/services/document_service.py:709`, `backend/task/task_queue_manager.py:281`)。
5. `_run_graph()` 实例化 graph、估算节点总数、编译 graph、创建独立 event loop 并调用 `_invoke_graph_async()` (`backend/services/document_service.py:991`, `backend/services/document_service.py:1356`)。
6. `invoke_with_timing_async()` 先 `wait_for_turn()`，再获取 `CrossProcessFileLock`，登记运行中的 async task，并执行 compiled graph (`backend/graphs/base_graph.py:661`, `backend/task/task_queue_manager.py:756`)。
7. `StandardTenderWorkflowGraph.build_graph()` 执行 `prepare_template -> extract_tender_params`，并行进入 Word 子图和生成分支，之后汇合到 `update_word` (`backend/graphs/base_graph.py:491`)。
8. `DocumentService` 收敛 output file、file size、model、style/comment writeback summary，并通过 task queue 与 `SSEManager` 推送 `done` 或 `error` (`backend/core/sse_manager.py:675`, `backend/core/sse_manager.py:719`)。

### Rewrite 智能体链路

1. `POST /api/agent/runs/stream` 进入 `AgentRunService.stream()` 并返回 NDJSON (`backend/api/agent.py:19`, `backend/services/agent_run_service.py`)。
2. `AgentRunService` 先输出 `run_started`、`thinking_stage`，再做 preflight guard 或调用 DeepAgents runner (`backend/services/agent_run_service.py`)。
3. 条件缺失时返回 `needs_input`；条件满足时由 `create_rewrite_task_tool()` 调用 `DocumentService.create_rewrite_task()` (`backend/agents/task_context_assistant/tools.py`, `backend/services/document_service.py:464`)。
4. 上传文件 rewrite 必须具备 `file_path`、`form_type`、完整 `insertion_config`、`tender_lx`、`fund_source_lx`；会话 rewrite 必须已有 latest rewrite history (`backend/models/agent_run.py:39`, `backend/agents/task_context_assistant/tools.py`)。
5. `RewriteSkillGraph` 执行 `resolve_rewrite_target`、`extract_rewrite_context`、`get_rewrite_comments`、`delete_section`、`rewrite_text`、`update_word`，条件分支来自 `backend/skills/rewrite/scripts/runtime.py` (`backend/graphs/skill_graph.py:31`, `backend/graphs/skill_graph.py:63`)。
6. rewrite 后台任务复用 task/SSE/download 链路；agent run 只负责 `task_accepted` 和终态摘要 (`backend/services/agent_run_service.py`)。

### 补充批注链路

1. `POST /api/comment-supplement` 进入 `DocumentService.create_comment_supplement_task()` (`backend/api/comment_supplement.py:24`, `backend/services/document_service.py:594`)。
2. Service 校验 `conversation_id`、`source_file`、latest `rewrite_state`、`polished_text` 和当前文件是否仍是会话 latest 文档 (`backend/services/document_service.py:594`)。
3. `CommentSupplementGraph` 执行 `prepare_comment_supplement -> comment_agent -> finalize_comment_supplement` (`backend/graphs/comment_supplement_graph.py:35`)。
4. 成功后 `ConversationService.append_comment_supplement_success()` 更新 latest rewrite state (`backend/services/conversation_service.py`)。

### SSE 链路

1. 前端连接 `GET /api/stream/{task_id}`，`stream_task_events()` 校验任务并解析 `Last-Event-ID` (`backend/api/stream.py:23`)。
2. `SSEManager.event_stream()` 建立 client、重放 missed events、持续 yield SSE 字符串并在 `done`/`error` 后结束 (`backend/core/sse_manager.py:395`)。
3. 后台线程通过 `send_*_threadsafe()` 把事件调度回 FastAPI 主 loop (`backend/core/sse_manager.py:99`, `backend/core/sse_manager.py:127`)。

### 模板候选链路

1. `GET /api/template-candidates` 调用 `fetch_template_candidates()` 代理外部候选列表 (`backend/api/template_candidates.py`, `backend/util/common_util/template_candidates.py`)。
2. `TemplateCandidateRankingService.rank_candidates()` 对同优先级候选按项目名称调用 LLM 重排；失败时保持优先级排序 (`backend/services/template_candidate_ranking_service.py`)。
3. `GET /api/template-candidates/download` 和 `POST /api/template-candidates/select` 通过 allowlist 校验外部模板链接，再下载或保存到上传目录 (`backend/api/template_candidates.py`, `backend/util/common_util/upload_storage.py`)。

## 关键抽象

**`FormType` 与 runtime `tender_type`:**
- 职责： 连接 API 表单类型和 graph 运行态招标类型。
- Examples: `backend/models/generate.py:56`, `backend/services/document_service.py:902`
- Pattern: API 使用带 `_tender` 的 `FormType`；进入 graph state 时去掉 `_tender`。新增类型要同步 model、registry、state、graph、nodes、config、tests 和前端映射。

**`TenderAnchorConfig` / `ProtectedFieldProfile`:**
- 职责： 集中管理锚点、字号、content start/update mode 和受保护字段顺序。
- Examples: `backend/config/tender_config.py:20`, `backend/config/tender_config.py:30`
- Pattern: 锚点/字号/少量保护字段差异优先进入配置；流程差异明显时才新增类型节点或 graph。

**`StandardTenderWorkflowGraph`:**
- 职责： 初次生成主流程真源。
- Examples: `backend/graphs/base_graph.py:438`, `backend/graphs/xjcg_tender_graph.py`
- Pattern: 类型 graph 覆盖 `STATE_CLS` 和必要 `NODE_*`，不要复制 `build_graph()`。

**`RewriteSkillGraph`:**
- 职责： rewrite 任务显式 graph。
- Examples: `backend/graphs/skill_graph.py:54`, `backend/skills/rewrite/SKILL.md`
- Pattern: 节点、边和条件分支直接写在 `backend/graphs/skill_graph.py`；新增 skill 先评估是否新增显式 graph 类。

**`TaskQueueManager`:**
- 职责： 长任务排队、公平锁、进度、取消和心跳。
- Examples: `backend/task/task_queue_manager.py:169`, `backend/task/task_queue_manager.py:756`
- Pattern: Word 任务必须先进入队列；取消通过 cancel event、worker future 和 async task cancel 传播。

**`SSEEvent` / `AgentStepEventData`:**
- 职责： 后台任务事件和 agent 过程卡契约。
- Examples: `backend/models/sse.py:17`, `backend/models/sse.py`
- Pattern: 新字段或事件类型必须同步发送方、前端 parser、类型和测试。

**Word COM lifecycle helpers:**
- 职责： 创建、打开、保存、关闭 Word COM，并统一处理 pywin32 缺失、COM 初始化、RPC 重试和资源释放。
- Examples: `backend/util/word_util/word_application_util.py:132`, `backend/util/word_util/word_com_manager.py:100`
- Pattern: 节点只通过 helper 操作 COM；不要在 API/service/agent 里直接 `Dispatch` 或打开 Word。

**Content agent / Comment agent:**
- 职责： 自主生成正文和批注锚点校验/写回。
- Examples: `backend/agents/generation/content_agents.py`, `backend/agents/comments/comment_agent.py`
- Pattern: agent 的长正文、草稿、审核和修订通过 workspace 文件交接；Word 写回仍由 graph 节点线程执行。

**结构化表占位符:**
- 职责： 标记技术参数结构化表的内部写回入口 `[[TABLE:<id>]]`。
- Examples: `backend/agents/generation/table_placeholder_utils.py`
- Pattern: 占位符只在生成/审核/写回运行时内部使用，不是最终正文可见内容；缺失占位符不再单独产出 finding，写回层会按 sidecar 模型恢复真实表格，或在无法恢复时静默丢弃占位符与其投影表，避免把 Markdown/手绘表格当成最终真源。

**Bad case retrieval:**
- 职责： 给批注生成注入坏案例上下文。
- Examples: `backend/retrieval/comment_bad_case_runtime.py`, `backend/retrieval/hybrid.py`
- Pattern: hybrid 检索失败降级为 `bm25_only`；retrieval 状态不进入前端 SSE、下载卡或 agent_step 展示。

## 入口清单

**ASGI app:**
- Location: `backend/main.py`
- Triggers: `uvicorn backend.main:app` 或等价 ASGI 启动。
- Responsibilities: 初始化 app、router、CORS、日志队列、SSE 主 loop、健康检查。

**Generate API:**
- Location: `backend/api/generate.py`
- Triggers: `POST /api/generate`
- Responsibilities: 创建初次生成任务，返回 `GenerateResponse`。

**Task API:**
- Location: `backend/api/tasks.py`
- Triggers: `GET /api/tasks`, `GET /api/tasks/{task_id}`, `DELETE /api/tasks/{task_id}`, `POST /api/tasks/{task_id}/heartbeat`
- Responsibilities: 查询任务、取消任务、续任务心跳。

**SSE API:**
- Location: `backend/api/stream.py`
- Triggers: `GET /api/stream/{task_id}`
- Responsibilities: 推送 `log`、`llm`、`progress`、`agent_step`、`done`、`error`、`heartbeat`。

**Agent run API:**
- Location: `backend/api/agent.py`
- Triggers: `POST /api/agent/runs/stream`
- Responsibilities: 返回 NDJSON agent run 过程，并在上下文满足时创建 rewrite 任务。

**Comment supplement API:**
- Location: `backend/api/comment_supplement.py`
- Triggers: `POST /api/comment-supplement`
- Responsibilities: 基于会话 latest Word 文件创建补充批注任务。

**Tender/template/upload/download APIs:**
- Location: `backend/api/tender.py`, `backend/api/template_candidates.py`, `backend/api/upload.py`, `backend/api/download.py`
- Triggers: `/api/tender/{tender_no}`, `/api/template-candidates`, `/api/upload`, `/api/download/{file_path:path}`
- Responsibilities: 外部数据代理、模板候选代理、文件落盘和下载。

## 架构约束

- **Threading:** FastAPI 主 loop 处理 HTTP/SSE；`DocumentService` 用 `ThreadPoolExecutor(max_workers=4)` 提交任务；每个 graph 任务在后台线程中创建独立 asyncio loop (`backend/services/document_service.py`)。
- **Word COM:** 所有 Word 写入必须经过 task queue、graph 锁、取消检查、进度包装、`CrossProcessFileLock` 和 `com_lock()` (`backend/graphs/base_graph.py:53`, `backend/util/word_util/word_com_manager.py:100`)。
- **Global state:** 单例包括 `_task_queue`、`sse_manager`、`_document_service`、`_conversation_service`、`_agent_run_service`、`settings` 和 graph registry (`backend/task/task_queue_manager.py:945`, `backend/core/sse_manager.py:788`, `backend/services/document_service.py:190`)。
- **Persistence:** task、SSE、conversation history 是进程内状态，服务重启不恢复；文件产物和日志是本地文件状态。
- **Environment:** `backend/config/settings.py` 和 `backend/retrieval/config.py` 会读取 `backend/.env`；文档、日志和回复不得输出真实 env 值。
- **Circular imports:** 未记录明确循环链；需要跨层引用时优先延迟导入，现有 `backend/graphs/base_graph.py`、`backend/task/task_queue_manager.py` 已使用延迟导入规避循环。
- **Document hierarchy:** 子项目事实写入 `backend/.planning/codebase/`；根级系统文档不复制后端实现细节。相关项目内规则见 `.agents/skills/ai-coding-first/SKILL.md`、`.agents/skills/agents-map/SKILL.md`。
- **Cross-layer sync:** API shape、SSE、任务类型、招标类型、prompt/LLM、Word helper、模板候选和 retrieval 改动必须同步后端模型、前端类型/API client、测试和长期知识包。

## 反模式

### API 路由直接执行 Word COM 或 LangGraph

**What happens:** 在 `backend/api/*.py` 里直接打开 Word、调用 COM、运行 graph 或拼接长业务流程。
**Why it's wrong:** 会绕过 `TaskQueueManager`、公平锁、文件锁、取消检查、SSE 终态和日志上下文。
**Do this instead:** API route 委派 service，例如 `backend/api/generate.py` 调 `backend/services/document_service.py`；Word 写入只能由 graph 节点进入 `backend/util/word_util/`。

### 复制标准生成 graph 主干

**What happens:** 为新招标类型复制 `StandardTenderWorkflowGraph.build_graph()`，只改少量节点。
**Why it's wrong:** `generation_mode`、`comment_generation_mode`、`comment_agent`、进度节点和后写回分支容易漂移。
**Do this instead:** 继承 `StandardTenderWorkflowGraph` 或现有 family graph，覆盖 `STATE_CLS` 和必要 `NODE_*`，参照 `backend/graphs/gngk_hw_cz_tender_graph.py`。

### 把 generate-only 字段带入 rewrite

**What happens:** 将 `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 写入 rewrite request、skill state 或 prompt。
**Why it's wrong:** rewrite 的语义来源是会话 latest state 或上传文件上下文；generate-only 字段会污染 rewrite prompt 和分支条件。
**Do this instead:** 这些字段只在 `backend/models/generate.py` 和 `DocumentService._build_initial_state()` 使用；rewrite 使用 `TaskSkillGraphState` 和 `rewrite_user_prompt` (`backend/states/skill_state.py`)。

### 恢复旧 edit 入口或第二套修改链路

**What happens:** 新建 `/api/edit`、`edit` task kind、`backend/skills/edit/` 或绕开 rewrite 的上传文件修改流程。
**Why it's wrong:** 上传文件修改已经收敛到 `rewrite_source="uploaded_file"`，后台复用 `RewriteSkillGraph`、任务队列、SSE、下载和类型感知写回。
**Do this instead:** 上传文件和会话修改都进入 `DocumentService.create_rewrite_task()`，skill 源在 `backend/skills/rewrite/`，graph 在 `backend/graphs/skill_graph.py`。

### Agent run 暴露敏感运行态

**What happens:** 在 agent run 审计、摘要工具、SSE 或前端卡片中返回完整客户原文、真实 token、私有路径、traceback、完整任务结果或下载路径。
**Why it's wrong:** Agent run 是前置流和 UI 摘要，不是排障日志或文件浏览接口。
**Do this instead:** 使用 scrub 和白名单摘要工具，参照 `backend/agents/task_context_assistant/logging.py`、`backend/agents/task_context_assistant/tools.py`。

## 错误处理

**Strategy:** API 层用 `HTTPException` 返回结构化错误；后台任务捕获异常后写 task 失败状态和 SSE `error`；取消按非 fatal 终态处理；retrieval、批注生成等可降级失败写 warning 后继续。

**Patterns:**
- API 错误 payload 使用 `success=false`、`error.code`、`message`、`timestamp`，示例在 `backend/api/template_candidates.py`。
- `_run_graph()` 捕获异常后推 `ErrorEventData`、调用 `sse_manager.send_error_threadsafe()`，再 `complete_task()` (`backend/services/document_service.py:991`)。
- `TaskCancelledException` 和 `asyncio.CancelledError` 作为取消处理，不应表现为致命失败 (`backend/graphs/base_graph.py:38`)。
- Word COM 创建失败抛诊断性 `RuntimeError`，并在 finally 路径关闭 doc、退出 Word、`CoUninitialize()` (`backend/util/word_util/word_application_util.py:132`)。
- bad case retrieval 失败降级为 `bm25_only` 或 unavailable payload，不阻塞批注生成 (`backend/retrieval/comment_bad_case_runtime.py`)。

## 横切关注点

**Logging:** `backend/util/log_util/progress_log.py` 处理用户可见进度日志；`backend/util/log_util/execution_log.py` 记录生成成功审计；`backend/util/log_util/sse_log_handler.py` 将任务上下文日志推到 SSE；`backend/agents/task_context_assistant/logging.py` 负责 agent run scrub 审计。
**Validation:** Pydantic 模型校验 API shape；service 校验上下文和文件一致性；`backend/api/download.py` 限制下载路径；`backend/util/common_util/template_candidates.py` 校验模板下载 allowlist。
**Authentication:** 未检测到统一应用鉴权中间件；新增外部暴露接口时要显式设计认证、授权、日志 scrub 和路径/URL 白名单。
**Security:** 不读取或输出 `backend/.env`；外部模板下载使用 allowlist；agent run 和任务摘要不得暴露完整客户原文、私有路径、token、traceback 或下载路径。
**Verification:** 后端代码改动至少运行 `python -m pytest tests -v`；Word COM 闭环必须回到 Windows + Word/WPS COM 环境；仅文档变更至少运行 `git diff --check`。

---

*后端架构分析：2026-06-25*
