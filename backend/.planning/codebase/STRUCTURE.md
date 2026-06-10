# 后端结构事实地图

**分析日期：** 2026-06-09

**范围：** 仅覆盖 `backend/` 子项目。输出限定为 `backend/.planning/codebase/ARCHITECTURE.md` 和 `backend/.planning/codebase/STRUCTURE.md`。`backend/.env` 文件存在，但不得读取或引用内容。

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
├── graphs/                     # LangGraph graph 类和 task skill workflow 元数据
├── helper/
│   └── word_helper/            # Word 业务 helper
├── models/                     # Pydantic API/runtime 模型
├── nodes/                      # LangGraph 节点
│   ├── common_word_nodes/      # 共享 Word/LLM/agent graph 节点
│   ├── gjgk_word_nodes/        # 国际公开差异节点
│   ├── gngk_word_nodes/        # 国内公开差异节点
│   ├── skills_nodes/           # rewrite skill 节点和 tender-aware dispatch
│   └── xjcg_word_nodes/        # 询价采购差异节点
├── prompts/                    # prompt builders、prompt types、契约解析
├── retrieval/                  # 批注 bad case BM25/Qdrant/embedding/hybrid runtime
├── scripts/                    # Word 诊断和检索调试脚本
├── services/                   # API 与 graph/task/agent 之间的业务编排
├── skills/
│   └── rewrite/                # 当前被跟踪的 rewrite task skill 声明与 runtime helper
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
- 用途： 暴露 FastAPI HTTP、SSE 和 NDJSON 入口；保持薄路由。
- 包含： `generate.py`、`agent.py`、`comment_supplement.py`、`tasks.py`、`stream.py`、`upload.py`、`download.py`、`tender.py`、`template_candidates.py`、`conversations.py`
- 关键文件： `backend/api/generate.py:51`, `backend/api/agent.py:19`, `backend/api/stream.py:23`, `backend/api/tasks.py:36`

**`backend/models/`:**
- 用途： 定义 API 请求/响应、任务状态、SSE 事件、agent run、模板候选、上传和招标数据模型。
- 包含： Pydantic `BaseModel`、`Enum`、validator。
- 关键文件： `backend/models/generate.py:117`, `backend/models/task.py:17`, `backend/models/sse.py:17`, `backend/models/agent_run.py:92`

**`backend/config/`:**
- 用途： 管理运行配置和招标类型配置。
- 包含： `settings.py`、`tender_config.py`
- 关键文件： `backend/config/settings.py:24`, `backend/config/tender_config.py:142`

**`backend/services/`:**
- 用途： API 与任务队列、graph、agent、会话、外部调用之间的编排层。
- 包含： 文档任务、agent run、会话、任务查询、NDJSON 行辅助、模板候选 AI 重排。
- 关键文件： `backend/services/document_service.py:402`, `backend/services/agent_run_service.py:306`, `backend/services/conversation_service.py:24`, `backend/services/template_candidate_ranking_service.py:31`

**`backend/task/`:**
- 用途： 管理长任务队列、进度、取消、心跳、后台清理和公平执行。
- 包含： `TaskQueueManager`、`Task`、`TaskProgress`、节点显示名。
- 关键文件： `backend/task/task_queue_manager.py:169`

**`backend/core/`:**
- 用途： 核心运行基础设施。
- 包含： SSE 连接、事件缓存、重放、心跳和跨线程事件调度。
- 关键文件： `backend/core/sse_manager.py:44`

**`backend/graphs/`:**
- 用途： 定义 LangGraph 工作流和 task skill graph 元数据。
- 包含： `BaseGraph`、`StandardTenderWorkflowGraph`、类型 graph、`SkillGraph`、`CommentSupplementGraph`、`TaskSkillWorkflow`。
- 关键文件： `backend/graphs/base_graph.py:480`, `backend/graphs/skill_graph.py:15`, `backend/graphs/task_skill_workflows.py:27`, `backend/graphs/comment_supplement_graph.py:19`

**`backend/states/`:**
- 用途： 保存 LangGraph state TypedDict，作为节点输入输出 shape。
- 包含： `TenderGraphStateBase`、`TaskSkillGraphState`、`XjcgTenderGraphState`、`GngkTenderGraphState`、`GjgkTenderGraphState`。
- 关键文件： `backend/states/base_state.py`, `backend/states/skill_state.py`, `backend/states/gngk_tender_state.py`

**`backend/nodes/common_word_nodes/`:**
- 用途： 共享 graph 节点，覆盖模板准备、抽参、删除、替换、正文生成、批注生成、agent 节点、补充批注和写回。
- 包含： `prepare_template.py`、`extract_tender_params.py`、`delete_tender_param.py`、`replace_content.py`、`generate_polished_text.py`、`generate_comments.py`、`content_agent_generate.py`、`comment_agent.py`、`update_word.py`。
- 关键文件： `backend/nodes/common_word_nodes/update_word.py`, `backend/nodes/common_word_nodes/generate_comments.py:237`, `backend/nodes/common_word_nodes/comment_agent.py:327`

**`backend/nodes/gngk_word_nodes/`:**
- 用途： 国内公开类型差异节点。
- 包含： `gngk_hw_zc`、`gngk_hw_cz`、`gngk_fw_zc` 的 replacement、delete、update 实现。
- 关键文件： `backend/nodes/gngk_word_nodes/gngk_hw_cz_update_word.py`, `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`, `backend/nodes/gngk_word_nodes/gngk_get_replacements.py`

**`backend/nodes/gjgk_word_nodes/`:**
- 用途： 国际公开类型差异节点。
- 包含： 国际公开抽取、删除、替换、写回。
- 关键文件： `backend/nodes/gjgk_word_nodes/gjgk_update_word.py`, `backend/nodes/gjgk_word_nodes/gjgk_get_replacements.py`, `backend/nodes/gjgk_word_nodes/gjgk_delete_tender_param.py`

**`backend/nodes/xjcg_word_nodes/`:**
- 用途： 询价采购类型差异节点。
- 包含： 询价采购 replacement 逻辑。
- 关键文件： `backend/nodes/xjcg_word_nodes/xjcg_get_replacements.py`

**`backend/nodes/skills_nodes/`:**
- 用途： task skill 节点，主要服务 rewrite。
- 包含： rewrite target 选择、上下文抽取、rewrite LLM、类型感知删除和写回 dispatch。
- 关键文件： `backend/nodes/skills_nodes/rewrite_nodes.py`, `backend/nodes/skills_nodes/tender_aware_word_dispatch.py:26`

**`backend/helper/word_helper/`:**
- 用途： Word 业务 helper，适合放跨节点复用逻辑。
- 包含： 正文写回、段落边界、受保护字段、样式回填、删除、cleanup、range、语义匹配。
- 关键文件： `backend/helper/word_helper/content_ops.py`, `backend/helper/word_helper/inline_style_ops.py`, `backend/helper/word_helper/protected_fields.py`, `backend/helper/word_helper/paragraph_boundary_ops.py`

**`backend/util/word_util/`:**
- 用途： Word COM 技术工具层。
- 包含： COM app 生命周期、COM lock/retry、Word 常量、锚点工具、底层插入、文档检查、诊断。
- 关键文件： `backend/util/word_util/word_application_util.py:132`, `backend/util/word_util/word_com_manager.py:100`, `backend/util/word_util/anchor_utils.py`, `backend/util/word_util/word_diagnostics.py`

**`backend/agents/generation/`:**
- 用途： `generation_mode=agent` 的正文生成智能体运行时。
- 包含： DeepAgents 主 agent、generate/verify/revise 子图、workspace、model factory、JSON 协议和 `agent_step` emitter。
- 关键文件： `backend/agents/generation/content_agents.py:845`, `backend/agents/generation/generate_agent_graph.py:195`, `backend/agents/generation/verify_agent_graph.py:369`, `backend/agents/generation/workspace.py:39`

**`backend/agents/comments/`:**
- 用途： 批注 agent 运行时。
- 包含： LangChain agent、工具调用限制、引用校验、Word 写回工具、审计 workspace。
- 关键文件： `backend/agents/comments/comment_agent.py:611`, `backend/agents/comments/tools.py:175`, `backend/agents/comments/tools.py:478`, `backend/agents/comments/workspace.py:17`

**`backend/agents/task_context_assistant/`:**
- 用途： 右侧聊天 agent run 前置流。
- 包含： DeepAgents factory、rewrite 工具、只读摘要工具、scrub 审计日志。
- 关键文件： `backend/agents/task_context_assistant/factory.py:55`, `backend/agents/task_context_assistant/tools.py:197`, `backend/agents/task_context_assistant/logging.py:32`

**`backend/prompts/`:**
- 用途： Prompt Layer，负责纯渲染和机器契约解析。
- 包含： generate、comment、rewrite target、skill、template candidate ranking prompt 和 prompt types。
- 关键文件： `backend/prompts/generate_prompt.py`, `backend/prompts/comment_prompt.py`, `backend/prompts/skill_prompt.py`, `backend/prompts/template_candidate_ranking_prompt.py`

**`backend/retrieval/`:**
- 用途： 批注 bad case 检索运行时，为 `generate_comments` 和 `comment_agent` 提供 prompt context。
- 包含： bad case loader、BM25、Qdrant HTTP store、embedding client、hybrid ranking、runtime cache。
- 关键文件： `backend/retrieval/comment_bad_case_runtime.py:421`, `backend/retrieval/bm25.py:32`, `backend/retrieval/qdrant_store.py:22`, `backend/retrieval/hybrid.py:31`, `backend/retrieval/config.py:64`

**`backend/util/common_util/`:**
- 用途： 非 Word 的通用工具。
- 包含： 上传落盘、模板候选代理、招标详情代理、LLM stream、招标编号归一化。
- 关键文件： `backend/util/common_util/upload_storage.py:61`, `backend/util/common_util/template_candidates.py:73`, `backend/util/common_util/fetch_tender_data.py`, `backend/util/common_util/llm_stream_utils.py:190`

**`backend/util/log_util/`:**
- 用途： 日志基础设施和任务/agent 审计辅助。
- 包含： progress log、execution log、SSE log handler、skill audit log、prompt log、daily handler、cleanup。
- 关键文件： `backend/util/log_util/progress_log.py`, `backend/util/log_util/execution_log.py`, `backend/util/log_util/sse_log_handler.py`, `backend/util/log_util/skill_audit_log.py`

**`backend/skills/`:**
- 用途： task skill 声明和 loader。
- 包含： `catalog.py`、`rewrite/SKILL.md`、`rewrite/scripts/runtime.py`
- 关键文件： `backend/skills/catalog.py`, `backend/skills/rewrite/SKILL.md`, `backend/skills/rewrite/scripts/runtime.py`
- 约束： 当前被 Git 跟踪的 task skill 源码只有 `backend/skills/rewrite/`；不要把本地 `__pycache__` 或旧缓存目录当作可用 skill 来源。

**`backend/tests/`:**
- 用途： 后端 pytest 测试。
- 包含： API、agents、config、graphs、helper、logging、models、nodes、progress、prompts、retrieval、services、skills、util 测试。
- 关键文件： `backend/tests/conftest.py`, `backend/tests/api/test_generate_api.py`, `backend/tests/graphs/test_generation_mode_branching.py`, `backend/tests/services/test_document_service_task_result.py`

## 关键文件位置

**入口点：**
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

**核心逻辑：**
- `backend/services/document_service.py`: 生成/rewrite/补充批注任务创建、graph 执行、结果收敛。
- `backend/task/task_queue_manager.py`: 任务队列、进度、取消、心跳、公平锁。
- `backend/graphs/base_graph.py`: graph 基类、标准生成主干、锁、进度、取消。
- `backend/graphs/task_skill_workflows.py`: rewrite task skill graph 元数据。
- `backend/core/sse_manager.py`: SSE 事件管理。
- `backend/services/agent_run_service.py`: agent run NDJSON 流和 rewrite guard。

**Word 逻辑：**
- `backend/nodes/common_word_nodes/update_word.py`: 共享 Word 更新节点。
- `backend/nodes/common_word_nodes/delete_tender_param.py`: 共享 protected-field 删除节点。
- `backend/nodes/common_word_nodes/replace_content.py`: 共享模板替换节点。
- `backend/nodes/gngk_word_nodes/gngk_hw_cz_update_word.py`: 国内公开货物财政 direct-replace 写回。
- `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`: 国内公开服务自筹写回。
- `backend/nodes/gjgk_word_nodes/gjgk_update_word.py`: 国际公开写回。
- `backend/helper/word_helper/inline_style_ops.py`: 样式回填和 inline style 匹配。
- `backend/helper/word_helper/protected_fields.py`: 受保护字段识别与严格匹配。
- `backend/util/word_util/word_application_util.py`: Word COM 创建、打开、关闭。

**智能体与 Prompt：**
- `backend/agents/generation/content_agents.py`: content agent 主运行时。
- `backend/agents/comments/comment_agent.py`: comment agent 主运行时。
- `backend/agents/task_context_assistant/tools.py`: agent run 受控工具。
- `backend/prompts/generate_prompt.py`: generate prompt 路由。
- `backend/prompts/comment_prompt.py`: 批注 prompt 和 bad case context 渲染。
- `backend/prompts/skill_prompt.py`: rewrite skill prompt。

**检索：**
- `backend/retrieval/comment_bad_case_runtime.py`: 批注 bad case runtime、hybrid/BM25 降级。
- `backend/retrieval/bad_case_loader.py`: bad case Markdown 加载和 chunk。
- `backend/retrieval/bad_cases/comment_bad_cases.md`: committed bad case 数据源。
- `backend/scripts/test_comment_hybrid_retrieval.py`: 手动检索诊断脚本。

**测试：**
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

**目录：**
- `api`、`models`、`services`、`graphs`、`nodes`、`states`、`tests` 按职责分层。
- Word 业务复用逻辑放入 `backend/helper/word_helper/`。
- Word COM 技术工具放入 `backend/util/word_util/`。
- 非 Word 通用工具放入 `backend/util/common_util/`。
- task skill 节点放入 `backend/nodes/skills_nodes/`，声明和 runtime helper 放入 `backend/skills/`。
- 新增测试跟随被测层级放入 `backend/tests/<scope>/`。

## 新代码落位

**新增 API 端点：**
- 路由： `backend/api/<feature>.py`
- 模型： `backend/models/<feature>.py` 或现有模型文件
- Service 编排： `backend/services/<feature>_service.py`
- 路由注册： `backend/main.py`
- 测试： `backend/tests/api/test_<feature>_api.py` 和 `backend/tests/services/test_<feature>_service.py`

**新增生成请求字段：**
- 后端模型： `backend/models/generate.py`
- 初始状态映射： `backend/services/document_service.py`
- Graph/node 消费方： `backend/graphs/` 或 `backend/nodes/`
- 用户可见时的 SSE/task result 契约： `backend/models/sse.py` 或 `backend/models/task.py`
- 测试： `backend/tests/models/`、`backend/tests/api/`、相关 `backend/tests/services/` 或 `backend/tests/graphs/`

**新增招标类型：**
- API enum/model： `backend/models/generate.py`
- 锚点/配置： `backend/config/tender_config.py`
- 状态： `backend/states/`
- Graph class： `backend/graphs/<runtime_type>_tender_graph.py`
- 节点差异： `backend/nodes/<family>_word_nodes/`
- Registry： `backend/services/document_service.py`
- 测试： `backend/tests/config/`、`backend/tests/graphs/`、相关 `backend/tests/nodes/`

**新增 Word 业务 Helper：**
- 共享实现： `backend/helper/word_helper/<topic>.py`
- 需要时导出： `backend/helper/word_helper/__init__.py`
- 节点使用方： `backend/nodes/common_word_nodes/` 或类型节点
- 测试： `backend/tests/helper/test_<topic>.py`

**新增 Word COM 技术 Helper：**
- 实现： `backend/util/word_util/<topic>.py`
- 需要时导出： `backend/util/word_util/__init__.py`
- 环境相关诊断： `backend/scripts/diagnose_word.py`
- 测试：尽可能在 `backend/tests/util/` 覆盖纯逻辑；COM 闭环需要 Windows + Word/WPS。

**新增 Graph 节点：**
- 共享节点： `backend/nodes/common_word_nodes/<node>.py`
- 类型专属节点： `backend/nodes/<family>_word_nodes/<runtime_type>_<operation>.py`
- 进度追踪：只有需要用户可见进度时，才在 `backend/graphs/base_graph.py` 和 `backend/task/task_queue_manager.py` 增加节点名。
- 测试：`backend/tests/nodes/test_<node>.py` 和 `backend/tests/graphs/` 中的 graph 分支测试。

**新增 Task Skill：**
- Skill 声明： `backend/skills/<skill_id>/SKILL.md`
- Runtime helper： `backend/skills/<skill_id>/scripts/runtime.py`
- 节点： `backend/nodes/skills_nodes/<skill_id>_nodes.py`
- Workflow 元数据： `backend/graphs/task_skill_workflows.py`
- Graph 执行：使用 `SkillGraph.for_skill("<skill_id>")`
- 测试： `backend/tests/skills/`、`backend/tests/graphs/`、`backend/tests/nodes/`
- 兼容约束：不要恢复旧 `/api/edit`、`edit` task kind 或独立 `edit` skill；上传文件修改应继续复用 `backend/skills/rewrite/` 和 `rewrite_source="uploaded_file"`。

**新增智能体能力：**
- 生成智能体： `backend/agents/generation/`
- 批注智能体： `backend/agents/comments/`
- 任务上下文助手工具： `backend/agents/task_context_assistant/tools.py`
- 共享模型工厂： `backend/agents/generation/model_factory.py`
- Prompt： `backend/prompts/`
- 审计/workspace 命名： `backend/agents/log_naming.py`
- 测试：`backend/tests/agents/`，以及 `backend/tests/models/` 或 `backend/tests/services/` 中的事件契约测试。

**新增检索行为：**
- 运行时代码： `backend/retrieval/`
- Prompt 集成：`backend/nodes/common_word_nodes/generate_comments.py` 或 `backend/nodes/common_word_nodes/comment_agent.py`
- Bad case 数据： `backend/retrieval/bad_cases/`
- 测试：`backend/tests/retrieval/` 和 `backend/tests/prompts/` 中的 prompt 测试。

**新增外部集成：**
- 设置： `backend/config/settings.py`
- HTTP 工具： `backend/util/common_util/<integration>.py`
- API 代理： `backend/api/<integration>.py`
- 如需 LLM 或业务编排，Service： `backend/services/<integration>_service.py`
- 安全：校验 allowlist、timeout、file type、path，并保持日志 scrub。
- 测试： `backend/tests/util/`、`backend/tests/api/`、`backend/tests/services/`

## 特殊目录

**`backend/.planning/codebase/`:**
- 用途： 后端事实地图。
- 是否生成：是
- 是否提交：是

**`backend/.venv/`, `backend/.venv-linux/`:**
- 用途： 本地虚拟环境。
- 是否生成：是
- 是否提交：否
- 映射规则： 不扫描、不引用其中实现作为项目代码。

**`backend/**/__pycache__/`:**
- 用途： Python 运行时缓存。
- 是否生成：是
- 是否提交：否
- 映射规则： 不扫描、不把缓存目录反推为架构模块或已支持功能。

**`backend/logs/`:**
- 用途： 后端运行日志、进度日志、execution log、agent run audit 等。
- 是否生成：是
- 是否提交：否
- 映射规则： 不读取真实运行日志内容，避免泄露客户文本、路径或异常细节。

**`backend/context_log/`:**
- 用途： context、prompt、LLM 输出、agent workspace 和 retrieval 审计输出。
- 是否生成：是
- 是否提交：否
- 映射规则： 不读取真实生成日志内容，文档中只引用代码里的写入路径和机制。

**`backend/retrieval/bad_cases/`:**
- 用途： 批注 bad case Markdown 数据源。
- 是否生成：否
- 是否提交：是

**`backend/test_doc/`:**
- 用途： 本地/样例 Word 测试文档目录。
- 是否生成：混合
- 是否提交：混合
- 映射规则： 不依赖其中私有文档内容描述架构。

**`backend/.env`, `backend/.env.example`:**
- 用途： `.env` 是本地私有配置；`.env.example` 是示例配置。
- 是否生成：`.env` 本地生成，`.env.example` 已提交
- 是否提交：`.env` 否，`.env.example` 是
- 映射规则： 不读取 `.env` 内容；可以记录文件存在和代码读取机制。

---

*结构分析： 2026-06-09*
