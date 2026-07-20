# 后端架构事实地图

**分析日期：** 2026-07-21
**HEAD:** `e748f16d1a2b253c766008f1a060e3ebba9b2f85`

**范围：** 仅覆盖 `backend/` 子项目。`backend/.env` 文件存在，但不得读取、摘录或把其中任何值写入文档、日志、测试夹具或回复。

## Pattern Overview

后端是 TenderWord 的 FastAPI + LangGraph + Word COM 执行端，负责招标详情代理、模板候选代理、上传下载、初次生成、rewrite、补充批注、任务队列、SSE、LLM/agent 调用、bad case retrieval 和 Word 文件写回。

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
│ `backend/skills/` (rewrite)   │   │                         │
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

**Overall pattern:** FastAPI 薄入口 + Service 编排 + 进程内任务队列 + LangGraph 工作流 + Word COM 临界资源串行化。

**Key Characteristics:**
- API route 只做 HTTP 边界处理；业务编排进入 `backend/services/`，graph/node/helper 承担实际生成与写回。
- 初次生成使用 `StandardTenderWorkflowGraph` 共享主干；类型差异通过 graph class attribute 绑定节点。
- rewrite 使用 `RewriteSkillGraph` 显式 graph；不要恢复 `SkillGraph.for_skill + TaskSkillWorkflow` 元数据驱动框架。
- Word COM 写入必须经过 `DocumentService`、`TaskQueueManager`、graph 锁、节点取消检查、进度包装和 `backend/util/word_util/`。
- Agent run 只负责任务创建前置流；后台 task、SSE、取消、下载仍沿用 task/SSE/download 链路。
- 当前后台任务类型只有 `generate`、`rewrite`、`comment_supplement`（见 `TaskKind`）。
- 完整 Word 闭环必须运行在 Windows Python、`pywin32`、本机 Word/WPS COM 环境中；无 COM 环境只能验证纯逻辑、API 契约和非写回分支。
- 子项目 `.planning/codebase/` 是事实层；根级 `AGENTS.md`、`ARCHITECTURE.md`、`INTERFACES.md` 只做导航和跨项目边界。

## Layers

**API 层:**
- 职责： 暴露 HTTP、SSE、NDJSON 入口，转换为 service 调用。
- Location: `backend/api/`
- 包含： `generate.py`, `agent.py`, `comment_supplement.py`, `tasks.py`, `stream.py`, `upload.py`, `download.py`, `tender.py`, `template_candidates.py`, `conversations.py`
- Depends on: `backend/models/`, `backend/services/`, `backend/util/common_util/`
- Used by: 前端 API client、浏览器 SSE、agent run UI 和本地调试。

**模型与配置层:**
- 职责： 保存 API shape、runtime state shape、配置和招标类型规则。
- Location: `backend/models/`, `backend/states/`, `backend/config/`
- 包含： Pydantic models、TypedDict graph states、Settings、`TenderAnchorConfig`、`ProtectedFieldProfile`。
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
- 包含： `TaskQueueManager`, `Task`, `TaskProgress`, `TaskKind`, `SSEManager`, event cache。
- Depends on: settings、models、log util。
- Used by: `DocumentService`, `TaskService`, `SSELogHandler`, `stream.py`。

**Graph/Node 层:**
- 职责： 用 LangGraph 编排 generate、rewrite、comment supplement，并用 state 在节点间传递数据。
- Location: `backend/graphs/`, `backend/nodes/`, `backend/states/`, `backend/skills/`
- 包含： 标准 graph、类型 graph、`RewriteSkillGraph`、`CommentSupplementGraph`、共享 Word 节点、类型专属节点、skill 节点与 rewrite runtime helper。
- Depends on: Word helper/util、agents、prompts、retrieval、task queue。
- Used by: `DocumentService`。

**Word 操作层:**
- 职责： 执行 Word 文件复制、打开、抽取、删除、替换、样式回填、批注写回、结构化表占位符恢复、保存和关闭。
- Location: `backend/nodes/`, `backend/helper/word_helper/`, `backend/util/word_util/`
- 包含： 业务 helper 和 COM 技术 helper。
- Depends on: pywin32/COM、Word/WPS、本地文件、tender config。
- Used by: graph nodes 和 `backend/scripts/diagnose_word.py`。

**Agent/Prompt/LLM 层:**
- 职责： 渲染 prompt、调用 OpenAI-compatible LLM、执行 DeepAgents/LangChain agent、产出结构化过程事件。
- Location: `backend/agents/`, `backend/prompts/`, `backend/skills/`, `backend/util/common_util/llm_stream_utils.py`
- 包含： content agent、comment agent、task context assistant、rewrite skill runtime helper、LLM stream util。
- Depends on: settings、LangChain、DeepAgents、OpenAI-compatible SDK。
- Used by: graph nodes、agent run service、template candidate ranking。

**Retrieval 层:**
- 职责： 为批注生成提供 bad case context，向量能力不可用时降级。
- Location: `backend/retrieval/`
- 包含： bad case loader、BM25、Qdrant store、embedding client、hybrid merge、runtime cache。
- Depends on: `backend/retrieval/bad_cases/`, Qdrant, embedding API, env。
- Used by: `generate_comments`、`comment_agent`、`comment_supplement` 相关路径。

## 组件职责

| Component | Responsibility | File |
|-----------|----------------|------|
| FastAPI app | 创建应用、注册 `/api` routers、配置 CORS、绑定 startup/shutdown、提供 health endpoints、全局异常处理 | `backend/main.py` |
| API routers | 保持薄入口，解析 HTTP/SSE/NDJSON 请求并委派 service 或 util | `backend/api/generate.py`, `backend/api/agent.py`, `backend/api/stream.py`, `backend/api/tasks.py` |
| Pydantic models | 定义 generate、task、SSE、agent run、tender、upload、template candidate 的 API/runtime shape | `backend/models/generate.py`, `backend/models/task.py`, `backend/models/sse.py`, `backend/models/agent_run.py` |
| Settings | 从环境变量和 `backend/.env` 加载 LLM、上传、外部接口、锁、日志、SSE、任务配置 | `backend/config/settings.py` |
| Tender config | 集中管理招标类型锚点、字号、content mode、受保护字段 profile 和 family 归并 | `backend/config/tender_config.py` |
| DocumentService | 选择 graph、构建初始 state、创建任务、提交后台线程、执行 graph、收敛 task result 与 SSE 终态 | `backend/services/document_service.py` |
| TaskQueueManager | 管理进程内任务队列、状态、心跳、取消、后台清理、公平锁、进度和 worker future | `backend/task/task_queue_manager.py` |
| SSEManager | 管理 SSE client、事件缓存、断线重连、heartbeat 和后台线程到主事件循环的 threadsafe 调度 | `backend/core/sse_manager.py` |
| BaseGraph | 提供跨进程文件锁、节点进度包装、取消检查、同步/异步执行包装 | `backend/graphs/base_graph.py` |
| StandardTenderWorkflowGraph | 初次生成的共享 LangGraph 主干，维护 Word 子图、`generation_mode`、批注分支和写回分支 | `backend/graphs/base_graph.py` |
| Tender graph classes | 按招标类型绑定差异节点，复用标准生成主干 | `backend/graphs/xjcg_tender_graph.py`, `backend/graphs/gngk_*_tender_graph.py`, `backend/graphs/gjgk_tender_graph.py` |
| RewriteSkillGraph | 显式声明 rewrite 节点顺序、普通边和条件分支 | `backend/graphs/skill_graph.py` |
| CommentSupplementGraph | 独立补充批注 graph，复用任务队列、SSE、锁、`comment_agent` 写回 | `backend/graphs/comment_supplement_graph.py` |
| Word nodes | 承载模板准备、抽参、删除、替换、正文生成、批注生成、rewrite 上下文和写回节点 | `backend/nodes/` |
| Word helper | 段落边界、正文操作、删除、cleanup、样式回填、受保护字段、range、结构化表占位符解析 | `backend/helper/word_helper/` |
| Word util | COM lock/retry、Word app 生命周期、锚点工具、文档检查、常量和诊断 | `backend/util/word_util/` |
| Generation agents | `generation_mode=agent` 的 DeepAgents 主/子智能体、workspace、协议校验、结构化表占位符和 `agent_step` | `backend/agents/generation/` |
| Comment agents | 批注候选首版生成/校验、工具门禁、确定性 Word 写回和审计 | `backend/agents/comments/` |
| Task context assistant | 右侧 agent run 前置流，只用受控上下文和白名单工具创建 rewrite 任务 | `backend/services/agent_run_service.py`, `backend/agents/task_context_assistant/` |
| Prompt layer | 只做 prompt 渲染和机器契约解析，不承载副作用、SSE、COM 或 session state | `backend/prompts/` |
| Retrieval layer | 为批注生成注入 bad case prompt context，hybrid 失败时降级 | `backend/retrieval/` |

## Data Flow

### 初次生成主链路（generate）

1. `POST /api/generate` 进入 `create_generate_task()`，请求模型是 `GenerateRequest`（`backend/api/generate.py`, `backend/models/generate.py`）。
2. `DocumentService.create_task()` 使用 `request.form_type.value` 从 `GRAPH_REGISTRY` 选择 graph（`backend/services/document_service.py`）。
3. `GRAPH_REGISTRY` 覆盖六个具体 form type：
   - `xjcg_tender` → `XjcgTenderGraph`
   - `gngk_hw_zc_tender` → `GngkHwZcTenderGraph`
   - `gngk_hw_cz_tender` → `GngkHwCzTenderGraph`
   - `gngk_fw_zc_tender` → `GngkFwZcTenderGraph`
   - `gngk_fw_cz_tender` → `GngkFwCzTenderGraph`
   - `gjgk_tender` → `GjgkTenderGraph`
4. **gngk 分派：** 前端 UI 的 `gngk` 不是后端 form type；提交时必须由前端共享 helper 按 `tender_lx + fund_lx/fund_source_lx + ifzgcg` 分派到上述四个 `gngk_*` form type。后端 registry 只认具体 form type。
5. `_build_initial_state()` 将 tender data、文件路径、锚点，以及 **generate-only** 字段写入 state：
   - `generation_style`（`template` / `param`）
   - `generation_mode`（`workflow` / `agent`）
   - `comment_generation_mode`（`on` / `off`）
   - `style_writeback_mode`（`full` / `bold_only`）
   - 另有 `tender_lx`、`fund_source_lx` 等业务字段
6. `_submit_graph_task()` 调用 `TaskQueueManager.add_task(task_kind="generate")` 并把 `_run_graph()` 提交到 `ThreadPoolExecutor`。
7. `_run_graph()` 实例化 graph、估算节点总数、编译 graph、创建独立 event loop 并调用 graph `ainvoke`。
8. `invoke_with_timing_async()` 先 `wait_for_turn()`，再获取 `CrossProcessFileLock`，登记运行中的 async task，并执行 compiled graph（`backend/graphs/base_graph.py`）。
9. `StandardTenderWorkflowGraph.build_graph()` 拓扑：
   ```text
   START
     → prepare_template
     → extract_tender_params
        ├→ word_operations_subgraph
        │    (delete_tender_param → get_replacements → replace_content 等类型差异步骤)
        └→ generation_mode_gate
             ├ workflow → generate_polished_text
             └ agent    → content_agent
                  ↓
             annotate_corrections   # 仅 generate 接入
                  ├ workflow+comment on → generate_comments → comments_branch_done
                  └ otherwise            → comments_branch_done
                       ↓
             [word_ops 与 comments_branch_done 汇合]
                  → update_word
                       ├ agent + comment on → comment_agent → (post_update / END)
                       └ otherwise          → (post_update / END)
   ```
10. **`annotate_corrections` 仅首次 generate 接入**（`RewriteSkillGraph` / `CommentSupplementGraph` 不挂该节点）。职责：
    - 条款标识规范化（`*`/`※→★`、`△`/`Δ→▲` 等）
    - 产出 `correction_comments`（差异更正批注候选）
    - **不得**把编号/项目符号/展示壳变化当作事实更正
    - `comment_agent` **不得**生成「原技术参数为…现改为…」类差异批注；该类只由 `annotate_corrections` 产出
11. **Word 写回批注顺序**（`apply_correction_and_ai_comments` in `backend/nodes/common_word_nodes/comment_writeback.py`）：
    - 先写 `correction_comments`（更正批注）
    - 再写 `polished_comments`（普通 AI 批注）
    - `comment_generation_mode=off` 或 `suppress_ai_comment_writeback=True` **只跳过普通 AI 批注**，不跳过更正批注
    - agent 模式下 `comments_branch_done` 会置 `suppress_ai_comment_writeback=True`，普通批注改由 `update_word` 后的 `comment_agent` 写
12. **content agent 与 `[[TABLE:<id>]]`：**
    - 提取阶段把结构化表写入 `tender_param_table_models` sidecar（`backend/util/word_util/table_models.py`）
    - content agent 在正文中保留 `[[TABLE:id]]` 作为内部写回入口（`backend/agents/generation/table_placeholder_utils.py`、`content_sanitizer.py`）
    - 写回层（`backend/helper/word_helper/text_parsing.py`、`content_ops.py`）按 sidecar 恢复真实表格；占位符绝不可见写入最终 Word
13. `DocumentService` 收敛 output file、file size、model、style/comment writeback summary，并通过 task queue 与 `SSEManager` 推送 `done` 或 `error`。

### Rewrite 链路（显式 RewriteSkillGraph）

1. 入口有两条，最终都汇入 `DocumentService.create_rewrite_task()`：
   - `POST /api/agent/runs/stream` → `AgentRunService` 前置流 → `create_rewrite_task_tool()`
   - 其他前端受控入口（仍走同一 service，不另开任务链路）
2. `AgentRunService.stream()` 返回 NDJSON：`run_started`、`thinking_stage`、preflight guard 或 DeepAgents runner。
3. 条件缺失时返回 `needs_input`（**不创建任务**）；条件满足时创建 rewrite 任务。
4. **上传文件 rewrite** 必须具备 `file_path`、`form_type`、完整 `insertion_config`、`tender_lx`、`fund_source_lx`，并设置 `rewrite_source="uploaded_file"`；**会话 rewrite** 必须已有 latest rewrite history。
5. **generate-only 字段不得进入 rewrite** request 模型、`TaskSkillGraphState` 或 prompt surface。
6. `RewriteSkillGraph.build_graph()` 显式拼装 6 个节点（`backend/graphs/skill_graph.py`）：
   ```text
   START → resolve_rewrite_target
            ├ uploaded_file → extract_rewrite_context → rewrite_text
            └ otherwise     → rewrite_text
                 ├ need comments → get_rewrite_comments → delete_section ─┐
                 └ skip comments → delete_section ───────────────────────┤
                 rewrite_text ──────────────────────────────────────────┤
                                                                         ↓
                                                                   update_word → END
   ```
7. 条件分支由 `backend/skills/rewrite/scripts/runtime.py` 决定：
   - `select_resolve_branch`：`rewrite_source=="uploaded_file"` 时走 `extract_rewrite_context`
   - `select_comment_branch`：`uploaded_file` 或无有效 `source_document_path` 时跳过 `get_rewrite_comments`
8. `delete_section` / `update_word` 经 `dispatch_tender_aware_delete_section` / `dispatch_tender_aware_update_word` 按类型路由（`backend/nodes/skills_nodes/tender_aware_word_dispatch.py`）。
9. rewrite **不接入** `annotate_corrections`；后台任务复用 task/SSE/download；agent run 只负责 `task_accepted` 和终态摘要。

### 补充批注链路（comment_supplement）

1. `POST /api/comment-supplement` 进入 `DocumentService.create_comment_supplement_task()`（`backend/api/comment_supplement.py`）。
2. Service 校验 `conversation_id`、`source_file`、latest `rewrite_state`、`polished_text` 和当前文件是否仍是会话 latest 文档。
3. `CommentSupplementGraph` 执行：
   ```text
   prepare_comment_supplement → comment_agent → finalize_comment_supplement
   ```
4. 成功后 `ConversationService` 更新 latest rewrite state。
5. 该链路只做普通 AI 批注补充，不跑 generate 主干，也不产出技术参数差异更正批注。

### Agent run 前置流

1. `POST /api/agent/runs/stream` → `AgentRunService.stream()` → NDJSON。
2. 只用受控上下文和白名单工具；条件满足时通过 `create_rewrite_task_tool` 创建 rewrite 任务。
3. 审计日志和摘要工具只暴露 scrub 后白名单信息（`backend/agents/task_context_assistant/logging.py`），不记录或返回完整客户原文、真实密钥、私有路径、traceback 或下载路径。
4. Agent run **不替代** task queue / SSE / download；任务创建后进度与终态仍走 `/api/stream/{task_id}`。

### SSE 链路

1. 前端连接 `GET /api/stream/{task_id}`，`stream_task_events()` 校验任务并解析 `Last-Event-ID`（`backend/api/stream.py`）。
2. `SSEManager.event_stream()` 建立 client、重放 missed events、持续 yield SSE 字符串并在 `done`/`error` 后结束（`backend/core/sse_manager.py`）。
3. 后台线程通过 `send_*_threadsafe()` 把事件调度回 FastAPI 主 loop（startup 阶段 `sse_manager.bind_loop()` 绑定主 loop）。
4. 事件类型：`log`、`llm`、`progress`、`agent_step`、`done`、`error`、`heartbeat`。

### 模板候选链路

1. `GET /api/template-candidates` 调用 `fetch_template_candidates()` 代理外部候选列表。
2. `TemplateCandidateRankingService.rank_candidates()` 对同优先级候选按项目名称调用 LLM 重排；失败时保持优先级排序。
3. `GET /api/template-candidates/download` 和 `POST /api/template-candidates/select` 通过 allowlist 校验外部模板链接，再下载或保存到上传目录。

## Key Abstractions

**`FormType` 与 runtime `tender_type`:**
- 职责： 连接 API 表单类型和 graph 运行态招标类型。
- Examples: `backend/models/generate.py`, `backend/services/document_service.py`
- Pattern: API 使用带 `_tender` 的 `FormType`（6 个值）；进入 graph state 时用 `form_type.value.replace("_tender", "")` 得到 runtime `tender_type`。新增类型要同步 model、registry、state、graph、nodes、config、tests 和前端映射。
- `gngk` 在前端是 UI 类型；提交到后端时必须分派到具体 form type。`get_tender_type_family()` 把 gngk 子类型归并为 `gngk` 共享行为族（`backend/config/tender_config.py`）。

**Generate-only 字段:**
- 字段： `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode`。
- 职责： 仅影响初次 `generate` 的 prompt 路由、graph 分支、批注开关和样式回填。
- Pattern: 只出现在 `GenerateRequest` 与 `_build_initial_state()`；**不得**进入 rewrite request 模型、skill state 或 prompt surface。

**`TenderAnchorConfig` / `ProtectedFieldProfile`:**
- 职责： 集中管理锚点、字号、content start/update mode 和受保护字段顺序。
- Examples: `backend/config/tender_config.py`
- Pattern: 锚点/字号/少量保护字段差异优先进入配置；流程差异明显时才新增类型节点或 graph。`gngk_hw_cz` 使用 `content_update_mode=direct_replace` 与同页插入；`gngk_fw_zc` 覆写三字段受保护 profile。

**`StandardTenderWorkflowGraph`:**
- 职责： 初次生成主流程真源。
- Examples: `backend/graphs/base_graph.py`, `backend/graphs/gngk_hw_zc_tender_graph.py`
- Pattern: 类型 graph 覆盖 `STATE_CLS` 和必要 `NODE_*`，不要复制 `build_graph()`。通过 `get_word_operation_steps()` / `get_post_update_steps()` 注入差异 Word 节点（如 `GjgkTenderGraph` 把 `replace_content` 放到 post-update）。

**`RewriteSkillGraph`:**
- 职责： rewrite 任务显式 graph。
- Examples: `backend/graphs/skill_graph.py`, `backend/skills/rewrite/scripts/runtime.py`
- Pattern: 节点、边和条件分支直接写在 `skill_graph.py`，分支判定集中在 `runtime.py`；新增 skill 先评估是否新增显式 graph 类，不要恢复元数据驱动框架。

**`annotate_corrections` / 更正批注契约:**
- 职责： 条款标识规范化 + 技术参数事实差异更正候选。
- Examples: `backend/nodes/common_word_nodes/annotate_corrections.py`, `backend/nodes/common_word_nodes/comment_writeback.py`
- Pattern: 仅 generate 主干在正文确定后统一调用；写回时更正批注优先于普通 AI 批注；`comment_agent` 禁止产出差异更正文案。

**`TaskQueueManager`:**
- 职责： 长任务排队、公平锁、进度、取消和心跳。
- Examples: `backend/task/task_queue_manager.py`
- Pattern: Word 任务必须先进入队列；取消通过 cancel event、worker future 和 async task cancel 传播。`TaskKind` 仅 `generate` / `rewrite` / `comment_supplement`。

**`SSEEvent` / `AgentStepEventData`:**
- 职责： 后台任务事件和 agent 过程卡契约。
- Examples: `backend/models/sse.py`, `backend/agents/generation/agent_step_events.py`
- Pattern: 新字段或事件类型必须同步发送方、前端 parser、类型和测试。过程事件不替代 `done` / `error` 终态。

**Word COM lifecycle helpers:**
- 职责： 创建、打开、保存、关闭 Word COM，并统一处理 pywin32 缺失、COM 初始化、RPC 重试和资源释放。
- Examples: `backend/util/word_util/word_application_util.py`, `backend/util/word_util/word_com_manager.py`
- Pattern: 节点只通过 helper 操作 COM；不要在 API/service/agent 里直接 `Dispatch` 或打开 Word。关键原语：`com_lock()`、`CrossProcessFileLock`。

**结构化表占位符与 sidecar 写回模型:**
- 职责： 标记技术参数结构化表的内部写回入口 `[[TABLE:<id>]]`。
- Examples: `backend/agents/generation/table_placeholder_utils.py`, `backend/helper/word_helper/text_parsing.py`, `backend/util/word_util/table_models.py`
- Pattern: 提取阶段写入 `tender_param_table_models`；content agent 保留占位符；写回层按 sidecar 恢复真实表格。不得把占位符当成用户可见正文，也不得写成 Markdown/手绘表格。

**Content agent / Comment agent:**
- 职责： 自主生成正文和批注锚点校验/写回。
- Examples: `backend/agents/generation/content_agents.py`, `backend/agents/comments/comment_agent.py`
- Pattern: agent 的长正文、草稿、审核和修订通过 workspace 文件交接；Word 写回仍由 graph 节点线程执行。

**Bad case retrieval:**
- 职责： 给批注生成注入坏案例上下文。
- Examples: `backend/retrieval/comment_bad_case_runtime.py`, `backend/retrieval/hybrid.py`
- Pattern: hybrid 检索失败降级为 `bm25_only`；retrieval 状态不进入前端 SSE、下载卡或 agent_step 展示；rewrite 与 `comment_generation_mode=off` 不触发该检索。

## Entry Points

**ASGI app:**
- Location: `backend/main.py`
- Triggers: 在 `backend/` 下 `python -m uvicorn main:app --reload --port 8000`，或 `uvicorn backend.main:app`。
- Responsibilities: 初始化 app、router、CORS、日志队列、SSE 主 loop、健康检查（`/health`、`/health/ready`、`/health/live`）。健康检查只探测进程，不替代 Word COM 诊断。

**Generate API:**
- Location: `backend/api/generate.py`
- Triggers: `POST /api/generate`，`GET /api/generate/{task_id}`
- Responsibilities: 创建初次生成任务，返回 `GenerateResponse`。

**Task API:**
- Location: `backend/api/tasks.py`
- Triggers: `GET /api/tasks`, `GET /api/tasks/{task_id}`, `DELETE /api/tasks/{task_id}`, `POST /api/tasks/{task_id}/heartbeat`
- Responsibilities: 查询任务、取消任务、续任务心跳。

**SSE API:**
- Location: `backend/api/stream.py`
- Triggers: `GET /api/stream/{task_id}`, `GET /api/stream/{task_id}/status`
- Responsibilities: 推送 `log`、`llm`、`progress`、`agent_step`、`done`、`error`、`heartbeat`。

**Agent run API:**
- Location: `backend/api/agent.py`
- Triggers: `POST /api/agent/runs/stream`
- Responsibilities: 返回 NDJSON agent run 过程，并在上下文满足时创建 rewrite 任务。

**Comment supplement API:**
- Location: `backend/api/comment_supplement.py`
- Triggers: `POST /api/comment-supplement`
- Responsibilities: 基于会话 latest Word 文件创建补充批注任务。

**Tender/template/upload/download/conversations APIs:**
- Location: `backend/api/tender.py`, `backend/api/template_candidates.py`, `backend/api/upload.py`, `backend/api/download.py`, `backend/api/conversations.py`
- Triggers: `/api/tender/{tender_no}`, `/api/template-candidates*`, `/api/upload*`, `/api/download/{file_path:path}`, `/api/conversations*`
- Responsibilities: 外部数据代理、模板候选代理、文件落盘和下载、会话状态。

## Error Handling

**Strategy:** API 层用 `HTTPException` 返回结构化错误；全局未捕获异常由 `global_exception_handler` 兜底返回 500；后台任务捕获异常后写 task 失败状态和 SSE `error`；取消按非 fatal 终态处理；retrieval、批注生成等可降级失败写 warning 后继续。

**Patterns:**
- API 错误 payload 使用 `success=false`、`error`、`message` 等字段。
- `_run_graph()` 捕获异常后推 `ErrorEventData`、调用 `sse_manager.send_error_threadsafe()`，再 `complete_task()`。
- `TaskCancelledException` 和 `asyncio.CancelledError` 作为取消处理，不应表现为致命失败。
- Word COM 创建失败抛诊断性 `RuntimeError`，并在 finally 路径关闭 doc、退出 Word、`CoUninitialize()`。
- bad case retrieval 失败降级为 `bm25_only` 或 unavailable payload，不阻塞批注生成。
- 未知 form type 在 `create_task` 返回 400 级错误信息（「未知的表单类型」）。

## Concurrency

**Threading model:**
- FastAPI 主 loop 处理 HTTP/SSE。
- `DocumentService` 用进程内 `ThreadPoolExecutor(max_workers=4)` 提交 `_run_graph`。
- 每个 graph 任务在后台线程中创建独立 asyncio event loop 执行 `ainvoke`。

**Task queue fairness:**
- `TaskQueueManager` 单例维护 `_queue`、`_current_task_id`、`_execution_condition`。
- `wait_for_turn(task_id)` 确保任务按提交顺序获得执行权（公平锁）。
- 状态：`queued` / `running` / `completed` / `failed` / `cancelled`。

**Graph lock (Word COM 串行化):**
- `CrossProcessFileLock`（`backend/graphs/base_graph.py`）：线程锁 + Windows `msvcrt.locking` 文件锁，跨进程互斥 Word COM。
- 节点级 `com_lock()`（`backend/util/word_util/word_com_manager.py`）：细粒度 COM 调用互斥与 RPC 重试。
- 同一时间只允许一个 graph 持有跨进程锁执行 Word 写回相关流程。

**Cancellation:**
- `cancel_task()` 设置 cancel event；运行中任务通过 `wrap_node` 取消检查、worker future cancel、async task cancel 尽快中断。
- 心跳超时（`TASK_HEARTBEAT_TIMEOUT`）由后台 cleanup 线程清理失联任务。

**SSE concurrency:**
- 后台线程用 `send_*_threadsafe` 把事件调度到主 loop。
- SSE client 支持 `Last-Event-ID` 断线重放；进程内 event cache，重启不恢复。

**Global state:**
- 单例：task queue、`sse_manager`、document/conversation/agent_run service、`settings`、graph registry。
- task、SSE、conversation history 是进程内状态，服务重启不恢复；文件产物和日志是本地文件状态。

## 架构约束

- **Word COM 红线:** 所有 Word 写入必须经过 task queue、graph 锁、取消检查、进度包装、`CrossProcessFileLock` 和 `com_lock()`。不得在 API route、service、前端或随意脚本中直接操作 COM。
- **Rewrite 边界:** 上传文件与会话修改统一走 `rewrite` + `RewriteSkillGraph`；上传来源用 `rewrite_source="uploaded_file"` 标记；不要恢复 `/api/edit`、edit skill 或第二套任务链路。
- **Generate-only 字段边界:** `generation_style` / `generation_mode` / `comment_generation_mode` / `style_writeback_mode` 只服务初次 generate。
- **gngk 分派边界:** 前端 `gngk` UI 类型必须在提交前分派到具体 `FormType`；后端 registry 只认 6 个具体 form type。
- **更正批注边界:** `annotate_corrections` 仅 generate；写回先更正后普通；`comment_generation_mode=off` / `suppress_ai_comment_writeback` 只跳过普通 AI 批注。
- **表格占位符边界:** `[[TABLE:id]]` 是内部写回入口；最终正文是否恢复真实表格由写回层决定。
- **Environment:** `backend/config/settings.py` 和 `backend/retrieval/config.py` 会读取 `backend/.env`；文档、日志和回复不得输出真实 env 值。
- **Circular imports:** 跨层引用优先延迟导入（如 `DocumentService` 的 graph registry 初始化）。
- **Cross-layer sync:** API shape、SSE、任务类型、招标类型、prompt/LLM、Word helper、模板候选和 retrieval 改动必须同步后端模型、前端类型/API client、测试和长期知识包。

## 反模式

### API 路由直接执行 Word COM 或 LangGraph

**What happens:** 在 `backend/api/*.py` 里直接打开 Word、调用 COM、运行 graph 或拼接长业务流程。
**Why it's wrong:** 会绕过 `TaskQueueManager`、公平锁、文件锁、取消检查、SSE 终态和日志上下文。
**Do this instead:** API route 委派 service；Word 写入只能由 graph 节点进入 `backend/util/word_util/`。

### 复制标准生成 graph 主干

**What happens:** 为新招标类型复制 `StandardTenderWorkflowGraph.build_graph()`，只改少量节点。
**Why it's wrong:** `generation_mode`、`comment_generation_mode`、`comment_agent`、进度节点和后写回分支容易漂移。
**Do this instead:** 继承 `StandardTenderWorkflowGraph` 或现有 family graph，覆盖 `STATE_CLS` 和必要 `NODE_*` / `get_word_operation_steps()`。

### 把 generate-only 字段带入 rewrite

**What happens:** 将 `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 写入 rewrite request、skill state 或 prompt。
**Why it's wrong:** rewrite 的语义来源是会话 latest state 或上传文件上下文；generate-only 字段会污染 rewrite prompt 和分支条件。
**Do this instead:** 这些字段只在 `backend/models/generate.py` 和 `DocumentService._build_initial_state()` 使用；rewrite 使用 `TaskSkillGraphState` 和 `rewrite_user_prompt`。

### 恢复旧 edit 入口或第二套修改链路

**What happens:** 新建 `/api/edit`、`edit` task kind、`backend/skills/edit/` 或绕开 rewrite 的上传文件修改流程。
**Why it's wrong:** 上传文件修改已经收敛到 `rewrite_source="uploaded_file"`，后台复用 `RewriteSkillGraph`、任务队列、SSE、下载和类型感知写回。
**Do this instead:** 上传文件和会话修改都进入 `DocumentService.create_rewrite_task()`。

### 恢复元数据驱动 skill 框架

**What happens:** 重新引入 `SkillGraph.for_skill + TaskSkillWorkflow`。
**Why it's wrong:** 当前 rewrite 已显式落在 `RewriteSkillGraph`，可读性和可测性更好。
**Do this instead:** 新 skill 优先新增显式 graph 类与 runtime helper。

### comment_agent 产出差异更正批注

**What happens:** 在 `comment_agent` 或普通批注 prompt 中生成「原技术参数为…现改为…」。
**Why it's wrong:** 技术参数差异更正只由 generate 链路的 `annotate_corrections` 产出，且写回顺序要求更正批注优先。
**Do this instead:** 普通批注只做建议类 AI 批注；更正候选只来自 `annotate_corrections`。

### Agent run 暴露敏感运行态

**What happens:** 在 agent run 审计、摘要工具、SSE 或前端卡片中返回完整客户原文、真实 token、私有路径、traceback、完整任务结果或下载路径。
**Why it's wrong:** Agent run 是前置流和 UI 摘要，不是排障日志或文件浏览接口。
**Do this instead:** 使用 scrub 和白名单摘要工具（`backend/agents/task_context_assistant/logging.py`、`tools.py`）。

## 横切关注点

**Logging:** `progress_log` 只写用户可理解进度；`execution_log` 记排障与成功审计；`sse_log_handler` 将任务上下文日志推到 SSE；agent run 使用 scrub 审计；`backend/main.py` 启动时绑定监听器并清理过期 `backend/logs`。
**Validation:** Pydantic 模型校验 API shape；service 校验上下文和文件一致性；download 限制路径；template candidates 校验 allowlist。
**Authentication:** 未检测到统一应用鉴权中间件；新增外部暴露接口时要显式设计认证、授权、日志 scrub 和路径/URL 白名单。
**Security:** 不读取或输出 `backend/.env`；外部模板下载使用 allowlist；agent run 和任务摘要不得暴露完整客户原文、私有路径、token、traceback 或下载路径。
**Verification:** 后端代码改动至少运行 `python -m pytest tests -v`；Word COM 闭环必须回到 Windows + Word/WPS COM 环境；仅文档变更至少运行 `git diff --check`。

---

*后端架构分析：2026-07-21 · HEAD e748f16d1a2b253c766008f1a060e3ebba9b2f85*
