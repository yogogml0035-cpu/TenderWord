# 后端结构事实地图

**分析日期：** 2026-06-08

**范围：** 仅覆盖 `backend/` 子项目。输出限定到 `backend/.planning/codebase/`；不读取 `backend/.env` 内容。

## Directory Layout

```text
backend/
├── agents/                    # DeepAgents/LangChain 智能体运行时
│   ├── comments/               # 批注生成、校验、写回工具和审计
│   ├── generation/             # content_agent 主/子智能体和 workspace
│   └── task_context_assistant/ # agent run 前置流工具、审计和工厂
├── api/                        # FastAPI routers
├── config/                     # settings 与招标类型配置
├── core/                       # SSE manager 等核心运行设施
├── graphs/                     # LangGraph graph 类和 task skill workflow
├── helper/word_helper/         # Word 业务 helper
├── models/                     # Pydantic API/runtime 模型
├── nodes/                      # LangGraph 节点
│   ├── common_word_nodes/      # 共享 Word 节点
│   ├── gjgk_word_nodes/        # 国际公开特化节点
│   ├── gngk_word_nodes/        # 国内公开特化节点
│   ├── skills_nodes/           # rewrite skill 节点和类型感知 dispatch
│   └── xjcg_word_nodes/        # 询价采购特化节点
├── prompts/                    # prompt builders 和机器契约解析
├── retrieval/                  # 批注坏案例 BM25/Qdrant/embedding 检索诊断/实验入口
├── scripts/                    # 后端诊断与检索脚本
├── services/                   # API 与 graph 之间的业务编排
├── skills/                     # task skill 声明与 loader
│   └── rewrite/                # rewrite skill 真源
├── states/                     # LangGraph state TypedDict
├── task/                       # 任务队列和进度状态
├── tests/                      # pytest 测试
├── util/                       # 通用工具、日志、Word COM 技术工具
├── .planning/codebase/         # 后端事实文档
├── main.py                     # FastAPI 应用入口
└── requirements.txt            # 后端依赖清单
```

## Directory Purposes

**`backend/api/`:**
- Purpose: 暴露 FastAPI HTTP/SSE/NDJSON 入口。
- Contains: `generate.py`、`agent.py`、`comment_supplement.py`、`tasks.py`、`stream.py`、`upload.py`、`download.py`、`tender.py`、`template_candidates.py`、`conversations.py`
- Key files: `backend/api/generate.py`, `backend/api/agent.py`, `backend/api/stream.py`

**`backend/models/`:**
- Purpose: 保存 API shape、任务状态、SSE event、agent run、模板候选和招标数据模型。
- Contains: Pydantic `BaseModel`、`Enum`、validator。
- Key files: `backend/models/generate.py`, `backend/models/agent_run.py`, `backend/models/sse.py`, `backend/models/task.py`

**`backend/services/`:**
- Purpose: 业务编排层，连接 API、task queue、graph、SSE、会话和外部调用。
- Contains: 文档任务、agent run、会话、任务查询、NDJSON 流辅助、模板候选 AI 重排。
- Key files: `backend/services/document_service.py`, `backend/services/agent_run_service.py`, `backend/services/chat_stream_service.py`, `backend/services/task_service.py`, `backend/services/template_candidate_ranking_service.py`

**`backend/task/`:**
- Purpose: 管理长任务队列、进度、取消、心跳和公平执行。
- Contains: `TaskQueueManager`、`Task`、`TaskProgress`、节点显示名。
- Key files: `backend/task/task_queue_manager.py`

**`backend/core/`:**
- Purpose: 核心运行基础设施。
- Contains: SSE 连接、事件缓存、重放、跨线程调度。
- Key files: `backend/core/sse_manager.py`

**`backend/graphs/`:**
- Purpose: LangGraph 工作流定义。
- Contains: `BaseGraph`、标准 tender graph、招标类型 graph、rewrite skill graph、补充批注 graph。
- Key files: `backend/graphs/base_graph.py`, `backend/graphs/skill_graph.py`, `backend/graphs/task_skill_workflows.py`, `backend/graphs/comment_supplement_graph.py`

**`backend/states/`:**
- Purpose: Graph state 类型定义。
- Contains: 基础 state、`xjcg`、`gngk`、`gjgk`、task skill state。
- Key files: `backend/states/base_state.py`, `backend/states/skill_state.py`, `backend/states/gngk_tender_state.py`

**`backend/nodes/common_word_nodes/`:**
- Purpose: 共享 Word graph 节点。
- Contains: 模板准备、抽参、删除、替换、生成正文、生成批注、content agent、comment agent、补充批注、写回。
- Key files: `backend/nodes/common_word_nodes/update_word.py`, `backend/nodes/common_word_nodes/content_agent_generate.py`, `backend/nodes/common_word_nodes/comment_agent.py`

**`backend/nodes/gngk_word_nodes/`:**
- Purpose: 国内公开类型差异节点。
- Contains: `gngk_hw_zc`、`gngk_hw_cz`、`gngk_fw_zc` 等 get_replacements/delete/update。
- Key files: `backend/nodes/gngk_word_nodes/gngk_hw_cz_update_word.py`, `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`

**`backend/nodes/gjgk_word_nodes/`:**
- Purpose: 国际公开类型差异节点。
- Contains: 国际公开替换字段、删除、写回和替换内容。
- Key files: `backend/nodes/gjgk_word_nodes/gjgk_update_word.py`, `backend/nodes/gjgk_word_nodes/gjgk_get_replacements.py`

**`backend/nodes/skills_nodes/`:**
- Purpose: rewrite task skill 的节点实现和按 tender type dispatch。
- Contains: rewrite target 选择、上下文抽取、rewrite LLM、类型感知删除/更新。
- Key files: `backend/nodes/skills_nodes/rewrite_nodes.py`, `backend/nodes/skills_nodes/tender_aware_word_dispatch.py`

**`backend/helper/word_helper/`:**
- Purpose: Word 业务 helper，适合放跨类型复用逻辑。
- Contains: 正文写回、段落边界、删除、受保护字段、样式回填、语义匹配、range 工具。
- Key files: `backend/helper/word_helper/inline_style_ops.py`, `backend/helper/word_helper/protected_fields.py`, `backend/helper/word_helper/content_ops.py`

**`backend/util/word_util/`:**
- Purpose: Word COM 技术工具层。
- Contains: COM app/document 生命周期、COM lock/retry、Word 常量、锚点工具、底层插入、诊断。
- Key files: `backend/util/word_util/word_application_util.py`, `backend/util/word_util/word_com_manager.py`, `backend/util/word_util/anchor_utils.py`

**`backend/agents/log_naming.py`:**
- Purpose: 生成/批注 agent workspace 与审计日志文件名片段清洗辅助。
- Contains: agent log stem 构造和安全文件名片段归一化。
- Key files: `backend/agents/log_naming.py`

**`backend/agents/generation/`:**
- Purpose: 初次生成 `generation_mode=agent` 的 DeepAgents 运行时。
- Contains: content agent runner、generate/verify/revise 子图、JSON 协议、workspace、model factory。
- Key files: `backend/agents/generation/content_agents.py`, `backend/agents/generation/generate_agent_graph.py`, `backend/agents/generation/verify_agent_graph.py`

**`backend/agents/comments/`:**
- Purpose: 批注智能体运行时。
- Contains: LangChain agent、工具门禁、引用校验、写回工具、审计 workspace。
- Key files: `backend/agents/comments/comment_agent.py`, `backend/agents/comments/tools.py`, `backend/agents/comments/workspace.py`

**`backend/agents/task_context_assistant/`:**
- Purpose: 右侧聊天/agent run 的任务创建前置流。
- Contains: DeepAgents factory、rewrite 工具、只读摘要工具、scrub 审计日志。
- Key files: `backend/agents/task_context_assistant/factory.py`, `backend/agents/task_context_assistant/tools.py`, `backend/agents/task_context_assistant/logging.py`

**`backend/prompts/`:**
- Purpose: Prompt Layer，纯渲染和机器契约解析。
- Contains: generate/comment/rewrite/template ranking prompt builders 和 types。
- Key files: `backend/prompts/generate_prompt.py`, `backend/prompts/comment_prompt.py`, `backend/prompts/template_candidate_ranking_prompt.py`

**`backend/retrieval/`:**
- Purpose: 批注坏案例检索诊断/实验入口，当前未接入主业务链路。
- Contains: BM25、Qdrant HTTP store、embedding client、hybrid ranking、bad case loader。
- Key files: `backend/retrieval/config.py`, `backend/retrieval/qdrant_store.py`, `backend/retrieval/hybrid.py`

**`backend/tests/`:**
- Purpose: 后端 pytest 测试。
- Contains: API、agent、config、graph、helper、logging、model、node、progress、prompt、service、skill、util 测试。
- Key files: `backend/tests/conftest.py`, `backend/tests/api/test_generate_api.py`, `backend/tests/graphs/test_generation_mode_branching.py`

## Key File Locations

**Entry Points:**
- `backend/main.py`: FastAPI 应用入口、router 注册、健康检查和启动/关闭 hook。
- `backend/api/generate.py`: `POST /api/generate` 和生成任务状态查询。
- `backend/api/agent.py`: `POST /api/agent/runs/stream` NDJSON agent run。
- `backend/api/comment_supplement.py`: `POST /api/comment-supplement`。
- `backend/api/stream.py`: `GET /api/stream/{task_id}` 和 SSE 状态。

**Configuration:**
- `backend/config/settings.py`: Pydantic Settings、LLM provider、CORS、上传、SSE、任务和日志配置。
- `backend/config/tender_config.py`: 招标类型锚点、字号、content mode、受保护字段 profile。
- `backend/requirements.txt`: 后端依赖真源。
- `backend/.env.example`: 示例环境配置；不要引用真实值。
- `backend/.env`: 本地私有配置文件存在；不得读取内容。

**Core Logic:**
- `backend/services/document_service.py`: 生成/rewrite/补充批注任务创建和 graph 执行。
- `backend/task/task_queue_manager.py`: 任务队列和进度。
- `backend/graphs/base_graph.py`: 锁、进度、取消和标准 graph 主干。
- `backend/graphs/task_skill_workflows.py`: rewrite task skill graph 元数据。
- `backend/core/sse_manager.py`: SSE 事件管理。

**Word Logic:**
- `backend/helper/word_helper/inline_style_ops.py`: 样式回填和匹配复杂逻辑。
- `backend/helper/word_helper/protected_fields.py`: 受保护字段识别与校验。
- `backend/nodes/common_word_nodes/update_word.py`: 共享 Word 更新节点。
- `backend/nodes/gngk_word_nodes/gngk_hw_cz_update_word.py`: direct-replace 财政货物写回。
- `backend/nodes/gjgk_word_nodes/gjgk_update_word.py`: 国际公开写回。

**Agents and Prompts:**
- `backend/agents/generation/content_agents.py`: content agent 主运行时。
- `backend/agents/comments/comment_agent.py`: comment agent 主运行时。
- `backend/agents/task_context_assistant/tools.py`: agent run 受控工具。
- `backend/prompts/generate_prompt.py`: generate prompt 路由。
- `backend/prompts/comment_prompt.py`: 批注 prompt 契约。

**Testing:**
- `backend/tests/api/`: API 测试。
- `backend/tests/graphs/`: graph 分支和类型绑定测试。
- `backend/tests/helper/`: Word helper 纯逻辑测试。
- `backend/tests/nodes/`: Word 节点和 skill 节点测试。
- `backend/tests/services/`: service、SSE、任务结果测试。

## Naming Conventions

**Files:**
- Python 源码使用 `snake_case.py`，例如 `document_service.py`、`task_queue_manager.py`。
- 测试使用 `test_*.py`，并放入 `backend/tests/<scope>/`。
- 类型 graph 文件使用 `<runtime_type>_tender_graph.py`，例如 `gngk_hw_cz_tender_graph.py`。
- 类型节点文件使用 `<runtime_type>_<operation>.py`，例如 `gngk_fw_zc_update_word.py`。
- Skill 声明使用 `backend/skills/<skill_id>/SKILL.md`。

**Directories:**
- API、models、services、graphs、nodes、states、tests 按职责分层。
- Word 业务 helper 放在 `backend/helper/word_helper/`，底层 COM 工具放在 `backend/util/word_util/`。
- task skill 节点放在 `backend/nodes/skills_nodes/`，声明放在 `backend/skills/`。

## Where to Add New Code

**New API Endpoint:**
- Router: `backend/api/<feature>.py`
- Models: `backend/models/<feature>.py` 或现有模型文件
- Service orchestration: `backend/services/<feature>_service.py`
- Tests: `backend/tests/api/test_<feature>_api.py` 和 `backend/tests/services/test_<feature>_service.py`

**New Tender Type:**
- API enum/model: `backend/models/generate.py`
- Anchor/config: `backend/config/tender_config.py`
- State: `backend/states/`
- Graph class: `backend/graphs/<runtime_type>_tender_graph.py`
- Node deltas: `backend/nodes/<family>_word_nodes/`
- Registry: `backend/services/document_service.py`
- Tests: `backend/tests/graphs/`、`backend/tests/config/`、相关 `backend/tests/nodes/`

**New Word Business Helper:**
- Shared implementation: `backend/helper/word_helper/`
- COM lifecycle utility: `backend/util/word_util/`
- Node integration: `backend/nodes/common_word_nodes/` 或类型节点目录
- Tests: `backend/tests/helper/` 和相关 `backend/tests/nodes/`

**New Prompt or LLM Contract:**
- Prompt builder: `backend/prompts/`
- Model/provider config: `backend/config/settings.py` 和 `backend/util/common_util/llm_stream_utils.py`
- Tests: `backend/tests/prompts/` 和调用侧测试

**New Task Skill:**
- Skill guide: `backend/skills/<skill_id>/SKILL.md`
- Workflow metadata: `backend/graphs/task_skill_workflows.py`
- Runtime nodes: `backend/nodes/skills_nodes/`
- State: `backend/states/skill_state.py` 或新增 state 文件
- Tests: `backend/tests/skills/`、`backend/tests/nodes/`、`backend/tests/services/`

**New Agent Capability:**
- Initial generation: extend `backend/agents/generation/` and `backend/nodes/common_word_nodes/content_agent_generate.py`
- Comment capability: extend `backend/agents/comments/` and `backend/nodes/common_word_nodes/comment_agent.py`
- Agent run tool: extend `backend/agents/task_context_assistant/tools.py` and `backend/services/agent_run_service.py`
- Tests: `backend/tests/agents/`、`backend/tests/services/`、相关 SSE/model 测试

**New Retrieval Feature:**
- Retrieval implementation or experiment: `backend/retrieval/`
- Diagnostic or ingestion script: `backend/scripts/`
- Tests: add focused util/retrieval tests under `backend/tests/` before connecting retrieval to a production path.

## Special Directories

**`backend/.planning/codebase/`:**
- Purpose: 后端事实文档。
- Generated: Yes
- Committed: Yes

**`backend/.venv/`:**
- Purpose: Windows 后端虚拟环境。
- Generated: Yes
- Committed: No

**`backend/.venv-linux/`:**
- Purpose: WSL/Linux 后端测试虚拟环境。
- Generated: Yes
- Committed: No

**`backend/logs/`:**
- Purpose: 运行日志目录。
- Generated: Yes
- Committed: No

**`backend/prompts_log/`:**
- Purpose: prompt、content agent workspace、comment agent audit 输出。
- Generated: Yes
- Committed: No

**`backend/test_doc/`:**
- Purpose: Word 测试或本地验证素材目录。
- Generated: Mixed
- Committed: 以仓库实际追踪状态为准。

---

*后端结构分析：2026-06-08*
