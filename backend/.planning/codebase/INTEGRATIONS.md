# 后端外部集成

**分析日期：** 2026-07-21

**last_mapped_commit：** `e748f16d1a2b253c766008f1a060e3ebba9b2f85`

**范围：** 本文只覆盖 `backend/` 子项目。事实来源包括 `backend/main.py`、`backend/config/settings.py`、`backend/.env.example`、`backend/api/`、`backend/services/`、`backend/agents/`、`backend/retrieval/`、`backend/util/common_util/`、`backend/util/word_util/`、`backend/util/log_util/`、`backend/task/task_queue_manager.py`、`backend/core/sse_manager.py`、`backend/models/`、`backend/graphs/base_graph.py`、`backend/graphs/skill_graph.py`、`backend/nodes/common_word_nodes/annotate_corrections.py`。`backend/.env` 与 `backend/.env.example` 均可能存在；本文档只引用配置键名与 `.env.example` 中的示例值，不读取或泄露 `.env` 真实值。

## API 与外部服务

**浏览器到后端 API：**
- FastAPI app 在 `backend/main.py` 创建；业务 routers 统一挂载 `/api` 前缀，健康检查保留根级 `/health*`。
- 生成和任务：
  - `POST /api/generate`、`GET /api/generate/{task_id}` — `backend/api/generate.py`
  - `GET /api/tasks`、`GET /api/tasks/{task_id}`、`DELETE /api/tasks/{task_id}`、`POST /api/tasks/{task_id}/heartbeat` — `backend/api/tasks.py`
  - `GET /api/stream/{task_id}`、`GET /api/stream/{task_id}/status` — `backend/api/stream.py`
- 文件、招标和模板：
  - `POST /api/upload`、`POST /api/upload/multiple` — `backend/api/upload.py`
  - `GET /api/download/{file_path:path}` — `backend/api/download.py`
  - `GET /api/tender/{tender_no}` — `backend/api/tender.py`
  - `GET /api/template-candidates`、`GET /api/template-candidates/download`、`POST /api/template-candidates/select` — `backend/api/template_candidates.py`
- Agent/chat：
  - `POST /api/agent/runs/stream` — NDJSON task context assistant 入口，`backend/api/agent.py`（router prefix `/agent/runs`）
  - `POST /api/conversations/{conversation_id}/heartbeat` — 会话心跳，`backend/api/conversations.py`
  - Chat stream NDJSON 序列化和 OpenAI-compatible 调用辅助在 `backend/services/chat_stream_service.py`（`to_ndjson_line()`）
- 补充批注：
  - `POST /api/comment-supplement` — `backend/api/comment_supplement.py`

**LLM 服务商：**
- DeepSeek — 默认文本生成 provider。
  - SDK/Client: OpenAI-compatible `openai.AsyncOpenAI`、`langchain_openai.ChatOpenAI`
  - Auth: `DEEPSEEK_API_KEY`
  - Config: `DEEPSEEK_BASE_URL`（默认 `https://api.deepseek.com`）、`DEEPSEEK_MODEL`（默认 `deepseek-v4-flash`）
  - 调用参数: `MODEL_CONFIGS["deepseek"]` → `max_tokens=8192`、`temperature=0.1`、`extra_body={"thinking": {"type": "disabled"}}`
  - 使用路径：`backend/config/settings.py`、`backend/util/common_util/llm_stream_utils.py`、`backend/agents/generation/model_factory.py`、`backend/services/chat_stream_service.py`
- Qwen / DashScope — 可选 provider。
  - SDK/Client: OpenAI-compatible `openai.AsyncOpenAI`、`langchain_openai.ChatOpenAI`
  - Auth: `DASHSCOPE_API_KEY`
  - Config: `DASHSCOPE_BASE_URL`（默认 `https://dashscope.aliyuncs.com/compatible-mode/v1`）、`QWEN_MODEL`（`settings.py` 默认 `Qwen/Qwen3.6-35B-A3B`，`backend/.env.example` 示例值为 `qwen-plus`）
  - 调用参数: `MODEL_CONFIGS["qwen"]` → `max_tokens=32768`、`temperature=0.1`、`extra_body={"enable_thinking": False}`、`stream_options={"include_usage": True}`
  - 使用路径：`backend/config/settings.py`、`backend/util/common_util/llm_stream_utils.py`、`backend/retrieval/config.py`（embedding key 可 fallback 到 `DASHSCOPE_API_KEY`）
- Doubao / ARK — 可选 provider。
  - SDK/Client: OpenAI-compatible `openai.AsyncOpenAI`、`langchain_openai.ChatOpenAI`；依赖声明包含 `volcengine-python-sdk[ark]`
  - Auth: `ARK_API_KEY`
  - Config: `ARK_BASE_URL`（默认 `https://ark.cn-beijing.volces.com/api/v3`）、`DOUBAO_MODEL`（默认 `doubao-seed-1-6-251015`）
  - 调用参数: `MODEL_CONFIGS["doubao"]` → `max_tokens=32768`、`temperature=0.1`、`extra_body={"thinking": {"type": "disabled"}}`
  - 使用路径：`backend/config/settings.py`、`backend/util/common_util/llm_stream_utils.py`
- 统一 model factory：`create_generation_chat_model(provider)` 在 `backend/agents/generation/model_factory.py`，根据 `settings.get_llm_config(provider)` 取 `model/api_key/base_url`，叠加 `MODEL_CONFIGS` 的 `extra_params`/`extra_body`，`max_retries=0`，超时取 `LLM_STREAM_TIMEOUT_SECONDS`。
- Provider 枚举：`backend/models/generate.py` 中 `LLMModel`：`deepseek` / `qwen` / `doubao`。
- LangSmith — 可选 tracing。
  - SDK/Client: LangChain/LangSmith SDK 读取进程环境变量
  - Auth: `LANGSMITH_API_KEY`
  - Config: `LANGSMITH_TRACING`、`LANGSMITH_ENDPOINT`（默认 `https://api.smith.langchain.com`）、`LANGSMITH_PROJECT`
  - 使用路径：`backend/config/settings.py`（`Settings.apply_langsmith_environment()`，模块加载时已调用一次）、`backend/tests/config/test_settings_langsmith.py`

**智能体运行时：**
- DeepAgents content agent — `generation_mode=agent` 的初次正文生成智能体，内部组合 `content_generate_agent`、`content_verify_agent`、`content_revise_agent`。
  - SDK/Client: `deepagents.create_deep_agent`、`CompiledSubAgent`、`BackendProtocol` / `FilesystemBackend`
  - Auth: 使用请求选择的 LLM provider 配置
  - 使用路径：`backend/agents/generation/content_agents.py`、`backend/agents/generation/workspace.py`、`backend/agents/generation/model_factory.py`、`backend/agents/generation/*_agent_graph.py`
  - 表格占位符：content agent 将技术参数中的 `[[TABLE:<id>]]` 视为内部写回入口；提取与缺失校验在 `backend/agents/generation/table_placeholder_utils.py`；最终是否恢复真实表格由 Word 写回层决定（`backend/helper/word_helper/text_parsing.py` + `backend/util/word_util/table_models.py`），占位符不得作为用户可见正文。
- DeepAgents task context assistant — 右侧聊天 agent run 前置流，仅允许受控 `rewrite` skill 和只读摘要工具，受控路由 `/skills/`、`/scratch/`、`/workspace/`。
  - SDK/Client: `deepagents.create_deep_agent`、`CompositeBackend`、`FilesystemBackend`、`FilesystemPermission`
  - Auth: 使用请求选择的 LLM provider 配置
  - 使用路径：`backend/agents/task_context_assistant/factory.py`、`backend/agents/task_context_assistant/tools.py`、`backend/services/agent_run_service.py`
- LangChain comment agent — 批注生成、锚点校验和写回提交。
  - SDK/Client: `langchain.agents.create_agent`、`ToolCallLimitMiddleware`
  - Auth: 使用请求选择的 LLM provider 配置
  - 使用路径：`backend/agents/comments/comment_agent.py`、`backend/agents/comments/tools.py`
  - 边界：普通合规批注与 `★/▲` 规范化例外由 comment agent 处理；技术参数差异批注不由 comment agent 生成，而由 `annotate_corrections` 专用链路产出。

**后生成更正批注链路（内部，依赖 LLM）：**
- `annotate_corrections` 节点位于 workflow/agent 最终正文确定之后、普通批注与 Word 写回之前。
  - SDK/Client: `stream_llm_completion`（`backend/util/common_util/llm_stream_utils.py`）
  - 职责：条款标识规范化（`clause_marker_normalize`）+ 技术参数差异更正批注候选生成/审核
  - 使用路径：`backend/nodes/common_word_nodes/annotate_corrections.py`、`backend/helper/word_helper/clause_marker_normalize.py`、`backend/graphs/base_graph.py`
  - 写回顺序：先写更正批注再写普通 AI 批注；`comment_generation_mode=off` / `suppress_ai_comment_writeback` 只跳过普通 AI 批注，不跳过更正批注。

**外部招标详情系统：**
- 招标详情接口 — 按招标编号获取项目数据并归一化 form routing 所需 `type`。
  - SDK/Client: `requests.get`
  - Auth: 未检测到单独认证字段；URL 来自配置
  - Config: `TENDER_DATA_API_URL`（`settings.py` 默认 `http://dserp.dongsong-cn.com/dongsong//servlet/tender.TenderJsonAction`；`.env.example` 同键）、`EXTERNAL_REQUEST_TIMEOUT_SECONDS`（默认 `15`）
  - 请求参数：`tenderno`
  - 响应形状：`{"data": {...}, "type": {"tender_lx": int, "purchase_method": int, "fund_lx": 0|1}}`；`type` 非法时归一为 `None`
  - 使用路径：`backend/util/common_util/fetch_tender_data.py`、`backend/api/tender.py`

**模板候选系统：**
- 模板候选列表 / 文件下载 / 选择落盘 — 后端代理外部模板系统，按年份阻断过旧模板（`year < 2025` 不可自动选择），并限制下载主机白名单。
  - SDK/Client: `requests.get`
  - Auth: 未检测到单独认证字段；URL 和白名单来自配置
  - Config: `TEMPLATE_CANDIDATE_API_URL`（`settings.py` 默认 `http://dserp.dongsong-cn.com/dongsong/servlet/tender.TenderJsonActionMb`；`.env.example` 示例 `http://10.11.1.224/dongsong/servlet/tender.TenderJsonActionMb`）、`TEMPLATE_CANDIDATE_ALLOWED_HOSTS`、`TEMPLATE_CANDIDATE_RANKING_LLM_PROVIDER`、`EXTERNAL_REQUEST_TIMEOUT_SECONDS`
  - 列表请求参数：`tenderno`
  - 下载：先 `validate_template_download_url` 校验 scheme 与 host 白名单，再 stream GET
  - AI 排序：`backend/services/template_candidate_ranking_service.py` + `backend/prompts/template_candidate_ranking_prompt.py`
  - 使用路径：`backend/util/common_util/template_candidates.py`、`backend/api/template_candidates.py`

**检索 / 向量搜索：**
- Qdrant — 批注 bad case hybrid 检索的向量层。
  - SDK/Client: direct `httpx.Client`（`trust_env=False`），距离度量 `Cosine`
  - Auth: `QDRANT_API_KEY`（通过 `api-key` header；可空）
  - Config: `QDRANT_URL`（默认 `http://127.0.0.1:6333`）、`COMMENT_BAD_CASE_COLLECTION`（默认 `tenderword_comment_bad_cases_demo`）
  - 使用路径：`backend/retrieval/qdrant_store.py`、`backend/retrieval/config.py`、`backend/retrieval/comment_bad_case_runtime.py`
- Embedding API — 为 bad case 检索生成查询向量。
  - SDK/Client: OpenAI-compatible `openai.OpenAI`
  - Auth: `EMBEDDING_API_KEY`，可 fallback 到 `DASHSCOPE_API_KEY`；缺失则 `RuntimeError`
  - Config: `EMBEDDING_BASE_URL`（fallback `SILICONFLOW_BASE_URL`，默认 `https://api.siliconflow.cn/v1`）、`EMBEDDING_MODEL`（默认 `BAAI/bge-large-zh-v1.5`）、`EMBEDDING_DIMENSIONS`；`backend/.env.example` 另含 `EMBEDDING_PROVIDER`
  - 使用路径：`backend/retrieval/config.py`、`backend/retrieval/embeddings.py`
- BM25 fallback — Qdrant、embedding 或 hybrid 任一环节失败时回退到进程内 BM25。
  - SDK/Client: 本地 Python 实现（`backend/retrieval/bm25.py`）
  - Auth: Not applicable
  - 使用路径：`backend/retrieval/bm25.py`、`backend/retrieval/hybrid.py`、`backend/retrieval/comment_bad_case_runtime.py`
- 检索消费方 — bad case context 注入 `generate_comments`、自主批注 `comment_agent` 和 `comment_supplement`；rewrite 不触发该检索。
  - 使用路径：`backend/nodes/common_word_nodes/generate_comments.py`、`backend/nodes/common_word_nodes/comment_agent.py`、`backend/nodes/common_word_nodes/comment_supplement.py`
- 离线索引/自测脚本：`backend/scripts/index_comment_bad_cases.py`、`backend/scripts/test_comment_hybrid_retrieval.py`

**本地 Word COM：**
- Microsoft Word/WPS COM — Word 文档读取、写入、批注、样式回填、诊断和 `.doc/.docx` 保存。
  - SDK/Client: `pywin32` / `pythoncom` / `win32com.client`
  - Auth: Not applicable
  - 创建顺序（`word_application_util.py`）：`GetActiveObject("Word.Application")` → `DispatchEx("Word.Application")` → `EnsureDispatch("Word.Application")`；缓存损坏时 `clear_win32com_cache()` 后重试
  - 诊断 ProgID（`word_diagnostics.py`）：`Word.Application`、`WPS.Application`、`KWPS.Application`
  - 并发护栏：`com_lock()`（`backend/util/word_util/word_com_manager.py`）、任务队列 `wait_for_turn`（`backend/task/task_queue_manager.py`）、`CrossProcessFileLock`（`backend/graphs/base_graph.py`）
  - 抽取保真：`word_extraction_utils` 保留 Symbol/Wingdings 与未知字形（`[[WORD_SYMBOL:...]]`）、段落自动编号（`ListFormat`/`ListString`）；写回侧 `word_symbol_tokens` + `content_ops` 解码并恢复字体；字段替换查找串长度上限 256（`replace_content.WORD_FIND_TEXT_MAX_LEN`）
  - 表格 sidecar：`backend/util/word_util/table_models.py` 配合 `[[TABLE:id]]` 占位符在写回时恢复真实表格结构
  - 使用路径：`backend/util/word_util/word_application_util.py`、`backend/util/word_util/word_com_manager.py`、`backend/util/word_util/word_diagnostics.py`、`backend/util/word_util/word_extraction_utils.py`、`backend/util/word_util/word_symbol_tokens.py`、`backend/helper/word_helper/content_ops.py`、`backend/nodes/common_word_nodes/replace_content.py`、`backend/scripts/diagnose_word.py`

## 数据存储

**数据库：**
- 外部关系数据库、ORM、migration 和 SQL client 未检测到。
- 任务、取消事件、任务结果、SSE event buffer、conversation rewrite history 和 retrieval runtime cache 均为进程内状态。
  - 使用路径：`backend/task/task_queue_manager.py`、`backend/core/sse_manager.py`、`backend/services/conversation_service.py`、`backend/retrieval/comment_bad_case_runtime.py`

**文件存储：**
- 本地文件系统是主要持久化层。
- 上传文件、模板选择结果、生成产物和下载文件位于 `settings.UPLOAD_DIR`（默认 `D:/UploadFiles`）。
  - Config: `UPLOAD_DIR`、`MAX_UPLOAD_SIZE`、`ALLOWED_EXTENSIONS`
  - 使用路径：`backend/config/settings.py`、`backend/util/common_util/upload_storage.py`、`backend/api/upload.py`、`backend/api/download.py`
- 文件下载必须留在 `UPLOAD_DIR` 下；路径 containment 校验在 `backend/api/download.py`。
- Content agent workspace 位于 `backend/context_log/content_agent_workspace/`，管理点是 `backend/agents/generation/workspace.py`。
- Comment agent audit 位于 `backend/context_log/comment_agent_audit/`，管理点是 `backend/agents/comments/workspace.py`。
- 生成 context 日志目录 helper：`backend/util/log_util/context_log.py`（`generate_log` / `content_agent_log` / `verify_log` 子目录名）。
- Skill 审计日志根：`backend/util/log_util/skill_audit_log.py` 写入 `backend/context_log/<subdir>`。
- Agent run audit JSONL 默认位于 `backend/logs/agent-run-*.jsonl`，实现点是 `backend/agents/task_context_assistant/logging.py`。
- 批注 bad case 源文件位于 `backend/retrieval/bad_cases/`，加载器是 `backend/retrieval/bad_case_loader.py`。
- 进度、执行、prompt、skill audit、SSE 日志由 `backend/util/log_util/` 管理，默认与 `LOG_DIR`、`backend/logs/` 相关（如 `progress-YYYYMMDD.log`、`execution-YYYYMMDD.log`）。

**缓存：**
- SSE events：按 task 维护进程内缓存，受 `SSE_MAX_EVENTS_PER_TASK` 和 `SSE_EVENT_TTL` 控制；路径是 `backend/core/sse_manager.py`。
- Task queue：进程内单例；路径是 `backend/task/task_queue_manager.py`。
- Conversation runtime：进程内单例，含 heartbeat 和 rewrite history；路径是 `backend/services/conversation_service.py`。
- Bad case BM25 index：进程内缓存，按 markdown 文件签名失效；路径是 `backend/retrieval/comment_bad_case_runtime.py`。
- Redis、Memcached 或独立 cache service：未检测到。

## 认证与身份

**Auth Provider:**
- 未检测到强制执行的 API 鉴权层。
  - Implementation: `backend/main.py` 注册的 routers 未发现统一 `Depends(...)` auth dependency；`backend/requirements.txt` 未声明 `python-jose` 或 `passlib`。

**身份 / 会话标识：**
- `conversation_id` 用于 rewrite history、agent run 上下文和补充批注状态连续性。
  - 使用路径：`backend/models/generate.py`、`backend/models/agent_run.py`、`backend/services/conversation_service.py`
- `user_session_id` 用于任务归属和队列状态。
  - 使用路径：`backend/task/task_queue_manager.py`、`backend/models/task.py`
- `task_id` 用于任务队列、SSE topic、日志命名、下载结果和心跳取消。
  - 使用路径：`backend/task/task_queue_manager.py`、`backend/core/sse_manager.py`、`backend/services/document_service.py`

## 监控与可观测性

**Error Tracking:**
- 外部 error tracking service 未检测到。
- 可选 LangSmith tracing 由 `backend/config/settings.py` 的 `Settings.apply_langsmith_environment()` 暴露给 LangChain/LangSmith SDK。

**Logs:**
- JSON stdout logging：`backend/main.py`（`JSONFormatter`）
- 用户进度日志：`backend/util/log_util/progress_log.py`
- 执行诊断日志：`backend/util/log_util/execution_log.py`
- Context 日志：`backend/util/log_util/context_log.py`
- Skill 审计日志：`backend/util/log_util/skill_audit_log.py`
- SSE 日志桥：`backend/util/log_util/sse_log_handler.py`
- 日志清理：`backend/util/log_util/log_cleanup.py`（启动时 `cleanup_logs("backend/logs", max_total_mb=200)`）
- Agent run 审计与 scrub：`backend/agents/task_context_assistant/logging.py`
- Agent workspace / audit 命名清洗：`backend/agents/log_naming.py`、`backend/agents/generation/workspace.py`、`backend/agents/comments/workspace.py`

**SSE / NDJSON 可观测性：**
- SSE event model 来源：`backend/models/sse.py`（`SSEEventType` 枚举）
- SSE manager 来源：`backend/core/sse_manager.py`
- SSE 事件类别包括 `log`、`llm`、`progress`、`node_start`、`node_complete`、`agent_step`、`done`、`error`、`heartbeat`。
- 默认心跳间隔 `SSE_HEARTBEAT_INTERVAL=15` 秒。
- `Last-Event-ID` 断线重连支持在 `backend/api/stream.py` 和 `backend/core/sse_manager.py`。
- Agent run NDJSON 行由 `backend/services/chat_stream_service.py` 的 `to_ndjson_line()` 复用（`backend/services/agent_run_service.py` 导入并调用），流式入口在 `backend/api/agent.py` 和 `backend/services/agent_run_service.py`。NDJSON 事件名示例：`start`、`chunk`、`done`、`error`。

## CI/CD 与部署

**Hosting:**
- 未检测到生产托管配置。
- 本地 ASGI 入口是 `backend/main.py`。
- Windows 开发入口是 `scripts/start-dev-win.ps1`；兼容入口是 `scripts/start-dev.ps1`；WSL 协作入口是 `scripts/start-dev-wsl.sh`。

**CI 流水线:**
- 未检测到 `.github/workflows` 或后端专用 CI 配置。
- 完整 Word COM 验证必须在 Windows + Word/WPS COM 环境执行；无 COM 环境只能覆盖 API shape、service、prompt、retrieval、agent guard 和 helper 纯逻辑。

## 环境配置

**Required / 常用 env vars：**
- DeepSeek LLM：`DEEPSEEK_API_KEY`；可覆盖 `DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`。
- Qwen/DashScope LLM：`DASHSCOPE_API_KEY`；可覆盖 `DASHSCOPE_BASE_URL`、`QWEN_MODEL`。
- Doubao/ARK LLM：`ARK_API_KEY`；可覆盖 `ARK_BASE_URL`、`DOUBAO_MODEL`。
- 流式超时：`LLM_STREAM_TIMEOUT_SECONDS`。
- 可选 LangSmith：`LANGSMITH_TRACING`、`LANGSMITH_ENDPOINT`、`LANGSMITH_API_KEY`、`LANGSMITH_PROJECT`。
- 外部招标/模板：`TENDER_DATA_API_URL`、`TEMPLATE_CANDIDATE_API_URL`、`TEMPLATE_CANDIDATE_ALLOWED_HOSTS`、`EXTERNAL_REQUEST_TIMEOUT_SECONDS`。
- 模板候选 AI 排序：`TEMPLATE_CANDIDATE_RANKING_LLM_PROVIDER`。
- 文件、任务、SSE、日志：`UPLOAD_DIR`、`MAX_UPLOAD_SIZE`、`ALLOWED_EXTENSIONS`、`LOCK_FILE_PATH`、`LOCK_TIMEOUT`、`LOCK_WAIT_TIMEOUT`、`TASK_TOTAL_NODES`、`TASK_HEARTBEAT_TIMEOUT`、`TASK_CLEANUP_INTERVAL`、`SSE_MAX_EVENTS_PER_TASK`、`SSE_EVENT_TTL`、`SSE_HEARTBEAT_INTERVAL`、`LOG_DIR`。
- 检索：`QDRANT_URL`、`QDRANT_API_KEY`、`COMMENT_BAD_CASE_COLLECTION`、`EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL`、`SILICONFLOW_BASE_URL`、`EMBEDDING_MODEL`、`EMBEDDING_DIMENSIONS`（`.env.example` 另有 `EMBEDDING_PROVIDER`）。

**Secrets location:**
- `backend/.env` 文件存在时包含本地私有配置；不得读取、引用或提交真实值。
- `backend/.env.example` 文件存在，仅含键名与示例占位值。
- 文档、日志、测试夹具和最终回复只允许记录变量名，不记录 secret value。

## Webhook 与回调

**Incoming:**
- 第三方入站 webhook：未检测到。
- 浏览器任务事件流：`GET /api/stream/{task_id}` 使用 SSE，文件是 `backend/api/stream.py`。
- 浏览器 agent 流：`POST /api/agent/runs/stream` 返回 NDJSON，文件是 `backend/api/agent.py`。
- 浏览器普通 chat stream helper 输出 NDJSON 行，文件是 `backend/services/chat_stream_service.py`。

**Outgoing:**
- LLM provider 调用来自 `backend/util/common_util/llm_stream_utils.py`、`backend/services/chat_stream_service.py`、`backend/agents/generation/model_factory.py`。
- 招标详情外部 HTTP 调用来自 `backend/util/common_util/fetch_tender_data.py`。
- 模板候选列表、模板下载和模板选择落盘调用来自 `backend/util/common_util/template_candidates.py`、`backend/api/template_candidates.py`。
- Qdrant 和 embedding HTTP 调用来自 `backend/retrieval/qdrant_store.py`、`backend/retrieval/embeddings.py`。
- LangSmith tracing 由 `backend/config/settings.py` 暴露环境变量后交给 LangChain/LangSmith SDK 使用。

## 内部集成（前端 API / SSE / 任务契约）

**前端到后端契约要点：**
- 前端所有后端请求应统一走 API client，不直接访问外部模板候选 URL 或招标详情 URL；后端侧对应代理入口是 `backend/api/template_candidates.py`、`backend/api/tender.py`。
- 任务进度与实时日志通过 SSE（`GET /api/stream/{task_id}`）推送；agent 前置流通过 NDJSON（`POST /api/agent/runs/stream`）推送。
- CORS 默认允许前端开发端口 `8502`（及 `.env.example` 中的 `3000`），并暴露 `Last-Event-ID`、`X-Accel-Buffering` 等 SSE 相关头。

**任务类型与 generate-only 字段：**
- `TaskKind`：`generate` / `rewrite` / `comment_supplement`（`backend/task/task_queue_manager.py`）。
- `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 仅用于初次 generate，写入 `base_state` / `document_service` 初始状态；不得进入 rewrite 请求模型、skill state 或 prompt surface。
- 上传文件 rewrite：后端 skill state 使用 `rewrite_source="uploaded_file"` 标记来源（`backend/states/skill_state.py`、`backend/services/document_service.py`、`backend/skills/rewrite/scripts/runtime.py`）；不要恢复旧 edit 入口或第二套任务链路。
- rewrite 由显式 `RewriteSkillGraph` 承载（`backend/graphs/skill_graph.py`），节点：`resolve_rewrite_target`、`extract_rewrite_context`、`get_rewrite_comments`、`delete_section`、`rewrite_text`、`update_word`。

## 集成护栏

- 前端不得直接访问外部招标详情或模板候选 URL；统一走后端代理和白名单校验；实现点是 `backend/api/template_candidates.py`、`backend/util/common_util/template_candidates.py`。
- 模板候选下载必须保留 `TEMPLATE_CANDIDATE_ALLOWED_HOSTS` 校验；实现点是 `backend/util/common_util/template_candidates.py`。
- 文件下载必须保留 `settings.UPLOAD_DIR` containment 校验；实现点是 `backend/api/download.py`。
- 新增 LLM provider 时同步 `backend/models/generate.py`、`backend/config/settings.py`、`backend/util/common_util/llm_stream_utils.py`（`MODEL_CONFIGS`）、`backend/agents/generation/model_factory.py` 和相关测试。
- 新增 SSE event 时同步 `backend/models/sse.py`（`SSEEventType`）、`backend/core/sse_manager.py`、前端 parser/types 和测试。
- Agent/chat NDJSON shape 改动时同步 `backend/services/chat_stream_service.py`（`to_ndjson_line`）、`backend/services/agent_run_service.py`、前端 parser/types 和测试。
- Word COM 写入必须继续经过后端任务队列（`backend/task/task_queue_manager.py` 公平锁 `wait_for_turn`）、graph 文件锁（`backend/graphs/base_graph.py` 的 `CrossProcessFileLock` + `msvcrt.locking`）、取消检查和进度包装；不得在 API route、service、前端或随意脚本中直接操作 COM。
- `generation_style`、`generation_mode`、`comment_generation_mode` 和 `style_writeback_mode` 是 generate-only 字段，不得进入 rewrite 请求模型、skill state 或 prompt surface；实现点是 `backend/models/generate.py`、`backend/graphs/base_graph.py`、`backend/services/document_service.py`。
- 上传文件 rewrite 前端使用 `rewrite_source` 文件类型，后端 task skill state 用 `rewrite_source="uploaded_file"` 标记来源；不要恢复旧 edit 入口或把上传修改做成第二套任务链路；实现点是 `backend/services/document_service.py`、`backend/graphs/skill_graph.py`。
- rewrite 任务由显式 `RewriteSkillGraph` 承载；不要恢复 `SkillGraph.for_skill + TaskSkillWorkflow` 元数据驱动框架；实现点是 `backend/graphs/skill_graph.py`。
- `annotate_corrections` 与 comment agent 职责隔离：技术参数差异批注只由更正链路产出；comment agent 不得生成“原技术参数为…现改为…”类差异批注。
- 批注写回同锚点策略：`write_polished_comments(..., allow_existing_comments=False)` 为默认保守去重；仅 `comment_agent` 工具写回传 `True`。
- Retrieval bad case 命中详情只进入后端 prompt/retrieval 审计，不进入 SSE、下载卡、任务结果或 `agent_step`。
- Agent run 审计日志只记录 scrub 后白名单字段；不要返回完整客户原文、真实密钥、私有路径、traceback 或下载路径；实现点是 `backend/agents/task_context_assistant/logging.py`。
- `[[TABLE:<id>]]` 是 content agent / 写回层内部契约，不得当作用户可见正文或 Markdown 手绘表格；实现点是 `backend/agents/generation/table_placeholder_utils.py`、`backend/helper/word_helper/text_parsing.py`。

---

*后端集成分析：2026-07-21*
