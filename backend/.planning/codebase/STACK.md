# 后端技术栈

**分析日期：** 2026-06-16

**范围：** 仅覆盖 `backend/` 后端子项目。事实来源包括 `backend/` 源码、`backend/requirements.txt`、`backend/.env.example`、`backend/.planning/codebase/` 现有事实文档、`README.md`、`docs/backend.md`、`docs/interfaces-runtime.md`、`docs/knowledge-validation.md`、根级启动脚本 `scripts/start-dev.ps1`、`scripts/start-dev-win.ps1`、`scripts/start-dev-wsl.sh`，以及项目内 `.agents/skills/*/SKILL.md` 的轻量规则索引。`backend/.env` 存在但未读取；`frontend/.env.local` 未读取。

## 语言

**主要语言：**
- Python - FastAPI API、LangGraph 工作流、DeepAgents/LangChain 智能体、Word COM 自动化、任务队列、SSE、检索运行时和 pytest 测试；关键路径是 `backend/main.py`、`backend/api/`、`backend/services/`、`backend/graphs/`、`backend/nodes/`、`backend/util/word_util/`、`backend/retrieval/`、`backend/tests/`。

**辅助语言：**
- Markdown - rewrite skill、批注 bad case 知识、事实文档和项目协作规则；路径包括 `backend/skills/rewrite/SKILL.md`、`backend/retrieval/bad_cases/comment_bad_cases.md`、`backend/.planning/codebase/`、`.agents/skills/*/SKILL.md`。
- PowerShell - Windows 后端和前后端联调启动脚本；路径包括 `scripts/start-dev.ps1`、`scripts/start-dev-win.ps1`。
- Bash - WSL 协作启动入口；路径是 `scripts/start-dev-wsl.sh`。

## 运行时

**环境：**
- 完整 Word 生成运行时是 Windows Python + `pywin32` + 本机 Microsoft Word 或兼容 Word/WPS COM 环境；证据在 `README.md`、`docs/backend.md`、`backend/requirements.txt`、`backend/util/word_util/word_application_util.py`。
- `README.md` 写明 Windows Python 3.10+；自动启动脚本 `scripts/start-dev.ps1` 的 venv 创建逻辑实际查找 Python 3.11 或 3.12。
- WSL/Linux Python 只适合无 COM 单元测试或前端协作启动；真实 `.doc/.docx` 读取、写回、批注和保存闭环需要 Windows COM。
- ASGI 入口是 `backend/main.py`，`__main__` 分支调用 `uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG, log_config=None)`。
- 开发启动脚本在 `backend/` 工作目录执行 `python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload`，并限制 reload 目录为后端源码子目录；路径是 `scripts/start-dev.ps1`。
- 长任务由 `backend/services/document_service.py` 中的 `ThreadPoolExecutor(max_workers=4)` 承接，graph 执行时每个任务在线程内创建独立 asyncio loop；Word 写入仍通过 `TaskQueueManager` 公平队列、`CrossProcessFileLock` 和 `com_lock()` 串行保护。

**包管理器：**
- pip / venv - 后端依赖真源是 `backend/requirements.txt`。
- Windows venv 目录是 `backend/.venv/`；脚本会检测并避免误用 WSL/Linux venv。
- WSL/Linux venv 目录 `backend/.venv-linux/` 存在，但不是完整 Word COM 运行时。
- Lockfile：未检测到后端 lockfile。

## 框架

**核心：**
- FastAPI `>=0.115.0` - HTTP API、上传、下载、SSE、NDJSON agent run 和健康检查；入口在 `backend/main.py`，routers 在 `backend/api/`。
- Uvicorn `>=0.32.0` - ASGI 运行时；依赖在 `backend/requirements.txt`，启动脚本在 `scripts/start-dev.ps1`。
- Pydantic `>=2.9.0` - API model、任务模型、SSE 事件和 agent run 协议；路径包括 `backend/models/generate.py`、`backend/models/task.py`、`backend/models/sse.py`、`backend/models/agent_run.py`。
- Pydantic Settings `>=2.6.0` - 从环境变量和 `backend/.env` 加载设置；路径是 `backend/config/settings.py`。
- LangGraph `>=0.2.0` - 初次生成、rewrite skill、补充批注和 content agent 子图；路径包括 `backend/graphs/base_graph.py`、`backend/graphs/skill_graph.py`、`backend/graphs/comment_supplement_graph.py`、`backend/agents/generation/generate_agent_graph.py`。
- LangChain Core / LangChain OpenAI / LangChain DeepSeek - `ChatOpenAI` model factory、message/tool 类型和 agent 工具；路径包括 `backend/agents/generation/model_factory.py`、`backend/agents/comments/comment_agent.py`、`backend/agents/task_context_assistant/tools.py`。
- DeepAgents `>=0.6.4` - content generation agent 和 task context assistant；路径包括 `backend/agents/generation/content_agents.py`、`backend/agents/task_context_assistant/factory.py`。
- Word COM / pywin32 - Word 应用生命周期、COM 初始化、缓存修复、诊断和全局 COM 锁；路径包括 `backend/util/word_util/word_application_util.py`、`backend/util/word_util/word_com_manager.py`、`backend/util/word_util/word_diagnostics.py`。

**测试：**
- pytest `>=8.3.0` - 后端测试 runner；测试根目录是 `backend/tests/`。
- pytest-asyncio `>=0.24.0` - async API、service、graph、SSE 和 agent 测试；依赖在 `backend/requirements.txt`。

**构建 / 开发：**
- `python-multipart>=0.0.12` - FastAPI 上传文件解析；使用点是 `backend/api/upload.py`。
- `python-dotenv>=1.0.0` - retrieval 配置加载 `backend/.env`；使用点是 `backend/retrieval/config.py`。
- watchfiles 由 `uvicorn[standard]` 间接提供，开发脚本设置 `WATCHFILES_FORCE_POLLING` 和 `WATCHFILES_POLL_DELAY_MS`；路径是 `scripts/start-dev.ps1`。

> 日志与 HTTP client 说明：当前 `backend/requirements.txt` 已不再声明 `structlog`、`aiohttp`、`python-jose[cryptography]` 和 `passlib[bcrypt]`；主日志实现使用 stdlib `logging` 和 `backend/util/log_util/`，HTTP 调用主要使用 `requests` 与 `httpx`，业务 API 也未启用统一鉴权层（参见 INTEGRATIONS.md 与 CONCERNS.md）。

## 关键依赖

**关键：**
- `pywin32>=306; platform_system == "Windows"` - Word COM 自动化、诊断、`pythoncom.CoInitialize()` 和 `win32com.client.DispatchEx`；路径包括 `backend/util/word_util/word_application_util.py`、`backend/util/word_util/word_diagnostics.py`。
- `openai>=1.0.0` - OpenAI-compatible LLM streaming、chat stream 和 embedding；路径包括 `backend/util/common_util/llm_stream_utils.py`、`backend/services/chat_stream_service.py`、`backend/retrieval/embeddings.py`。
- `httpx>=0.27.0` - OpenAI-compatible timeout、chat stream、Qdrant HTTP client；路径包括 `backend/util/common_util/llm_stream_utils.py`、`backend/services/chat_stream_service.py`、`backend/retrieval/qdrant_store.py`。
- `requests>=2.32.0` - 外部招标详情、模板候选列表和模板文件代理下载；路径包括 `backend/util/common_util/fetch_tender_data.py`、`backend/util/common_util/template_candidates.py`、`backend/api/template_candidates.py`。
- `langgraph>=0.2.0` - `StateGraph` 工作流编排；路径是 `backend/graphs/`。
- `deepagents>=0.6.4` - DeepAgents 主智能体、文件系统 backend 和受控 skill workspace；路径包括 `backend/agents/generation/content_agents.py`、`backend/agents/task_context_assistant/factory.py`。

**基础设施：**
- `langchain-openai>=1.2.0` - `ChatOpenAI` 统一 model factory；路径是 `backend/agents/generation/model_factory.py`。
- `langchain-core>=0.3.0` - message、tool、runnable 类型；路径包括 `backend/agents/comments/comment_agent.py`、`backend/agents/comments/tools.py`。
- `langchain-deepseek>=0.1.0` - 依赖已声明；当前主要 provider 调用路径通过 OpenAI-compatible base URL 和 `langchain_openai.ChatOpenAI`。
- `volcengine-python-sdk[ark]>=1.0.0` - ARK/Doubao 依赖已声明；当前 provider 配置同样走 OpenAI-compatible base URL，配置在 `backend/config/settings.py`。

## 配置

**环境：**
- 配置类真源：`backend/config/settings.py`。
- 私有配置文件：`backend/.env` 文件存在；只允许记录变量名，不读取或引用真实值。
- 示例配置：`backend/.env.example` 文件存在；本次只用于确认变量名和占位结构。
- `Settings.model_config` 指向 `backend/.env`，`case_sensitive=True`，`extra="ignore"`。
- Retrieval 运行时另有 `backend/retrieval/config.py`，会通过 `python-dotenv` 加载 `backend/.env`；加载失败时有手写 fallback 读取逻辑，因此日志和文档都不得输出真实 key 值。
- 项目内 `.agents/skills/ai-coding-first/SKILL.md` 和 `.agents/skills/gsd-map-codebase/SKILL.md` 要求子项目 `.planning/codebase/` 文档使用中文、路径相对仓库根目录、禁止读取真实密钥文件。

**关键配置区域：**
- App/server/CORS：`APP_NAME`、`APP_VERSION`、`DEBUG`、`HOST`、`PORT`、`CORS_*`。
- LLM providers：`DEEPSEEK_BASE_URL`、`DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL`、`ARK_BASE_URL`、`ARK_API_KEY`、`DOUBAO_MODEL`、`DASHSCOPE_BASE_URL`、`DASHSCOPE_API_KEY`、`QWEN_MODEL`、`LLM_STREAM_TIMEOUT_SECONDS`。
- LangSmith tracing：`LANGSMITH_TRACING`、`LANGSMITH_ENDPOINT`、`LANGSMITH_API_KEY`、`LANGSMITH_PROJECT`；环境回写在 `Settings.apply_langsmith_environment()`。
- 上传和产物：`UPLOAD_DIR`、`MAX_UPLOAD_SIZE`、`ALLOWED_EXTENSIONS`。
- 外部招标和模板：`TENDER_DATA_API_URL`、`TEMPLATE_CANDIDATE_API_URL`、`TEMPLATE_CANDIDATE_ALLOWED_HOSTS`、`EXTERNAL_REQUEST_TIMEOUT_SECONDS`、`TEMPLATE_CANDIDATE_RANKING_LLM_PROVIDER`。
- 锁、任务、SSE、日志：`LOCK_FILE_PATH`、`LOCK_TIMEOUT`、`LOCK_WAIT_TIMEOUT`、`TASK_TOTAL_NODES`、`TASK_HEARTBEAT_TIMEOUT`、`TASK_CLEANUP_INTERVAL`、`SSE_MAX_EVENTS_PER_TASK`、`SSE_EVENT_TTL`、`SSE_HEARTBEAT_INTERVAL`、`LOG_*`。
- 检索：`QDRANT_URL`、`QDRANT_API_KEY`、`COMMENT_BAD_CASE_COLLECTION`、`EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL`、`SILICONFLOW_BASE_URL`、`EMBEDDING_MODEL`、`EMBEDDING_DIMENSIONS`。
- 招标类型、锚点、字号、content mode 和受保护字段 profile：`backend/config/tender_config.py`。

**构建：**
- 后端专用 `pyproject.toml`、`pytest.ini`、`tox.ini`、`Dockerfile`、`docker-compose.yml`、CI workflow 未检测到。
- 格式化/lint 配置未检测到后端专用 ruff、black、mypy 或 biome 配置。
- 测试组织由 `backend/tests/` 和依赖 `pytest`、`pytest-asyncio` 体现。

## 平台要求

**开发：**
- Windows 10/11、本机 Word 或兼容 COM 的 Office 环境、Windows Python、`backend/.venv`、`backend/.env` 和可写 `UPLOAD_DIR` 是完整后端开发闭环的前置条件。
- 后端依赖安装以 `backend/requirements.txt` 为准：

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
copy .env.example .env
```

- Windows 启动入口：

```powershell
cd <repo>
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-dev-win.ps1
```

- 只启动后端：

```powershell
cd <repo>
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-dev-win.ps1 -BackendOnly
```

- WSL 协作启动入口会在 Windows 侧启动后端、在 WSL 侧启动前端：

```bash
./scripts/start-dev-wsl.sh
```

**生产：**
- 托管平台、容器镜像、CI/CD 和生产部署配置未检测到。
- 若生产需要真实 Word 生成，必须提供 Windows Python、pywin32、Word/WPS COM、`msvcrt` 文件锁可用环境、可写 `UPLOAD_DIR`、至少一个可用 LLM provider key，以及外部招标/模板和可选检索服务网络访问。
- `/health`、`/health/ready`、`/health/live` 位于 `backend/main.py`，只代表应用进程层状态；`/health/ready` 中 `upload_dir_accessible` 当前是 TODO 占位，不代表上传目录、Word COM、LLM、Qdrant 或外部 HTTP 可用。

## 验证入口

**后端测试：**

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -v
```

**Word COM 诊断：**

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\diagnose_word.py
```

**文档变更检查：**

```bash
git diff --check
```

---

*技术栈分析：2026-06-16*
