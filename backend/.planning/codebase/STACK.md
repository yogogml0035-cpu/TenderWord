# 后端技术栈

**分析日期：** 2026-06-29

**范围：** 本文只覆盖 `backend/` 子项目。事实来源包括 `backend/requirements.txt`、`backend/.env.example`、`backend/main.py`、`backend/config/settings.py`、`backend/config/tender_config.py`、`backend/api/`、`backend/services/`、`backend/graphs/`、`backend/agents/`、`backend/nodes/`、`backend/retrieval/`、`backend/helper/`、`backend/util/`、`backend/tests/conftest.py`、`docs/backend.md`、`docs/interfaces-runtime.md`、`scripts/start-dev.ps1`、`scripts/start-dev-win.ps1`、`scripts/start-dev-wsl.sh`。`backend/.env` 与 `backend/.env.example` 均存在；本文档只引用配置键名与 `.env.example` 中的示例值，不读取或泄露 `.env` 真实值。

## 语言

**主要语言：**
- Python 3.12.10 - 当前 `backend/.venv/Scripts/python.exe --version` 返回 `Python 3.12.10`；后端 API、任务队列、LangGraph graph、DeepAgents/LangChain 智能体、Word COM 自动化、检索运行时和 pytest 测试均在 Python 中实现，核心路径包括 `backend/main.py`、`backend/api/`、`backend/services/`、`backend/graphs/`、`backend/nodes/`、`backend/agents/`、`backend/retrieval/`、`backend/helper/`、`backend/util/` 和 `backend/tests/`。

**辅助语言：**
- Markdown - 后端 rewrite skill、bad case 知识、事实文档和项目规则；路径包括 `backend/skills/rewrite/`、`backend/retrieval/bad_cases/`、`backend/.planning/codebase/` 和 `.agents/skills/*/SKILL.md`。
- PowerShell - Windows 原生开发启动和依赖准备；路径包括 `scripts/start-dev.ps1`、`scripts/start-dev-win.ps1`。
- Bash - WSL 协作启动入口；路径是 `scripts/start-dev-wsl.sh`。

## 运行时

**环境：**
- 完整后端闭环是 Windows Python + `pywin32` + 本机 Microsoft Word 或兼容 Word/WPS COM；依据是 `docs/backend.md`、`backend/requirements.txt`、`backend/util/word_util/word_application_util.py` 和 `backend/util/word_util/word_diagnostics.py`。
- 启动脚本 `scripts/start-dev.ps1` 的 `Test-PythonCommand` 要求 Windows Python 3.11+（`sys.version_info >= (3, 11)`），并优先按 `py.exe -3.12`、`py.exe -3.11`、`py.exe -3` 顺序探测，最后回退 `python.exe`；实际 venv 是 Python 3.12.10。
- WSL/Linux 只适合前端协作和无 COM 逻辑验证；真实 `.doc/.docx` 读取、写回、批注和保存需要 Windows COM。
- ASGI 入口是 `backend/main.py`，模块级 `app = create_application()` 注册 FastAPI app；`__main__` 分支调用 `uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG, log_config=None)`。
- Windows 后端开发启动由 `scripts/start-dev.ps1` 在 `backend/` 目录内运行 `python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload`，并显式为每个源码子目录（`agents`、`api`、`config`、`core`、`graphs`、`helper`、`models`、`nodes`、`prompts`、`services`、`skills`、`states`、`task`、`util`）设置 `--reload-dir`，避免 watchfiles 扫到 `.venv-linux` 等目录；同时设置 `WATCHFILES_FORCE_POLLING=true`、`WATCHFILES_POLL_DELAY_MS=300`。`scripts/start-dev-win.ps1` 是显式 Windows wrapper。
- 启动前 `scripts/start-dev.ps1` 会执行后端预检查 `python -c "import asyncio; import fastapi; import uvicorn; import pydantic_settings; import backend.main"`，失败会尝试重装依赖后再检查一次。
- WSL 协作启动由 `scripts/start-dev-wsl.sh` 通过 Windows PowerShell 以 `-BackendOnly` 启动后端，再在 WSL 当前终端启动前端。
- 长任务由 `backend/services/document_service.py` 提交到线程池；Word 写入仍必须经过 `backend/task/task_queue_manager.py` 的公平队列、`backend/graphs/base_graph.py` 的 `CrossProcessFileLock` 和 `backend/util/word_util/word_com_manager.py` 的 `com_lock()`。

**包管理器：**
- pip / venv - 依赖真源是 `backend/requirements.txt`。
- Windows venv 目录是 `backend/.venv/`；`scripts/start-dev.ps1` 的 `Ensure-WindowsBackendVenv` 会识别并移走 WSL/Linux 的 `.venv`（重命名为 `.venv-linux`）或不完整的 `.venv`（`.venv-backup`），避免误用非 Windows Python。
- Lockfile：未检测到后端 lockfile。

## 框架

**核心：**
- FastAPI `>=0.115.0` - HTTP API、上传、下载、SSE、NDJSON agent run 和健康检查；入口在 `backend/main.py`，routers 在 `backend/api/`。
- Uvicorn `>=0.32.0`（`uvicorn[standard]`）- ASGI 运行时；依赖在 `backend/requirements.txt`，启动入口在 `backend/main.py` 和 `scripts/start-dev.ps1`。
- Pydantic `>=2.9.0` - API 请求/响应、任务状态、SSE event、agent run 协议和领域模型；路径包括 `backend/models/generate.py`、`backend/models/task.py`、`backend/models/sse.py`、`backend/models/agent_run.py`、`backend/models/template_candidates.py`、`backend/models/tender.py`、`backend/models/upload.py`、`backend/models/common.py`。
- Pydantic Settings `>=2.6.0` - 从环境变量和 `backend/.env` 加载配置；实现是 `backend/config/settings.py`。
- LangGraph `>=0.2.0` - `StateGraph` 工作流编排；初次生成、rewrite skill、补充批注、各招标类型 graph 和生成 agent 子图；路径包括 `backend/graphs/base_graph.py`、`backend/graphs/skill_graph.py`、`backend/graphs/comment_supplement_graph.py`、`backend/graphs/*_tender_graph.py`（gjgk、gngk_fw_cz、gngk_fw_zc、gngk_hw_cz、gngk_hw_zc、xjcg）、`backend/agents/generation/*_agent_graph.py`。
- LangChain Core / LangChain OpenAI / LangChain DeepSeek - message、tool、`ChatOpenAI` model factory 和 agent 工具类型；路径包括 `backend/agents/generation/model_factory.py`、`backend/agents/comments/comment_agent.py`、`backend/agents/comments/tools.py`、`backend/agents/task_context_assistant/tools.py`。
- DeepAgents `>=0.6.4` - content generation agent、task context assistant、受控 filesystem backend 和 skill workspace；路径包括 `backend/agents/generation/content_agents.py`、`backend/agents/generation/workspace.py`、`backend/agents/task_context_assistant/factory.py`。
- Word COM / pywin32 - Word 应用生命周期、COM 初始化、缓存修复、诊断、读写、批注和全局 COM 锁；路径包括 `backend/util/word_util/word_application_util.py`、`backend/util/word_util/word_com_manager.py`、`backend/util/word_util/word_diagnostics.py`、`backend/util/word_util/word_extraction_utils.py`。

**测试：**
- pytest `>=8.3.0` - 后端测试 runner；测试根目录是 `backend/tests/`。
- pytest-asyncio `>=0.24.0` - async API、service、graph、SSE 和 agent 测试。未检测到 `pytest.ini`、`pyproject.toml`、`setup.cfg`、`tox.ini` 中的 `asyncio_mode` 配置，因此 pytest-asyncio 运行在默认 strict 模式，async 测试需显式标注 `@pytest.mark.asyncio`（测试中确实使用该标记）。

**构建/开发：**
- `python-multipart>=0.0.12` - FastAPI 上传文件解析；使用点是 `backend/api/upload.py`。
- `python-dotenv>=1.0.0` - retrieval 运行时加载 `backend/.env`；使用点是 `backend/retrieval/config.py`。
- `uvicorn[standard]` 间接提供开发 reload 与 watchfiles 能力；`scripts/start-dev.ps1` 设置 watch 目录和轮询参数。

## 关键依赖

**关键：**
- `pywin32>=306; platform_system == "Windows"` - Word COM 自动化、`pythoncom.CoInitialize()`、`win32com.client.DispatchEx` 和 COM 诊断；路径包括 `backend/util/word_util/word_application_util.py`、`backend/util/word_util/word_diagnostics.py`。
- `openai>=1.0.0` - OpenAI-compatible LLM streaming、chat stream 和 embedding 调用；路径包括 `backend/util/common_util/llm_stream_utils.py`、`backend/services/chat_stream_service.py`、`backend/retrieval/embeddings.py`。
- `httpx>=0.27.0` - OpenAI-compatible timeout、chat stream 和 Qdrant HTTP client；路径包括 `backend/util/common_util/llm_stream_utils.py`、`backend/services/chat_stream_service.py`、`backend/retrieval/qdrant_store.py`。
- `requests>=2.32.0` - 外部招标详情、模板候选列表和模板文件代理下载；路径包括 `backend/util/common_util/fetch_tender_data.py`、`backend/util/common_util/template_candidates.py`、`backend/api/template_candidates.py`。
- `langgraph>=0.2.0` - `StateGraph` 工作流编排；路径是 `backend/graphs/` 和 `backend/agents/generation/*_agent_graph.py`。
- `deepagents>=0.6.4` - DeepAgents 主智能体、子智能体和受控文件系统 backend；路径包括 `backend/agents/generation/content_agents.py`、`backend/agents/task_context_assistant/factory.py`。

**基础设施：**
- `langchain-openai>=1.2.0` - `ChatOpenAI` 统一 model factory；路径是 `backend/agents/generation/model_factory.py`。
- `langchain-core>=0.3.0` - tool、message、runnable 类型；路径包括 `backend/agents/comments/tools.py`、`backend/agents/comments/comment_agent.py`。
- `langchain-deepseek>=0.1.0` - 依赖已声明；当前主要 provider 调用路径通过 OpenAI-compatible base URL 和 `langchain_openai.ChatOpenAI`。
- `volcengine-python-sdk[ark]>=1.0.0` - ARK/Doubao 依赖已声明；当前 provider 配置同样通过 OpenAI-compatible base URL 调用，配置在 `backend/config/settings.py`。

## 配置

**环境：**
- 配置类真源是 `backend/config/settings.py`。
- `Settings.model_config` 指向 `backend/.env`，`env_file_encoding="utf-8"`，`case_sensitive=True`，`extra="ignore"`。
- `settings.apply_langsmith_environment()` 会把 LangSmith 相关配置写回进程环境，供 LangChain/LangSmith SDK 使用；模块加载时已自动调用一次（`settings = get_settings(); settings.apply_langsmith_environment()`）。
- Retrieval 另有 `backend/retrieval/config.py`，会通过 `python-dotenv` 加载 `backend/.env`；如果 `python-dotenv` 未加载成功，会用 fallback 解析该文件。文档和日志只能记录变量名，不能输出真实值。
- `.agents/skills/ai-coding-first/SKILL.md` 和 `.agents/skills/gsd-map-codebase/SKILL.md` 要求子项目 `.planning/codebase/` fact docs 使用中文，并禁止读取或泄露真实密钥文件。

**关键配置区域：**
- App/server/CORS：`APP_NAME`、`APP_VERSION`、`DEBUG`、`HOST`、`PORT`、`CORS_ORIGINS`、`CORS_ALLOW_CREDENTIALS`、`CORS_ALLOW_METHODS`、`CORS_ALLOW_HEADERS`。
- LLM providers：`DEEPSEEK_BASE_URL`、`DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL`、`ARK_BASE_URL`、`ARK_API_KEY`、`DOUBAO_MODEL`、`DASHSCOPE_BASE_URL`、`DASHSCOPE_API_KEY`、`QWEN_MODEL`、`LLM_STREAM_TIMEOUT_SECONDS`。
- LLM 默认模型与调用参数（`backend/config/settings.py` + `backend/util/common_util/llm_stream_utils.py` 的 `MODEL_CONFIGS`）：
  - DeepSeek：默认模型 `deepseek-v4-flash`；`max_tokens=8192`、`temperature=0.1`、`extra_body={"thinking": {"type": "disabled"}}`。
  - Doubao/ARK：默认模型 `doubao-seed-1-6-251015`；`max_tokens=32768`、`temperature=0.1`、`extra_body={"thinking": {"type": "disabled"}}`。
  - Qwen/DashScope：`settings.py` 默认模型 `Qwen/Qwen3.6-35B-A3B`（注意 `backend/.env.example` 示例值为 `qwen-plus`，两者不一致，以实际 `.env` 为准）；`max_tokens=32768`、`temperature=0.1`、`extra_body={"enable_thinking": False}`、`stream_options={"include_usage": True}`。
- LangSmith：`LANGSMITH_TRACING`、`LANGSMITH_ENDPOINT`、`LANGSMITH_API_KEY`、`LANGSMITH_PROJECT`。
- 上传和产物：`UPLOAD_DIR`、`MAX_UPLOAD_SIZE`、`ALLOWED_EXTENSIONS`。
- 外部招标和模板：`TENDER_DATA_API_URL`、`TEMPLATE_CANDIDATE_API_URL`、`TEMPLATE_CANDIDATE_ALLOWED_HOSTS`、`EXTERNAL_REQUEST_TIMEOUT_SECONDS`、`TEMPLATE_CANDIDATE_RANKING_LLM_PROVIDER`。
- Word / graph 锁：`LOCK_FILE_PATH`、`LOCK_TIMEOUT`、`LOCK_WAIT_TIMEOUT`。
- 日志、SSE、任务：`LOG_DIR`、`LOG_QUEUE_MAXSIZE`、`PROGRESS_LOG_BACKUP_COUNT`、`EXECUTION_LOG_BACKUP_COUNT`、`LOG_ROTATION_WHEN`、`LOG_CLEANUP_MAX_MB`、`SSE_MAX_EVENTS_PER_TASK`、`SSE_EVENT_TTL`、`SSE_HEARTBEAT_INTERVAL`、`TASK_TOTAL_NODES`、`TASK_HEARTBEAT_TIMEOUT`、`TASK_CLEANUP_INTERVAL`。
- Retrieval：`QDRANT_URL`、`QDRANT_API_KEY`、`COMMENT_BAD_CASE_COLLECTION`、`EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL`、`SILICONFLOW_BASE_URL`、`EMBEDDING_MODEL`、`EMBEDDING_DIMENSIONS`（`backend/.env.example` 另含 `EMBEDDING_PROVIDER`，由 retrieval 运行时使用）。
- 招标类型、锚点、受保护字段 profile 和默认插入文本：`backend/config/tender_config.py`。

**构建：**
- 后端专用 `pyproject.toml`、`pytest.ini`、`setup.cfg`、`tox.ini`、`Dockerfile`、`docker-compose.yml`、CI workflow 均未检测到。
- 后端专用 ruff、black、mypy、biome 配置未检测到。
- 测试组织由 `backend/tests/`、`backend/tests/conftest.py`（仅把项目根和 backend 加入 `sys.path`，无 `asyncio_mode` 设置）、`pytest` 和 `pytest-asyncio` 体现。

## 平台要求

**开发：**
- 完整后端开发需要 Windows 10/11、本机 Microsoft Word 或兼容 COM 的 Office 环境、Windows Python 3.11+、`backend/.venv`、`backend/.env` 和可写 `UPLOAD_DIR`。
- 安装依赖：

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
copy .env.example .env
```

- Windows 启动（前后端）：

```powershell
cd <repo>
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-dev-win.ps1
```

- 仅启动后端：

```powershell
cd <repo>
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-dev-win.ps1 -BackendOnly
```

- WSL 协作启动：

```bash
./scripts/start-dev-wsl.sh
```

- 手动启动后端（开发，热加载）：

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- 运行测试（在 `backend/` 目录下）：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

- 检索脚本（`backend/scripts/`）：`diagnose_word.py`（Word COM 诊断）、`index_comment_bad_cases.py`（向 Qdrant 索引 bad case）、`test_comment_hybrid_retrieval.py`（混合检索自测）。

**生产：**
- 托管平台、容器镜像和 CI/CD 配置未检测到。
- 生产若需要真实 Word 生成，必须提供 Windows Python、`pywin32`、Word/WPS COM、可用 `msvcrt` 文件锁、可写 `UPLOAD_DIR`、至少一个 LLM provider key，以及外部招标/模板系统和可选 Qdrant/embedding 服务网络访问。
- `/health`、`/health/ready`、`/health/live` 位于 `backend/main.py`，只代表应用进程层状态；`/health/ready` 中 `upload_dir_accessible` 当前是固定 `True`（标注 TODO，未真实检查目录权限），不代表真实上传目录、Word COM、LLM、Qdrant 或外部 HTTP 可用。

---

*后端技术栈分析：2026-06-29*
