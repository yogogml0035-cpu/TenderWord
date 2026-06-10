<!-- refreshed: 2026-06-09 -->
# 后端架构事实地图

**分析日期：** 2026-06-09

**范围：** 仅覆盖 `backend/` 子项目。事实来源为 `backend/` 源码、`backend/tests/`、`backend/requirements.txt`、`README.md`、`docs/backend.md`、`docs/interfaces-runtime.md` 和 `.agents/skills/gsd-map-codebase/SKILL.md`。`backend/.env` 文件存在，但不得读取或引用内容。

## 系统总览

```text
┌─────────────────────────────────────────────────────────────┐
│                       FastAPI 应用入口                       │
│                       `backend/main.py`                      │
├──────────────┬────────────────┬────────────────┬────────────┤
│  HTTP routers │ Pydantic models │ Service 编排层 │ SSE/任务查询 │
│ `backend/api` │ `backend/models` │`backend/services`│`backend/core`│
└───────┬──────┴────────┬───────┴────────┬───────┴─────┬──────┘
        │               │                │             │
        ▼               ▼                ▼             ▼
┌─────────────────────────────────────────────────────────────┐
│             任务队列 + LangGraph 执行层                      │
│ `backend/task/task_queue_manager.py`, `backend/graphs/`       │
└───────────────┬─────────────────────────────┬───────────────┘
                │                             │
                ▼                             ▼
┌───────────────────────────────┐   ┌─────────────────────────┐
│ Word 节点、业务 helper、COM 工具 │   │ Agent、Prompt、LLM、RAG  │
│ `backend/nodes/`              │   │ `backend/agents/`       │
│ `backend/helper/word_helper/` │   │ `backend/prompts/`      │
│ `backend/util/word_util/`     │   │ `backend/retrieval/`    │
└───────────────┬───────────────┘   └─────────────┬───────────┘
                │                                 │
                ▼                                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 本地上传/生成文件、会话内存态、日志、agent workspace、外部 HTTP/LLM │
│ `settings.UPLOAD_DIR`, `backend/logs/`, `backend/context_log/` │
└─────────────────────────────────────────────────────────────┘
```

后端是 TenderWord 的 FastAPI + LangGraph + Word COM 执行端，负责招标文档初次生成、上传文件/会话 rewrite、补充批注、模板候选代理、招标详情代理、上传下载、SSE、任务队列、LLM/agent 调用和 Word 写回。完整 Word 闭环依赖 Windows Python、`pywin32` 和本机 Word/WPS COM 环境；无 COM 环境只能验证非 COM 分支和纯逻辑。

## 组件职责

| 组件 | 职责 | 文件 |
| --- | --- | --- |
| FastAPI app | 创建应用、注册 `/api` router、配置 CORS、启动日志队列和绑定 SSE 主事件循环 | `backend/main.py:143`, `backend/main.py:176`, `backend/main.py:198` |
| API routers | 暴露生成、任务、SSE、agent run、补充批注、上传下载、模板候选、招标详情、会话心跳接口 | `backend/api/` |
| Pydantic models | 定义 API shape、任务状态、SSE event、agent run、生成模式、招标类型和模板候选契约 | `backend/models/generate.py:56`, `backend/models/sse.py:17`, `backend/models/agent_run.py:92` |
| Settings | 从 `backend/.env` 和环境变量加载运行配置、LLM、上传、外部接口、SSE、任务、锁和日志参数 | `backend/config/settings.py:20`, `backend/config/settings.py:24` |
| Tender config | 集中管理招标类型锚点、字号、content mode、受保护字段 profile 和 family 归并 | `backend/config/tender_config.py:142`, `backend/config/tender_config.py:157`, `backend/config/tender_config.py:185` |
| DocumentService | 选择 graph、创建任务、构造初始 state、提交后台线程、收敛 `done`/`error` 和任务结果 | `backend/services/document_service.py:402`, `backend/services/document_service.py:432`, `backend/services/document_service.py:993` |
| TaskQueueManager | 进程内任务队列、状态、心跳取消、后台清理、公平锁、进度、取消事件和 worker future | `backend/task/task_queue_manager.py:169`, `backend/task/task_queue_manager.py:281`, `backend/task/task_queue_manager.py:756` |
| SSEManager | 管理 SSE 连接、事件缓存、`Last-Event-ID` 重放、心跳和后台线程到主 loop 的调度 | `backend/core/sse_manager.py:44`, `backend/core/sse_manager.py:99`, `backend/core/sse_manager.py:395` |
| BaseGraph | LangGraph 基类，提供跨进程文件锁、节点进度包装、取消检查和同步/异步执行包装 | `backend/graphs/base_graph.py:351`, `backend/graphs/base_graph.py:703` |
| StandardTenderWorkflowGraph | 初次生成主拓扑，维护 Word 子图、`generation_mode` 分支、批注开关和后写回分支 | `backend/graphs/base_graph.py:480`, `backend/graphs/base_graph.py:533` |
| Tender graph classes | 按招标类型绑定差异节点，复用标准 graph 主干 | `backend/graphs/xjcg_tender_graph.py`, `backend/graphs/gngk_hw_zc_tender_graph.py`, `backend/graphs/gjgk_tender_graph.py` |
| SkillGraph | 通过 `TaskSkillWorkflow` 元数据构建 rewrite 等 task skill graph | `backend/graphs/skill_graph.py:15`, `backend/graphs/task_skill_workflows.py:27` |
| CommentSupplementGraph | 补充批注独立 graph，复用任务队列、SSE、锁和 `comment_agent` 写回 | `backend/graphs/comment_supplement_graph.py:19`, `backend/graphs/comment_supplement_graph.py:60` |
| Word nodes | 模板准备、抽参、删除、替换、正文生成、批注生成、写回、rewrite 节点 | `backend/nodes/` |
| Word helper | Word 业务 helper：段落边界、受保护字段、正文写回、样式回填、range、删除、语义匹配 | `backend/helper/word_helper/` |
| Word util | Word COM 技术层：COM lock/retry、Word 应用生命周期、锚点工具、常量、诊断 | `backend/util/word_util/word_com_manager.py:100`, `backend/util/word_util/word_application_util.py:132` |
| Generation agents | `generation_mode=agent` 的 DeepAgents 主/子智能体、workspace、协议解析和 `agent_step` | `backend/agents/generation/content_agents.py:845`, `backend/agents/generation/workspace.py:39` |
| Comment agents | 批注生成/校验/写回 LangChain agent、工具门禁和审计日志 | `backend/agents/comments/comment_agent.py:611`, `backend/agents/comments/tools.py:478` |
| Task context assistant | Agent run 前置流，读取白名单上下文并受控创建 rewrite 任务 | `backend/services/agent_run_service.py:306`, `backend/agents/task_context_assistant/tools.py:197` |
| Prompt layer | 生成、批注、rewrite、模板候选重排 prompt 渲染和机器契约解析 | `backend/prompts/` |
| Retrieval layer | 批注 bad case 检索，优先 hybrid，失败降级 `bm25_only`，为 `generate_comments` 和 `comment_agent` 注入 prompt context | `backend/retrieval/comment_bad_case_runtime.py:421`, `backend/nodes/common_word_nodes/generate_comments.py:237`, `backend/nodes/common_word_nodes/comment_agent.py:192` |

## 模式概览

**总体：** FastAPI 薄入口 + Pydantic 契约 + Service 编排 + 进程内任务队列 + LangGraph 工作流 + Word COM 临界资源串行化。

**关键特征：**
- API route 只做请求/响应、HTTP 错误封装和 service 调用；业务流程放入 `backend/services/`、`backend/graphs/`、`backend/nodes/`、`backend/helper/word_helper/`。
- 初次生成 graph 使用共享主干和 class attribute 绑定差异节点；新增招标类型优先复用 `StandardTenderWorkflowGraph`。
- 所有 Word 写入必须经过 `DocumentService`、`TaskQueueManager`、`BaseGraph`、跨进程文件锁、COM lock、取消检查和进度包装。
- 长任务状态、SSE 缓存和会话 rewrite history 是进程内状态；文档产物写入 `settings.UPLOAD_DIR`。
- Agent run 是任务创建前置流，输出 NDJSON；后台任务、SSE、取消、下载仍走 task/SSE/download 链路。
- `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 只属于初次 generate state，不进入 rewrite skill state 或 prompt surface。

## 分层

**API 层：**
- 用途：暴露 HTTP、SSE、NDJSON 入口，并把请求交给 service 或 util。
- 位置：`backend/api/`
- 包含：`generate.py`、`agent.py`、`comment_supplement.py`、`tasks.py`、`stream.py`、`upload.py`、`download.py`、`tender.py`、`template_candidates.py`、`conversations.py`
- 依赖：`backend/models/`、`backend/services/`、`backend/util/common_util/`
- 使用方：前端 API client、本地调试和外部健康检查。

**模型层：**
- 用途：保存跨 API、service、SSE、task 和前端同步的 shape。
- 位置：`backend/models/`
- 包含：`GenerateRequest`、`FormType`、`TaskKind`、`SSEEventType`、`AgentRunStreamRequest`、模板候选、上传和招标数据模型。
- 依赖：Pydantic v2。
- 使用方：`backend/api/`、`backend/services/`、`backend/core/`、`backend/task/` 和前端类型同步。

**配置层：**
- 用途：管理运行配置、招标类型锚点、受保护字段和外部接口配置。
- 位置：`backend/config/`
- 包含：`settings.py`、`tender_config.py`
- 依赖：`pydantic-settings`、环境变量和 `backend/.env`。
- 使用方：service、task queue、Word nodes、外部 HTTP util、retrieval。

**Service 层：**
- 用途：封装业务编排，避免 API route 直接操作 graph、任务队列、COM 或 agent。
- 位置：`backend/services/`
- 包含：`document_service.py`、`task_service.py`、`conversation_service.py`、`agent_run_service.py`、`chat_stream_service.py`、`template_candidate_ranking_service.py`
- 依赖：models、graphs、task queue、SSE、agents、prompts、common util。
- 使用方：`backend/api/`。

**Task/SSE 层：**
- 用途：管理长任务生命周期、进度、取消、心跳和浏览器事件通道。
- 位置：`backend/task/`, `backend/core/`
- 包含：`TaskQueueManager`、`TaskProgress`、`SSEManager`、SSE event cache 和 replay。
- 依赖：settings、models、log util。
- 使用方：`DocumentService`、`TaskService`、`stream.py`、agent step callback。

**Graph/State/Node 层：**
- 用途：用 LangGraph 编排生成、rewrite 和补充批注，并用 TypedDict state 承载节点输入输出。
- 位置：`backend/graphs/`, `backend/states/`, `backend/nodes/`
- 包含：标准 tender graph、类型 graph、skill graph、comment supplement graph、共享节点和类型节点。
- 依赖：Word helper/util、agents、prompts、retrieval、task queue。
- 使用方：`DocumentService`。

**Word 操作层：**
- 用途：操作 Word 文档、范围、段落、表格、批注、样式和 COM 生命周期。
- 位置：`backend/helper/word_helper/`, `backend/util/word_util/`
- 包含：业务 helper 和 COM 技术 helper。
- 依赖：pywin32/COM、Word/WPS、本地文件、tender config。
- 使用方：`backend/nodes/` 和 `backend/scripts/diagnose_word.py`。

**Agent/Prompt/LLM 层：**
- 用途：渲染 prompt、调用 LLM、执行 DeepAgents/LangChain agent、记录审计和产出结构化过程事件。
- 位置：`backend/agents/`, `backend/prompts/`, `backend/skills/`, `backend/util/common_util/llm_stream_utils.py`
- 包含：content agent、comment agent、task context assistant、rewrite skill、LLM stream util。
- 依赖：settings、LangChain、DeepAgents、OpenAI-compatible SDK。
- 使用方：graph nodes、agent run service、template candidate ranking。

**Retrieval 层：**
- 用途：为批注生成注入 bad case context，并在向量检索不可用时自动降级。
- 位置：`backend/retrieval/`
- 包含：bad case loader、BM25、Qdrant store、embedding client、hybrid merge、runtime cache。
- 依赖：`backend/retrieval/bad_cases/`、Qdrant、embedding API、环境变量。
- 使用方：`backend/nodes/common_word_nodes/generate_comments.py` 和 `backend/nodes/common_word_nodes/comment_agent.py`。

## 数据流

### 初次生成路径

1. `POST /api/generate` 进入 `create_generate_task()`，请求模型是 `GenerateRequest` (`backend/api/generate.py:51`, `backend/models/generate.py:117`)。
2. `DocumentService.create_task()` 使用 `request.form_type.value` 从 `GRAPH_REGISTRY` 选择 graph (`backend/services/document_service.py:432`, `backend/services/document_service.py:443`)。
3. `_build_initial_state()` 将 tender data、文件路径、锚点、模型相关 generate-only 字段写入 graph state (`backend/services/document_service.py:904`)。
4. `_submit_graph_task()` 调用 `TaskQueueManager.add_task()` 并把 `_run_graph()` 提交到后台线程池 (`backend/services/document_service.py:711`, `backend/task/task_queue_manager.py:281`)。
5. `_run_graph()` 实例化 graph、估算节点总数、创建独立事件循环并调用 `_invoke_graph_async()` (`backend/services/document_service.py:993`, `backend/services/document_service.py:1358`)。
6. `invoke_with_timing_async()` 等待公平锁、获取跨进程文件锁、登记运行中的 async task，并执行 compiled graph (`backend/graphs/base_graph.py:703`, `backend/graphs/base_graph.py:761`, `backend/graphs/base_graph.py:771`, `backend/graphs/base_graph.py:782`)。
7. `StandardTenderWorkflowGraph.build_graph()` 执行 `prepare_template -> extract_tender_params`，并行进入 Word 子图和生成分支，再汇合到 `update_word` (`backend/graphs/base_graph.py:533`, `backend/graphs/base_graph.py:573`, `backend/graphs/base_graph.py:595`)。
8. 结果由 `_build_task_result_payload()` 收敛为 output file、file size、model、style/comment writeback summary；`SSEManager` 推送 `done` 或 `error` (`backend/services/document_service.py:1304`, `backend/core/sse_manager.py:202`, `backend/core/sse_manager.py:230`)。

### Rewrite Skill 路径

1. `POST /api/agent/runs/stream` 进入 `stream_agent_run()`，返回 NDJSON `StreamingResponse` (`backend/api/agent.py:19`)。
2. `AgentRunService.stream()` 先发 `run_started` 和 `thinking_stage`，再执行上下文 guard 或 DeepAgents runner (`backend/services/agent_run_service.py:329`, `backend/services/agent_run_service.py:410`)。
3. 需要更多上下文时返回 `needs_input`；条件满足时由 `create_rewrite_task_tool()` 受控调用 `DocumentService.create_rewrite_task()` (`backend/services/agent_run_service.py:438`, `backend/agents/task_context_assistant/tools.py:197`)。
4. 上传文件 rewrite 必须具备 `form_type`、`insertion_config`、`tender_lx`、`fund_source_lx`；会话 rewrite 必须已有 latest rewrite history (`backend/services/document_service.py:466`)。
5. `SkillGraph.for_skill("rewrite")` 根据 `TaskSkillWorkflow` 元数据执行 `resolve_rewrite_target`、`extract_rewrite_context`、`get_rewrite_comments`、`delete_section`、`rewrite_text`、`update_word` (`backend/graphs/skill_graph.py:15`, `backend/graphs/task_skill_workflows.py:27`)。
6. rewrite 后台任务复用 task/SSE/download 链路；agent run 只输出 `task_accepted` 和 `done` (`backend/services/agent_run_service.py:490`, `backend/services/agent_run_service.py:499`)。

### 补充批注路径

1. `POST /api/comment-supplement` 进入 `create_comment_supplement_task()` (`backend/api/comment_supplement.py:24`)。
2. `DocumentService.create_comment_supplement_task()` 校验 `conversation_id`、`source_file`、latest `rewrite_state`、`polished_text` 和 source/latest 文件一致性 (`backend/services/document_service.py:596`)。
3. `CommentSupplementGraph` 执行 `prepare_comment_supplement -> comment_agent -> finalize_comment_supplement` (`backend/graphs/comment_supplement_graph.py:60`)。
4. `comment_agent_writeback()` 允许在 `task_kind=comment_supplement` 或 `generation_mode=agent` 且无初始批注时生成批注，再校验并写回 Word (`backend/nodes/common_word_nodes/comment_agent.py:327`)。
5. 成功后 `ConversationService.append_comment_supplement_success()` 更新会话 latest `rewrite_state` (`backend/services/conversation_service.py:129`)。

### SSE 事件路径

1. 前端连接 `GET /api/stream/{task_id}`，`stream_task_events()` 校验任务存在并解析 `Last-Event-ID` (`backend/api/stream.py:23`)。
2. `SSEManager.event_stream()` 建立 client、重放 missed events、创建心跳并持续 yield SSE 格式字符串 (`backend/core/sse_manager.py:395`)。
3. 后台线程通过 `send_*_threadsafe()` 把 coroutine 调度回 FastAPI 主事件循环 (`backend/core/sse_manager.py:99`, `backend/core/sse_manager.py:127`)。
4. `done` 或 `error` 事件结束 SSE 流；历史事件中已有终态时刷新连接直接结束 (`backend/core/sse_manager.py:395`)。

### 模板候选路径

1. `GET /api/template-candidates` 调用 `fetch_template_candidates()` 代理外部模板候选接口 (`backend/api/template_candidates.py:90`, `backend/util/common_util/template_candidates.py:73`)。
2. `TemplateCandidateRankingService.rank_candidates()` 对同优先级候选按项目名调用 LLM 重排，失败时回退优先级排序 (`backend/services/template_candidate_ranking_service.py:31`)。
3. `GET /api/template-candidates/download` 代理下载外部模板文件，`fetch_template_file()` 校验协议和允许主机 (`backend/api/template_candidates.py:142`, `backend/util/common_util/template_candidates.py:117`)。
4. `POST /api/template-candidates/select` 下载推荐模板并通过 `persist_file_bytes()` 落到 `settings.UPLOAD_DIR` (`backend/api/template_candidates.py:201`, `backend/util/common_util/upload_storage.py:61`)。

**状态管理：**
- 任务状态、队列和结果：进程内 `TaskQueueManager`，路径 `backend/task/task_queue_manager.py`。
- SSE 客户端和事件 cache：进程内 `SSEManager`，路径 `backend/core/sse_manager.py`。
- 会话 rewrite history：进程内 `ConversationService`，最多保留 `MAX_REWRITE_MESSAGES`，路径 `backend/services/conversation_service.py:12`。
- graph state：TypedDict state 在节点之间传递，路径 `backend/states/base_state.py` 和 `backend/states/skill_state.py`。
- 文档产物：本地文件，根目录来自 `settings.UPLOAD_DIR`，路径安全由 `backend/api/download.py:25` 和 `backend/util/common_util/upload_storage.py:38` 维护。
- Agent workspace 和审计日志：本地 `backend/context_log/`、`backend/logs/` 相关目录，命名清洗复用 `backend/agents/log_naming.py:15`。

## 核心抽象

**`FormType` / runtime `tender_type`:**
- 用途：API 表单类型和 graph 运行态类型之间的桥。
- 示例：`backend/models/generate.py:56`, `backend/services/document_service.py:904`
- 模式：API 使用带 `_tender` 的 `FormType`；进入 graph state 时去掉 `_tender`。新增类型必须同步 model、graph registry、state、nodes、config、tests 和前端映射。

**`TenderAnchorConfig` / `ProtectedFieldProfile`:**
- 用途：管理锚点、字号、content start/update mode 和受保护字段顺序。
- 示例：`backend/config/tender_config.py:20`, `backend/config/tender_config.py:30`
- 模式：新类型差异优先进入配置；只有 Word 流程闭环不同才新增节点或 graph。

**`StandardTenderWorkflowGraph`:**
- 用途：初次生成主流程真源。
- 示例：`backend/graphs/base_graph.py:480`
- 模式：类型 graph 通过 class attribute 绑定 `NODE_*`，不要复制 `build_graph()`。

**`TaskSkillWorkflow`:**
- 用途：声明 task skill 的 state、节点、普通边、等待边、条件边和节点估算；当前跟踪源码中只注册 `rewrite`。
- 示例：`backend/graphs/task_skill_workflows.py:27`, `backend/graphs/task_skill_types.py`
- 模式：新 skill 先新增 `backend/skills/<skill_id>/SKILL.md` 和运行时节点，再在 `_TASK_SKILL_WORKFLOWS` 注册。

**`SSEEvent` / `AgentStepEventData`:**
- 用途：后台任务事件和 agent 过程卡事件契约。
- 示例：`backend/models/sse.py:17`, `backend/models/sse.py:219`
- 模式：新事件字段必须同步后端发送方、前端 SSE parser、类型和测试。

**`AgentRunStreamRequest`:**
- 用途：右侧 agent run 可见的最小受控上下文。
- 示例：`backend/models/agent_run.py:92`
- 模式：agent run 只消费白名单 `context_snapshot`，不要读取完整客户原文、真实路径清单、token、traceback 或下载路径。

**`stream_llm_completion()`:**
- 用途：OpenAI-compatible LLM 流式调用统一入口，支持超时、回调和模型配置。
- 示例：`backend/util/common_util/llm_stream_utils.py:190`
- 模式：后端 LLM 调用复用该 helper 或 `create_generation_chat_model()`，不要在节点里散落新的 SDK 初始化。

**`Comment bad case retrieval` 运行时：**
- 用途：为批注生成提供可注入 prompt 的坏案例上下文。
- 示例：`backend/retrieval/comment_bad_case_runtime.py:421`
- 模式：retrieval 失败不阻塞批注生成；记录 warning 和 retrieval JSON，前端不展示命中详情。

## 入口点

**应用入口：**
- 位置：`backend/main.py`
- 触发：`uvicorn backend.main:app` 或等价 ASGI 启动。
- 职责：初始化日志、FastAPI app、CORS、router、startup/shutdown、健康检查。

**生成 API：**
- 位置：`backend/api/generate.py:51`
- 触发：`POST /api/generate`
- 职责：创建初次生成任务并返回 `GenerateResponse`。

**任务 API：**
- 位置：`backend/api/tasks.py:36`, `backend/api/tasks.py:127`, `backend/api/tasks.py:220`
- 触发：`GET /api/tasks`、`DELETE /api/tasks/{task_id}`、`POST /api/tasks/{task_id}/heartbeat`
- 职责：查询、取消和维持任务心跳。

**SSE 接口：**
- 位置：`backend/api/stream.py:23`
- 触发：`GET /api/stream/{task_id}`
- 职责：推送任务日志、LLM snapshot、进度、agent_step、done、error 和 heartbeat。

**前置智能体接口：**
- 位置：`backend/api/agent.py:19`
- 触发：`POST /api/agent/runs/stream`
- 职责：输出 NDJSON agent run 过程，创建 rewrite 任务或返回 needs_input。

**补充批注 API：**
- 位置：`backend/api/comment_supplement.py:24`
- 触发：`POST /api/comment-supplement`
- 职责：基于会话 latest 文档创建补充批注任务。

**模板候选 API：**
- 位置：`backend/api/template_candidates.py:90`, `backend/api/template_candidates.py:142`, `backend/api/template_candidates.py:201`
- 触发：`GET /api/template-candidates`、`GET /api/template-candidates/download`、`POST /api/template-candidates/select`
- 职责：外部模板候选代理、AI 重排、白名单下载、落盘选择。

**招标详情 API：**
- 位置：`backend/api/tender.py:63`
- 触发：`GET /api/tender/{tender_no}` 或 router 定义的招标详情查询。
- 职责：代理外部招标详情接口并归一化招标类型 payload。

## 架构约束

- **线程模型：** FastAPI 主事件循环负责 HTTP/SSE；`DocumentService` 用 `ThreadPoolExecutor(max_workers=4)` 提交任务；每个 graph 任务在线程中创建独立 asyncio loop (`backend/services/document_service.py:41`, `backend/services/document_service.py:993`)。
- **Word 串行化：** 任务先通过 `TaskQueueManager.wait_for_turn()` 保证公平顺序，再通过 `CrossProcessFileLock` 保护 graph 执行，再通过 `com_lock()` 保护 COM 创建/关闭和底层操作 (`backend/graphs/base_graph.py:761`, `backend/graphs/base_graph.py:771`, `backend/util/word_util/word_com_manager.py:100`)。
- **全局状态：** 单例包括 `_task_queue`、`sse_manager`、`_conversation_service`、`_document_service`、`_agent_run_service`、`settings` 和 graph registry (`backend/task/task_queue_manager.py:942`, `backend/services/document_service.py:188`, `backend/config/settings.py:277`)。
- **持久化：** 任务、SSE、会话都是进程内态，服务重启后不恢复；文档和日志是文件态。
- **环境：** `backend/config/settings.py` 和 `backend/retrieval/config.py` 会读取 `backend/.env`，但代码地图、日志和回复不得输出真实值。
- **循环导入：** 未检测到需要记录的已知循环链；多处通过延迟导入降低循环风险，例如 `backend/graphs/base_graph.py` 内部导入 task queue。
- **跨层契约：** API shape、SSE、任务类型、招标类型、prompt/LLM、Word helper、模板候选和 retrieval 改动必须同步模型、前端类型/API client、测试和知识包。

## 反模式

### API route 直接执行业务或 Word COM

**问题形态：** 在 `backend/api/*.py` 中直接打开 Word、跑 LangGraph、调用 COM 或拼接复杂业务流程。
**风险原因：** 绕过 `TaskQueueManager`、公平锁、文件锁、取消检查、SSE 终态和日志上下文，会导致并发写 Word、前端静默等待或任务状态丢失。
**正确做法：** API route 调用 service；Word 写入必须从 `DocumentService` 进入 graph/node/helper，例如 `backend/api/generate.py:51` -> `backend/services/document_service.py:432`。

### 复制类型 graph 主流程

**问题形态：** 为新招标类型复制 `StandardTenderWorkflowGraph.build_graph()` 并只改少量节点。
**风险原因：** `generation_mode`、`comment_generation_mode`、`comment_agent`、进度节点和后写回分支容易漂移。
**正确做法：** 新建 `<runtime_type>_tender_graph.py` 继承 `StandardTenderWorkflowGraph` 或现有 family graph，仅覆盖 `STATE_CLS` 和必要 `NODE_*`，参照 `backend/graphs/gngk_hw_cz_tender_graph.py`。

### 把 generate-only 字段带入 rewrite

**问题形态：** 将 `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 写入 rewrite request、skill state 或 rewrite prompt。
**风险原因：** rewrite 是 task skill 链路，语义来源是会话 latest state 或上传文件上下文；generate-only 字段污染 rewrite prompt 和分支条件。
**正确做法：** 只在 `GenerateRequest` 和 `_build_initial_state()` 使用这些字段，rewrite state 使用 `TaskSkillGraphState` 和 `rewrite_user_prompt`，参照 `backend/models/generate.py:117`、`backend/services/document_service.py:784`。

### 恢复旧 edit 入口或平行 task skill 链路

**问题形态：** 为上传文件修改重新创建 `/api/edit`、`edit` task kind、`backend/skills/edit/` 或绕过 `rewrite` 的第二套 graph。
**风险原因：** 当前上传文件修改语义已经收敛到 `rewrite_source="uploaded_file"`，后台仍复用 `SkillGraph.for_skill("rewrite")`、任务队列、SSE 和下载链路；平行入口会绕开上下文 guard、类型感知写回和既有测试。
**正确做法：** 上传文件和会话修改都进入 `DocumentService.create_rewrite_task()`，skill 源码落在 `backend/skills/rewrite/SKILL.md`、workflow 注册在 `backend/graphs/task_skill_workflows.py:27`，上传来源状态由 `backend/services/document_service.py:849` 设置。

### 前端或 agent 暴露完整运行态敏感信息

**问题形态：** agent run 审计、摘要工具或 SSE 返回完整客户原文、真实 token、traceback、完整任务结果、私有下载路径。
**风险原因：** Agent run 是前置流和 UI 摘要，不是排障日志或文件系统浏览接口。
**正确做法：** 使用 scrub 和只读公共摘要工具，参照 `backend/agents/task_context_assistant/logging.py:32`、`backend/agents/task_context_assistant/tools.py:362`。

## 错误处理

**策略：** API 层用 `HTTPException` 返回结构化错误；后台任务捕获异常后同时写任务失败状态和 SSE `error`；取消被标记为非 fatal；retrieval 和批注生成的可降级失败记录 warning 后返回空/降级结果。

**模式：**
- API 错误封装为带 `success=false`、`error.code`、`message`、`timestamp` 的 payload，示例在 `backend/api/template_candidates.py:44`。
- `_run_graph()` 捕获异常，发送 `ErrorEventData` 和 `sse_manager.send_error_threadsafe()`，再调用 `TaskQueueManager.complete_task()` (`backend/services/document_service.py:993`)。
- `TaskCancelledException` 和 `asyncio.CancelledError` 作为取消处理，`is_fatal=False` (`backend/services/document_service.py:1194`)。
- `generate_comments()` 捕获 retrieval/LLM/JSON 异常，返回空 `polished_comments` 或降级 prompt，不阻塞主任务 (`backend/nodes/common_word_nodes/generate_comments.py:237`)。
- Word COM 创建失败生成诊断性 `RuntimeError`，并在 finally 路径关闭文档、退出 Word、`CoUninitialize()` (`backend/util/word_util/word_application_util.py:132`)。

## 横切关注点

**日志：** 使用标准 logging、`progress_log`、`execution_log`、SSE log handler、agent audit log。用户可见进度进入 `progress_log`；排障详情进入 execution/audit 日志。关键路径：`backend/util/log_util/`、`backend/agents/task_context_assistant/logging.py`。

**校验：** Pydantic 模型做 API 入参校验；service 做上下文和文件存在性校验；download/template candidate util 做路径和 URL 白名单校验。关键路径：`backend/models/generate.py`、`backend/models/agent_run.py`、`backend/api/download.py:25`、`backend/util/common_util/template_candidates.py:108`。

**认证：** 未检测到应用级用户鉴权中间件；存在 `python-jose` 和 `passlib` 依赖，但 API router 未启用统一认证层。新增外部暴露接口需要显式设计认证和授权。

**安全：** 不读取或输出 `backend/.env`；下载只允许 `settings.UPLOAD_DIR`；模板下载只允许配置白名单主机；agent run 审计需要 scrub。关键路径：`backend/api/download.py:25`、`backend/util/common_util/template_candidates.py:108`、`backend/agents/task_context_assistant/logging.py:32`。

---

*架构分析：2026-06-09*
