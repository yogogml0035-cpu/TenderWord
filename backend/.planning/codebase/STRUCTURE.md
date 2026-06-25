# 后端结构事实地图

**分析日期：** 2026-06-25

**范围：** 仅覆盖 `backend/` 子项目。`backend/.env` 文件存在，但不得读取或引用内容；`backend/logs/`、`backend/context_log/` 只按目录职责描述，不读取真实运行日志。

## 目录布局

```text
backend/
├── agents/                    # DeepAgents/LangChain 智能体运行时
│   ├── comments/               # 批注 agent、工具、校验、写回、审计
│   ├── generation/             # content_agent、generate/verify/revise 子图、workspace
│   └── task_context_assistant/ # agent run 前置流、受控工具、scrub 审计
├── api/                        # FastAPI routers
├── config/                     # settings 与招标类型配置
├── core/                       # SSE manager 等核心运行设施
├── graphs/                     # LangGraph 工作流
├── helper/
│   └── word_helper/            # Word 业务 helper
├── models/                     # Pydantic API/runtime 模型
├── nodes/                      # LangGraph 节点
│   ├── common_word_nodes/      # 共享 Word/LLM/agent 节点
│   ├── gjgk_word_nodes/        # 国际公开差异节点
│   ├── gngk_word_nodes/        # 国内公开差异节点
│   ├── skills_nodes/           # rewrite skill 节点和 tender-aware dispatch
│   └── xjcg_word_nodes/        # 询价采购差异节点
├── prompts/                    # prompt builders、prompt types、契约解析
├── retrieval/                  # 批注 bad case BM25/Qdrant/embedding/hybrid runtime
├── scripts/                    # Word 诊断和检索调试脚本
├── services/                   # API 与 graph/task/agent 之间的业务编排
├── skills/
│   └── rewrite/                # rewrite task skill 声明与 runtime helper
├── states/                     # LangGraph state TypedDict
├── task/                       # 任务队列、进度、取消、心跳
├── tests/                      # pytest 测试
├── util/
│   ├── common_util/            # 上传、外部 HTTP、LLM stream、模板候选等通用工具
│   ├── log_util/               # progress/execution/SSE/audit 日志工具
│   └── word_util/              # Word COM 技术工具和诊断
├── .planning/codebase/         # 后端事实文档
├── main.py                     # FastAPI 应用入口
└── requirements.txt            # 后端依赖清单
```

## 目录职责

**`backend/api/`:**
- 职责： FastAPI HTTP、SSE、NDJSON 入口，保持薄路由。
- 包含： `generate.py`, `agent.py`, `comment_supplement.py`, `tasks.py`, `stream.py`, `upload.py`, `download.py`, `tender.py`, `template_candidates.py`, `conversations.py`
- 关键文件： `backend/api/generate.py:51`, `backend/api/agent.py:19`, `backend/api/stream.py:23`, `backend/api/tasks.py:36`

**`backend/models/`:**
- 职责： API 请求/响应、任务状态、SSE 事件、agent run、模板候选、上传和招标数据模型。
- 包含： Pydantic `BaseModel`、`Enum`、validators。
- 关键文件： `backend/models/generate.py`, `backend/models/task.py`, `backend/models/sse.py`, `backend/models/agent_run.py`, `backend/models/tender.py`

**`backend/config/`:**
- 职责： 运行配置和招标类型配置。
- 包含： `settings.py`, `tender_config.py`
- 关键文件： `backend/config/settings.py:24`, `backend/config/tender_config.py:20`

**`backend/services/`:**
- 职责： API 与任务队列、graph、agent、会话、外部调用之间的编排层。
- 包含： `document_service.py`, `task_service.py`, `conversation_service.py`, `agent_run_service.py`, `chat_stream_service.py`, `template_candidate_ranking_service.py`
- 关键文件： `backend/services/document_service.py:400`, `backend/services/agent_run_service.py`, `backend/services/conversation_service.py`, `backend/services/template_candidate_ranking_service.py`

**`backend/task/`:**
- 职责： 长任务队列、状态、进度、取消、心跳、后台清理和公平执行。
- 包含： `task_queue_manager.py`
- 关键文件： `backend/task/task_queue_manager.py:169`

**`backend/core/`:**
- 职责： 核心运行基础设施。
- 包含： SSE 连接、事件缓存、断线重放、heartbeat 和跨线程调度。
- 关键文件： `backend/core/sse_manager.py:44`

**`backend/graphs/`:**
- 职责： LangGraph 工作流定义。
- 包含： `BaseGraph`, `StandardTenderWorkflowGraph`, 类型 graph（xjcg/gngk_*/gjgk）、`RewriteSkillGraph`, `CommentSupplementGraph`
- 关键文件： `backend/graphs/base_graph.py:438`, `backend/graphs/skill_graph.py:54`, `backend/graphs/comment_supplement_graph.py:19`

**`backend/states/`:**
- 职责： LangGraph state TypedDict，作为节点输入输出 shape。
- 包含： `TenderGraphStateBase`, `TaskSkillGraphState`, `XjcgTenderGraphState`, `GngkTenderGraphState`, `GjgkTenderGraphState`
- 关键文件： `backend/states/base_state.py`, `backend/states/skill_state.py`, `backend/states/gngk_tender_state.py`

**`backend/nodes/common_word_nodes/`:**
- 职责： 共享 graph 节点，覆盖模板准备、抽参、删除、替换、正文生成、批注生成、agent 节点、补充批注和写回。
- 包含： `prepare_template.py`, `extract_tender_params.py`, `delete_tender_param.py`, `replace_content.py`, `generate_polished_text.py`, `generate_comments.py`, `content_agent_generate.py`, `comment_agent.py`, `update_word.py`
- 关键文件： `backend/nodes/common_word_nodes/update_word.py`, `backend/nodes/common_word_nodes/generate_comments.py`, `backend/nodes/common_word_nodes/comment_agent.py`

**`backend/nodes/gngk_word_nodes/`:**
- 职责： 国内公开类型差异节点。
- 包含： `gngk_hw_zc`、`gngk_hw_cz`、`gngk_fw_zc` 的 replacement、delete、update 实现。
- 关键文件： `backend/nodes/gngk_word_nodes/gngk_hw_cz_update_word.py`, `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`, `backend/nodes/gngk_word_nodes/gngk_get_replacements.py`

**`backend/nodes/gjgk_word_nodes/`:**
- 职责： 国际公开类型差异节点。
- 包含： 国际公开抽取、删除、替换、写回。
- 关键文件： `backend/nodes/gjgk_word_nodes/gjgk_update_word.py`, `backend/nodes/gjgk_word_nodes/gjgk_get_replacements.py`, `backend/nodes/gjgk_word_nodes/gjgk_delete_tender_param.py`

**`backend/nodes/xjcg_word_nodes/`:**
- 职责： 询价采购类型差异节点。
- 包含： 询价采购 replacement 逻辑。
- 关键文件： `backend/nodes/xjcg_word_nodes/xjcg_get_replacements.py`

**`backend/nodes/skills_nodes/`:**
- 职责： task skill 节点，当前主要服务 rewrite。
- 包含： rewrite target 选择、上下文抽取、rewrite LLM、类型感知删除和写回 dispatch。
- 关键文件： `backend/nodes/skills_nodes/rewrite_nodes.py`, `backend/nodes/skills_nodes/tender_aware_word_dispatch.py`

**`backend/helper/word_helper/`:**
- 职责： Word 业务 helper，适合放跨节点复用逻辑。
- 包含： 正文写回、段落边界、受保护字段、样式回填、删除、cleanup、range、语义匹配。
- 关键文件： `backend/helper/word_helper/content_ops.py`, `backend/helper/word_helper/inline_style_ops.py`, `backend/helper/word_helper/protected_fields.py`, `backend/helper/word_helper/paragraph_boundary_ops.py`

**`backend/util/word_util/`:**
- 职责： Word COM 技术工具层。
- 包含： COM app 生命周期、COM lock/retry、Word 常量、锚点工具、底层插入、文档检查、诊断。
- 关键文件： `backend/util/word_util/word_application_util.py:132`, `backend/util/word_util/word_com_manager.py:100`, `backend/util/word_util/anchor_utils.py`, `backend/util/word_util/word_diagnostics.py`

**`backend/agents/generation/`:**
- 职责： `generation_mode=agent` 的正文生成智能体运行时。
- 包含： DeepAgents 主 agent、generate/verify/revise 子图、workspace、model factory、JSON 协议、`agent_step` emitter、结构化表占位符工具。
- 关键文件： `backend/agents/generation/content_agents.py`, `backend/agents/generation/generate_agent_graph.py`, `backend/agents/generation/verify_agent_graph.py`, `backend/agents/generation/table_placeholder_utils.py`, `backend/agents/generation/workspace.py`

**`backend/agents/comments/`:**
- 职责： 批注 agent 运行时。
- 包含： LangChain agent、工具调用限制、引用校验、Word 写回工具、审计 workspace。
- 关键文件： `backend/agents/comments/comment_agent.py`, `backend/agents/comments/tools.py`, `backend/agents/comments/workspace.py`

**`backend/agents/task_context_assistant/`:**
- 职责： 右侧聊天 agent run 前置流。
- 包含： DeepAgents factory、rewrite 工具、只读摘要工具、scrub 审计日志。
- 关键文件： `backend/agents/task_context_assistant/factory.py`, `backend/agents/task_context_assistant/tools.py`, `backend/agents/task_context_assistant/logging.py`

**`backend/prompts/`:**
- 职责： Prompt Layer，只负责 prompt 渲染和机器契约解析。
- 包含： generate、comment、rewrite target、skill、template candidate ranking prompt 和 prompt types。
- 关键文件： `backend/prompts/generate_prompt.py`, `backend/prompts/comment_prompt.py`, `backend/prompts/skill_prompt.py`, `backend/prompts/template_candidate_ranking_prompt.py`

**`backend/retrieval/`:**
- 职责： 批注 bad case 检索运行时，为 `generate_comments` 和 `comment_agent` 提供 prompt context。
- 包含： bad case loader、BM25、Qdrant HTTP store、embedding client、hybrid ranking、runtime cache。
- 关键文件： `backend/retrieval/comment_bad_case_runtime.py`, `backend/retrieval/bm25.py`, `backend/retrieval/qdrant_store.py`, `backend/retrieval/hybrid.py`, `backend/retrieval/config.py`

**`backend/util/common_util/`:**
- 职责： 非 Word 的通用工具。
- 包含： 上传落盘、模板候选代理、招标详情代理、LLM stream、招标编号归一化。
- 关键文件： `backend/util/common_util/upload_storage.py`, `backend/util/common_util/template_candidates.py`, `backend/util/common_util/fetch_tender_data.py`, `backend/util/common_util/llm_stream_utils.py`

**`backend/util/log_util/`:**
- 职责： 日志基础设施和任务/agent 审计辅助。
- 包含： progress log、execution log、SSE log handler、skill audit log、context log、daily handler、cleanup。
- 关键文件： `backend/util/log_util/progress_log.py`, `backend/util/log_util/execution_log.py`, `backend/util/log_util/sse_log_handler.py`, `backend/util/log_util/skill_audit_log.py`

**`backend/skills/`:**
- 职责： task skill 声明和 runtime helper。
- 包含： `catalog.py`, `rewrite/SKILL.md`, `rewrite/scripts/runtime.py`
- 关键文件： `backend/skills/rewrite/SKILL.md`, `backend/skills/rewrite/scripts/runtime.py`, `backend/skills/catalog.py`

**`backend/tests/`:**
- 职责： 后端 pytest 测试。
- 包含： API、agents、config、graphs、helper、logging、models、nodes、progress、prompts、retrieval、services、skills、util 测试。
- 关键文件： `backend/tests/conftest.py`, `backend/tests/api/test_generate_api.py`, `backend/tests/graphs/test_generation_mode_branching.py`, `backend/tests/services/test_document_service_task_result.py`

## 关键文件位置

**Entry Points:**
- `backend/main.py`: FastAPI app、router 注册、CORS、startup/shutdown、健康检查。
- `backend/api/generate.py`: `POST /api/generate` 和生成任务查询。
- `backend/api/agent.py`: `POST /api/agent/runs/stream` NDJSON agent run。
- `backend/api/comment_supplement.py`: `POST /api/comment-supplement`。
- `backend/api/stream.py`: `GET /api/stream/{task_id}` SSE。
- `backend/api/tasks.py`: 任务列表、详情、取消、心跳。

**配置：**
- `backend/config/settings.py`: Pydantic Settings、LLM provider、CORS、上传目录、外部接口、锁、SSE、任务、日志配置。
- `backend/config/tender_config.py`: 招标类型锚点、字号、content mode、受保护字段 profile。
- `backend/requirements.txt`: 后端依赖清单。
- `backend/.env.example`: 示例环境配置；不要引用真实值。
- `backend/.env`: 本地私有配置文件存在；不得读取内容。

**Core Logic:**
- `backend/services/document_service.py`: generate/rewrite/comment supplement 任务创建、graph 执行、结果收敛。
- `backend/task/task_queue_manager.py`: 任务队列、进度、取消、心跳、公平锁。
- `backend/graphs/base_graph.py`: graph 基类、标准生成主干、锁、进度、取消。
- `backend/graphs/skill_graph.py`: rewrite 显式 LangGraph 实现。
- `backend/core/sse_manager.py`: SSE 事件管理。
- `backend/services/agent_run_service.py`: agent run NDJSON 流和 rewrite guard。

**Word Logic:**
- `backend/nodes/common_word_nodes/update_word.py`: 共享 Word 更新节点。
- `backend/nodes/common_word_nodes/delete_tender_param.py`: 共享 protected-field 删除节点。
- `backend/nodes/common_word_nodes/replace_content.py`: 共享模板替换节点。
- `backend/nodes/gngk_word_nodes/gngk_hw_cz_update_word.py`: 国内公开货物财政 direct-replace 写回。
- `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`: 国内公开服务自筹写回。
- `backend/nodes/gjgk_word_nodes/gjgk_update_word.py`: 国际公开写回。
- `backend/helper/word_helper/inline_style_ops.py`: 样式回填和 inline style 匹配。
- `backend/helper/word_helper/protected_fields.py`: 受保护字段识别与严格匹配。
- `backend/util/word_util/word_application_util.py`: Word COM 创建、打开、保存、关闭。

**Agent and Prompt:**
- `backend/agents/generation/content_agents.py`: content agent 主运行时。
- `backend/agents/generation/table_placeholder_utils.py`: `[[TABLE:<id>]]` 占位符硬契约。
- `backend/agents/comments/comment_agent.py`: comment agent 主运行时。
- `backend/agents/task_context_assistant/tools.py`: agent run 受控工具。
- `backend/prompts/generate_prompt.py`: generate prompt 路由。
- `backend/prompts/comment_prompt.py`: 批注 prompt 和 bad case context 渲染。
- `backend/prompts/skill_prompt.py`: rewrite skill prompt。

**Testing:**
- `backend/tests/api/`: API 测试。
- `backend/tests/graphs/`: graph 分支和类型绑定测试。
- `backend/tests/helper/`: Word helper 纯逻辑测试。
- `backend/tests/nodes/`: Word 节点、rewrite 节点和写回逻辑测试。
- `backend/tests/services/`: service、SSE、任务结果、agent run 测试。
- `backend/tests/retrieval/`: bad case retrieval 运行时测试。

## 命名约定

**文件：**
- Python 源码使用 `snake_case.py`，例如 `document_service.py`、`task_queue_manager.py`。
- 测试文件使用 `test_*.py`，放入 `backend/tests/<scope>/`。
- 类型 graph 使用 `<runtime_type>_tender_graph.py`，例如 `gngk_hw_cz_tender_graph.py`。
- 类型节点使用 `<runtime_type>_<operation>.py`，例如 `gngk_fw_zc_update_word.py`。
- task skill 声明使用 `backend/skills/<skill_id>/SKILL.md`。
- Agent workspace/audit 文件名片段复用 `backend/agents/log_naming.py`。

**Directories:**
- `api`, `models`, `services`, `graphs`, `nodes`, `states`, `tests` 按职责分层。
- Word 业务复用逻辑放入 `backend/helper/word_helper/`。
- Word COM 技术工具放入 `backend/util/word_util/`。
- 非 Word 通用工具放入 `backend/util/common_util/`。
- task skill 节点放入 `backend/nodes/skills_nodes/`，声明和 runtime helper 放入 `backend/skills/`。

## 新代码落位

**New API Endpoint:**
- Primary code: `backend/api/<feature>.py`
- Models: `backend/models/<feature>.py` 或现有模型文件
- Service orchestration: `backend/services/<feature>_service.py`
- Router registration: `backend/main.py`
- Tests: `backend/tests/api/test_<feature>_api.py`, `backend/tests/services/test_<feature>_service.py`

**New Generate Request Field:**
- Model: `backend/models/generate.py`
- Initial state mapping: `backend/services/document_service.py`
- Graph/node consumer: `backend/graphs/` 或 `backend/nodes/`
- SSE/task result contract when user-visible: `backend/models/sse.py` 或 `backend/models/task.py`
- Tests: `backend/tests/models/`, `backend/tests/api/`, `backend/tests/services/`, `backend/tests/graphs/`

**New Tender Type:**
- API enum/model: `backend/models/generate.py`
- Anchor/config: `backend/config/tender_config.py`
- State: `backend/states/`
- Graph class: `backend/graphs/<runtime_type>_tender_graph.py`
- Node differences: `backend/nodes/<family>_word_nodes/`
- Registry: `backend/services/document_service.py`
- Tests: `backend/tests/config/`, `backend/tests/graphs/`, related `backend/tests/nodes/`

**New Word Business Helper:**
- Implementation: `backend/helper/word_helper/<topic>.py`
- Optional export: `backend/helper/word_helper/__init__.py`
- Node usage: `backend/nodes/common_word_nodes/` 或类型节点
- Tests: `backend/tests/helper/test_<topic>.py`

**New Word COM Helper:**
- Implementation: `backend/util/word_util/<topic>.py`
- Optional export: `backend/util/word_util/__init__.py`
- Diagnostic hook: `backend/scripts/diagnose_word.py`
- Tests: `backend/tests/util/` 覆盖纯逻辑；COM 闭环需要 Windows + Word/WPS。

**New Graph Node:**
- Shared node: `backend/nodes/common_word_nodes/<node>.py`
- Type-specific node: `backend/nodes/<family>_word_nodes/<runtime_type>_<operation>.py`
- User-visible progress: 同步 `backend/graphs/base_graph.py` 和 `backend/task/task_queue_manager.py`
- Tests: `backend/tests/nodes/test_<node>.py`, `backend/tests/graphs/`

**New Task Skill:**
- Skill declaration: `backend/skills/<skill_id>/SKILL.md`
- Runtime helper: `backend/skills/<skill_id>/scripts/runtime.py`
- Nodes: `backend/nodes/skills_nodes/<skill_id>_nodes.py`
- Graph: 当前 rewrite 由 `backend/graphs/skill_graph.py` 显式承载；新增 skill 优先新增显式 graph 类，不要恢复 `SkillGraph.for_skill + TaskSkillWorkflow`
- Tests: `backend/tests/skills/`, `backend/tests/graphs/`, `backend/tests/nodes/`
- Constraint: 不要恢复旧 `/api/edit`、`edit` task kind 或独立 `edit` skill；上传文件修改继续复用 `backend/skills/rewrite/` 和 `rewrite_source="uploaded_file"`。

**New Agent Capability:**
- Generation agent: `backend/agents/generation/`
- Comment agent: `backend/agents/comments/`
- Task context assistant tool: `backend/agents/task_context_assistant/tools.py`
- Shared model factory: `backend/agents/generation/model_factory.py`
- Prompt: `backend/prompts/`
- Workspace/audit naming: `backend/agents/log_naming.py`
- Tests: `backend/tests/agents/`, plus related `backend/tests/models/` or `backend/tests/services/`

**New Retrieval Behavior:**
- Runtime code: `backend/retrieval/`
- Prompt integration: `backend/nodes/common_word_nodes/generate_comments.py` 或 `backend/nodes/common_word_nodes/comment_agent.py`
- Bad case data: `backend/retrieval/bad_cases/`
- Tests: `backend/tests/retrieval/`, `backend/tests/prompts/`

**New External Integration:**
- Settings: `backend/config/settings.py`
- HTTP utility: `backend/util/common_util/<integration>.py`
- API proxy: `backend/api/<integration>.py`
- Service if orchestration or LLM is needed: `backend/services/<integration>_service.py`
- Security: add timeout、allowlist、file type/path validation、log scrub。
- Tests: `backend/tests/util/`, `backend/tests/api/`, `backend/tests/services/`

## 特殊目录

**`backend/.planning/codebase/`:**
- 职责： 后端事实地图。
- Generated: Yes
- Committed: Yes

**`backend/.venv/`:**
- 职责： 本地虚拟环境。
- Generated: Yes
- Committed: No
- Rule: 不扫描、不引用其中实现作为项目代码。

**`backend/**/__pycache__/`:**
- 职责： Python 运行时缓存。
- Generated: Yes
- Committed: No
- Rule: 不扫描、不把缓存目录反推为架构模块或已支持功能。

**`backend/logs/`:**
- 职责： 后端运行日志、进度日志、execution log、agent run audit 等。
- Generated: Yes
- Committed: No
- Rule: 不读取真实运行日志内容，避免泄露客户文本、路径或异常细节。

**`backend/context_log/`:**
- 职责： context、prompt、LLM 输出、agent workspace、rewrite audit 和 retrieval 审计输出。
- Generated: Yes
- Committed: No
- Rule: 不读取真实生成日志内容；文档中只引用代码里的写入路径和机制。

**`backend/retrieval/bad_cases/`:**
- 职责： 批注 bad case Markdown 数据源。
- Generated: No
- Committed: Yes

**`backend/scripts/`:**
- 职责： Word 诊断、bad case index 和 retrieval 手动调试脚本。
- Generated: No
- Committed: Yes

**`backend/.env`:**
- 职责： 本地私有配置。
- Generated: Local
- Committed: No
- Rule: 不读取内容；只记录文件存在和代码读取机制。

**`backend/.env.example`:**
- 职责： 示例环境配置。
- Generated: No
- Committed: Yes
- Rule: 可用于理解配置键，不得替代真实运行验证。

---

*后端结构分析：2026-06-25*
