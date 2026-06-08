# 后端集成事实地图

**分析日期：** 2026-06-08

**范围：** `backend/` 对前端、外部 HTTP、LLM、Word COM、文件系统、检索、日志和本地运行环境的集成边界。`backend/.env` 文件存在但不读取内容。

## APIs & External Services

**Frontend API Boundary:**
- FastAPI routers 注册在 `backend/main.py`，统一挂载 `/api` 前缀，健康检查除外。
- 主要 endpoints:
  - `POST /api/generate` - 创建初次生成任务，文件 `backend/api/generate.py`
  - `GET /api/generate/{task_id}` - 获取生成任务状态，文件 `backend/api/generate.py`
  - `GET /api/stream/{task_id}` - SSE 任务流，文件 `backend/api/stream.py`
  - `GET /api/stream/{task_id}/status` - SSE 连接状态，文件 `backend/api/stream.py`
  - `GET /api/tasks`、`GET /api/tasks/{task_id}`、`DELETE /api/tasks/{task_id}`、`POST /api/tasks/{task_id}/heartbeat` - 任务管理，文件 `backend/api/tasks.py`
  - `POST /api/agent/runs/stream` - NDJSON agent run，文件 `backend/api/agent.py`
  - `POST /api/comment-supplement` - 补充批注任务，文件 `backend/api/comment_supplement.py`
  - `POST /api/upload`、`POST /api/upload/multiple` - 文件上传，文件 `backend/api/upload.py`
  - `GET /api/download/{file_path:path}` - 文件下载，文件 `backend/api/download.py`
  - `GET /api/tender/{tender_no}` - 招标详情代理，文件 `backend/api/tender.py`
  - `GET /api/template-candidates`、`GET /api/template-candidates/download`、`POST /api/template-candidates/select` - 模板候选代理，文件 `backend/api/template_candidates.py`
  - `POST /api/conversations/{conversation_id}/heartbeat` - 会话心跳，文件 `backend/api/conversations.py`
- Root health endpoints:
  - `/health`、`/health/ready`、`/health/live`、`/` 在 `backend/main.py`，不挂 `/api`。

**LLM Providers:**
- DeepSeek - 文本生成默认 provider。
  - SDK/Client: OpenAI-compatible client via `openai` / `httpx`
  - Auth: `DEEPSEEK_API_KEY`
  - Config: `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL`
  - Files: `backend/config/settings.py`, `backend/util/common_util/llm_stream_utils.py`
- Qwen / DashScope - 可选 LLM provider。
  - SDK/Client: OpenAI-compatible API through `langchain-openai` / HTTP
  - Auth: `DASHSCOPE_API_KEY`
  - Config: `DASHSCOPE_BASE_URL`, `QWEN_MODEL`
  - Files: `backend/config/settings.py`, `backend/util/common_util/llm_stream_utils.py`
- Doubao / ARK - 可选 LLM provider。
  - SDK/Client: `volcengine-python-sdk[ark]` and OpenAI-compatible usage in model factory
  - Auth: `ARK_API_KEY`
  - Config: `ARK_BASE_URL`, `DOUBAO_MODEL`
  - Files: `backend/config/settings.py`, `backend/util/common_util/llm_stream_utils.py`
- LangSmith - 可选 tracing environment exposure.
  - SDK/Client: LangChain/LangSmith environment variables
  - Auth: `LANGSMITH_API_KEY`
  - Config: `LANGSMITH_TRACING`, `LANGSMITH_ENDPOINT`, `LANGSMITH_PROJECT`
  - Files: `backend/config/settings.py`, `backend/tests/config/test_settings_langsmith.py`

**Agents:**
- DeepAgents content generation.
  - SDK/Client: `deepagents.create_deep_agent`
  - Auth: uses selected LLM provider config
  - Files: `backend/agents/generation/content_agents.py`, `backend/agents/generation/model_factory.py`
- DeepAgents task context assistant.
  - SDK/Client: `deepagents.create_deep_agent`
  - Auth: uses selected LLM provider config
  - Files: `backend/agents/task_context_assistant/factory.py`, `backend/services/agent_run_service.py`
- LangChain comment agent.
  - SDK/Client: `langchain.agents.create_agent`, `ToolCallLimitMiddleware`
  - Auth: uses selected LLM provider config
  - Files: `backend/agents/comments/comment_agent.py`, `backend/agents/comments/tools.py`

**External Tender Data:**
- 招标详情系统 - 按招标编号拉取项目数据。
  - SDK/Client: `requests.get`
  - Auth: 未检测到单独认证字段；URL 来自配置。
  - Config: `TENDER_DATA_API_URL`, `EXTERNAL_REQUEST_TIMEOUT_SECONDS`
  - Files: `backend/util/common_util/fetch_tender_data.py`, `backend/api/tender.py`

**Template Candidate System:**
- 模板候选外部系统 - 获取候选、代理下载、选择并落盘。
  - SDK/Client: `requests.get`
  - Auth: 未检测到单独认证字段；URL 和白名单来自配置。
  - Config: `TEMPLATE_CANDIDATE_API_URL`, `TEMPLATE_CANDIDATE_ALLOWED_HOSTS`, `TEMPLATE_CANDIDATE_RANKING_LLM_PROVIDER`
  - Files: `backend/util/common_util/template_candidates.py`, `backend/api/template_candidates.py`, `backend/services/template_candidate_ranking_service.py`

**Retrieval / Vector Search:**
- Qdrant - 批注坏案例向量检索诊断/实验入口，当前未接入主业务链路。
  - SDK/Client: direct `httpx.Client`
  - Auth: `QDRANT_API_KEY`
  - Config: `QDRANT_URL`, `COMMENT_BAD_CASE_COLLECTION`
  - Files: `backend/retrieval/qdrant_store.py`, `backend/retrieval/config.py`
- Embedding API - 为检索诊断/实验脚本生成查询和坏案例向量。
  - SDK/Client: HTTP client in `backend/retrieval/embeddings.py`
  - Auth: `EMBEDDING_API_KEY` 或 fallback `DASHSCOPE_API_KEY`
  - Config: `EMBEDDING_BASE_URL`, `SILICONFLOW_BASE_URL`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`
  - Files: `backend/retrieval/config.py`, `backend/retrieval/embeddings.py`

## Data Storage

**Databases:**
- 外部数据库未检测到。
- 任务、队列、SSE buffer、会话快照均为进程内存态。
  - Files: `backend/task/task_queue_manager.py`, `backend/core/sse_manager.py`, `backend/services/conversation_service.py`

**File Storage:**
- Local filesystem only.
- 上传、模板选择、生成产物和下载文件位于 `settings.UPLOAD_DIR`。
  - Config: `UPLOAD_DIR`, `MAX_UPLOAD_SIZE`, `ALLOWED_EXTENSIONS`
  - Files: `backend/config/settings.py`, `backend/util/common_util/upload_storage.py`, `backend/api/download.py`
- Agent/workspace audit 文件位于 `backend/prompts_log/`。
  - Files: `backend/agents/generation/workspace.py`, `backend/agents/comments/workspace.py`
- 日志文件位于 `backend/logs/` 或配置目录。
  - Files: `backend/util/log_util/`

**Caching:**
- SSE events: in-memory per-task cache in `backend/core/sse_manager.py`，受 `SSE_MAX_EVENTS_PER_TASK` 和 `SSE_EVENT_TTL` 控制。
- Task queue and conversation snapshots: in-memory cache/singletons in `backend/task/task_queue_manager.py` and `backend/services/conversation_service.py`。
- Redis/cache service: 未检测到。

## Authentication & Identity

**Auth Provider:**
- Not detected as an enforced API layer.
  - Implementation: `backend/main.py` 注册的业务 routers 未检测到统一 auth dependency。
  - Auth-related packages: `python-jose[cryptography]`、`passlib[bcrypt]` 在 `backend/requirements.txt` 中声明，但不是当前 API router 的统一鉴权实现。

**Identity / Session:**
- `conversation_id` 用于会话级 rewrite history 和补充批注上下文。
  - Files: `backend/models/generate.py`, `backend/models/agent_run.py`, `backend/services/conversation_service.py`
- `user_session_id` 用于任务归属和队列状态。
  - Files: `backend/task/task_queue_manager.py`, `backend/models/task.py`

## Monitoring & Observability

**Error Tracking:**
- 外部 error tracking 未检测到。
- 可选 LangSmith tracing config 存在，但不是强依赖。

**Logs:**
- JSON stdout logging: `backend/main.py`
- User progress log: `backend/util/log_util/progress_log.py`
- Execution diagnostics: `backend/util/log_util/execution_log.py`
- Prompt log: `backend/util/log_util/prompt_log.py`
- Skill audit log: `backend/util/log_util/skill_audit_log.py`
- SSE log bridge: `backend/util/log_util/sse_log_handler.py`
- Log cleanup: `backend/util/log_util/log_cleanup.py`

**SSE Observability:**
- Event types: `log`、`llm`、`progress`、`node_start`、`node_complete`、`agent_step`、`done`、`error`、`heartbeat`。
- Contract source: `backend/models/sse.py`
- Manager source: `backend/core/sse_manager.py`

## CI/CD & Deployment

**Hosting:**
- Not detected.
- Local ASGI entry: `backend/main.py`
- Root development scripts: `scripts/start-dev.ps1`, `scripts/start-dev-wsl.sh`

**CI Pipeline:**
- Not detected from backend scan.
- Full Word COM validation requires Windows + Word/WPS COM; CI without COM should only claim no-COM unit coverage.

## Environment Configuration

**Required env vars by feature:**
- LLM generate/rewrite/comment/template ranking:
  - `DEEPSEEK_API_KEY` for DeepSeek
  - `DASHSCOPE_API_KEY` for Qwen/DashScope
  - `ARK_API_KEY` for Doubao/ARK
- Optional LangSmith:
  - `LANGSMITH_TRACING`
  - `LANGSMITH_ENDPOINT`
  - `LANGSMITH_API_KEY`
  - `LANGSMITH_PROJECT`
- External tender/template:
  - `TENDER_DATA_API_URL`
  - `TEMPLATE_CANDIDATE_API_URL`
  - `TEMPLATE_CANDIDATE_ALLOWED_HOSTS`
- File/task/SSE:
  - `UPLOAD_DIR`
  - `LOCK_FILE_PATH`
  - `LOCK_TIMEOUT`
  - `TASK_HEARTBEAT_TIMEOUT`
  - `SSE_MAX_EVENTS_PER_TASK`
- Retrieval:
  - `QDRANT_URL`
  - `QDRANT_API_KEY`
  - `COMMENT_BAD_CASE_COLLECTION`
  - `EMBEDDING_API_KEY`
  - `EMBEDDING_BASE_URL`
  - `EMBEDDING_MODEL`

**Secrets location:**
- `backend/.env` 文件存在，包含本地私有配置；不得读取或引用内容。
- `backend/.env.example` 文件存在，可用于字段名参考；不得把真实值写入文档、日志或测试夹具。

## Webhooks & Callbacks

**Incoming:**
- Third-party inbound webhooks: None detected.
- Browser-to-backend task event subscription: `GET /api/stream/{task_id}` via SSE。
- Browser-to-backend agent run stream: `POST /api/agent/runs/stream` returns NDJSON。

**Outgoing:**
- LLM provider calls from `backend/util/common_util/llm_stream_utils.py` and agent model factory.
- 招标详情 external HTTP from `backend/util/common_util/fetch_tender_data.py`。
- 模板候选 external HTTP from `backend/util/common_util/template_candidates.py`。
- Qdrant and embedding HTTP from `backend/retrieval/`，当前用于批注坏案例检索诊断/实验。

## Integration Guardrails

- Frontend must not call external tender/template URLs directly; backend proxies and validates.
- Template candidate downloads must preserve allowed-host validation in `backend/util/common_util/template_candidates.py`.
- File downloads must preserve `settings.UPLOAD_DIR` path containment in `backend/api/download.py`.
- LLM provider additions must update `backend/models/generate.py`, `backend/config/settings.py`, `backend/util/common_util/llm_stream_utils.py`, agent model factory, and tests.
- SSE event additions must update `backend/models/sse.py`, `backend/core/sse_manager.py`, frontend event parsing, and tests.
- NDJSON event shape changes for agent/chat streams must update `backend/services/chat_stream_service.py`, `backend/services/agent_run_service.py`, frontend parser/types, and tests.
- Word COM operations must stay behind task queue and graph locks; no direct COM use from API routes or agent run tools.
- Agent run audit logs must use scrubbed whitelist fields from `backend/agents/task_context_assistant/logging.py`.

---

*后端集成审计：2026-06-08*
