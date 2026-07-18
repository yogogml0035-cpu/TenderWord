# 后端技术栈

**分析日期：** 2026-07-18

**last_mapped_commit：** `29f47e1557a34bbbec0ad3f6938e1a46aa94e5e3`（分析时另含工作区未提交代码事实）

**范围：** 本文只覆盖 `backend/` 子项目。事实来源包括 `backend/requirements.txt`、`backend/.env.example`、`backend/main.py`、`backend/config/settings.py`、`backend/config/tender_config.py`、`backend/api/`、`backend/services/`、`backend/graphs/`、`backend/agents/`、`backend/nodes/`、`backend/retrieval/`、`backend/helper/`、`backend/util/`、`backend/task/`、`backend/core/`、`backend/models/`、`backend/skills/`、`backend/states/`、`backend/prompts/`、`backend/tests/conftest.py`、`backend/scripts/`，以及仓库根 `scripts/start-dev.ps1`、`scripts/start-dev-win.ps1`、`scripts/start-dev-wsl.sh`。`backend/.env` 与 `backend/.env.example` 均可能存在；本文档只引用配置键名与 `.env.example` 中的示例值，不读取或泄露 `.env` 真实值。

## 语言

**主要语言：**
- Python 3.12（开发机线索）— 仓库内可见 `backend/__pycache__/*.cpython-312.pyc` 等字节码产物，表明当前常用解释器为 CPython 3.12。启动脚本 `scripts/start-dev.ps1` 要求 Windows Python `sys.version_info >= (3, 11)`，并优先探测 `py.exe -3.12`、`py.exe -3.11`、`py.exe -3`，最后回退 `python.exe`。后端 API、任务队列、LangGraph graph、DeepAgents/LangChain 智能体、Word COM 自动化、检索运行时和 pytest 测试均用 Python 实现；核心路径包括 `backend/main.py`、`backend/api/`、`backend/services/`、`backend/graphs/`、`backend/nodes/`、`backend/agents/`、`backend/retrieval/`、`backend/helper/`、`backend/util/`、`backend/task/`、`backend/core/`、`backend/models/`、`backend/skills/`、`backend/states/`、`backend/prompts/` 和 `backend/tests/`。

**辅助语言：**
- Markdown — rewrite skill 说明、bad case 知识、事实文档；路径包括 `backend/skills/rewrite/`、`backend/retrieval/bad_cases/`、`backend/.planning/codebase/`。
- PowerShell — Windows 原生开发启动和依赖准备；路径包括 `scripts/start-dev.ps1`、`scripts/start-dev-win.ps1`。
- Bash — WSL 协作启动入口；路径是 `scripts/start-dev-wsl.sh`。

## 运行时

**环境：**
- 完整后端闭环是 Windows Python + `pywin32` + 本机 Microsoft Word 或兼容 Word/WPS COM；依据是 `backend/requirements.txt`（`pywin32>=306; platform_system == "Windows"`）、`backend/util/word_util/word_application_util.py`、`backend/util/word_util/word_diagnostics.py`、`backend/util/word_util/word_com_manager.py`。
- WSL/Linux 只适合前端协作和无 COM 逻辑验证；真实 `.doc/.docx` 读取、写回、批注和保存需要 Windows COM。
- ASGI 入口是 `backend/main.py`，模块级 `app = create_application()` 注册 FastAPI app；`__main__` 分支调用 `uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG, log_config=None)`。
- Windows 后端开发启动由 `scripts/start-dev.ps1` 在 `backend/` 目录内运行 `python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload`，并显式为源码子目录设置 `--reload-dir`（避免 watchfiles 扫到 `.venv-linux` 等目录）；同时设置 `WATCHFILES_FORCE_POLLING=true`、`WATCHFILES_POLL_DELAY_MS=300`。`scripts/start-dev-win.ps1` 是显式 Windows wrapper，委托给 `scripts/start-dev.ps1`。
- 启动前 `scripts/start-dev.ps1` 会执行后端预检查：`python -c "import asyncio; import fastapi; import uvicorn; import pydantic_settings; import backend.main"`，失败会尝试重装依赖后再检查一次。
- WSL 协作启动由 `scripts/start-dev-wsl.sh` 通过 Windows PowerShell 以 `-BackendOnly` 启动后端，再在 WSL 当前终端启动前端。
- 长任务由 `backend/services/document_service.py` 提交到后台执行；Word 写入必须经过 `backend/task/task_queue_manager.py` 的公平队列（`wait_for_turn`）、`backend/graphs/base_graph.py` 的 `CrossProcessFileLock`（`msvcrt.locking`）和 `backend/util/word_util/word_com_manager.py` 的 `com_lock()`。

**包管理器：**
- pip / venv — 依赖真源是 `backend/requirements.txt`（文件头注明 Keep ASCII-only，避免 Windows 非 UTF-8 locale 下 pip 读失败）。
- Windows venv 目录是 `backend/.venv/`；`scripts/start-dev.ps1` 的 `Ensure-WindowsBackendVenv` 会识别并移走 WSL/Linux 的 `.venv`（重命名为 `.venv-linux`）或不完整的 `.venv`（`.venv-backup`），避免误用非 Windows Python。
- Lockfile：未检测到后端 lockfile（无 `Pipfile.lock` / `poetry.lock` / `uv.lock`）。

## 框架

**核心：**
- FastAPI `>=0.115.0` — HTTP API、上传、下载、SSE、NDJSON agent run 和健康检查；入口在 `backend/main.py`，routers 在 `backend/api/`。
- Uvicorn `>=0.32.0`（`uvicorn[standard]`）— ASGI 运行时；依赖在 `backend/requirements.txt`，启动入口在 `backend/main.py` 和 `scripts/start-dev.ps1`。
- Pydantic `>=2.9.0` — API 请求/响应、任务状态、SSE event、agent run 协议和领域模型；路径包括 `backend/models/generate.py`、`backend/models/task.py`、`backend/models/sse.py`、`backend/models/agent_run.py`、`backend/models/template_candidates.py`、`backend/models/tender.py`、`backend/models/upload.py`、`backend/models/common.py`。
- Pydantic Settings `>=2.6.0` — 从环境变量和 `backend/.env` 加载配置；实现是 `backend/config/settings.py`。
- LangGraph `>=0.2.0` — `StateGraph` 工作流编排；初次生成、rewrite skill、补充批注、各招标类型 graph 和生成 agent 子图；路径包括 `backend/graphs/base_graph.py`、`backend/graphs/skill_graph.py`（`RewriteSkillGraph`）、`backend/graphs/comment_supplement_graph.py`、`backend/graphs/*_tender_graph.py`（`gjgk`、`gngk_fw_cz`、`gngk_fw_zc`、`gngk_hw_cz`、`gngk_hw_zc`、`xjcg`）、`backend/agents/generation/*_agent_graph.py`。
- LangChain Core / LangChain OpenAI / LangChain DeepSeek — message、tool、`ChatOpenAI` model factory 和 agent 工具类型；路径包括 `backend/agents/generation/model_factory.py`、`backend/agents/comments/comment_agent.py`、`backend/agents/comments/tools.py`、`backend/agents/task_context_assistant/tools.py`。`langchain-deepseek` 已在 `requirements.txt` 声明，但当前主要 provider 调用路径通过 OpenAI-compatible base URL + `langchain_openai.ChatOpenAI`。
- DeepAgents `>=0.6.4` — content generation agent、task context assistant、受控 filesystem backend 和 skill workspace；路径包括 `backend/agents/generation/content_agents.py`、`backend/agents/generation/workspace.py`、`backend/agents/task_context_assistant/factory.py`。
- Word COM / pywin32 — Word 应用生命周期、COM 初始化、缓存修复、诊断、读写、批注和全局 COM 锁；路径包括 `backend/util/word_util/word_application_util.py`、`backend/util/word_util/word_com_manager.py`、`backend/util/word_util/word_diagnostics.py`、`backend/util/word_util/word_extraction_utils.py`。

**测试：**
- pytest `>=8.3.0` — 后端测试 runner；测试根目录是 `backend/tests/`。
- pytest-asyncio `>=0.24.0` — async API、service、graph、SSE 和 agent 测试。未检测到 `pytest.ini`、`pyproject.toml`、`setup.cfg`、`tox.ini` 中的 `asyncio_mode` 配置，因此 pytest-asyncio 运行在默认 strict 模式，async 测试需显式标注 `@pytest.mark.asyncio`（测试中确实使用该标记）。
- `backend/tests/conftest.py` 仅把项目根与 `backend/` 加入 `sys.path`，无全局 fixture 配置。

**构建/开发：**
- `python-multipart>=0.0.12` — FastAPI 上传文件解析；使用点是 `backend/api/upload.py`。
- `python-dotenv>=1.0.0` — retrieval 运行时加载 `backend/.env`；使用点是 `backend/retrieval/config.py`。
- `uvicorn[standard]` 间接提供开发 reload 与 watchfiles 能力；`scripts/start-dev.ps1` 设置 watch 目录和轮询参数。

## 关键依赖

**关键（`backend/requirements.txt`）：**
- `fastapi>=0.115.0` / `uvicorn[standard]>=0.32.0` / `pydantic>=2.9.0` / `pydantic-settings>=2.6.0` / `python-multipart>=0.0.12` — HTTP 服务与配置。
- `httpx>=0.27.0` — OpenAI-compatible timeout、chat stream 和 Qdrant HTTP client；路径包括 `backend/util/common_util/llm_stream_utils.py`、`backend/services/chat_stream_service.py`、`backend/retrieval/qdrant_store.py`。
- `requests>=2.32.0` — 外部招标详情、模板候选列表和模板文件代理下载；路径包括 `backend/util/common_util/fetch_tender_data.py`、`backend/util/common_util/template_candidates.py`、`backend/api/template_candidates.py`。
- `langgraph>=0.2.0` / `langchain-core>=0.3.0` / `langchain-openai>=1.2.0` / `langchain-deepseek>=0.1.0` / `deepagents>=0.6.4` — 工作流与智能体。
- `volcengine-python-sdk[ark]>=1.0.0` / `openai>=1.0.0` — LLM SDK；当前业务路径以 OpenAI-compatible `openai` client 和 `ChatOpenAI` 为主，ARK/Doubao 也通过兼容 base URL 调用。
- `python-dotenv>=1.0.0` — 环境加载辅助。
- `pywin32>=306; platform_system == "Windows"` — Word COM 自动化、`pythoncom.CoInitialize()`、`win32com.client.DispatchEx` 和 COM 诊断。
- `pytest>=8.3.0` / `pytest-asyncio>=0.24.0` — 测试栈（requirements 中标注为 Dev dependencies optional，但仍与运行时依赖同文件）。

**未在 requirements 中、但运行时相关：**
- 标准库 `asyncio`、`threading`、`concurrent.futures`、`msvcrt`（Windows 文件锁）、`logging` — 任务队列、SSE 跨线程调度、跨进程锁、日志。
- 无 ORM / Redis / SQL client / JWT 鉴权库声明。

## 配置

**环境：**
- 配置类真源是 `backend/config/settings.py`。
- `Settings.model_config` 指向 `backend/.env`（`ENV_FILES = (BACKEND_ENV_FILE,)`），`env_file_encoding="utf-8"`，`case_sensitive=True`，`extra="ignore"`。
- `settings.apply_langsmith_environment()` 会把 LangSmith 相关配置写回进程环境，供 LangChain/LangSmith SDK 使用；模块加载时已自动调用一次（`settings = get_settings(); settings.apply_langsmith_environment()`）。
- Retrieval 另有 `backend/retrieval/config.py`，会通过 `python-dotenv` 加载 `backend/.env`；如果 `python-dotenv` 未加载成功，会用 fallback 解析该文件。文档和日志只能记录变量名，不能输出真实值。
- 配置模板：`backend/.env.example`。

**关键配置区域：**
- App/server/CORS：`APP_NAME`、`APP_VERSION`、`DEBUG`、`HOST`（默认 `0.0.0.0`）、`PORT`（默认 `8000`）、`CORS_ORIGINS`（默认含 `http://localhost:8502` / `http://127.0.0.1:8502`；`.env.example` 另示例 `3000`）、`CORS_ALLOW_CREDENTIALS`、`CORS_ALLOW_METHODS`、`CORS_ALLOW_HEADERS`（含 `Last-Event-ID`、`X-Accel-Buffering` 以支持 SSE）。
- LLM providers：`DEEPSEEK_BASE_URL`、`DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL`、`ARK_BASE_URL`、`ARK_API_KEY`、`DOUBAO_MODEL`、`DASHSCOPE_BASE_URL`、`DASHSCOPE_API_KEY`、`QWEN_MODEL`、`LLM_STREAM_TIMEOUT_SECONDS`（默认 `20`）。
- LLM 默认模型与调用参数（`backend/config/settings.py` + `backend/util/common_util/llm_stream_utils.py` 的 `MODEL_CONFIGS`）：
  - DeepSeek：默认模型 `deepseek-v4-flash`；`max_tokens=8192`、`temperature=0.1`、`extra_body={"thinking": {"type": "disabled"}}`。
  - Doubao/ARK：默认模型 `doubao-seed-1-6-251015`；`max_tokens=32768`、`temperature=0.1`、`extra_body={"thinking": {"type": "disabled"}}`。
  - Qwen/DashScope：`settings.py` 默认模型 `Qwen/Qwen3.6-35B-A3B`（注意 `backend/.env.example` 示例值为 `qwen-plus`，两者不一致，以实际 `.env` 为准）；`max_tokens=32768`、`temperature=0.1`、`extra_body={"enable_thinking": False}`、`stream_options={"include_usage": True}`。
- LangSmith：`LANGSMITH_TRACING`、`LANGSMITH_ENDPOINT`、`LANGSMITH_API_KEY`、`LANGSMITH_PROJECT`。
- 上传和产物：`UPLOAD_DIR`（默认 `D:/UploadFiles`）、`MAX_UPLOAD_SIZE`（默认 `104857600` / 100MB）、`ALLOWED_EXTENSIONS`（默认 `.docx/.doc/.pdf/.txt/.xlsx/.xls`）。
- 外部招标和模板：`TENDER_DATA_API_URL`、`TEMPLATE_CANDIDATE_API_URL`、`TEMPLATE_CANDIDATE_ALLOWED_HOSTS`（默认 `10.11.0.213`、`10.11.1.224`）、`EXTERNAL_REQUEST_TIMEOUT_SECONDS`（默认 `15`）、`TEMPLATE_CANDIDATE_RANKING_LLM_PROVIDER`（默认 `deepseek`）。
- Word / graph 锁：`LOCK_FILE_PATH`、`LOCK_TIMEOUT`（默认 `600`）、`LOCK_WAIT_TIMEOUT`（默认 `1200`）。
- 日志、SSE、任务：`LOG_DIR`（默认 `logs`，相对 backend）、`LOG_QUEUE_MAXSIZE`、`PROGRESS_LOG_BACKUP_COUNT`、`EXECUTION_LOG_BACKUP_COUNT`、`LOG_ROTATION_WHEN`、`LOG_CLEANUP_MAX_MB`、`SSE_MAX_EVENTS_PER_TASK`（默认 `1000`）、`SSE_EVENT_TTL`（默认 `3600`）、`SSE_HEARTBEAT_INTERVAL`（默认 `15`）、`TASK_TOTAL_NODES`（默认 `7`）、`TASK_HEARTBEAT_TIMEOUT`（默认 `15`）、`TASK_CLEANUP_INTERVAL`（默认 `5`）。
- Retrieval（主要由 `backend/retrieval/config.py` 读取，不完全进入 `Settings` 类）：`QDRANT_URL`、`QDRANT_API_KEY`、`COMMENT_BAD_CASE_COLLECTION`、`EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL`、`SILICONFLOW_BASE_URL`、`EMBEDDING_MODEL`、`EMBEDDING_DIMENSIONS`；`backend/.env.example` 另含 `EMBEDDING_PROVIDER`（示例 `siliconflow`）。
- 招标类型、锚点、受保护字段 profile 和默认插入文本：`backend/config/tender_config.py`。

**构建：**
- 后端专用 `pyproject.toml`、`pytest.ini`、`setup.cfg`、`tox.ini`、`Dockerfile`、`docker-compose.yml`、CI workflow 均未检测到。
- 后端专用 ruff、black、mypy、biome 配置未检测到。
- 测试组织由 `backend/tests/`、`backend/tests/conftest.py`、`pytest` 和 `pytest-asyncio` 体现。

## 子系统与运行模式

**HTTP / API：**
- FastAPI app 创建与 CORS、router 挂载、健康检查、全局异常处理：`backend/main.py`。
- 业务 routers（均挂 `/api` 前缀）：
  - `backend/api/upload.py` — `prefix=/upload`
  - `backend/api/tender.py` — `prefix=/tender`
  - `backend/api/tasks.py` — `prefix=/tasks`
  - `backend/api/stream.py` — `/stream/{task_id}`、`/stream/{task_id}/status`
  - `backend/api/generate.py` — `prefix=/generate`
  - `backend/api/comment_supplement.py` — `prefix=/comment-supplement`
  - `backend/api/download.py` — `prefix=/download`
  - `backend/api/agent.py` — `prefix=/agent/runs`
  - `backend/api/conversations.py` — `prefix=/conversations`
  - `backend/api/template_candidates.py` — `prefix=/template-candidates`
- 健康检查根级：`/health`、`/health/ready`、`/health/live`；`/health/ready` 中 `upload_dir_accessible` 当前固定 `True`（代码标注 TODO，未真实检查目录权限）。

**任务队列与进度：**
- 进程内全局队列：`backend/task/task_queue_manager.py`。
- 任务类别 `TaskKind`：`generate`、`rewrite`、`comment_supplement`。
- 节点枚举 `NodeName` 覆盖生成、批注、rewrite 各阶段节点名（含 `annotate_corrections`、`content_agent`、`comment_agent` 等），用于进度展示；`TOTAL_NODES` 取自 `settings.TASK_TOTAL_NODES`。
- 任务服务编排：`backend/services/task_service.py`、`backend/services/document_service.py`。

**SSE：**
- 事件模型：`backend/models/sse.py`（`SSEEventType`：`log`、`llm`、`progress`、`node_start`、`node_complete`、`agent_step`、`done`、`error`、`heartbeat`）。
- 连接管理：`backend/core/sse_manager.py`（按 task 缓存事件、心跳、`Last-Event-ID` 重连、`bind_loop` 跨线程安全调度）。
- 路由：`backend/api/stream.py`。
- 进度日志桥接到 SSE：`backend/util/log_util/sse_log_handler.py`，在 `startup_event` 中挂载。

**LangGraph / Skills：**
- 基类与跨进程锁：`backend/graphs/base_graph.py`。
  - 初次生成主链：`prepare_template` → `extract_tender_params` 后 fan-out 到 Word 操作子图与生成分支。
  - 生成分支：`generation_mode=workflow` → `generate_polished_text`；`generation_mode=agent` → `content_agent`。
  - 两路正文汇合后统一进入 `annotate_corrections`（条款标识规范化 + 技术参数更正批注候选），再按 `comment_generation_mode` / `generation_mode` 选择 `generate_comments` 或跳过，最终 fan-in 到 `update_word`；`generation_mode=agent` 且批注开启时，`update_word` 后进入 `comment_agent`。
- 招标类型 graph：`backend/graphs/gjgk_tender_graph.py`、`gngk_*_tender_graph.py`、`xjcg_tender_graph.py`。
- rewrite：`backend/graphs/skill_graph.py` 的 `RewriteSkillGraph` + `backend/skills/rewrite/` + `backend/nodes/skills_nodes/rewrite_nodes.py`（显式 Rewrite skill graph，非元数据驱动框架）。
- 补充批注：`backend/graphs/comment_supplement_graph.py`。
- Word 节点：`backend/nodes/common_word_nodes/`、`gjgk_word_nodes/`、`gngk_word_nodes/`、`xjcg_word_nodes/`、`skills_nodes/`。

**Agents：**
- Content agents（DeepAgents）：`backend/agents/generation/content_agents.py`、workspace `backend/agents/generation/workspace.py`、model factory `backend/agents/generation/model_factory.py`；子图 `generate_agent_graph.py` / `verify_agent_graph.py` / `revise_agent_graph.py`。
- Comment agent（LangChain `create_agent`）：`backend/agents/comments/comment_agent.py`；工具与写回校验 `backend/agents/comments/tools.py`；审计 workspace `backend/agents/comments/workspace.py`。comment agent 与 content agent 的编号/标识处理边界分离：`★/▲` 规范化例外由 comment agent 保留，技术参数差异批注由 `annotate_corrections` 专用链路产出。
- Task context assistant（DeepAgents）：`backend/agents/task_context_assistant/factory.py`、`tools.py`、`logging.py`；服务入口 `backend/services/agent_run_service.py`、API `backend/api/agent.py`（NDJSON）。

**检索：**
- 配置 / embedding / Qdrant / BM25 / hybrid：`backend/retrieval/config.py`、`embeddings.py`、`qdrant_store.py`、`bm25.py`、`hybrid.py`、`comment_bad_case_runtime.py`、`bad_case_loader.py`。
- 离线脚本：`backend/scripts/index_comment_bad_cases.py`、`backend/scripts/test_comment_hybrid_retrieval.py`。
- Word 诊断脚本：`backend/scripts/diagnose_word.py`。

**Word helper：**
- COM 之外的文档操作辅助：`backend/helper/word_helper/`（`content_ops`、`delete_ops`、`inline_style_ops`、`paragraph_boundary_ops`、`protected_fields`、`semantic_matcher`、`clause_marker_normalize`、`range_utils`、`text_parsing`、`cleanup_ops` 等）。

**领域模型与状态：**
- API/任务模型：`backend/models/`。
- Graph state：`backend/states/`（`base_state`、`gjgk_tender_state`、`gngk_tender_state`、`xjcg_tender_state`、`skill_state`）。
- Prompt 装配：`backend/prompts/`。
- Skill 目录与 rewrite skill：`backend/skills/catalog.py`、`backend/skills/rewrite/`。

## 平台要求

**开发：**
- 完整后端开发需要 Windows 10/11、本机 Microsoft Word 或兼容 COM 的 Office 环境、Windows Python 3.11+（当前线索 3.12）、`backend/.venv`、`backend/.env` 和可写 `UPLOAD_DIR`。
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
.\.venv\Scripts\python.exe -m pytest tests -v
```

- 检索与诊断脚本（`backend/scripts/`）：`diagnose_word.py`、`index_comment_bad_cases.py`、`test_comment_hybrid_retrieval.py`。

**生产：**
- 托管平台、容器镜像和 CI/CD 配置未检测到。
- 生产若需要真实 Word 生成，必须提供 Windows Python、`pywin32`、Word/WPS COM、可用 `msvcrt` 文件锁、可写 `UPLOAD_DIR`、至少一个 LLM provider key，以及外部招标/模板系统和可选 Qdrant/embedding 服务网络访问。
- `/health`、`/health/ready`、`/health/live` 只代表应用进程层状态，不代表真实上传目录、Word COM、LLM、Qdrant 或外部 HTTP 可用。

---

*后端技术栈分析：2026-07-18*
