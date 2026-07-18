# 后端结构事实地图

**分析日期：** 2026-07-18

**范围：** 仅覆盖 `backend/` 子项目。`backend/.env` 文件存在，但不得读取或引用内容；`backend/logs/`、`backend/context_log/` 只按目录职责描述，不读取真实运行日志。

## 目录布局

```text
backend/
├── agents/                    # DeepAgents/LangChain 智能体运行时
│   ├── comments/               # 批注 agent、工具、类型、写回、审计 workspace
│   ├── generation/             # content_agent、generate/verify/revise 子图、workspace、sanitizer、guard
│   ├── task_context_assistant/ # agent run 前置流、受控工具、scrub 审计
│   └── log_naming.py           # agent workspace/审计文件名清洗
├── api/                        # FastAPI routers（薄入口）
├── config/                     # settings 与招标类型配置
├── core/                       # SSE manager 等核心运行设施
├── graphs/                     # LangGraph 工作流
├── helper/
│   └── word_helper/            # Word 业务 helper（段落/样式/保护字段/表占位符）
├── models/                     # Pydantic API/runtime 模型
├── nodes/                      # LangGraph 节点
│   ├── common_word_nodes/      # 共享 Word/LLM/agent 节点
│   ├── gjgk_word_nodes/        # 国际公开差异节点
│   ├── gngk_word_nodes/        # 国内公开差异节点（hw/fw × zc/cz）
│   ├── skills_nodes/           # rewrite skill 节点和 tender-aware dispatch
│   └── xjcg_word_nodes/        # 询价采购差异节点
├── prompts/                    # prompt builders、prompt types、契约解析
├── retrieval/                  # 批注 bad case BM25/Qdrant/embedding/hybrid runtime
│   └── bad_cases/              # bad case 源数据
├── scripts/                    # Word 诊断和检索调试脚本
├── services/                   # API 与 graph/task/agent 之间的业务编排
├── skills/
│   ├── catalog.py              # skill 目录
│   └── rewrite/                # rewrite task skill 声明与 runtime helper
│       ├── SKILL.md
│       └── scripts/runtime.py
├── states/                     # LangGraph state TypedDict
├── task/                       # 任务队列、进度、取消、心跳
├── tests/                      # pytest 测试（镜像源码分层）
├── util/
│   ├── common_util/            # 上传、外部 HTTP、LLM stream、模板候选等通用工具
│   ├── log_util/               # progress/execution/SSE/audit 日志工具
│   └── word_util/              # Word COM 技术工具和诊断
├── .planning/codebase/         # 后端事实文档
├── main.py                     # FastAPI 应用入口
└── requirements.txt            # 后端依赖清单
```

运行产物目录（非源码，不要当业务模块扩展）：

```text
backend/logs/                   # progress/execution 日滚日志
backend/context_log/            # agent workspace 与审计落盘
```

## 目录职责

**`backend/api/`:**
- 职责： FastAPI HTTP、SSE、NDJSON 入口，保持薄路由。
- 包含： `generate.py`, `agent.py`, `comment_supplement.py`, `tasks.py`, `stream.py`, `upload.py`, `download.py`, `tender.py`, `template_candidates.py`, `conversations.py`
- 关键文件： `backend/api/generate.py`, `backend/api/agent.py`, `backend/api/stream.py`, `backend/api/tasks.py`
- 路由注册： 全部在 `backend/main.py` 以 `prefix="/api"` 挂载。

**`backend/models/`:**
- 职责： API 请求/响应、任务状态、SSE 事件、agent run、模板候选、上传和招标数据模型。
- 包含： Pydantic `BaseModel`、`Enum`、validators。
- 关键文件： `backend/models/generate.py`（`FormType`、`GenerateRequest`、generate-only 字段）、`backend/models/task.py`、`backend/models/sse.py`、`backend/models/agent_run.py`、`backend/models/tender.py`、`backend/models/upload.py`、`backend/models/template_candidates.py`、`backend/models/common.py`

**`backend/config/`:**
- 职责： 运行配置和招标类型配置。
- 包含： `settings.py`, `tender_config.py`
- 关键文件： `backend/config/settings.py`；`backend/config/tender_config.py`（`TenderAnchorConfig`、`ProtectedFieldProfile`、`get_tender_type_family`、`ANCHOR_CONFIGS`）

**`backend/services/`:**
- 职责： API 与任务队列、graph、agent、会话、外部调用之间的编排层。
- 包含： `document_service.py`, `task_service.py`, `conversation_service.py`, `agent_run_service.py`, `chat_stream_service.py`, `template_candidate_ranking_service.py`
- 关键文件： `backend/services/document_service.py`（`GRAPH_REGISTRY`、`create_task` / `create_rewrite_task` / `create_comment_supplement_task`、`_build_initial_state`、`_submit_graph_task`、`_run_graph`）

**`backend/task/`:**
- 职责： 长任务队列、状态、进度、取消、心跳、后台清理和公平执行。
- 包含： `task_queue_manager.py`
- 关键文件： `backend/task/task_queue_manager.py`（`TaskQueueManager`、`Task`、`TaskKind`、`NodeName`、公平锁、cancel 传播）

**`backend/core/`:**
- 职责： 核心运行基础设施。
- 包含： SSE 连接、事件缓存、断线重放、heartbeat 和跨线程调度。
- 关键文件： `backend/core/sse_manager.py`（`SSEManager`、`bind_loop`、`event_stream`、`send_*_threadsafe`）

**`backend/graphs/`:**
- 职责： LangGraph 工作流定义。
- 包含： `BaseGraph`, `StandardTenderWorkflowGraph`, 类型 graph（xjcg / gngk_hw_zc / hw_cz / fw_zc / fw_cz / gjgk）、`RewriteSkillGraph`, `CommentSupplementGraph`
- 关键文件：
  - `backend/graphs/base_graph.py`（`CrossProcessFileLock`、`wrap_node_with_progress`、`StandardTenderWorkflowGraph.build_graph`）
  - `backend/graphs/skill_graph.py`（`RewriteSkillGraph` + 条件分支）
  - `backend/graphs/comment_supplement_graph.py`
  - `backend/graphs/gngk_hw_zc_tender_graph.py`（gngk family 基图）
  - `backend/graphs/gngk_hw_cz_tender_graph.py`（覆写 delete/update，direct replace）
  - `backend/graphs/gngk_fw_zc_tender_graph.py` / `gngk_fw_cz_tender_graph.py`
  - `backend/graphs/gjgk_tender_graph.py`（post-update `replace_content`）
  - `backend/graphs/xjcg_tender_graph.py`

**`backend/states/`:**
- 职责： LangGraph state TypedDict，作为节点输入输出 shape。
- 包含： `BaseState` / `TenderGraphStateBase`, `TaskSkillGraphState`, `XjcgTenderGraphState`, `GngkTenderGraphState`, `GjgkTenderGraphState`
- 关键文件： `backend/states/base_state.py`（含 generate-only 字段与 `tender_param_table_models`）、`backend/states/skill_state.py`（`rewrite_source` / `rewrite_user_prompt` / `source_document_path`）

**`backend/nodes/common_word_nodes/`:**
- 职责： 共享 graph 节点，覆盖模板准备、抽参、删除、替换、正文生成、批注生成、agent 节点、补充批注和写回。
- 包含： `prepare_template.py`, `extract_tender_params.py`, `delete_tender_param.py`, `replace_content.py`, `generate_polished_text.py`, `annotate_corrections.py`, `generate_comments.py`, `content_agent_generate.py`, `comment_agent.py`, `comment_supplement.py`, `update_word.py`, `comment_writeback.py`, `get_replacements_core.py`, `get_replacements_shared.py`, `get_rewrite_comments.py`, `comment_extraction.py`
- 关键文件： `update_word.py`, `annotate_corrections.py`, `generate_comments.py`, `content_agent_generate.py`

**`backend/nodes/gngk_word_nodes/`:**
- 职责： 国内公开类型差异节点（货物/服务 × 自筹/财政）。
- 包含： `gngk_hw_zc_get_replacements.py`, `gngk_hw_cz_delete_tender_param.py`, `gngk_hw_cz_update_word.py`, `gngk_fw_zc_*`, `gngk_get_replacements.py`
- 关键文件： `gngk_hw_cz_update_word.py`, `gngk_fw_zc_update_word.py`, `gngk_get_replacements.py`

**`backend/nodes/gjgk_word_nodes/`:**
- 职责： 国际公开类型差异节点。
- 包含： `gjgk_delete_tender_param.py`, `gjgk_get_replacements.py`, `gjgk_replace_content.py`, `gjgk_update_word.py`
- 关键文件： `gjgk_update_word.py`, `gjgk_get_replacements.py`

**`backend/nodes/xjcg_word_nodes/`:**
- 职责： 询价采购类型差异节点。
- 包含： `xjcg_get_replacements.py`

**`backend/nodes/skills_nodes/`:**
- 职责： task skill 节点，当前主要服务 rewrite。
- 包含： rewrite target 选择、上下文抽取、rewrite LLM、类型感知删除和写回 dispatch。
- 关键文件： `rewrite_nodes.py`（`resolve_rewrite_target`、`extract_rewrite_context`、`rewrite_text`）、`tender_aware_word_dispatch.py`（`dispatch_tender_aware_*`）

**`backend/helper/word_helper/`:**
- 职责： Word 业务 helper，适合放跨节点复用逻辑。
- 包含： `content_ops.py`, `paragraph_boundary_ops.py`, `protected_fields.py`, `inline_style_ops.py`, `delete_ops.py`, `cleanup_ops.py`, `range_utils.py`, `semantic_matcher.py`, `text_parsing.py`, `clause_marker_normalize.py`
- 关键文件： `text_parsing.py`（`[[TABLE:<id>]]` 与 sidecar 恢复）、`protected_fields.py`、`inline_style_ops.py`、`clause_marker_normalize.py`

**`backend/util/word_util/`:**
- 职责： Word COM 技术工具层。
- 包含： COM app 生命周期、COM lock/retry、Word 常量、锚点工具、底层插入、文档检查、诊断、table models、symbol tokens（`word_symbol_tokens.py`）、抽取（`word_extraction_utils.py`，含特殊字形与 `extract_text_with_list_numbers` 自动编号恢复）。
- 关键文件： `word_application_util.py`, `word_com_manager.py`, `anchor_utils.py`, `table_models.py`, `word_diagnostics.py`, `word_symbol_tokens.py`, `word_extraction_utils.py`

**`backend/agents/generation/`:**
- 职责： `generation_mode=agent` 的正文生成智能体运行时。
- 包含： DeepAgents 主 agent、generate/verify/revise 子图、workspace、model factory、JSON 协议、`agent_step` emitter、结构化表占位符工具、内容净化、受保护字段守卫。
- 关键文件： `content_agents.py`, `generate_agent_graph.py`, `verify_agent_graph.py`, `revise_agent_graph.py`, `table_placeholder_utils.py`, `content_sanitizer.py`, `protected_field_guard.py`, `workspace.py`, `model_factory.py`

**`backend/agents/comments/`:**
- 职责： 批注 agent 运行时。
- 包含： LangChain agent、工具调用限制、引用校验、Word 写回工具、类型、审计 workspace。
- 关键文件： `comment_agent.py`, `tools.py`, `types.py`, `workspace.py`

**`backend/agents/task_context_assistant/`:**
- 职责： 右侧聊天 agent run 前置流。
- 包含： DeepAgents factory、rewrite 工具、只读摘要工具、scrub 审计日志。
- 关键文件： `factory.py`, `tools.py`（`create_rewrite_task_tool`）、`logging.py`（`scrub_sensitive_text`）

**`backend/prompts/`:**
- 职责： Prompt Layer，只负责 prompt 渲染和机器契约解析。
- 包含： generate、comment、rewrite target、skill、template candidate ranking prompt 和 prompt types。
- 关键文件： `generate_prompt.py`, `generate_by_template_prompt.py`, `generate_by_param_prompt.py`, `comment_prompt.py`, `skill_prompt.py`, `rewrite_target_selection_prompt.py`, `template_candidate_ranking_prompt.py`, `types.py`

**`backend/retrieval/`:**
- 职责： 批注 bad case 检索运行时，为 `generate_comments` 和 `comment_agent` 提供 prompt context。
- 包含： bad case loader、BM25、Qdrant HTTP store、embedding client、hybrid ranking、runtime cache。
- 关键文件： `comment_bad_case_runtime.py`, `bm25.py`, `qdrant_store.py`, `hybrid.py`, `embeddings.py`, `bad_case_loader.py`, `config.py`

**`backend/util/common_util/`:**
- 职责： 非 Word 的通用工具。
- 包含： 上传落盘、模板候选代理、招标详情代理、LLM stream、招标编号归一化。
- 关键文件： `upload_storage.py`, `template_candidates.py`, `fetch_tender_data.py`, `llm_stream_utils.py`, `tender_number.py`

**`backend/util/log_util/`:**
- 职责： 日志基础设施和任务/agent 审计辅助。
- 包含： progress log、execution log、SSE log handler、skill audit log、context log、daily handler、cleanup。
- 关键文件： `progress_log.py`, `execution_log.py`, `sse_log_handler.py`, `skill_audit_log.py`, `log_cleanup.py`

**`backend/skills/`:**
- 职责： task skill 声明和 runtime helper。
- 包含： `catalog.py`, `rewrite/SKILL.md`, `rewrite/scripts/runtime.py`
- 关键文件： `runtime.py`（`select_resolve_branch` / `select_comment_branch` / `estimate_total_nodes` / `has_source_document`）

**`backend/tests/`:**
- 职责： 后端 pytest 测试，按源码分层镜像归档。
- 包含： `api/`, `agents/`, `config/`, `graphs/`, `helper/`, `logging/`, `models/`, `nodes/`, `progress/`, `prompts/`, `retrieval/`, `services/`, `skills/`, `util/`
- 关键文件： `backend/tests/conftest.py`；新增测试必须以 `test_` 开头。

**`backend/scripts/`:**
- 职责： 运维/诊断脚本，不是 API 入口。
- 包含： `diagnose_word.py`, `index_comment_bad_cases.py`, `test_comment_hybrid_retrieval.py`
- 约束： 诊断脚本可检查 COM，但业务写回仍不得绕开任务队列/graph 锁。

## 关键文件位置

**Entry Points:**
- `backend/main.py`: FastAPI app、router 注册、CORS、startup/shutdown、健康检查、全局异常处理。
- `backend/api/generate.py`: `POST /api/generate`
- `backend/api/agent.py`: `POST /api/agent/runs/stream`
- `backend/api/comment_supplement.py`: `POST /api/comment-supplement`
- `backend/api/stream.py`: `GET /api/stream/{task_id}`
- `backend/api/tasks.py`: 任务列表、详情、取消、心跳

**配置：**
- `backend/config/settings.py`
- `backend/config/tender_config.py`
- `backend/requirements.txt`
- `backend/.env`：本地私有配置存在；不得读取内容

**Core Logic:**
- `backend/services/document_service.py`
- `backend/task/task_queue_manager.py`
- `backend/graphs/base_graph.py`
- `backend/graphs/skill_graph.py`
- `backend/core/sse_manager.py`
- `backend/services/agent_run_service.py`
- `backend/services/conversation_service.py`

**Word Logic:**
- `backend/nodes/common_word_nodes/update_word.py`
- `backend/nodes/common_word_nodes/delete_tender_param.py`
- `backend/nodes/common_word_nodes/replace_content.py`
- `backend/nodes/gngk_word_nodes/gngk_hw_cz_update_word.py`
- `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`
- `backend/nodes/gjgk_word_nodes/gjgk_update_word.py`
- `backend/helper/word_helper/`
- `backend/util/word_util/word_application_util.py`
- `backend/util/word_util/word_com_manager.py`

**Agent and Prompt:**
- `backend/agents/generation/`
- `backend/agents/comments/`
- `backend/agents/task_context_assistant/`
- `backend/prompts/`

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
- 跨包导入使用 `backend.*` 绝对路径。

**标识符：**
- API form type：`*_tender`（如 `gngk_hw_zc_tender`）。
- Graph runtime `tender_type`：去掉 `_tender`（如 `gngk_hw_zc`）。
- 任务类别：`generate` / `rewrite` / `comment_supplement`。
- 上传 rewrite 来源标记：`rewrite_source="uploaded_file"`。

## 新代码落位（Where do I put new code?）

### 新 API Endpoint
| 落点 | 路径 |
|------|------|
| Router | `backend/api/<feature>.py` |
| Models | `backend/models/<feature>.py` 或现有模型文件 |
| Service | `backend/services/<feature>_service.py` |
| 注册 | `backend/main.py` → `include_router(..., prefix="/api")` |
| Tests | `backend/tests/api/test_<feature>_api.py`, `backend/tests/services/` |

### 新 Generate 请求字段
| 落点 | 路径 |
|------|------|
| Model | `backend/models/generate.py` |
| Initial state | `backend/services/document_service.py` → `_build_initial_state` |
| Graph/node 消费 | `backend/graphs/` 或 `backend/nodes/` / `backend/states/base_state.py` |
| 用户可见契约 | `backend/models/sse.py` / `backend/models/task.py`（如需要） |
| Tests | `backend/tests/models/`, `api/`, `services/`, `graphs/` |

**约束：** 若字段仅服务初次生成，标注为 generate-only，**不要**写入 rewrite request 或 `TaskSkillGraphState`。

### 新招标类型
| 落点 | 路径 |
|------|------|
| `FormType` | `backend/models/generate.py` |
| 锚点/保护字段配置 | `backend/config/tender_config.py` |
| State | `backend/states/`（可复用 family state） |
| Graph | `backend/graphs/<runtime_type>_tender_graph.py` |
| 差异节点 | `backend/nodes/<family>_word_nodes/` |
| Registry | `backend/services/document_service.py` → `GRAPH_REGISTRY` |
| rewrite dispatch（如有 Word 差异） | `backend/nodes/skills_nodes/tender_aware_word_dispatch.py` |
| Tests | `backend/tests/config/`, `graphs/`, `nodes/` |

**约束：** 优先「共享主干 + 局部特化」；仅流程明显不同时才新 graph。`gngk` UI 分派逻辑在前端共享 helper，后端只收具体 form type。

### 新 Word 业务 Helper
| 落点 | 路径 |
|------|------|
| 实现 | `backend/helper/word_helper/<topic>.py` |
| 节点调用 | `backend/nodes/common_word_nodes/` 或类型节点 |
| Tests | `backend/tests/helper/test_<topic>.py` |

### 新 Word COM 技术 Helper
| 落点 | 路径 |
|------|------|
| 实现 | `backend/util/word_util/<topic>.py` |
| 诊断 | `backend/scripts/diagnose_word.py`（可选） |
| Tests | `backend/tests/util/`（纯逻辑）；COM 闭环需 Windows + Word/WPS |

**红线：** 不得在 API/service/脚本中直接写业务 COM 写回；必须经 task queue + graph 节点。

### 新 Graph 节点
| 落点 | 路径 |
|------|------|
| 共享节点 | `backend/nodes/common_word_nodes/<node>.py` |
| 类型专属 | `backend/nodes/<family>_word_nodes/<runtime_type>_<operation>.py` |
| 挂到主干 | 类型 graph 的 `NODE_*` 或 `get_word_operation_steps()` / `get_post_update_steps()` |
| 进度可见 | `backend/task/task_queue_manager.py` 的 `NodeName` / `NODE_DISPLAY_NAMES` |
| Tests | `backend/tests/nodes/`, `backend/tests/graphs/` |

### 新 Task Skill
| 落点 | 路径 |
|------|------|
| 声明 | `backend/skills/<skill_id>/SKILL.md` |
| Runtime helper | `backend/skills/<skill_id>/scripts/runtime.py` |
| Nodes | `backend/nodes/skills_nodes/<skill_id>_nodes.py` |
| Graph | 新增显式 graph 类（参考 `RewriteSkillGraph`） |
| Service 入口 | `backend/services/document_service.py` |
| `TaskKind` | `backend/task/task_queue_manager.py` + `backend/models/task.py` |
| Tests | `backend/tests/skills/`, `graphs/`, `nodes/`, `services/` |

**约束：** 不要恢复 `SkillGraph.for_skill + TaskSkillWorkflow`；不要恢复 `/api/edit` 或独立 edit skill。上传文件修改继续复用 rewrite + `rewrite_source="uploaded_file"`。

### 新 Agent 能力
| 落点 | 路径 |
|------|------|
| 正文 agent | `backend/agents/generation/` |
| 批注 agent | `backend/agents/comments/` |
| 任务上下文助手工具 | `backend/agents/task_context_assistant/tools.py` |
| 共享 model factory | `backend/agents/generation/model_factory.py` |
| Prompt | `backend/prompts/` |
| Graph 节点接入 | `backend/nodes/common_word_nodes/` |
| Tests | `backend/tests/agents/`, `nodes/`, `prompts/` |

### 新 Prompt
| 落点 | 路径 |
|------|------|
| Builder | `backend/prompts/<topic>_prompt.py` |
| 类型/契约 | `backend/prompts/types.py` |
| 调用方 | node / agent / service（不在 prompt 层做副作用） |
| Tests | `backend/tests/prompts/` |

### 新 Retrieval / Bad case
| 落点 | 路径 |
|------|------|
| Runtime | `backend/retrieval/` |
| 源数据 | `backend/retrieval/bad_cases/` |
| 索引脚本 | `backend/scripts/index_comment_bad_cases.py` |
| 接入点 | `generate_comments` / `comment_agent` / `comment_supplement` |
| Tests | `backend/tests/retrieval/` |

### 新日志/审计
| 落点 | 路径 |
|------|------|
| 通用日志工具 | `backend/util/log_util/` |
| Agent scrub 审计 | `backend/agents/task_context_assistant/logging.py` |
| Skill audit | `backend/util/log_util/skill_audit_log.py` |
| 文件名清洗 | `backend/agents/log_naming.py` |

## 放置决策速查

| 我想改的是… | 先看 |
|-------------|------|
| HTTP 契约 | `backend/api/` + `backend/models/` |
| 任务排队/取消/进度 | `backend/task/task_queue_manager.py` |
| SSE 事件 | `backend/core/sse_manager.py` + `backend/models/sse.py` |
| 初次生成主干 | `backend/graphs/base_graph.py` → `StandardTenderWorkflowGraph` |
| 类型差异 Word 步骤 | 对应 `*_tender_graph.py` + `nodes/*_word_nodes/` |
| rewrite 流程 | `backend/graphs/skill_graph.py` + `skills/rewrite/` + `nodes/skills_nodes/` |
| 补充批注 | `backend/graphs/comment_supplement_graph.py` + `nodes/common_word_nodes/comment_supplement.py` |
| 正文 LLM/agent | `backend/prompts/` + `agents/generation/` + `nodes/.../generate_polished_text.py` / `content_agent_generate.py` |
| 批注 LLM/agent | `backend/prompts/comment_prompt.py` + `agents/comments/` + `nodes/.../generate_comments.py` / `comment_agent.py` |
| Word 写回业务规则 | `backend/helper/word_helper/` |
| Word COM 生命周期 | `backend/util/word_util/` |
| 招标锚点/保护字段 | `backend/config/tender_config.py` |
| Agent run 前置流 | `backend/services/agent_run_service.py` + `agents/task_context_assistant/` |

## 禁止落位

- 不要在 `backend/api/` 写 Word COM 或 LangGraph 长流程。
- 不要在 `backend/services/` 直接 `Dispatch` Word。
- 不要把 Word 业务规则塞进 `backend/util/word_util/`（技术层）或把 COM 生命周期塞进 `helper/word_helper/`（业务层）。
- 不要把 prompt 渲染副作用（SSE、COM、会话状态）放进 `backend/prompts/`。
- 不要把 generate-only 字段塞进 rewrite skill state。
- 不要在 `backend/logs/`、`backend/context_log/` 下新增业务源码。

---

*后端结构分析：2026-07-18*
