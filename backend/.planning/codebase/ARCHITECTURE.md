<!-- refreshed: 2026-06-08 -->
# 后端架构事实地图

**分析日期：** 2026-06-08

**范围：** 仅覆盖 `backend/` 子项目。事实来源为 `backend/` 源码、`backend/tests/`、`backend/requirements.txt`、项目根 `AGENTS.md` 和项目内 `.agents/skills/` 的轻量索引；`backend/.env` 只记录存在性，不读取内容。

## 系统总览

```text
┌─────────────────────────────────────────────────────────────┐
│                       FastAPI 后端入口                       │
│                         `backend/main.py`                    │
├──────────────┬───────────────┬───────────────┬──────────────┤
│   API 路由    │   Pydantic 模型 │   Service 编排 │  SSE/任务状态 │
│ `backend/api`│ `backend/models`│`backend/services`│`backend/core`│
└──────┬───────┴───────┬───────┴───────┬───────┴──────┬───────┘
       │               │               │              │
       ▼               ▼               ▼              ▼
┌─────────────────────────────────────────────────────────────┐
│          TaskQueueManager + LangGraph 工作流执行层           │
│ `backend/task/task_queue_manager.py`, `backend/graphs/`       │
└───────────────┬─────────────────────────────┬───────────────┘
                │                             │
                ▼                             ▼
┌───────────────────────────────┐   ┌─────────────────────────┐
│ Word 节点 / Word helper / COM  │   │ Agent / Prompt / LLM     │
│ `backend/nodes/`, `backend/helper/word_helper/`,              │
│ `backend/util/word_util/`      │   │ `backend/agents/`,       │
│                               │   │ `backend/prompts/`       │
└───────────────┬───────────────┘   └─────────────┬───────────┘
                │                                 │
                ▼                                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 本地上传目录、生成文档、日志、agent workspace、外部 LLM/HTTP/RAG │
│ `settings.UPLOAD_DIR`, `backend/logs/`, `backend/prompts_log/`, │
│ `backend/retrieval/`, `backend/util/common_util/`             │
└─────────────────────────────────────────────────────────────┘
```

后端是 TenderWord 的 API 和任务执行端，负责招标文档生成、rewrite、补充批注、模板候选代理、招标详情代理、文件上传下载、任务队列、SSE 事件、LLM 调用、LangGraph 编排和 Word COM 写回。完整 Word 闭环依赖 Windows Python、`pywin32` 和本机 Word/WPS COM 环境。

## 组件职责

| 组件 | 职责 | 文件 |
|-----------|----------------|------|
| FastAPI app | 创建应用、注册 router、配置 CORS、启动日志监听和 SSE loop | `backend/main.py` |
| API routers | 暴露 `/api` 下生成、任务、SSE、agent run、上传下载、模板候选、招标详情接口 | `backend/api/` |
| Pydantic models | 定义 API 请求/响应、SSE、任务、agent run、模板候选和招标数据契约 | `backend/models/` |
| DocumentService | 生成、rewrite、补充批注任务创建，graph 初始 state 装配，任务结果收敛 | `backend/services/document_service.py` |
| TaskQueueManager | 进程内任务队列、串行执行、公平锁等待、取消、心跳和进度 | `backend/task/task_queue_manager.py` |
| SSEManager | SSE 客户端管理、事件缓存、跨线程发送、`Last-Event-ID` 重放 | `backend/core/sse_manager.py` |
| BaseGraph | LangGraph 基类、跨进程文件锁、取消检查、进度包装 | `backend/graphs/base_graph.py` |
| StandardTenderWorkflowGraph | 标准生成主拓扑，维护 `workflow`/`agent` 生成分支和批注分支 | `backend/graphs/base_graph.py` |
| Tender graph classes | 按招标类型绑定差异节点，复用标准主干 | `backend/graphs/*_tender_graph.py` |
| SkillGraph | 按 task skill 元数据构建 rewrite 工作流 graph | `backend/graphs/skill_graph.py` |
| CommentSupplementGraph | 补充批注任务图，复用任务队列、SSE、锁和 `comment_agent` | `backend/graphs/comment_supplement_graph.py` |
| Word nodes | 模板准备、抽参、删除、替换、生成、批注、写回等 graph 节点 | `backend/nodes/` |
| Word helper | Word 业务逻辑，包含段落边界、正文写回、受保护字段、样式回填 | `backend/helper/word_helper/` |
| Word util | COM 生命周期、Word 常量、锚点查找、底层插入和诊断工具 | `backend/util/word_util/` |
| Generation agents | `generation_mode=agent` 的 DeepAgents 主/子智能体和 workspace | `backend/agents/generation/` |
| Comment agents | 批注候选生成、校验、写回工具和审计 workspace | `backend/agents/comments/` |
| Task context assistant | 任务创建前置 agent run，受控调用 rewrite skill | `backend/agents/task_context_assistant/` |
| Prompt layer | 生成、rewrite、批注、模板候选重排 prompt 渲染与契约解析 | `backend/prompts/` |
| Retrieval layer | 批注坏案例检索的 BM25、Qdrant、embedding 与 hybrid merge，当前主要服务诊断/实验脚本 | `backend/retrieval/` |

## 模式概览

**Overall:** FastAPI 薄入口 + Service 编排 + 进程内任务队列 + LangGraph workflow + Word COM 临界资源串行化。

**Key Characteristics:**
- API route 负责校验和 HTTP 错误封装，业务流程进入 `backend/services/`、`backend/graphs/`、`backend/nodes/` 和 `backend/helper/word_helper/`。
- 标准生成 graph 通过 class attribute 绑定类型差异节点，避免复制整套流程。
- 所有 Word 写入经 `DocumentService`、`TaskQueueManager`、`BaseGraph`、COM lock、取消检查和进度包装。
- 长任务结果、任务状态、SSE buffer 和会话快照是进程内状态；文件产物落到 `settings.UPLOAD_DIR`。
- 智能体运行时通过统一 callback 写入 `agent_step` SSE，终态仍由任务 `done` / `error` 表达。

## 分层

**API 层：**
- Purpose: 暴露 HTTP 和流式接口，封装 FastAPI `HTTPException` 与响应模型。
- Location: `backend/api/`
- Contains: `generate.py`、`agent.py`、`comment_supplement.py`、`tasks.py`、`stream.py`、`upload.py`、`download.py`、`tender.py`、`template_candidates.py`、`conversations.py`
- Depends on: `backend/models/`、`backend/services/`、`backend/util/common_util/`
- Used by: 前端 API client 和本地调试调用。

**模型层：**
- Purpose: 定义跨层 API shape 和运行态枚举。
- Location: `backend/models/`
- Contains: `GenerateRequest`、`FormType`、`GenerationMode`、`CommentGenerationMode`、`TaskKind`、`SSEEventType`、`AgentRunStreamRequest`
- Depends on: Pydantic v2。
- Used by: API、service、task、SSE、前后端契约同步。

**Service 层：**
- Purpose: 创建任务、选择 graph、装配初始 state、收敛结果、提供任务/会话/agent run 编排。
- Location: `backend/services/`
- Contains: `document_service.py`、`task_service.py`、`conversation_service.py`、`agent_run_service.py`、`chat_stream_service.py`、`template_candidate_ranking_service.py`
- Depends on: models、task queue、graphs、SSE、prompt/agent 工具。
- Used by: API routers。

**Task/SSE 层：**
- Purpose: 管理长任务生命周期和浏览器事件通道。
- Location: `backend/task/`, `backend/core/`
- Contains: 任务状态、心跳取消、进度节点、SSE cache、重连重放、跨线程事件调度。
- Depends on: settings、models、log util。
- Used by: `DocumentService`、`TaskService`、`stream.py`、agent step callback。

**Graph/Node 层：**
- Purpose: 用 LangGraph 编排生成、rewrite 和补充批注节点。
- Location: `backend/graphs/`, `backend/nodes/`, `backend/states/`
- Contains: 标准 tender graph、类型 graph、task skill graph、state TypedDict、Word 节点。
- Depends on: Word helper/util、prompts、agents、task queue。
- Used by: `DocumentService`。

**Word 操作层：**
- Purpose: 操作 Word 文档内容、范围、段落、表格、批注和样式。
- Location: `backend/helper/word_helper/`, `backend/util/word_util/`
- Contains: 业务 helper 和底层 COM 工具。
- Depends on: pywin32/COM、配置锚点、Word 常量。
- Used by: graph nodes 和诊断脚本。

**智能体与 Prompt 层：**
- Purpose: 生成正文、审核修订、批注候选和任务上下文助手。
- Location: `backend/agents/`, `backend/prompts/`, `backend/skills/`
- Contains: DeepAgents content agent、LangChain comment agent、rewrite skill 声明、prompt builders。
- Depends on: LLM config、LangGraph/LangChain/DeepAgents、workspace 文件系统。
- Used by: 标准 graph、comment supplement graph、agent run service。

**检索层：**
- Purpose: 为批注坏案例提供 BM25 + vector hybrid retrieval，当前主要用于诊断/实验脚本，不属于主业务链路。
- Location: `backend/retrieval/`, `backend/scripts/test_comment_hybrid_retrieval.py`
- Contains: Qdrant store、embedding client、bad case loader、hybrid score。
- Depends on: Qdrant HTTP、embedding API、环境变量。
- Used by: 批注检索诊断脚本；接入正式批注链路前需要补降级行为和测试。

## 数据流

### Primary Request Path: 初次生成

1. 前端提交 `POST /api/generate`，`backend/api/generate.py` 校验 `GenerateRequest`。
2. `DocumentService.create_task()` 根据 `FormType` 从 `GRAPH_REGISTRY` 选择 graph，并创建进程内任务。
3. Service 将表单数据、文件路径、锚点、模型、`generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 写入初始 state。
4. `TaskQueueManager` 排队并通过后台线程运行 graph。
5. `BaseGraph.ainvoke()` 等待公平队列、获取跨进程文件锁、执行取消检查和进度包装。
6. `StandardTenderWorkflowGraph` 执行 `prepare_template`、`extract_tender_params`、Word 子流程、正文生成或 `content_agent`、批注分支、`update_word`。
7. `DocumentService` 收敛输出文件、下载 URL、样式/批注写回摘要和会话 `rewrite_state`。
8. `SSEManager` 推送 `progress`、`llm`、`agent_step`、`done` 或 `error`。

### Rewrite Skill Path

1. 前端提交 `POST /api/agent/runs/stream`，`backend/api/agent.py` 返回 NDJSON。
2. `AgentRunService` 读取受控 `AgentRunContextSnapshot`，通过 `backend/agents/task_context_assistant/` 判断 rewrite 前置条件。
3. 条件不足返回 `needs_input`，条件满足调用 `create_rewrite_task_tool`。
4. 工具进入 `DocumentService.create_rewrite_task()`，基于会话 history 或上传 Word 文件构造 `TaskSkillGraphState`。
5. `SkillGraph.for_skill("rewrite")` 使用 `backend/graphs/task_skill_workflows.py` 中的 workflow 元数据执行 `resolve_rewrite_target`、上下文抽取、批注提取、删除、`rewrite_text`、类型感知 `update_word`。
6. 后台任务继续使用既有 task/SSE/download 链路；agent run 只返回 `task_accepted` 和 `done`。

### Comment Supplement Path

1. 前端提交 `POST /api/comment-supplement`，请求模型为 `CommentSupplementRequest`。
2. `DocumentService.create_comment_supplement_task()` 校验 `conversation_id`、`source_file`、latest `rewrite_state` 和 `polished_text`。
3. `CommentSupplementGraph` 执行 `prepare_comment_supplement -> comment_agent -> finalize_comment_supplement`。
4. `comment_agent_writeback` 调用 `backend/agents/comments/` 生成、校验并写回补充批注。
5. 成功后新的 `prepared_doc_path` 写回会话 latest `rewrite_state`，任务通过 `done` 暴露下载信息。

### Template Candidate Path

1. `GET /api/template-candidates` 调用 `fetch_template_candidates()` 从外部系统代理获取候选。
2. `TemplateCandidateRankingService.rank_candidates()` 在同优先级候选内使用 LLM 重排。
3. `GET /api/template-candidates/download` 代理下载外部模板文件，校验 URL 和允许主机。
4. `POST /api/template-candidates/select` 下载推荐模板并通过 `persist_file_bytes()` 落到上传目录。

**State Management:**
- 任务、SSE、会话快照：进程内存态，核心文件是 `backend/task/task_queue_manager.py`、`backend/core/sse_manager.py`、`backend/services/conversation_service.py`。
- 文档产物：本地文件态，核心配置是 `settings.UPLOAD_DIR`，路径安全在 `backend/api/download.py` 和 `backend/util/common_util/upload_storage.py`。
- Agent workspace：本地审计文件态，路径在 `backend/prompts_log/content_agent_workspace/` 和 `backend/prompts_log/comment_agent_audit/`。

## 核心抽象

**FormType / tender_type:**
- Purpose: 区分 UI 表单类型和 graph 运行态招标类型。
- Examples: `FormType.GNGK_HW_CZ_TENDER` in `backend/models/generate.py`，`tender_type="gngk_hw_cz"` in state。
- Pattern: `<runtime_type>_tender` 进入 API；无 `_tender` 的 runtime type 进入 graph 和 tender config。

**TenderAnchorConfig:**
- Purpose: 管理锚点、字号、content start/update mode 和 protected field profile。
- Examples: `backend/config/tender_config.py`
- Pattern: 新类型先补配置，不在节点里硬编码 fallback。

**StandardTenderWorkflowGraph:**
- Purpose: 标准生成拓扑真源。
- Examples: `backend/graphs/base_graph.py`
- Pattern: 类型 graph 只绑定差异节点；`generation_mode` 和 `comment_generation_mode` 分支在基类维护。

**TaskSkillWorkflow:**
- Purpose: 用元数据声明 rewrite task skill 的节点、边、条件边和总节点估算。
- Examples: `backend/graphs/task_skill_workflows.py`
- Pattern: 新 skill 应注册 `TaskSkillWorkflow`，再通过 `SkillGraph.for_skill()` 执行。

**SSEEvent / AgentStepEventData:**
- Purpose: 任务事件和智能体过程事件契约。
- Examples: `backend/models/sse.py`, `backend/core/sse_manager.py`
- Pattern: 新事件必须同步后端发送方、前端 SSE named event、类型和测试。

**NDJSON stream line:**
- Purpose: agent run 和 plain chat 流的事件行序列化辅助，不承载业务决策。
- Examples: `backend/services/chat_stream_service.py`, `backend/services/agent_run_service.py`
- Pattern: 事件 shape 变化同步前端 NDJSON parser 和类型；不要在调用方重复拼 JSON 行。

**Agent log stem:**
- Purpose: 生成/批注 agent workspace 与审计日志的文件名片段清洗辅助。
- Examples: `backend/agents/log_naming.py`, `backend/agents/generation/workspace.py`, `backend/agents/comments/workspace.py`
- Pattern: 新 agent workspace 复用统一命名清洗，不在各 agent 内复制文件名规则。

**AgentRunStreamRequest:**
- Purpose: 任务上下文助手的最小受控输入。
- Examples: `backend/models/agent_run.py`
- Pattern: agent run 只读取白名单上下文，不直接访问前端未提交本地状态或外部路径。

## 入口点

**FastAPI 应用：**
- Location: `backend/main.py`
- Triggers: `python backend/main.py` 或 uvicorn。
- Responsibilities: app 创建、router 注册、日志 listener、SSE loop 绑定、健康检查。

**生成任务：**
- Location: `backend/api/generate.py`
- Triggers: `POST /api/generate`
- Responsibilities: 创建后台生成任务并返回 `GenerateResponse`。

**任务上下文助手：**
- Location: `backend/api/agent.py`
- Triggers: `POST /api/agent/runs/stream`
- Responsibilities: 返回 NDJSON 前置流，创建 rewrite 后台任务或返回缺条件事件。

**补充批注：**
- Location: `backend/api/comment_supplement.py`
- Triggers: `POST /api/comment-supplement`
- Responsibilities: 基于会话最新文档创建补充批注任务。

**任务与 SSE：**
- Location: `backend/api/tasks.py`, `backend/api/stream.py`
- Triggers: `GET /api/tasks/{task_id}`、`DELETE /api/tasks/{task_id}`、`POST /api/tasks/{task_id}/heartbeat`、`GET /api/stream/{task_id}`
- Responsibilities: 查询、取消、心跳、事件流和重连。

**Word 诊断：**
- Location: `backend/scripts/diagnose_word.py`
- Triggers: Windows Python 手动运行。
- Responsibilities: 验证 Word/WPS COM 运行环境。

## 架构约束

- **Threading:** FastAPI async 入口 + `ThreadPoolExecutor` 后台任务 + `TaskQueueManager` 进程内公平队列；Word/graph 执行通过文件锁和线程锁串行化。
- **Global state:** `get_task_queue()`、`sse_manager`、`get_document_service()`、`get_conversation_service()` 都是进程内单例或缓存状态，位于 `backend/task/task_queue_manager.py`、`backend/core/sse_manager.py`、`backend/services/`。
- **Circular imports:** 任务取消、进度和 service 中存在函数内延迟导入，例如 `backend/graphs/base_graph.py` 内延迟读取 `get_task_queue()`；新增延迟导入只用于真实循环依赖。
- **Word COM:** 任何 Word 写入必须经过任务队列、graph 锁、取消检查和进度包装；不得在 API route、service、前端或随意脚本中直接操作 COM。
- **Generate-only fields:** `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 只进入初次 generate，不进入 rewrite 请求模型、skill state 或 prompt surface。
- **API shape:** 改 `FormType`、SSE event、task kind、agent run event 必须同步后端模型、前端 API/types、客户端解析和测试。
- **Secrets:** `backend/.env` 存在但不得读取、打印或写入文档；日志与审计不得落真实 key、token、客户原文和私有路径。

## 反模式

### API route 直接承担业务编排

**发生什么：** 在 `backend/api/*.py` 中直接选择 graph、操作 Word、拼 prompt 或访问外部服务细节。
**为什么错：** API 层会绕过 task/SSE/service 边界，导致取消、进度、下载和错误收敛不一致。
**应该这样做：** API 调 `backend/services/`；业务进入 `DocumentService`、`AgentRunService`、`TemplateCandidateRankingService` 或工具层。

### 复制整套招标类型 graph

**发生什么：** 为少量锚点、字号或 Word 节点差异复制完整流程。
**为什么错：** `generation_mode`、批注、进度和后续节点变更会在类型间漂移。
**应该这样做：** 继承 `StandardTenderWorkflowGraph`，仅覆写 class attribute 节点；参考 `backend/graphs/gngk_hw_cz_tender_graph.py` 和 `backend/graphs/gngk_fw_zc_tender_graph.py`。

### 绕过 task skill 创建 rewrite

**发生什么：** 在 agent run 中直接执行重写、写 Word 或维护第二套任务状态。
**为什么错：** agent run 是任务创建前置流，不是后台任务执行器。
**应该这样做：** 调用 `create_rewrite_task_tool`，让 `DocumentService.create_rewrite_task()` 和 `SkillGraph` 接管。

### 将 prompt、日志、SSE 和 Word 副作用混在 Prompt Layer

**发生什么：** 在 `backend/prompts/` 中写日志、发 SSE 或操作文档。
**为什么错：** Prompt Layer 应是纯渲染/解析层，否则测试和安全审计难以隔离。
**应该这样做：** prompt builder 返回 `RenderedPrompt`；副作用留在 node/service/agent runtime。

## 错误处理

**策略：** API 输入用 Pydantic 和 `HTTPException`，长任务错误统一收敛为任务状态和 SSE `error`，Word 契约错误 fail-fast。

**Patterns:**
- API 404/400/502/403 使用结构化 `detail`，例子在 `backend/api/generate.py`、`backend/api/template_candidates.py`、`backend/api/download.py`。
- 任务取消使用 `TaskCancelledException`，从 `backend/graphs/base_graph.py` 向 service 收敛。
- 任务心跳超时由 `TaskQueueManager` 自动取消，原因常量为 `HEARTBEAT_TIMEOUT_REASON`。
- LLM 超时和网络错误在 `backend/util/common_util/llm_stream_utils.py` 中集中处理。
- 下载路径非法直接 403，路径校验在 `backend/api/download.py`。

## 横切关注点

**日志：** `backend/main.py` 使用 JSON stdout；`backend/util/log_util/progress_log.py` 面向用户进度，`execution_log.py` 面向排障，`prompt_log.py` 面向 prompt，`skill_audit_log.py` 面向 rewrite 审计。

**校验：** Pydantic v2 模型、field/model validator、配置 helper 和 Word helper fail-fast。重点文件包括 `backend/models/generate.py`、`backend/models/agent_run.py`、`backend/config/tender_config.py`、`backend/helper/word_helper/protected_fields.py`。

**认证：** `backend/main.py` 注册的业务 router 未检测到稳定认证依赖；`python-jose`、`passlib` 在 `backend/requirements.txt` 中存在但不是当前 API router 的统一鉴权层。

**文件安全：** 上传落盘走 `backend/util/common_util/upload_storage.py`；下载必须限定在 `settings.UPLOAD_DIR`；模板候选下载必须经过 `TEMPLATE_CANDIDATE_ALLOWED_HOSTS`。

**外部调用：** LLM 统一通过 provider settings；招标详情、模板候选和 Qdrant/embedding 访问集中在工具层。

---

*后端架构分析：2026-06-08*
