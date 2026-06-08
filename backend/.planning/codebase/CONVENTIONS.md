# 后端编码约定

**分析日期：** 2026-06-08

**范围：** `backend/` 源码、`backend/tests/`、`backend/requirements.txt`、`docs/backend.md`、`docs/interfaces-runtime.md`、根级 `AGENTS.md` 和项目内 `.agents/skills/gsd-map-codebase/SKILL.md`。

**关键事实来源：**
- 后端入口与路由：`backend/main.py`、`backend/api/generate.py`、`backend/api/tasks.py`、`backend/api/agent.py`、`backend/api/template_candidates.py`、`backend/api/download.py`
- 模型与配置：`backend/models/generate.py`、`backend/models/task.py`、`backend/models/agent_run.py`、`backend/config/settings.py`、`backend/config/tender_config.py`
- 任务、Graph、节点：`backend/services/document_service.py`、`backend/services/task_service.py`、`backend/services/agent_run_service.py`、`backend/graphs/base_graph.py`、`backend/graphs/skill_graph.py`、`backend/graphs/task_skill_workflows.py`、`backend/nodes/skills_nodes/rewrite_nodes.py`
- Word helper 与日志：`backend/helper/word_helper/protected_fields.py`、`backend/helper/word_helper/content_ops.py`、`backend/util/log_util/progress_log.py`、`backend/util/log_util/execution_log.py`、`backend/util/log_util/skill_audit_log.py`、`backend/agents/task_context_assistant/logging.py`

## 命名模式

**文件：**
- 后端 Python 文件使用 `snake_case.py`，例如 `backend/services/document_service.py`、`backend/core/sse_manager.py`、`backend/helper/word_helper/protected_fields.py`。
- API、service、graph、node、helper、util 按职责目录放置；不要为单个功能新增平行目录结构。现有边界在 `backend/api/`、`backend/services/`、`backend/graphs/`、`backend/nodes/`、`backend/helper/`、`backend/util/`。
- Graph 文件使用 `<runtime_type>_tender_graph.py`，例如 `backend/graphs/gngk_hw_cz_tender_graph.py`。
- 类型专属 Word 节点使用 `<runtime_type>_<operation>.py`，例如 `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`。
- task skill 指令放在 `backend/skills/<skill_id>/SKILL.md`，运行时注册逻辑在 `backend/skills/catalog.py` 和 `backend/graphs/task_skill_workflows.py`。
- 测试文件统一使用 `test_*.py`，位于 `backend/tests/<scope>/`，例如 `backend/tests/api/test_generate_api.py`。

**函数：**
- 函数使用 `snake_case`，例如 `create_generate_task()`、`get_task_skill_workflow()`、`dispatch_tender_aware_update_word()`。
- FastAPI endpoint 函数以资源动作命名，例如 `create_generate_task()`、`create_comment_supplement_task()`、`download_file()`。
- 单例 getter 使用 `get_*()`，例如 `get_document_service()`、`get_task_queue()`、`get_agent_run_service()`。
- Graph 节点函数使用节点名或业务动作名，例如 `content_agent_generate()`、`generate_comments()`、`rewrite_text()`。

**变量：**
- 局部变量、参数和 dict key 使用 `snake_case`。
- 模块常量使用 `UPPER_SNAKE_CASE`，例如 `REWRITE_SKILL_ID`、`TASK_KIND_TO_LLM_NODE`、`DEFAULT_DEEPSEEK_MODEL`。
- 协议字符串保持后端契约值，例如 `gngk_hw_cz_tender`、`agent_step`、`uploaded_file`、`comment_supplement`。

**类型：**
- 类、Pydantic model、Graph class 使用 PascalCase，例如 `GenerateRequest`、`AgentRunStreamRequest`、`StandardTenderWorkflowGraph`、`SkillGraph`。
- Enum class 使用 PascalCase，成员使用 `UPPER_SNAKE_CASE`，值使用稳定协议字符串；参考 `backend/models/generate.py` 和 `backend/models/task.py`。
- Graph state 类型放在 `backend/states/`；不要在节点之间靠隐式 dict key 扩散新状态。

## 代码风格

**格式化：**
- 未检测到后端专用 `pyproject.toml`、`pytest.ini`、`setup.cfg`、`ruff.toml`、`.flake8`、`mypy.ini`。
- 使用现有 Python 风格：4 空格缩进、类型注解优先、Pydantic v2 模型、局部最小改动。
- 后端文档字符串和用户可见文本多为中文，代码标识符保持英文。
- 修改已有文件时匹配同文件风格；不要为了格式统一重排无关 import、注释或空行。

**代码检查：**
- 未检测到自动 lint 配置；文档型变更至少运行 `git diff --check`。
- 后端代码改动以 `python -m pytest tests -v` 或更窄相关测试作为主要质量门禁，规则来自 `docs/backend.md`。

## 导入组织

**顺序：**
1. `from __future__ import annotations`，若文件已有该模式则保持在首个 import 前。
2. 标准库 imports，例如 `json`、`logging`、`pathlib`、`typing`。
3. 第三方 imports，例如 `fastapi`、`pydantic`、`langgraph`、`requests`、`deepagents`。
4. `backend.*` 绝对导入。
5. `TYPE_CHECKING` 下的类型导入或函数内延迟导入，用于避免循环依赖。

**路径别名：**
- 新后端代码使用 `backend.*` 包绝对导入，例如 `from backend.models import GenerateRequest`、`from backend.services.document_service import get_document_service`。
- 不新增 `from services...`、`from models...`、`from util...` 这类脱离包根的短导入。
- `backend/main.py` 和 `backend/tests/conftest.py` 会把项目根加入 `sys.path`，用于支持 `backend.*` 导入解析。

## 错误处理

**模式：**
- API 输入形状用 Pydantic model 和 validator 收口，参考 `backend/models/generate.py`、`backend/models/agent_run.py`。
- API 错误使用 `HTTPException`，`detail` 保持结构化字段：`success`、`error.code`、`error.message`、可选 `details` 和 `timestamp`；参考 `backend/api/template_candidates.py`、`backend/api/tasks.py`、`backend/api/download.py`。
- Service 层返回 `GenerateResponse` / `TaskResponse` 这类模型给 API 层；API 层只把已知失败映射为 HTTP 状态，参考 `backend/api/comment_supplement.py` 和 `backend/services/document_service.py`。
- 长任务失败必须更新任务队列状态并推送 SSE `error`；不要只写日志。相关路径是 `backend/services/document_service.py`、`backend/task/task_queue_manager.py`、`backend/core/sse_manager.py`。
- Graph 节点必须通过 `BaseGraph.wrap_node()` 接入取消检查和进度更新；不要绕过 `backend/graphs/base_graph.py` 直接执行 Word 写入。
- Word 受保护字段、direct-replace 范围、上传 rewrite 必填上下文使用 fail-fast，参考 `backend/helper/word_helper/protected_fields.py`、`backend/nodes/skills_nodes/rewrite_nodes.py`、`backend/services/agent_run_service.py`。
- Retrieval/embedding/Qdrant 失败降级为 `bm25_only` 并记录 warning，不阻塞批注生成；参考 `backend/retrieval/comment_bad_case_runtime.py` 和 `backend/tests/retrieval/test_comment_bad_case_runtime.py`。

## 日志

**框架：** stdlib `logging` + 自有日志工具；`structlog` 在 `backend/requirements.txt` 中存在，但主要运行路径使用 stdlib logging。

**模式：**
- 应用启动配置 JSON stdout logging，入口在 `backend/main.py`。
- 用户可见进度日志走 `backend/util/log_util/progress_log.py`，使用 `QueueHandler` / `QueueListener` 和 `DailyFileHandler`。
- 排障执行日志走 `backend/util/log_util/execution_log.py`，只记录生成成功审计消息。
- Prompt 和 agent artifacts 写入 `backend/prompts_log/`，辅助函数在 `backend/util/log_util/prompt_log.py`。
- Rewrite task audit JSON 走 `backend/util/log_util/skill_audit_log.py`，只写受控 stage：`skill_directory_route`、`skill_prompt_render`、`rewrite_target_selection`、`rewrite_text`。
- SSE 日志桥只在 `task_log_context()` 中推送 INFO 及以上日志，参考 `backend/util/log_util/sse_log_handler.py`。
- Agent run 审计只写白名单字段并 scrub 敏感内容，参考 `backend/agents/task_context_assistant/logging.py`。
- 不把完整客户原文、真实密钥、私有路径、traceback、下载路径写入日志、文档或测试夹具。

## 注释

**注释时机：**
- 复杂跨线程、Word COM、Graph 分支、任务取消、安全边界和协议约束可以保留简短中文注释。
- 不为自解释赋值、简单 wrapper 或显然的字段映射添加重复注释。
- 修改代码时只补与本次改动直接相关的说明，不重写旧注释和周边叙述。

**JSDoc/TSDoc 注释：**
- 不适用。Python docstring 在 API、service、graph、helper 中较常见，例如 `backend/main.py`、`backend/services/task_service.py`、`backend/graphs/base_graph.py`。

## 函数设计

**规模：**
- API endpoint 保持薄入口，复杂编排下沉到 `backend/services/`、`backend/graphs/`、`backend/nodes/` 或 `backend/helper/`。
- 两个以上招标类型复用的 Word 业务逻辑放到 `backend/helper/word_helper/`，底层 COM 生命周期和常量留在 `backend/util/word_util/`。
- Graph 类型差异优先通过 class attribute、配置或 `backend/config/tender_config.py` 表达；不要在共享节点里铺满类型判断。

**参数：**
- API/request 参数使用 Pydantic model，例如 `GenerateRequest`、`AgentRunStreamRequest`、`CommentSupplementRequest`。
- Graph 节点遵循 `(state, config=None)` 或 LangGraph 可调用约定。
- Service 对外方法使用模型或显式关键字参数，例如 `DocumentService.create_task(request)`、`DocumentService.create_rewrite_task(...)`。

**返回值：**
- API 返回 Pydantic response model，例如 `GenerateResponse`、`TaskResponse`。
- Graph 节点返回 state patch dict 或 state 类型实例，例如 `TenderGraphStateBase(...)`、`TaskSkillGraphState(...)`。
- Agent run stream 返回 NDJSON 行，序列化辅助在 `backend/services/chat_stream_service.py`。
- Helper 返回结构化 dict/dataclass/model 或明确状态，不用多义字符串跨层传递。

## 模块设计

**导出：**
- 包级 `__init__.py` 用于稳定 re-export，例如 `backend/models/__init__.py`、`backend/graphs/__init__.py`、`backend/agents/generation/__init__.py`、`backend/nodes/common_word_nodes/__init__.py`。
- 新增公开对象时同步相应 `__all__`，保持调用方导入路径稳定。

**Barrel 文件：**
- 使用 barrel 暴露稳定 API、Graph、Node、Agent runtime。
- 不把易变内部 helper 暴露为跨层公共 API；调用方优先使用已有 service、graph registry 或 helper facade。

## 后端专属边界

- `backend/models/` 是 API 和运行态模型真源；API shape、任务状态、SSE 事件、`TaskKind`、`FormType` 变更必须同步前后端类型和测试。
- `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 是 generate-only 字段；不要进入 rewrite 请求模型、skill state 或 prompt surface。事实来源：`backend/models/generate.py`、`docs/interfaces-runtime.md`。
- Word COM 写入只能在后端任务 Graph 内发生，且必须经过任务队列、Graph 锁、取消检查和进度包装；事实来源：`docs/backend.md`、`backend/graphs/base_graph.py`。
- `gngk` family 行为收敛使用 `backend/config/tender_config.py` 和类型 graph class attribute；不要新增独立重复流程来表达少量锚点或字段差异。
- Prompt Layer 保持纯 prompt 渲染和机器契约解析；副作用、日志、SSE、Word COM、会话状态放到 service/node/helper 层。

## 安全与隐私规则

- 不读取或引用 `backend/.env` 内容；`backend/config/settings.py` 从 `backend/.env` 加载环境变量，但文档和测试只记录变量名和行为，不记录值。
- API key、token、完整客户原文、私有路径、traceback 和下载路径不得进入日志、文档、测试夹具或最终回复。
- 模板候选下载保留 `TEMPLATE_CANDIDATE_ALLOWED_HOSTS` 白名单，相关校验在 `backend/util/common_util/template_candidates.py` 和 `backend/api/template_candidates.py`。
- 下载接口保留 `settings.UPLOAD_DIR` containment check，相关逻辑在 `backend/api/download.py`。

---

*后端编码约定分析：2026-06-08*
