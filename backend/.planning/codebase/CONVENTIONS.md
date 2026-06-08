# 后端编码约定事实地图

**分析日期：** 2026-06-08

**范围：** `backend/` 源码、测试和项目级 agent 规则。

## Naming Patterns

**Files:**
- 使用 `snake_case.py`，例如 `backend/services/document_service.py`、`backend/core/sse_manager.py`。
- 测试文件使用 `test_*.py`，例如 `backend/tests/api/test_generate_api.py`。
- Graph 文件使用 `<runtime_type>_tender_graph.py`，例如 `backend/graphs/gngk_hw_cz_tender_graph.py`。
- 类型节点文件使用 `<runtime_type>_<operation>.py`，例如 `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`。
- task skill 声明放 `backend/skills/<skill_id>/SKILL.md`。

**Functions:**
- 函数使用 `snake_case`，例如 `create_generate_task()`、`get_task_skill_workflow()`、`dispatch_tender_aware_update_word()`。
- FastAPI endpoint 函数以动词或资源动作命名，例如 `create_comment_supplement_task()`、`download_file()`。
- 单例 getter 使用 `get_*()`，例如 `get_document_service()`、`get_task_queue()`。

**Variables:**
- Python 局部变量使用 `snake_case`。
- 常量使用 `UPPER_SNAKE_CASE`，例如 `REWRITE_SKILL_ID`、`TRACKED_PROGRESS_NODES`、`DEFAULT_DEEPSEEK_MODEL`。
- API 枚举值使用后端契约字符串，例如 `gngk_hw_cz_tender`、`agent_step`。

**Types:**
- 类、Pydantic model、Graph class 使用 PascalCase，例如 `GenerateRequest`、`AgentRunStreamRequest`、`GngkHwCzTenderGraph`。
- Enum class 使用 PascalCase，成员使用 UPPER_SNAKE_CASE，例如 `GenerationMode.AGENT`。
- Graph state 类型位于 `backend/states/`，不要靠隐式 dict key 扩散。

## Code Style

**Formatting:**
- Tool used: 未检测到后端专用 Black/Ruff/Prettier 配置。
- Key settings: 按现有 Python 风格，4 空格缩进，类型注解优先，局部最小改动。
- 文档字符串和用户可见说明多为中文；代码标识符保持英文。

**Linting:**
- Tool used: 未检测到后端专用 lint 配置文件。
- Key rules: 以现有测试和导入约定为准；文档型变更至少跑 `git diff --check`。

## Import Organization

**Order:**
1. `from __future__ import annotations`。
2. 标准库 imports。
3. 第三方 imports，例如 `fastapi`、`pydantic`、`langgraph`、`langchain_*`。
4. `backend.*` 绝对导入。
5. `TYPE_CHECKING` 下的类型导入或函数内延迟导入。

**Path Aliases:**
- 新后端代码使用 `backend.*` 绝对导入，例如 `from backend.models import GenerateRequest`。
- 不新增 `from services...`、`from models...`、`from util...` 这类脱离包根的短导入。
- `backend/main.py` 和 `backend/__init__.py` 会把项目根加入 `sys.path`，用于支持 `backend.*` 导入解析。

## Error Handling

**Patterns:**
- API 输入校验放 Pydantic 模型和 validator 中，例子在 `backend/models/generate.py`、`backend/models/agent_run.py`。
- API 错误使用 `HTTPException`，`detail` 包含 `success`、`error.code`、`error.message`，例子在 `backend/api/template_candidates.py` 和 `backend/api/download.py`。
- 长任务失败必须更新任务状态并发 SSE `error`；不要只写日志。
- 业务缺条件在 agent run 中优先返回 `needs_input`，不要创建不完整任务。
- Word 边界、受保护字段、direct-replace 非法范围应 fail-fast，相关逻辑在 `backend/helper/word_helper/protected_fields.py` 和类型 update 节点。
- `progress_log` 不写 traceback、token、完整客户原文或私有路径；排障细节进入 `execution_log`。

## Logging

**Framework:** stdlib `logging` + 自有 log util；`structlog` 依赖存在但不是主要实现。

**Patterns:**
- 应用启动配置 JSON stdout logging，文件 `backend/main.py`。
- 用户进度日志走 `backend/util/log_util/progress_log.py`。
- 排障执行日志走 `backend/util/log_util/execution_log.py`。
- Prompt 记录走 `backend/util/log_util/prompt_log.py`。
- Rewrite task skill 审计走 `backend/util/log_util/skill_audit_log.py`。
- Agent run 审计 scrub 逻辑走 `backend/agents/task_context_assistant/logging.py`。
- SSE 日志桥走 `backend/util/log_util/sse_log_handler.py`。

## Comments

**When to Comment:**
- 复杂跨线程、Word COM、graph 分支、任务取消和安全边界可以保留简短中文注释。
- 不为自解释赋值或简单 wrapper 添加重复注释。
- 修改代码时只补与本次改动直接相关的说明，不顺手重写旧注释。

**JSDoc/TSDoc:**
- 不适用。Python docstring 在 API、service、graph、helper 中较常见。

## Function Design

**Size:**
- API endpoint 保持短函数，复杂编排下沉到 `backend/services/`。
- 共享 Word 业务逻辑从节点中抽到 `backend/helper/word_helper/`。
- 大型 Word/样式逻辑集中在 `backend/helper/word_helper/inline_style_ops.py`，修改前优先定位现有 helper，而不是在节点中复制。

**Parameters:**
- API/request 参数用 Pydantic model。
- Graph 节点遵循 `(state, config=None)` 或 LangGraph 可调用约定。
- Service 对外方法接受模型或显式关键参数，例如 `DocumentService.create_task(request)`、`create_rewrite_task(...)`。

**Return Values:**
- API 返回 Pydantic response model，例如 `GenerateResponse`。
- Graph 节点返回 state patch dict。
- Agent run stream 返回 NDJSON event data。
- Helper 返回结构化 dataclass/model 或明确的 tuple/status，避免把多义字符串散落到调用方。

## Module Design

**Exports:**
- 包级 `__init__.py` 用于稳定 re-export，例如 `backend/graphs/__init__.py`、`backend/agents/generation/__init__.py`。
- 新增公开对象时保持导出路径稳定，避免调用方跨目录 import 私有 helper。

**Barrel Files:**
- 使用包级 barrel 统一导出 graph、node、agent runtime。
- 不把易变内部 helper 暴露为跨层公共 API。

## API and Model Rules

- `backend/models/` 是 API 和运行态模型真源。
- `GenerateRequest.form_type` 改动必须同步前端类型、gngk 分派 helper、service registry、graph 测试和 API 测试。
- `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 是 generate-only 字段，不进入 rewrite 请求模型、skill state 或 prompt surface。
- `TaskKind` 当前只有 `generate`、`rewrite`、`comment_supplement`，真源在 `backend/models/task.py` 和 `backend/task/task_queue_manager.py`。
- `SSEEventType.AGENT_STEP` 是智能体过程事件，不替代任务终态。
- Agent run 输入只接受受控 `context_snapshot`，真源在 `backend/models/agent_run.py`。

## Graph and Node Rules

- 新 graph 优先继承 `StandardTenderWorkflowGraph`，只覆写必要节点。
- `generation_mode` 分支只在 `StandardTenderWorkflowGraph` 维护：`workflow` 走 `generate_polished_text`，`agent` 走 `content_agent`。
- `comment_generation_mode=off` 只跳过初次生成批注分支，不影响正文生成、Word 写回、下载和任务结果。
- 节点必须尊重 `BaseGraph.wrap_node()` 的取消检查和进度包装。
- 类型差异先放配置或 class attribute；不要在共享节点中铺满类型判断。
- `gngk` family 行为收敛使用 `backend/config/tender_config.py` 中的 helper。

## Word Helper Rules

- `backend/helper/word_helper/` 是 Word 业务层；`backend/util/word_util/` 是底层 COM/技术工具层。
- 两个以上类型复用的删除、正文写回、段落边界、表格、受保护字段、cleanup、样式回填逻辑放到 helper。
- 受保护字段 profile 由 `backend/config/tender_config.py` 管理。
- 受保护字段识别必须严格匹配，不用模糊 `keyword in text`。
- direct-replace 类型通过 `content_update_mode` 和 `content_start_mode` 显式声明；不能误走 protected-fields profile。
- Word 写入只能在后端任务 graph 中进行，不能从 API route、agent run、前端或随意脚本直接执行。

## Prompt and Agent Rules

- `backend/prompts/` 只做纯 prompt 渲染和机器契约解析。
- LLM streaming timeout 使用 `settings.LLM_STREAM_TIMEOUT_SECONDS`。
- Prompt 文案改动同步检查 `backend/tests/prompts/`。
- `content_agent`、`content_generate_agent`、`content_verify_agent`、`content_revise_agent`、`comment_agent` 等机器标识符不能翻译或改名。
- `content_verify_agent` 输出中“无问题/无需修改/实质一致”类无效 finding 要在解析层折叠为 `[]`，相关测试在 `backend/tests/agents/test_generation_content_agent.py`。
- Agent run 审计只记录白名单字段和 scrub 摘要；不要记录完整用户原文、真实路径、下载路径、traceback 或 token。

## Security and Privacy Rules

- 不读取或引用 `backend/.env` 内容。
- 不把真实 API key、token、客户原文、私有路径写入日志、文档或测试夹具。
- 模板候选下载保留 `TEMPLATE_CANDIDATE_ALLOWED_HOSTS` 白名单。
- 下载接口保留 `settings.UPLOAD_DIR` containment check。
- Retrieval/embedding/Qdrant 配置只记录变量名，不记录值。

---

*后端编码约定分析：2026-06-08*
