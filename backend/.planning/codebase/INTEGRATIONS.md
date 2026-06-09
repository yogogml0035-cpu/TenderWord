# 后端外部集成

**分析日期：** 2026-06-09

**范围：** 仅覆盖 `backend/` 后端子项目。事实来源包括 `backend/` 源码、`backend/requirements.txt`、`backend/.env.example`、`backend/.planning/codebase/` 现有事实文档、`README.md`、`docs/backend.md`、`docs/interfaces-runtime.md`、`docs/knowledge-validation.md`、根级启动脚本 `scripts/start-dev.ps1`、`scripts/start-dev-win.ps1`、`scripts/start-dev-wsl.sh`，以及项目内 `.agents/skills/*/SKILL.md` 的轻量规则索引。`backend/.env` 存在但未读取；`frontend/.env.local` 未读取。

## API 与外部服务

**前端 API 边界：**
- FastAPI routers 在 `backend/main.py` 注册，业务 routes 统一挂载 `/api` 前缀；根级 `/health`、`/health/ready`、`/health/live` 不挂 `/api`。
- 生成、任务、SSE：
  - `POST /api/generate`、`GET /api/generate/{task_id}` - 文件 `backend/api/generate.py`
  - `GET /api/tasks`、`GET /api/tasks/{task_id}`、`DELETE /api/tasks/{task_id}`、`POST /api/tasks/{task_id}/heartbeat` - 文件 `backend/api/tasks.py`
  - `GET /api/stream/{task_id}`、`GET /api/stream/{task_id}/status` - 文件 `backend/api/stream.py`
- Agent/chat：
  - `POST /api/agent/runs/stream` - NDJSON task context assistant 入口，文件 `backend/api/agent.py`
  - `POST /api/conversations/{conversation_id}/heartbeat` - 会话心跳，文件 `backend/api/conversations.py`
  - Chat stream NDJSON 辅助序列化和 OpenAI-compatible 调用位于 `backend/services/chat_stream_service.py`
- 文件、招标数据、模板：
  - `POST /api/upload`、`POST /api/upload/multiple` - 文件 `backend/api/upload.py`
  - `GET /api/download/{file_path:path}` - 文件 `backend/api/download.py`
  - `GET /api/tender/{tender_no}` - 招标详情代理，文件 `backend/api/tender.py`
  - `GET /api/template-candidates`、`GET /api/template-candidates/download`、`POST /api/template-candidates/select` - 模板候选代理，文件 `backend/api/template_candidates.py`
  - `POST /api/comment-supplement` - 补充批注任务，文件 `backend/api/comment_supplement.py`

**LLM 服务商：**
- DeepSeek - 默认文本生成 provider。
  - SDK / 客户端：OpenAI-compatible `openai.AsyncOpenAI`、`langchain_openai.ChatOpenAI`
  - 认证：`DEEPSEEK_API_KEY`
  - 配置：`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`
  - 使用路径：`backend/config/settings.py`、`backend/util/common_util/llm_stream_utils.py`、`backend/agents/generation/model_factory.py`、`backend/services/chat_stream_service.py`
- Qwen / DashScope - 可选 provider。
  - SDK / 客户端：OpenAI-compatible `openai.AsyncOpenAI`、`langchain_openai.ChatOpenAI`
  - 认证：`DASHSCOPE_API_KEY`
  - 配置：`DASHSCOPE_BASE_URL`、`QWEN_MODEL`
  - 使用路径：`backend/config/settings.py`、`backend/util/common_util/llm_stream_utils.py`、`backend/retrieval/config.py`
- Doubao / ARK - 可选 provider。
  - SDK / 客户端：OpenAI-compatible `openai.AsyncOpenAI`、`langchain_openai.ChatOpenAI`；依赖声明包含 `volcengine-python-sdk[ark]`
  - 认证：`ARK_API_KEY`
  - 配置：`ARK_BASE_URL`、`DOUBAO_MODEL`
  - 使用路径：`backend/config/settings.py`、`backend/util/common_util/llm_stream_utils.py`
- LangSmith - 可选 tracing。
  - SDK / 客户端：LangChain/LangSmith 通过环境变量读取
  - 认证：`LANGSMITH_API_KEY`
  - 配置：`LANGSMITH_TRACING`、`LANGSMITH_ENDPOINT`、`LANGSMITH_PROJECT`
  - 使用路径：`backend/config/settings.py`、`backend/tests/config/test_settings_langsmith.py`

**智能体运行时：**
- DeepAgents content agent - 初次生成 `generation_mode=agent` 的正文生成智能体。
  - SDK / 客户端：`deepagents.create_deep_agent`
  - 认证：使用请求选择的 LLM provider 配置
  - 使用路径：`backend/agents/generation/content_agents.py`、`backend/agents/generation/workspace.py`、`backend/agents/generation/model_factory.py`
- DeepAgents task context assistant - 右侧聊天 agent run 前置流，只允许受控 rewrite skill 和只读摘要工具。
  - SDK / 客户端：`deepagents.create_deep_agent`、`CompositeBackend`、`FilesystemBackend`
  - 认证：使用请求选择的 LLM provider 配置
  - 使用路径：`backend/agents/task_context_assistant/factory.py`、`backend/agents/task_context_assistant/tools.py`、`backend/services/agent_run_service.py`
- LangChain comment agent - 批注生成、锚点校验和写回提交。
  - SDK / 客户端：`langchain.agents.create_agent`、`ToolCallLimitMiddleware`
  - 认证：使用请求选择的 LLM provider 配置
  - 使用路径：`backend/agents/comments/comment_agent.py`、`backend/agents/comments/tools.py`

**外部招标详情：**
- 招标详情系统 - 按招标编号拉取项目数据并归一化表单分派所需 type。
  - SDK / 客户端：`requests.get`
  - 认证：未检测到单独认证字段；URL 来自配置
  - 配置：`TENDER_DATA_API_URL`、`EXTERNAL_REQUEST_TIMEOUT_SECONDS`
  - 使用路径：`backend/util/common_util/fetch_tender_data.py`、`backend/api/tender.py`

**模板候选系统：**
- 模板候选外部系统 - 获取候选、按年份阻断过旧模板、代理下载、选择后落入上传区。
  - SDK / 客户端：`requests.get`
  - 认证：未检测到单独认证字段；URL 和下载主机白名单来自配置
  - 配置：`TEMPLATE_CANDIDATE_API_URL`、`TEMPLATE_CANDIDATE_ALLOWED_HOSTS`、`TEMPLATE_CANDIDATE_RANKING_LLM_PROVIDER`、`EXTERNAL_REQUEST_TIMEOUT_SECONDS`
  - 使用路径：`backend/util/common_util/template_candidates.py`、`backend/api/template_candidates.py`、`backend/services/template_candidate_ranking_service.py`

**检索 / 向量搜索：**
- Qdrant - 批注 bad case hybrid 检索的向量层。
  - SDK / 客户端：direct `httpx.Client`
  - 认证：`QDRANT_API_KEY`
  - 配置：`QDRANT_URL`、`COMMENT_BAD_CASE_COLLECTION`
  - 使用路径：`backend/retrieval/qdrant_store.py`、`backend/retrieval/config.py`、`backend/retrieval/comment_bad_case_runtime.py`
- Embedding API - 为 bad case 检索生成查询向量。
  - SDK / 客户端：OpenAI-compatible `openai.OpenAI`
  - 认证：`EMBEDDING_API_KEY`，可 fallback 到 `DASHSCOPE_API_KEY`
  - 配置：`EMBEDDING_BASE_URL`、`SILICONFLOW_BASE_URL`、`EMBEDDING_MODEL`、`EMBEDDING_DIMENSIONS`
  - 使用路径：`backend/retrieval/config.py`、`backend/retrieval/embeddings.py`
- BM25 fallback - Qdrant、embedding 或 hybrid 检索任一环节失败时回退到进程内 BM25。
  - SDK / 客户端：本地 Python 实现
  - 认证：不适用
  - 使用路径：`backend/retrieval/bm25.py`、`backend/retrieval/comment_bad_case_runtime.py`
- 运行时消费方 - bad case context 注入 `generate_comments`、自主批注 `comment_agent` 和 `comment_supplement`；rewrite 不触发该检索。
  - 使用路径：`backend/nodes/common_word_nodes/generate_comments.py`、`backend/nodes/common_word_nodes/comment_agent.py`、`docs/backend.md`、`docs/interfaces-runtime.md`

**本地 Word COM：**
- Microsoft Word/WPS COM - Word 文档读取、写入、批注、样式回填、诊断和 `.doc/.docx` 保存。
  - SDK / 客户端：`pywin32` / `pythoncom` / `win32com.client`
  - 认证：不适用
  - 使用路径：`backend/util/word_util/word_application_util.py`、`backend/util/word_util/word_com_manager.py`、`backend/util/word_util/word_diagnostics.py`

## 数据存储

**数据库：**
- 外部数据库未检测到。
- ORM、migration、SQL client 未检测到。
- 任务、取消事件、任务结果、SSE event buffer、会话 rewrite history 和检索 runtime cache 均为进程内状态。
  - 使用路径：`backend/task/task_queue_manager.py`、`backend/core/sse_manager.py`、`backend/services/conversation_service.py`、`backend/retrieval/comment_bad_case_runtime.py`

**文件存储：**
- 本地文件系统是主要持久化层。
- 上传文件、模板选择结果、生成产物和下载文件位于 `settings.UPLOAD_DIR`。
  - 配置：`UPLOAD_DIR`、`MAX_UPLOAD_SIZE`、`ALLOWED_EXTENSIONS`
  - 使用路径：`backend/config/settings.py`、`backend/util/common_util/upload_storage.py`、`backend/api/upload.py`、`backend/api/download.py`
- Content agent workspace 位于 `backend/prompts_log/content_agent_workspace/`，由 `backend/agents/generation/workspace.py` 管理。
- Comment agent audit 位于 `backend/prompts_log/comment_agent_audit/`，由 `backend/agents/comments/workspace.py` 管理。
- 批注 bad case 源文件位于 `backend/retrieval/bad_cases/`，加载器在 `backend/retrieval/bad_case_loader.py`。
- 进度、执行、prompt、skill audit、SSE 日志由 `backend/util/log_util/` 管理，默认日志根与 `LOG_DIR` 和 `backend/logs/` 相关。

**缓存：**
- SSE events：按 task 维护进程内缓存，受 `SSE_MAX_EVENTS_PER_TASK` 和 `SSE_EVENT_TTL` 控制；路径是 `backend/core/sse_manager.py`。
- Task queue：进程内单例；路径是 `backend/task/task_queue_manager.py`。
- Conversation runtime：进程内单例，含 heartbeat 和 rewrite history；路径是 `backend/services/conversation_service.py`。
- Bad case BM25 index：进程内缓存，按 markdown 文件签名失效；路径是 `backend/retrieval/comment_bad_case_runtime.py`。
- Redis、Memcached 或独立 cache service：未检测到。

## 认证与身份

**认证提供方：**
- 未检测到强制执行的 API 鉴权层。
  - 实现：`backend/main.py` 注册的业务 routers 未检测到统一 `Depends(...)` auth dependency。
  - 依赖：`python-jose[cryptography]`、`passlib[bcrypt]` 在 `backend/requirements.txt` 中声明，但不是当前 API router 的统一鉴权实现。

**身份 / 会话：**
- `conversation_id` 用于 rewrite history、agent run 上下文和补充批注状态连续性。
  - 使用路径：`backend/models/generate.py`、`backend/models/agent_run.py`、`backend/services/conversation_service.py`
- `user_session_id` 用于任务归属和队列状态。
  - 使用路径：`backend/task/task_queue_manager.py`、`backend/models/task.py`
- `task_id` 用于任务队列、SSE topic、日志命名、下载结果和心跳取消。
  - 使用路径：`backend/task/task_queue_manager.py`、`backend/core/sse_manager.py`、`backend/services/document_service.py`

## 监控与可观测性

**错误追踪：**
- 外部 error tracking service 未检测到。
- 可选 LangSmith tracing 由 `backend/config/settings.py` 中的 `Settings.apply_langsmith_environment()` 暴露给 LangChain/LangSmith SDK。

**日志：**
- JSON stdout logging：`backend/main.py`
- 用户进度日志：`backend/util/log_util/progress_log.py`
- 执行诊断：`backend/util/log_util/execution_log.py`
- Prompt 日志：`backend/util/log_util/prompt_log.py`
- Skill 审计日志：`backend/util/log_util/skill_audit_log.py`
- SSE 日志桥：`backend/util/log_util/sse_log_handler.py`
- 日志清理：`backend/util/log_util/log_cleanup.py`
- Agent 日志命名和 scrub helper：`backend/agents/log_naming.py`、`backend/agents/task_context_assistant/logging.py`

**SSE 可观测性：**
- 事件模型来源：`backend/models/sse.py`
- Manager 来源：`backend/core/sse_manager.py`
- 事件类别包括 `log`、`llm`、`progress`、`node_start`、`node_complete`、`agent_step`、`done`、`error`、`heartbeat`。
- `Last-Event-ID` 断线重连支持在 `backend/api/stream.py` 和 `backend/core/sse_manager.py`。

## CI/CD 与部署

**托管：**
- 未检测到生产托管配置。
- 本地 ASGI 入口是 `backend/main.py`。
- Windows 开发入口是 `scripts/start-dev-win.ps1`；兼容入口是 `scripts/start-dev.ps1`；WSL 协作入口是 `scripts/start-dev-wsl.sh`。

**CI 流水线：**
- 后端扫描未检测到 `.github/workflows` 或后端专用 CI 配置。
- 完整 Word COM 验证需要 Windows + Word/WPS COM；无 COM CI 只能覆盖 no-COM 单元测试、API shape、service、prompt、retrieval 和 helper 纯逻辑。

## 环境配置

**按功能划分的必需环境变量：**
- DeepSeek LLM：`DEEPSEEK_API_KEY`，可覆盖 `DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`。
- Qwen/DashScope LLM：`DASHSCOPE_API_KEY`，可覆盖 `DASHSCOPE_BASE_URL`、`QWEN_MODEL`。
- Doubao/ARK LLM：`ARK_API_KEY`，可覆盖 `ARK_BASE_URL`、`DOUBAO_MODEL`。
- 可选 LangSmith：`LANGSMITH_TRACING`、`LANGSMITH_ENDPOINT`、`LANGSMITH_API_KEY`、`LANGSMITH_PROJECT`。
- 外部招标/模板：`TENDER_DATA_API_URL`、`TEMPLATE_CANDIDATE_API_URL`、`TEMPLATE_CANDIDATE_ALLOWED_HOSTS`、`EXTERNAL_REQUEST_TIMEOUT_SECONDS`。
- 模板候选 AI 排序：`TEMPLATE_CANDIDATE_RANKING_LLM_PROVIDER`。
- 文件、任务、SSE、日志：`UPLOAD_DIR`、`MAX_UPLOAD_SIZE`、`ALLOWED_EXTENSIONS`、`LOCK_FILE_PATH`、`LOCK_TIMEOUT`、`LOCK_WAIT_TIMEOUT`、`TASK_TOTAL_NODES`、`TASK_HEARTBEAT_TIMEOUT`、`TASK_CLEANUP_INTERVAL`、`SSE_MAX_EVENTS_PER_TASK`、`SSE_EVENT_TTL`、`SSE_HEARTBEAT_INTERVAL`、`LOG_DIR`。
- 检索：`QDRANT_URL`、`QDRANT_API_KEY`、`COMMENT_BAD_CASE_COLLECTION`、`EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL`、`SILICONFLOW_BASE_URL`、`EMBEDDING_MODEL`、`EMBEDDING_DIMENSIONS`。

**密钥位置：**
- `backend/.env` 文件存在，包含本地私有配置；不得读取、引用或提交真实值。
- `backend/.env.example` 文件存在，只作为变量名和占位结构参考。
- 文档、日志、测试夹具和最终回复只允许记录变量名，不记录 secret value。

## Webhook 与回调

**入站：**
- 第三方入站 webhook：未检测到。
- 浏览器到后端任务流：`GET /api/stream/{task_id}` 通过 SSE，文件 `backend/api/stream.py`。
- 浏览器到后端 agent 流：`POST /api/agent/runs/stream` 返回 NDJSON，文件 `backend/api/agent.py`。
- 浏览器到后端 chat stream helper 输出 NDJSON 行，文件 `backend/services/chat_stream_service.py`。

**出站：**
- LLM provider 调用来自 `backend/util/common_util/llm_stream_utils.py`、`backend/services/chat_stream_service.py`、`backend/agents/generation/model_factory.py`。
- 招标详情外部 HTTP 调用来自 `backend/util/common_util/fetch_tender_data.py`。
- 模板候选列表、模板下载和模板选择落盘调用来自 `backend/util/common_util/template_candidates.py`、`backend/api/template_candidates.py`。
- Qdrant 和 embedding HTTP 调用来自 `backend/retrieval/qdrant_store.py`、`backend/retrieval/embeddings.py`。
- LangSmith tracing 环境变量由 `backend/config/settings.py` 暴露，启用时由 LangChain/LangSmith SDK 使用。

## 集成护栏

- 前端不得直接访问外部招标详情或模板候选 URL；统一走后端代理和白名单校验，证据在 `docs/interfaces-runtime.md`、`backend/api/template_candidates.py`。
- 模板候选下载必须保留 `TEMPLATE_CANDIDATE_ALLOWED_HOSTS` 校验；实现点是 `backend/util/common_util/template_candidates.py`。
- 文件下载必须保留 `settings.UPLOAD_DIR` containment 校验；实现点是 `backend/api/download.py`。
- 新增 LLM provider 时同步 `backend/models/generate.py`、`backend/config/settings.py`、`backend/util/common_util/llm_stream_utils.py`、`backend/agents/generation/model_factory.py` 和相关测试。
- 新增 SSE event 时同步 `backend/models/sse.py`、`backend/core/sse_manager.py`、前端 parser/types 和测试。
- Agent/chat NDJSON shape 改动时同步 `backend/services/chat_stream_service.py`、`backend/services/agent_run_service.py`、前端 parser/types 和测试。
- Word COM 写入必须继续经过后端任务队列、graph 锁、取消检查和进度包装；不得在 API route、service、前端或随意脚本中直接操作 COM，证据在 `docs/backend.md`。
- Retrieval 的 bad case 命中详情只进入后端 prompt/retrieval 审计，不进入 SSE、下载卡、任务结果或 `agent_step`，证据在 `docs/interfaces-runtime.md`。
- Agent run 审计日志只记录 scrub 后白名单字段；不要返回完整客户原文、真实密钥、私有路径、traceback 或下载路径，证据在 `docs/backend.md`、`docs/interfaces-runtime.md`、`backend/agents/task_context_assistant/logging.py`。

---

*集成审计：2026-06-09*
