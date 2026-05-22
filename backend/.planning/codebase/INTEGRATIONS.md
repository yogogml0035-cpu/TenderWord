# External Integrations

**Analysis Date:** 2026-05-22

**Scope:** Backend only: `backend/`, plus root setup files `README.md`, `scripts/start-dev.ps1`, and `scripts/start-dev-wsl.sh` where they define backend runtime boundaries.

## APIs & External Services

**LLM Providers:**
- DeepSeek - OpenAI-compatible streaming provider for generation, rewrite/edit, user routing, chat streaming, and template ranking; SDK/client is `openai.AsyncOpenAI` in `backend/util/common_util/llm_stream_utils.py` and `backend/services/chat_stream_service.py`, with auth/config from `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, and `DEEPSEEK_MODEL` in `backend/config/settings.py`.
- Doubao / Volcengine ARK - OpenAI-compatible streaming provider selected as `doubao`; SDK/client is `openai.AsyncOpenAI` in `backend/util/common_util/llm_stream_utils.py`, package support is declared as `volcengine-python-sdk[ark]` and `openai` in `backend/requirements.txt`, and auth/config comes from `ARK_API_KEY`, `ARK_BASE_URL`, and `DOUBAO_MODEL` in `backend/config/settings.py`.
- Qwen / DashScope - OpenAI-compatible streaming provider selected as `qwen`; SDK/client is `openai.AsyncOpenAI` in `backend/util/common_util/llm_stream_utils.py`, and auth/config comes from `DASHSCOPE_API_KEY`, `DASHSCOPE_BASE_URL`, and `QWEN_MODEL` in `backend/config/settings.py`.
- LLM timeout and retry boundaries - stream timeout is centralized as `LLM_STREAM_TIMEOUT_SECONDS` in `backend/config/settings.py`, enforced by `HeartbeatMonitor` and retry handling in `backend/util/common_util/llm_stream_utils.py`, and covered by `backend/tests/util/test_llm_stream_utils.py`.

**Tender Data APIs:**
- Tender project detail lookup - backend calls an external tender detail endpoint configured as `TENDER_DATA_API_URL`; implementation uses `requests.get(..., params={"tenderno": tender_no})` in `backend/util/common_util/fetch_tender_data.py` and is exposed through `GET /api/tender/{tender_no}` in `backend/api/tender.py`.
- Template candidate listing - backend calls an external template candidate endpoint configured as `TEMPLATE_CANDIDATE_API_URL`; implementation uses `requests.get` in `backend/util/common_util/template_candidates.py` and is exposed through `GET /api/template-candidates` in `backend/api/template_candidates.py`.
- Template file proxy/download - backend downloads candidate files from selected external URLs via `fetch_template_file()` in `backend/util/common_util/template_candidates.py`, proxies them via `GET /api/template-candidates/download` in `backend/api/template_candidates.py`, and persists selected files via `POST /api/template-candidates/select` in `backend/api/template_candidates.py`.

**Microsoft Word COM:**
- Word automation - backend creates, opens, saves, unprotects, and closes Word documents through `pythoncom` and `win32com.client` in `backend/util/word_util/word_application_util.py`.
- COM serialization - graph execution is protected by `CrossProcessFileLock` in `backend/graphs/base_graph.py`, and lower-level COM operations are serialized by `com_lock()` in `backend/util/word_util/word_com_manager.py`.
- Environment diagnostics - Word/WPS and pywin32 availability are checked by `backend/util/word_util/word_diagnostics.py` and CLI wrapper `backend/scripts/diagnose_word.py`.

**Frontend-Facing Streams:**
- Task progress stream - `GET /api/stream/{task_id}` returns Server-Sent Events from `backend/api/stream.py`, backed by event storage and heartbeats in `backend/core/sse_manager.py`.
- User message stream - `POST /api/user/stream` returns NDJSON from `backend/api/user.py`, using `UserGraph` in `backend/graphs/user_graph.py` and chat streaming helpers in `backend/services/chat_stream_service.py`.
- Task status/cancel/heartbeat - task polling and control are exposed through `backend/api/tasks.py`, mediated by `backend/services/task_service.py` and `backend/task/task_queue_manager.py`.

## Data Storage

**Databases:**
- No external database is used by the reviewed backend; task state is in memory in `backend/task/task_queue_manager.py`, conversation runtime state is in memory in `backend/services/conversation_service.py`, and SSE events are buffered in memory in `backend/core/sse_manager.py`.
- No database client is declared in the backend manifest `backend/requirements.txt`.

**File Storage:**
- Upload and generated-document storage is local filesystem storage rooted at `UPLOAD_DIR`, implemented by `backend/util/common_util/upload_storage.py` and guarded on download by `backend/api/download.py`.
- Template candidate selection saves downloaded external template bytes into the same upload storage helper through `persist_file_bytes()` in `backend/api/template_candidates.py` and `backend/util/common_util/upload_storage.py`.
- Prompt, rewrite, edit, and task audit artifacts are local files under `backend/prompts_log`, written by `backend/util/log_util/prompt_log.py` and `backend/util/log_util/skill_audit_log.py`.
- Runtime logs are local files under `settings.LOG_DIR`, written by queue-backed handlers in `backend/util/log_util/progress_log.py` and `backend/util/log_util/execution_log.py`; generated log directories are ignored by `.gitignore`.

**Caching:**
- Settings are cached with `@lru_cache` in `backend/config/settings.py`.
- SSE events are retained per task in memory with TTL and maximum count from `SSE_EVENT_TTL` and `SSE_MAX_EVENTS_PER_TASK` in `backend/config/settings.py`, implemented in `backend/core/sse_manager.py`.
- No Redis, Memcached, or external cache service is declared in `backend/requirements.txt`.

## Authentication & Identity

**Auth Provider:**
- No backend user-auth provider is wired into the reviewed API routes; routers are included directly in `backend/main.py`, and route files such as `backend/api/generate.py`, `backend/api/tasks.py`, `backend/api/user.py`, and `backend/api/template_candidates.py` do not define auth dependencies.
- Auth-like secret boundaries are outbound provider keys in `backend/config/settings.py`: `DEEPSEEK_API_KEY`, `ARK_API_KEY`, `DASHSCOPE_API_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_PUBLIC_KEY`.
- CORS allows credentials and includes the `Authorization` header in `backend/config/settings.py`, with middleware applied in `backend/main.py`.

## Monitoring & Observability

**Error Tracking:**
- No external error tracking client is wired in the backend runtime; active logging uses stdlib `logging` with JSON stdout formatting in `backend/main.py` and file-backed queue listeners in `backend/util/log_util/progress_log.py` and `backend/util/log_util/execution_log.py`.
- LangSmith/LangFuse configuration fields exist in `backend/config/settings.py`, but the reviewed backend logging implementation is local/stdout in `backend/main.py`, `backend/util/log_util/progress_log.py`, `backend/util/log_util/execution_log.py`, and `backend/util/log_util/sse_log_handler.py`.

**Logs:**
- User-facing progress logging uses `progress_log` in `backend/util/log_util/progress_log.py` and is bridged to SSE by `backend/util/log_util/sse_log_handler.py`.
- Execution audit logging for successful generate tasks uses `backend/util/log_util/execution_log.py`, called from `backend/services/document_service.py`.
- Prompt and task-skill audit logs use `backend/util/log_util/prompt_log.py` and `backend/util/log_util/skill_audit_log.py`, with rewrite/edit nodes writing audit stages in `backend/nodes/skills_nodes/rewrite_nodes.py` and `backend/nodes/skills_nodes/edit_nodes.py`.

## CI/CD & Deployment

**Hosting:**
- Production hosting is not declared in backend-scoped files; the backend ASGI entry is `backend.main:app` in `backend/main.py`.
- Local Windows development startup is `scripts/start-dev.ps1`, and WSL development delegates backend startup to Windows via `scripts/start-dev-wsl.sh`.

**CI Pipeline:**
- No backend CI pipeline file is present in the reviewed root listing; backend validation commands are documented in `README.md` and `AGENTS.md`, and tests live under `backend/tests/`.

## Environment Configuration

**Required env vars:**
- LLM provider keys and endpoints: `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL`, `ARK_API_KEY`, `ARK_BASE_URL`, `DOUBAO_MODEL`, `DASHSCOPE_API_KEY`, `DASHSCOPE_BASE_URL`, and `QWEN_MODEL` are declared in `backend/config/settings.py` and validated by `ensure_llm_env()` in `backend/util/common_util/llm_stream_utils.py`.
- LLM runtime behavior: `LLM_STREAM_TIMEOUT_SECONDS` and `TEMPLATE_CANDIDATE_RANKING_LLM_PROVIDER` are declared in `backend/config/settings.py` and used by `backend/util/common_util/llm_stream_utils.py` and `backend/services/template_candidate_ranking_service.py`.
- File and external HTTP behavior: `UPLOAD_DIR`, `MAX_UPLOAD_SIZE`, `ALLOWED_EXTENSIONS`, `TEMPLATE_CANDIDATE_API_URL`, `TENDER_DATA_API_URL`, `TEMPLATE_CANDIDATE_ALLOWED_HOSTS`, and `EXTERNAL_REQUEST_TIMEOUT_SECONDS` are declared in `backend/config/settings.py` and used by `backend/util/common_util/upload_storage.py`, `backend/util/common_util/template_candidates.py`, and `backend/util/common_util/fetch_tender_data.py`.
- Queue, lock, log, and SSE behavior: `LOCK_FILE_PATH`, `LOCK_TIMEOUT`, `LOCK_WAIT_TIMEOUT`, `LOG_DIR`, `LOG_QUEUE_MAXSIZE`, `PROGRESS_LOG_BACKUP_COUNT`, `EXECUTION_LOG_BACKUP_COUNT`, `SSE_MAX_EVENTS_PER_TASK`, `SSE_EVENT_TTL`, `SSE_HEARTBEAT_INTERVAL`, `TASK_TOTAL_NODES`, `TASK_HEARTBEAT_TIMEOUT`, and `TASK_CLEANUP_INTERVAL` are declared in `backend/config/settings.py` and used by `backend/graphs/base_graph.py`, `backend/core/sse_manager.py`, `backend/task/task_queue_manager.py`, `backend/util/log_util/progress_log.py`, and `backend/util/log_util/execution_log.py`.

**Secrets location:**
- Secrets are expected in environment variables or `backend/.env`; `backend/config/settings.py` loads `backend/.env`, and `README.md` instructs developers to create it from `backend/.env.example` without committing values.
- Do not read or quote `backend/.env`; `.gitignore` excludes `.env`, `.env.local`, and `.env.*.local`.

## Webhooks & Callbacks

**Incoming:**
- REST task creation/control endpoints are registered under `/api` in `backend/main.py`, with concrete routers in `backend/api/generate.py`, `backend/api/edit.py`, `backend/api/tasks.py`, `backend/api/tender.py`, `backend/api/upload.py`, `backend/api/download.py`, `backend/api/conversations.py`, and `backend/api/template_candidates.py`.
- Streaming endpoints are incoming long-lived responses: SSE via `backend/api/stream.py` and NDJSON via `backend/api/user.py`.
- No incoming third-party webhook endpoint is represented in the reviewed backend routers under `backend/api/`.

**Outgoing:**
- Outgoing LLM calls use OpenAI-compatible streaming over `openai.AsyncOpenAI` and `httpx.Timeout` in `backend/util/common_util/llm_stream_utils.py` and `backend/services/chat_stream_service.py`.
- Outgoing tender/template calls use `requests.get` in `backend/util/common_util/fetch_tender_data.py` and `backend/util/common_util/template_candidates.py`.
- Outgoing template file download is constrained by `TEMPLATE_CANDIDATE_ALLOWED_HOSTS` in `backend/config/settings.py` and `validate_template_download_url()` in `backend/util/common_util/template_candidates.py`.

---

*Integration audit: 2026-05-22*
