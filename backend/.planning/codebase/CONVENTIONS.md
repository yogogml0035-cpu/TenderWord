# 编码约定

**分析日期：** 2026-07-21

**范围：** `backend/` 源码与 `backend/tests/`。未读取 `backend/.env` 或任何密钥文件；配置键名仅来自 `backend/config/settings.py` 与公开代码引用。

**关键事实来源：**
- 入口与 API：`backend/main.py`、`backend/api/*.py`
- 模型与状态：`backend/models/`、`backend/states/`
- 编排：`backend/services/`、`backend/graphs/`、`backend/task/task_queue_manager.py`
- Word 与节点：`backend/nodes/`、`backend/helper/word_helper/`、`backend/util/word_util/`
- Prompt / Agent / 清洗：`backend/prompts/`、`backend/agents/`
- 日志 scrub：`backend/util/log_util/`、`backend/agents/task_context_assistant/logging.py`

## 命名模式

**文件：**
- Python 源文件使用 `snake_case.py`，例如 `document_service.py`、`sse_manager.py`、`inline_style_ops.py`、`annotate_corrections.py`、`comment_writeback.py`。
- 目录按职责划分：`api/`、`models/`、`services/`、`graphs/`、`states/`、`nodes/`、`helper/word_helper/`、`util/`、`agents/`、`prompts/`、`retrieval/`、`skills/`、`config/`、`core/`、`task/`。
- 招标类型 graph：`<form_type>_tender_graph.py`（如 `gngk_hw_cz_tender_graph.py`）。
- 类型专属 Word 节点：`<runtime_type>_<operation>.py`（如 `gngk_fw_zc_update_word.py`），放在 `nodes/gngk_word_nodes/`、`nodes/gjgk_word_nodes/`、`nodes/xjcg_word_nodes/`。
- 跨类型公共节点在 `nodes/common_word_nodes/`；rewrite 相关在 `nodes/skills_nodes/`。
- task skill 声明在 `skills/<skill_id>/SKILL.md`，运行时 helper 在 `skills/<skill_id>/scripts/`；rewrite 执行图为显式 `RewriteSkillGraph`（`graphs/skill_graph.py`），**不要**恢复 `SkillGraph.for_skill + TaskSkillWorkflow` 元数据驱动框架。
- 测试文件：`backend/tests/<scope>/test_*.py`。

**函数：**
- 函数与测试函数使用 `snake_case`：`create_generate_task()`、`create_rewrite_task()`、`annotate_corrections()`、`write_polished_comments()`、`comment_agent_writeback()`、`scrub_sensitive_text()`。
- FastAPI endpoint 以资源动作命名：`create_generate_task`、`stream_agent_run`、`get_tender_data`、`create_comment_supplement_task`。
- 单例 getter：`get_document_service()`、`get_agent_run_service()`、`get_task_service()`、`get_settings()`。
- Graph 节点函数使用业务动作名：`generate_comments`、`rewrite_text`、`dispatch_tender_aware_update_word`、`comment_agent_writeback`。

**变量与常量：**
- 参数、局部变量、state key、JSON key 使用 `snake_case`。
- 模块级常量 `UPPER_SNAKE_CASE`：`TASK_KIND_TO_LLM_NODE`、`TRACKED_PROGRESS_NODES`、`UPLOADED_REWRITE_SOURCE`、`REWRITE_NODE_NAMES`、`REWRITE_NODE_HANDLERS`、`TASK_AUDIT_STAGES`、`COMMENT_AGENT_NODE`。
- 协议字符串保持稳定原文：`xjcg_tender`、`gngk_hw_cz_tender`、`agent_step`、`uploaded_file`、`comment_supplement`、`[[TABLE:<id>]]`。

**类型：**
- Pydantic model、Graph class、Service class：PascalCase（`GenerateRequest`、`DocumentService`、`RewriteSkillGraph`、`ErrorResponse`）。
- Enum class PascalCase，成员 `UPPER_SNAKE_CASE`，**值**为跨端协议字符串：`FormType`、`LLMModel`、`GenerationStyle`、`GenerationMode`、`CommentGenerationMode`、`StyleWritebackMode`、`TaskStatus`、`TaskKind`。
- LangGraph state 放在 `backend/states/`，使用 `TypedDict`（`total=False` 可选字段）；节点间只通过已声明 state key 传递契约。

## 代码风格

**格式化：**
- 未检测到后端专用 `pyproject.toml`、`pytest.ini`、`setup.cfg`、`ruff.toml`、`.flake8`、`mypy.ini`。
- 4 空格缩进；广泛使用 `from __future__ import annotations` 与原生类型注解。
- 说明性注释、进度文案、用户可见 message 多为中文；标识符、路径、协议值、配置键保持英文。
- 修改已有文件时匹配同文件风格；不为统一格式重排无关 import、空行或 docstring。

**质量门禁：**
- 无自动 lint 配置；文档型改动至少 `git diff --check`。
- 后端代码改动以 `python -m pytest tests -v`（在 `backend/` 下）或更窄路径为主要门禁。
- async 用例必须显式 `@pytest.mark.asyncio`。

## 导入组织

**推荐顺序：**
1. `from __future__ import annotations`（若使用）
2. 标准库
3. 第三方（`fastapi`、`pydantic`、`langgraph`、`langchain_*` 等）
4. `backend.*` 绝对导入
5. `TYPE_CHECKING` 或函数内延迟导入（避免循环依赖、重 COM 依赖）

**路径约定：**
- 新代码统一 `from backend.xxx import ...`。
- 不新增脱离包根的短导入（`from services...` / `from models...`）。
- `backend/main.py` 与 `backend/tests/conftest.py` 将项目根与 `backend/` 注入 `sys.path`，保证 `backend.*` 可解析。

## 后端分层与落位

**API（薄入口）— `backend/api/`**
- 只做 HTTP/SSE/NDJSON 绑定、校验、`HTTPException` 封装与 service 调用。
- **不**直接操作 LangGraph、任务队列或 Word COM。
- 示例：`create_comment_supplement_task()` 调用 `get_document_service().create_comment_supplement_task()`，失败时把 service 的 `error` 码写入 `HTTPException.detail`。

**模型 — `backend/models/`**
- API shape、任务状态、SSE、agent run、生成模式、招标类型、模板候选的真源。
- 跨前端字段变更必须同步前端类型/API client 与测试。

**Service（编排）— `backend/services/`**
- 连接 API 与 graph、task queue、SSE、agent、conversation、外部 ranking。
- 内部队列状态到公共 API 模型的转换集中在 `task_service.py`。
- 任务执行与取消结果收敛在 `document_service.py`（识别 `TaskCancelledException`，写进度日志，更新任务状态）。

**Graph / State / Node — `backend/graphs/`、`backend/states/`、`backend/nodes/`**
- LangGraph 承载长任务；新节点经 `BaseGraph.wrap_node()` / `wrap_node_with_progress()` 或 rewrite 的 `REWRITE_NODE_HANDLERS` 接入进度与取消检查。
- 子类实现 `build_graph()` 与 `get_state_class()`；可选覆写 `estimate_total_nodes()`。

**Word helper vs COM util**
- 可复用业务逻辑：`backend/helper/word_helper/`（段落边界、样式、删除、cleanup、受保护字段语义等）。
- COM 生命周期、锁、诊断、底层读写：`backend/util/word_util/`。

**Prompt / Agent / Retrieval**
- Prompt 只做渲染与机器契约解析（`backend/prompts/`），无副作用。
- Agent runtime：`backend/agents/`（generation content agent、comment agent、task context assistant）。
- Retrieval：`backend/retrieval/`，主要为批注 bad case context；失败应降级，不阻塞主流程。

## 请求与任务模型（Pydantic）

- API shape 真源在 `backend/models/`；route 不内联复杂 DTO。
- 通用 envelope：`ErrorResponse`（`success=False` + `error` dict + `timestamp`）、`SuccessResponse`（`success=True` + `message` + `timestamp`），见 `models/common.py`。
- 创建任务返回 `GenerateResponse` / 同类响应；查询/取消走 `models/task.py` 公共模型，不直接暴露 `task_queue_manager` 内部 dataclass。
- 边界模型优先 `model_config = ConfigDict(extra="forbid")`（如 `GenerateFilePaths`、`TenderParamFile`、`agent_run` 事件与快照模型）。
- 输入归一化放在 `field_validator` / `model_validator`；Pydantic 层抛 `ValueError`，由 FastAPI 转请求错误。
- `TaskKind` 协议值：`generate`、`rewrite`、`comment_supplement`。
- `TaskStatus` 公共值：`queued`、`running`、`completed`、`failed`、`cancelled`。
- `GenerateRequest.file_paths` 仅 `template` + `tender_params`；`tender_params` 兼容 `string[]` 与 `{file_path, original_name}`（`TenderParamItem`）。
- `AgentRunStreamRequest` 必填 `context_snapshot`（`extra="forbid"`）；`POST /api/agent/runs/stream` 返回 `application/x-ndjson`。
- Agent run 事件名：`run_started`、`thinking_stage`、`tool_call`、`task_accepted`、`needs_input`、`done`、`error`；新增须同步 model、service、审计白名单与前端。

## FormType 与 Graph 注册

- `FormType` 六值：`xjcg_tender`、`gngk_hw_zc_tender`、`gngk_hw_cz_tender`、`gngk_fw_zc_tender`、`gngk_fw_cz_tender`、`gjgk_tender`。
- `DocumentService` 内 `GRAPH_REGISTRY` 按 form type 字符串注册对应 graph class；`RewriteSkillGraph`、`CommentSupplementGraph` 独立挂载，不混入 `FormType` 键。
- 新增 form type 须同步 model、graph registry、prompt、helper 锚点、前端选项与测试。

## Generate 与 Rewrite 字段边界

- `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 为 **generate-only**，只进入 `GenerateRequest`、`TenderGraphStateBase` 与初次生成 initial state。
- rewrite 请求、`TaskSkillGraphState`、rewrite skill prompt surface **不得**接收上述字段。
- 上传文件 rewrite：`rewrite_source="uploaded_file"`（`UPLOADED_REWRITE_SOURCE`），由 `resolve_rewrite_target()` 等工作副本与进度/批注日志开关处理。
- 保护测试：`tests/services/test_document_service_initial_state.py`、`tests/nodes/test_uploaded_rewrite_inline_style_context.py` 等。

## Rewrite Skill Graph

- 显式类 `RewriteSkillGraph`（`graphs/skill_graph.py`），继承 `BaseGraph`。
- 节点序 `REWRITE_NODE_NAMES`：`resolve_rewrite_target` → `extract_rewrite_context` → `get_rewrite_comments` → `delete_section` → `rewrite_text` → `update_word`。
- 处理函数表 `REWRITE_NODE_HANDLERS`；每个节点经 `self.wrap_node(name, handler)` 注册。
- 条件分支：`select_resolve_branch` / `select_comment_branch`（`skills/rewrite/scripts/runtime.py`）；最终汇入 `update_word`。
- 上传 rewrite 进度节点须在 `TRACKED_PROGRESS_NODES` 中；见 `tests/progress/test_uploaded_rewrite_progress_tracking.py`。

## Content Agent 与表格占位符

- 统一清洗入口：`agents/generation/content_sanitizer.py::sanitize_generated_content()`——去 AI 客套/Markdown 外壳，**保留** `[[TABLE:<id>]]` 与技术符号。
- `[[TABLE:<id>]]` 是内部写回入口，不是用户可见最终正文；是否恢复真表由写回层 + `tender_param_table_models` sidecar 决定。
- 占位符工具真源：`table_placeholder_utils.py`；`table_id` 字符集与 `util/word_util/table_models.py` 对齐（`[A-Za-z0-9_-]+`）。
- Content agent 阶段 `draft → audit → revision → final`；审核 JSON 经 `json_utils`；受保护字段守卫 `protected_field_guard.sanitize_protected_field_findings()`。

## 批注与更正批注约定

- 批注 agent：`agents/comments/`（tools、workspace、runner）；节点写回 `nodes/common_word_nodes/comment_agent.py::comment_agent_writeback`。
- 更正批注：`nodes/common_word_nodes/annotate_corrections.py`——**仅接入初次 generate**；先规范化重要性标识（如 `△/*` → `▲/★`），再合并 LLM 更正批注；无技术参数时跳过 LLM。
- `comment_agent` **不得**生成「原技术参数为…现改为…」类差异批注；编号/项目符号/展示壳变化不得当作事实更正。
- 写回顺序：Word 写回 **先写更正批注再写普通 AI 批注**；`comment_generation_mode=off` / `suppress_ai_comment_writeback` 只跳过普通 AI 批注，**不**跳过更正批注。
- 批注写回：`nodes/common_word_nodes/comment_writeback.py::write_polished_comments`——RPC 重试、摘要 payload（`build_comment_writeback_summary_payload`）、表格/锚点匹配；`allow_existing_comments` 默认 `False`（标准写回跳过重叠锚点），`comment_agent` 经 `write_validated_comment_candidates_to_word` 显式 `True` 允许同锚点追加。
- 缺 Word 上下文时 `comment_agent_writeback` 降级为 warning（`missing_comment_agent_anchor_context`），不伪造成功写回。

## Word 抽取与替换约定

- 特殊字形：`util/word_util/word_extraction_utils.py` + `word_symbol_tokens.py`；已知 Symbol/Wingdings 映射为 Unicode，其余 `[[WORD_SYMBOL:<font>:<hex>]]` 可逆 token；`content_ops` 写回解码并恢复字体，失败 fail-fast。
- 自动编号：`extract_text_with_list_numbers` 从段落 `ListFormat` 取可见编号前缀，避免技术参数丢失 Word/WPS 自动编号。
- 字段替换：`replace_content.py` 中 `WORD_FIND_TEXT_MAX_LEN=256`；超长查找串跳过并写入 `replacement_log`；`replacement_fields` 记录字段名，分组/优先级冲突在 `get_replacements_core` 收敛。

## Prompt 与 LLM

- 初次生成：`prompts/generate_prompt.py::render_generate_prompt()` → `RenderedPrompt`。
- Skill prompt：`prompts/skill_prompt.py`。
- 流式调用：`util/common_util/llm_stream_utils.py::stream_llm_completion()`（`StreamCallbacks`、`ensure_llm_env()`、`HeartbeatMonitor`、`LLM_STREAM_TIMEOUT_SECONDS`）。
- Provider 真源：`MODEL_CONFIGS` 中 `deepseek` / `qwen` / `doubao`，与 `LLMModel` 对齐。
- 日志与审计只写 scrub 后摘要、配置键、节点名；不写完整客户原文、密钥值、traceback、私有路径。

## 错误处理

**API：**
- `HTTPException`，`detail` 结构化：`success: false`、`error`（稳定机器码如 `TASK_NOT_FOUND`、`COMMENT_SUPPLEMENT_NO_DOCUMENT`、`REQ_INVALID_PARAM`）、`message`、可选 `details` / `task_id`、`timestamp`。
- OpenAPI 优先引用 `ErrorResponse` 或端点局部错误模型。

**Service / Graph：**
- Service 返回响应模型或把失败收敛为任务 `failed`、SSE `error`、进度日志。
- Graph 节点对 Word 写入边界 fail-fast（受保护字段缺失、锚点缺失、空 rewrite 正文等）。
- 任务取消：`TaskCancelledException`（`graphs/base_graph.py`）；`document_service` 将其映射为取消态而非 fatal 失败。
- Retrieval/embedding/Qdrant 失败降级 `bm25_only` + warning。
- Agent run 预检失败 → `needs_input`（不创建任务）；运行时异常 → `error` 事件。
- LLM 超时：`LLMTimeoutError`；`ensure_llm_env()` 错误信息只含配置键名。
- 批注写回失败可 `progress_log.exception` 后降级继续完成任务（见 `comment_agent` 节点），不把批注失败一律升级为任务失败。

## 进度与取消检查

**真源：** `backend/graphs/base_graph.py`

- `TRACKED_PROGRESS_NODES`：纳入前端进度条的节点名集合（含 `prepare_template`、`content_agent`、`annotate_corrections`、`comment_agent`、rewrite 各节点、`update_word` 等）。
- `_check_cancellation(config)`：从 `config["configurable"]["task_id"]` 查 `get_task_queue().is_task_cancelled()`；若已取消则抛 `TaskCancelledException`。
- `_update_node_progress(node_name, config, completed)`：仅对 `TRACKED_PROGRESS_NODES` 内节点调用 `queue.update_progress`。
- `wrap_node_with_progress(node_func, node_name)`：
  - 执行前：`_check_cancellation` + 进度 `completed=False`
  - 执行节点
  - 执行后：`_check_cancellation` + 进度 `completed=True`
  - 同步与 async 节点均支持（`asyncio.iscoroutinefunction` 分支）。
- `BaseGraph.wrap_node(node_name, node_func)` 是子类注册节点的统一入口。
- `CrossProcessFileLock`：跨进程文件锁 + 同进程 `threading.Lock`，保证 Word COM 互斥；超时抛 `RuntimeError`。
- `invoke_with_timing` / `invoke_with_timing_async`：带锁、计时与等待期取消检查。

**进度日志：**
- `util/log_util/progress_log.py`：`QueueHandler` + `QueueListener` 线程安全；写入 `logs/progress-YYYYMMDD.log`。
- 节点内业务进度文案多用 `progress_log.info(f"[{NODE_NAME}] ...")`。
- state 开关：`verbose_style_progress_logs`、`suppress_comment_progress_logs`（`states/base_state.py`）。

## 异步模式

- FastAPI 路由普遍为 `async def`；后台 Word 任务在队列工作线程中跑 graph，经 `BaseGraph` 包装取消与进度。
- SSE：`core/sse_manager.py` 使用 `asyncio.Lock` / `asyncio.Queue`；`bind_loop()` 绑定主事件循环；跨线程推送用 `asyncio.run_coroutine_threadsafe` / `*_threadsafe` 方法。
- 节点内若需在同步上下文调用 async LLM（如 `annotate_corrections._run_annotation_llm`），本地 `asyncio.new_event_loop()` 驱动；rewrite 节点亦有 `get_event_loop` / `new_event_loop` 模式。
- 异步测试必须显式 `@pytest.mark.asyncio`（无全局 `asyncio_mode`）。

## 日志与审计 scrub

**框架：** stdlib `logging` + 自有工具；`main.py::JSONFormatter` 输出 JSON stdout。无 `structlog`。

**通道：**
- 进度：`util/log_util/progress_log.py` → `logs/progress-YYYYMMDD.log`（`settings.LOG_DIR`）。
- 执行：`util/log_util/execution_log.py`。
- Task skill 审计：`util/log_util/skill_audit_log.py` → `context_log/rewrite_log/<prefix>_<timestamp>_<audit_id>.json`（原子写）；白名单 stage `TASK_AUDIT_STAGES`：`skill_directory_route`、`skill_prompt_render`、`rewrite_target_selection`、`rewrite_text`；路径键 `task_audit_log_path`（兼容 `rewrite_log_path`）。
- Agent run 审计：`agents/task_context_assistant/logging.py::AgentRunAuditLogger` → `logs/agent-run-<run_id>.jsonl`。
- 文件名片段经 `_sanitize_filename_part` / `sanitize_agent_log_part` 清洗。

**`scrub_sensitive_text()`（`agents/task_context_assistant/logging.py`）：**
- Traceback 整体 → `[REDACTED_STACK]`
- 多行只保留首行再 scrub
- `Bearer ...` 与 `authorization|api_key|access_token|refresh_token|password|passwd|secret := 值` → `[REDACTED_SECRET]`
- Windows/Unix 敏感绝对路径、`.env` → `[REDACTED_PATH]`
- **禁止记录：** 完整客户原文、真实密钥/token、私有路径、traceback、下载路径、`.env` 内容

Agent run 摘要与 tool 返回经 scrub；见 `agents/task_context_assistant/tools.py`。

## SSE 与 LLM 快照

- 事件类型（`models/sse.py::SSEEventType`）：`log`、`llm`、`progress`、`node_start`、`node_complete`、`agent_step`、`done`、`error`、`heartbeat`。
- LLM 经 `_LLMSnapshotRelay` 以 **全文快照**（`content_mode="snapshot"`）推送，按间隔节流；`node` 来自 `TASK_KIND_TO_LLM_NODE`（generate → `generate_polished_text`，rewrite → `rewrite_text`，comment_supplement → `comment_agent`）。
- `agent_step` 可带 `content_agent` / `comment_agent` 结构化过程；阶段字段变更须同步 model、node、service、前端。

## Word COM 红线

- COM 写入 **仅** 经任务队列 + LangGraph + graph 锁 + 取消检查 + 进度包装。
- **禁止**在 API route、service、前端或随意脚本中直接操作 COM。
- `util/word_util/word_application_util.py`：`create_word_application` / `close_word_application`；节点内 `finally` 关闭。
- 可脱离 COM 的逻辑放 helper 并用 fake 对象测。
- 完整生成验收：Windows Python + `pywin32` + 本机 Word/WPS；诊断 `scripts/diagnose_word.py`。
- `pywin32` 在 `requirements.txt` 中为 `platform_system == "Windows"` 条件依赖。

## 函数与模块设计

- API 保持薄；编排下沉 service/graph/node/helper。
- Graph 节点签名遵循 `(state, config=None)` 或 LangGraph 可调用约定；返回 state patch dict。
- 包级 `__init__.py` 稳定 re-export 与 `__all__`；不把易变内部 helper 升为跨层公共 API。

## 安全与隐私

- Settings：`pydantic-settings` BaseSettings，从 `backend/.env` 加载；文档/测试只记键名。
- 关键键族：`DEBUG`、`LLM_STREAM_TIMEOUT_SECONDS`、`UPLOAD_DIR`、`TEMPLATE_CANDIDATE_ALLOWED_HOSTS`、`LOG_DIR`、`LOG_QUEUE_MAXSIZE`、`PROGRESS_LOG_BACKUP_COUNT`、`EXTERNAL_REQUEST_TIMEOUT_SECONDS`、`LOCK_FILE_PATH`、`LOCK_TIMEOUT`、`TASK_TOTAL_NODES`，以及 `ARK_*` / `DASHSCOPE_*` / `DEEPSEEK_*`（经 `settings.get_llm_config(provider)`）。
- 模板候选主机白名单；下载接口 `UPLOAD_DIR` 路径 containment（`api/download.py`）。
- 外部招标数据：`EXTERNAL_REQUEST_TIMEOUT_SECONDS`；采购方式越界返回非阻断 `warning`，不抛异常。

## 注释

- 复杂 COM、跨线程、取消、安全边界、prompt 机器契约可保留简短中文注释。
- 不为自解释代码堆叠重复注释；改动时只补与本次相关的说明。

---

*后端编码约定分析：2026-07-21*
