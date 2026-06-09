# 后端编码约定

**分析日期：** 2026-06-09

**范围：** `backend/` 源码、`backend/tests/`、`backend/requirements.txt`、`backend/.env.example`、`docs/backend.md`、`docs/interfaces-runtime.md`、`docs/knowledge-validation.md`、既有 `backend/.planning/codebase/` 事实文档和项目内 `.agents/skills/gsd-map-codebase/SKILL.md`。`backend/.env` 文件存在，但不得读取或引用内容。

**关键事实来源：**
- 应用入口与 API：`backend/main.py`、`backend/api/generate.py`、`backend/api/agent.py`、`backend/api/tasks.py`、`backend/api/template_candidates.py`、`backend/api/comment_supplement.py`
- 请求、任务与状态模型：`backend/models/generate.py`、`backend/models/agent_run.py`、`backend/models/task.py`、`backend/states/base_state.py`、`backend/states/skill_state.py`
- 任务与 Graph 编排：`backend/services/document_service.py`、`backend/services/agent_run_service.py`、`backend/graphs/base_graph.py`、`backend/graphs/skill_graph.py`、`backend/graphs/task_skill_workflows.py`
- rewrite 与 Word 写回：`backend/nodes/skills_nodes/rewrite_nodes.py`、`backend/nodes/skills_nodes/tender_aware_word_dispatch.py`、`backend/nodes/common_word_nodes/update_word.py`、`backend/helper/word_helper/`、`backend/util/word_util/`
- 日志与审计：`backend/util/log_util/progress_log.py`、`backend/util/log_util/skill_audit_log.py`、`backend/agents/task_context_assistant/logging.py`

## 命名模式

**文件：**
- Python 源文件使用 `snake_case.py`，例如 `backend/services/document_service.py`、`backend/core/sse_manager.py`、`backend/helper/word_helper/inline_style_ops.py`。
- API、model、service、graph、state、node、helper、util 按职责目录放置；新增后端能力优先落入 `backend/api/`、`backend/models/`、`backend/services/`、`backend/graphs/`、`backend/nodes/`、`backend/helper/word_helper/` 或 `backend/util/` 的既有边界。
- 招标类型 graph 使用 `<form_type>_tender_graph.py`，例如 `backend/graphs/gngk_hw_cz_tender_graph.py`。
- 类型专属 Word 节点使用 `<runtime_type>_<operation>.py`，例如 `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`。
- task skill 声明放在 `backend/skills/<skill_id>/SKILL.md`，运行时 helper 放在 `backend/skills/<skill_id>/scripts/`，workflow 注册在 `backend/graphs/task_skill_workflows.py`。
- 测试文件使用 `test_*.py`，并放在 `backend/tests/<scope>/`，例如 `backend/tests/api/test_agent_run_api.py`、`backend/tests/nodes/test_rewrite_nodes.py`。

**函数：**
- 函数、局部 helper 和测试函数使用 `snake_case`，例如 `create_generate_task()`、`create_rewrite_task()`、`resolve_rewrite_target()`、`test_generate_request_defaults_generation_mode_to_workflow()`。
- FastAPI endpoint 以资源动作命名，例如 `create_generate_task()`、`stream_agent_run()`、`select_template_candidate()`。
- 单例 getter 使用 `get_*()`，例如 `get_document_service()`、`get_agent_run_service()`、`get_task_service()`。
- Graph 节点函数使用节点名或业务动作名，例如 `generate_comments()`、`rewrite_text()`、`dispatch_tender_aware_update_word()`。

**变量：**
- 参数、局部变量、state key 和 JSON key 使用 `snake_case`。
- 模块级常量使用 `UPPER_SNAKE_CASE`，例如 `TASK_KIND_TO_LLM_NODE`、`TRACKED_PROGRESS_NODES`、`UPLOADED_REWRITE_SOURCE`。
- 协议字符串保持稳定原文，例如 `xjcg_tender`、`gngk_hw_cz_tender`、`agent_step`、`uploaded_file`、`comment_supplement`。

**类型：**
- Pydantic model、Graph class、service class 使用 PascalCase，例如 `GenerateRequest`、`AgentRunStreamRequest`、`StandardTenderWorkflowGraph`、`DocumentService`。
- Enum class 使用 PascalCase，成员使用 `UPPER_SNAKE_CASE`，值使用跨端协议字符串；参考 `backend/models/generate.py` 和 `backend/models/task.py`。
- LangGraph state 类型放在 `backend/states/`，节点之间通过 TypedDict state key 传递，不用临时 dict key 扩散跨节点契约。

## 代码风格

**格式化：**
- 未检测到后端专用 `pyproject.toml`、`pytest.ini`、`setup.cfg`、`ruff.toml`、`.flake8`、`mypy.ini`。
- 使用 4 空格缩进、类型注解、Pydantic v2、FastAPI response model 和局部 helper。
- 说明性注释、日志和用户可见文本多为中文；代码标识符、路径、协议值和配置键保持英文。
- 修改已有文件时匹配同文件风格；不要为了统一格式重排无关 import、注释、空行或 docstring。

**代码检查：**
- 未检测到自动 lint 配置；文档型改动至少运行 `git diff --check`。
- 后端代码改动以 `python -m pytest tests -v` 或更窄的相关 pytest 作为主要质量门禁。

## 导入组织

**顺序：**
1. `from __future__ import annotations`，若文件已有该模式，放在首个普通 import 前。
2. 标准库 imports，例如 `json`、`logging`、`pathlib`、`typing`。
3. 第三方 imports，例如 `fastapi`、`pydantic`、`langgraph`、`requests`、`deepagents`。
4. `backend.*` 绝对导入。
5. `TYPE_CHECKING` 下的类型导入或函数内延迟导入，用于避免循环依赖。

**路径别名：**
- 新后端代码使用 `backend.*` 包绝对导入，例如 `from backend.models import GenerateRequest`、`from backend.services.document_service import get_document_service`。
- 不新增 `from services...`、`from models...`、`from util...` 这类脱离包根的短导入。
- `backend/main.py` 和 `backend/tests/conftest.py` 会把项目根加入 `sys.path`，用于支持 `backend.*` 导入解析。

## 后端分层与落位规则

**API 层：**
- 位置：`backend/api/`
- 用法：只做 HTTP/SSE/NDJSON 入口、请求模型绑定、HTTP 错误封装和 service 调用。
- 新 endpoint 要引用 `backend/models/` 中的请求/响应模型，并通过 `backend/services/` 或 `backend/util/common_util/` 执行业务，不直接操作 LangGraph、任务队列或 Word COM。

**模型层：**
- 位置：`backend/models/`
- 用法：保存 API shape、任务状态、SSE 事件、agent run、生成模式、招标类型和模板候选契约。
- 跨前端字段变化必须同步前端类型/API client 和测试；相关跨端规则见 `docs/interfaces-runtime.md`。

**Service 层：**
- 位置：`backend/services/`
- 用法：编排 API 与 graph、task queue、SSE、agent、conversation、外部 ranking 之间的交互。
- 新后台任务入口应复用 `DocumentService`、`TaskQueueManager`、`SSEManager` 和既有 result payload 收敛方式。

**Graph/State/Node 层：**
- 位置：`backend/graphs/`、`backend/states/`、`backend/nodes/`
- 用法：LangGraph 负责长任务流程；state 定义跨节点字段；node 执行具体 Word、LLM、rewrite、comment 逻辑。
- 新节点必须通过 `BaseGraph.wrap_node()` 或 `SkillGraph` workflow 元数据接入进度与取消检查。

**Word helper 层：**
- 位置：`backend/helper/word_helper/`
- 用法：放跨节点复用的 Word 业务 helper，例如受保护字段、段落边界、样式回填、删除和 cleanup。
- 底层 COM 生命周期、COM lock、常量、诊断和底层文件读取留在 `backend/util/word_util/`。

**Prompt/Agent/Retrieval 层：**
- 位置：`backend/prompts/`、`backend/agents/`、`backend/retrieval/`
- 用法：Prompt Layer 只做 prompt 渲染和机器契约解析；agent runtime 负责 DeepAgents/LangChain 调用；retrieval 只为批注 bad case context 服务。
- 日志、副作用、SSE、Word COM 和会话状态不要放入 prompt builder。

## 请求与任务模型

- 请求模型优先使用 Pydantic model，并把输入归一化放在 validator 中；参考 `GenerateFilePaths`、`AgentRunStreamRequest`、`AgentRunRewriteContextSnapshot`。
- 需要禁止额外字段的边界模型使用 `model_config = ConfigDict(extra="forbid")`；参考 `backend/models/agent_run.py` 和 `backend/models/generate.py` 中的 `GenerateFilePaths`。
- `TaskKind` 的协议值只包含 `generate`、`rewrite`、`comment_supplement`，定义在 `backend/models/task.py`，任务创建时由 `backend/services/document_service.py` 传入 `TaskQueueManager`。
- `GenerateRequest.file_paths` 只接受 `template` 和 `tender_params`，对应测试在 `backend/tests/services/test_document_service_initial_state.py`。
- `AgentRunStreamRequest` 是 `POST /api/agent/runs/stream` 的 NDJSON 请求模型，`selected_skills` 会去重，上传文件 rewrite 上下文在 `AgentRunRewriteContextSnapshot` 中收口。

## Generate 与 Rewrite 字段边界

- `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 是 generate-only 字段，只在 `GenerateRequest`、`TenderGraphStateBase` 和 `DocumentService._build_initial_state()` 中进入初次生成 state。
- rewrite 请求、`TaskSkillGraphState`、`backend/skills/rewrite/SKILL.md` 和 rewrite prompt surface 不接收上述 generate-only 字段。
- 上传文件 rewrite 由 `DocumentService._build_uploaded_rewrite_initial_state()` 写入 `rewrite_source="uploaded_file"`，并由 `resolve_rewrite_target()` 复制工作副本、开启 `verbose_style_progress_logs` 和 `suppress_comment_progress_logs`。
- 会话 rewrite 由 `DocumentService._build_skill_graph_initial_state()` 使用 conversation rewrite history；上传文件 rewrite 使用 `source_document_path`、`form_type`、`insertion_config`、`tender_lx`、`fund_source_lx` 和可选 `tender_data_snapshot`。
- 保护该边界的测试位于 `backend/tests/services/test_document_service_initial_state.py`、`backend/tests/nodes/test_uploaded_rewrite_inline_style_context.py`、`backend/tests/agents/test_task_context_assistant_tools.py`。

## 错误处理

**模式：**
- API 层使用 `HTTPException`，`detail` 保持结构化字段：`success`、`error.code`、`error.message`、可选 `details` 和 `timestamp`；参考 `backend/api/tasks.py`、`backend/api/template_candidates.py`、`backend/api/download.py`。
- Pydantic validator 抛出 `ValueError`，由 FastAPI/Pydantic 负责请求错误响应；参考 `backend/models/generate.py` 和 `backend/models/agent_run.py`。
- Service 层返回 `GenerateResponse` / `TaskResponse` 等模型，或在后台任务中把失败收敛为任务失败状态、SSE `error` 和进度日志；参考 `backend/services/document_service.py`。
- Graph 节点用 fail-fast 保护 Word 写入边界；受保护字段缺失、锚点缺失、非法字段区间、空 rewrite 正文等应抛出明确异常。
- Retrieval/embedding/Qdrant 失败降级为 `bm25_only` 并记录 warning，不阻塞批注生成；参考 `backend/retrieval/comment_bad_case_runtime.py`。

## 日志

**框架：** stdlib `logging` + 自有日志工具。`structlog` 声明在 `backend/requirements.txt`，主要运行路径使用 stdlib logging。

**模式：**
- 应用启动在 `backend/main.py` 配置 JSON stdout logging，并启动 progress/execution log listener。
- 用户可见进度走 `backend/util/log_util/progress_log.py`，通过 `QueueHandler` / `QueueListener` 和 `DailyFileHandler` 写入 `backend/logs/`。
- rewrite task audit 写入 `backend/util/log_util/skill_audit_log.py` 支持的 stage：`skill_directory_route`、`skill_prompt_render`、`rewrite_target_selection`、`rewrite_text`。
- Agent run 审计只写白名单字段并 scrub 敏感内容；实现和测试在 `backend/agents/task_context_assistant/logging.py`、`backend/tests/agents/test_task_context_assistant_logging.py`。
- 不把完整客户原文、真实密钥、私有路径、traceback、下载路径写入日志、文档或测试夹具。

## Word Helper 与 COM 约束

- Word COM 写入只能经过后端任务队列、LangGraph、graph 锁、取消检查和进度包装；不得在 API route、service、前端或随意脚本中直接操作 COM。
- `backend/graphs/base_graph.py` 提供 `CrossProcessFileLock`、`wrap_node_with_progress()`、取消检查和 async 执行包装；新增 graph 或 skill workflow 必须复用这些机制。
- `backend/util/word_util/word_application_util.py` 负责 `create_word_application()`、COM 初始化、重试和 `close_word_application()`；节点内打开 Word 后必须在 `finally` 中关闭。
- 可脱离 COM 的段落、范围、样式、受保护字段、语义匹配和删除逻辑放到 `backend/helper/word_helper/` 并通过 fake objects 测试。
- 完整 Word 生成验收必须回到 Windows Python、`pywin32` 和本机 Word/WPS COM 环境；诊断入口是 `backend/scripts/diagnose_word.py`。

## 注释

**注释时机：**
- 复杂跨线程、Word COM、Graph 分支、任务取消、安全边界、字段协议和 prompt 机器契约可以保留简短中文注释。
- 不为自解释赋值、简单 wrapper 或显然字段映射添加重复注释。
- 修改代码时只补与本次改动直接相关的说明，不重写旧注释和周边叙述。

**Docstring：**
- Python docstring 用于 API、service、graph、helper 的职责说明；示例见 `backend/main.py`、`backend/services/task_service.py`、`backend/graphs/base_graph.py`。

## 函数设计

**规模：**
- API endpoint 保持薄入口；复杂编排下沉到 `backend/services/`、`backend/graphs/`、`backend/nodes/` 或 `backend/helper/word_helper/`。
- 多个招标类型复用的 Word 业务逻辑放在 `backend/helper/word_helper/`；底层 COM 技术逻辑放在 `backend/util/word_util/`。
- 招标类型差异优先通过 `backend/config/tender_config.py`、Graph class attribute 或 tender-aware dispatch 表达；不要复制整个标准 graph。

**参数：**
- API/request 参数使用 Pydantic model，例如 `GenerateRequest`、`AgentRunStreamRequest`、`CommentSupplementRequest`。
- Graph 节点遵循 `(state, config=None)` 或 LangGraph 可调用约定。
- Service 对外方法使用模型或显式关键字参数，例如 `DocumentService.create_task(request)`、`DocumentService.create_rewrite_task(...)`。

**返回值：**
- API 返回 Pydantic response model，例如 `GenerateResponse`、`TaskResponse`、`TemplateSelectResponse`。
- Graph 节点返回 state patch dict 或 state 类型实例，例如 `TaskSkillGraphState(...)`。
- Agent run stream 返回 NDJSON 行，序列化逻辑放在 service 层。
- Helper 返回结构化 dict、dataclass、model 或明确状态，不用多义字符串跨层传递。

## 模块设计

**导出：**
- 包级 `__init__.py` 用于稳定 re-export，例如 `backend/models/__init__.py`、`backend/graphs/__init__.py`、`backend/helper/word_helper/__init__.py`。
- 新增公开对象时同步相应 `__all__`，保持调用方导入路径稳定。

**Barrel 文件：**
- 使用 barrel 暴露稳定 API、Graph、Node、Agent runtime。
- 不把易变内部 helper 暴露为跨层公共 API；调用方优先使用已有 service、graph registry、workflow registry 或 helper facade。

## 安全与隐私规则

- `backend/config/settings.py` 从 `backend/.env` 加载环境变量；事实文档和测试只记录配置键和行为，不记录真实值。
- `backend/.env.example` 可作为示例配置来源；不要读取 `backend/.env`、`frontend/.env.local` 或任何真实密钥文件。
- 模板候选下载保留 `TEMPLATE_CANDIDATE_ALLOWED_HOSTS` 白名单，相关校验在 `backend/util/common_util/template_candidates.py` 和 `backend/api/template_candidates.py`。
- 下载接口保留 `settings.UPLOAD_DIR` containment check，相关逻辑在 `backend/api/download.py`。

---

*后端编码约定分析：2026-06-09*
