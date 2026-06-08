# 后端技术栈

**分析日期：** 2026-06-08

**范围：** 仅扫描 `backend/` 后端代码、后端配置、后端测试、根级 `README.md` 中的后端运行说明，以及必要的根级约定文档 `docs/backend.md`、`docs/interfaces-runtime.md`。`backend/.env` 与 `backend/.env.example` 只确认存在，不读取内容。

## 语言

**主要语言：**
- Python 3.10+ - FastAPI API、LangGraph 工作流、DeepAgents/LangChain agent、Word COM 自动化、任务队列、SSE、pytest 测试；证据在 `README.md`、`backend/requirements.txt`、`backend/main.py`、`backend/graphs/`、`backend/tests/`。

**辅助语言：**
- Markdown - rewrite skill、bad case 知识、codebase facts；证据在 `backend/skills/rewrite/SKILL.md`、`backend/retrieval/bad_cases/comment_bad_cases.md`、`backend/.planning/codebase/`。
- PowerShell - Windows 后端启动与 Windows/WSL 协作入口由根级脚本承载；证据在 `README.md`、`scripts/start-dev-win.ps1`、`scripts/start-dev.ps1`。
- Bash - WSL 协作启动入口；证据在 `README.md`、`scripts/start-dev-wsl.sh`。

## 运行时

**环境：**
- Windows Python 3.10+ 是完整后端运行时；真实 Word 生成依赖本机 Microsoft Word 或兼容 COM 的 Office 环境，证据在 `README.md`、`docs/backend.md`。
- Word COM 能力依赖 `pywin32>=306; platform_system == "Windows"`，核心封装在 `backend/util/word_util/`。
- WSL/Linux Python 可用于无 COM 单元测试；不要把 WSL 测试等同于 Word COM 写回闭环，证据在 `docs/backend.md`、`README.md`。
- FastAPI/ASGI 入口是 `backend/main.py`，默认 `HOST=0.0.0.0`、`PORT=8000` 来自 `backend/config/settings.py`。

**包管理器：**
- pip / venv - 后端依赖真源是 `backend/requirements.txt`。
- Lockfile： 未检测到后端 lockfile。
- Windows venv： `backend/.venv/`。
- WSL/Linux venv： `backend/.venv-linux/`。

## 框架

**核心：**
- FastAPI `>=0.115.0` - HTTP API、文件上传、SSE/NDJSON stream endpoint、Pydantic 请求响应校验；证据在 `backend/main.py`、`backend/api/`。
- Uvicorn `>=0.32.0` - ASGI 服务运行；证据在 `backend/requirements.txt`、`backend/main.py`。
- Pydantic `>=2.9.0` - API model、状态 model、response model；证据在 `backend/models/`。
- Pydantic Settings `>=2.6.0` - 环境变量和 `backend/.env` 配置加载；证据在 `backend/config/settings.py`。
- LangGraph `>=0.2.0` - generate、rewrite、comment_supplement 工作流；证据在 `backend/graphs/base_graph.py`、`backend/graphs/skill_graph.py`、`backend/graphs/comment_supplement_graph.py`。
- LangChain Core / LangChain OpenAI / LangChain DeepSeek - agent message/tool、`ChatOpenAI` model factory 和 LLM provider 适配；证据在 `backend/agents/`、`backend/agents/generation/model_factory.py`。
- DeepAgents `>=0.6.4` - content generation agent 与 task context assistant；证据在 `backend/agents/generation/content_agents.py`、`backend/agents/task_context_assistant/factory.py`。

**测试：**
- pytest `>=8.3.0` - 后端测试 runner；证据在 `backend/tests/`。
- pytest-asyncio `>=0.24.0` - async API/service/graph 测试；证据在 `backend/requirements.txt`、`backend/tests/api/`、`backend/tests/services/`。

**构建 / 开发：**
- `python-multipart>=0.0.12` - FastAPI 上传文件解析；证据在 `backend/api/upload.py`、`backend/requirements.txt`。
- `python-dotenv>=1.0.0` - retrieval 配置显式加载 `backend/.env`，Pydantic Settings 也配置 `env_file`；证据在 `backend/retrieval/config.py`、`backend/config/settings.py`。
- `structlog>=24.4.0` - 依赖已声明；当前应用主日志实现主要使用 stdlib `logging` 和自有 log util，证据在 `backend/main.py`、`backend/util/log_util/`。

## 关键依赖

**关键：**
- `pywin32>=306; platform_system == "Windows"` - Word COM 自动化和诊断；使用点在 `backend/util/word_util/word_application_util.py`、`backend/util/word_util/word_diagnostics.py`。
- `openai>=1.0.0` - OpenAI-compatible LLM streaming、embedding 调用；使用点在 `backend/util/common_util/llm_stream_utils.py`、`backend/services/chat_stream_service.py`、`backend/retrieval/embeddings.py`。
- `httpx>=0.27.0` - LLM streaming timeout、chat stream、Qdrant HTTP client；使用点在 `backend/util/common_util/llm_stream_utils.py`、`backend/services/chat_stream_service.py`、`backend/retrieval/qdrant_store.py`。
- `requests>=2.32.0` - 招标详情、模板候选列表和模板文件下载代理；使用点在 `backend/util/common_util/fetch_tender_data.py`、`backend/util/common_util/template_candidates.py`、`backend/api/template_candidates.py`。
- `langgraph>=0.2.0` - `StateGraph` 工作流编排；使用点在 `backend/graphs/`。
- `deepagents>=0.6.4` - content agent 和 task context assistant；使用点在 `backend/agents/generation/content_agents.py`、`backend/agents/task_context_assistant/factory.py`。
- `volcengine-python-sdk[ark]>=1.0.0` - ARK/Doubao 依赖已声明；当前 provider 配置走 OpenAI-compatible base URL，配置在 `backend/config/settings.py`。

**基础设施：**
- `langchain-openai>=1.2.0` - `ChatOpenAI` model factory；使用点在 `backend/agents/generation/model_factory.py`。
- `langchain-core>=0.3.0` - LangChain message、tool、runnable 类型；使用点在 `backend/agents/comments/comment_agent.py`、`backend/agents/comments/tools.py`。
- `python-jose[cryptography]>=3.3.0`、`passlib[bcrypt]>=1.7.4` - 认证相关依赖已声明；当前 `backend/main.py` 注册的业务 routers 未检测到统一认证 dependency。
- `aiohttp>=3.11.0` - HTTP client 依赖已声明；当前扫描到的后端 HTTP 调用主要使用 `requests` 和 `httpx`。

## 配置

**环境：**
- 配置类真源：`backend/config/settings.py`。
- 私有本地配置：`backend/.env` 文件存在；不得读取、打印或写入真实值。
- 示例配置：`backend/.env.example` 文件存在；本次不读取内容。
- `Settings.model_config` 指向 `backend/.env`，`case_sensitive=True`，`extra="ignore"`。
- retrieval 运行时另有 `backend/retrieval/config.py`，会读取环境变量并在需要时加载 `backend/.env`。

**关键配置区域：**
- App/server/CORS： `APP_NAME`、`APP_VERSION`、`DEBUG`、`HOST`、`PORT`、`CORS_*`。
- LLM providers： `DEEPSEEK_BASE_URL`、`DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL`、`ARK_BASE_URL`、`ARK_API_KEY`、`DOUBAO_MODEL`、`DASHSCOPE_BASE_URL`、`DASHSCOPE_API_KEY`、`QWEN_MODEL`、`LLM_STREAM_TIMEOUT_SECONDS`。
- 可选 tracing： `LANGSMITH_TRACING`、`LANGSMITH_ENDPOINT`、`LANGSMITH_API_KEY`、`LANGSMITH_PROJECT`；环境回写在 `Settings.apply_langsmith_environment()`。
- 文件上传/下载： `UPLOAD_DIR`、`MAX_UPLOAD_SIZE`、`ALLOWED_EXTENSIONS`。
- 外部招标/模板： `TENDER_DATA_API_URL`、`TEMPLATE_CANDIDATE_API_URL`、`TEMPLATE_CANDIDATE_ALLOWED_HOSTS`、`EXTERNAL_REQUEST_TIMEOUT_SECONDS`、`TEMPLATE_CANDIDATE_RANKING_LLM_PROVIDER`。
- 锁/任务/SSE/日志： `LOCK_FILE_PATH`、`LOCK_TIMEOUT`、`LOCK_WAIT_TIMEOUT`、`TASK_*`、`SSE_*`、`LOG_*`。
- 检索：`QDRANT_URL`、`QDRANT_API_KEY`、`COMMENT_BAD_CASE_COLLECTION`、`EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL`、`SILICONFLOW_BASE_URL`、`EMBEDDING_MODEL`、`EMBEDDING_DIMENSIONS`。
- 招标类型与受保护字段配置真源：`backend/config/tender_config.py`。

**构建：**
- 构建配置文件： 未检测到后端专用 `pyproject.toml`、`pytest.ini`、`tox.ini`、`Dockerfile`。
- 格式化/lint 配置： 未检测到后端专用 ruff/black/mypy 配置。
- 测试配置： pytest 依赖存在，测试组织由 `backend/tests/` 目录体现。

## 平台要求

**开发：**
- Windows 10/11、本机 Word/WPS COM、Windows Python 3.10+；证据在 `README.md`。
- 后端安装命令以 `backend/requirements.txt` 为准：

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
```

- Windows 后端启动可通过根级脚本，证据在 `README.md`：

```powershell
cd <repo>
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-dev-win.ps1
```

- WSL 协作启动入口，后端仍由 Windows Python + Word COM 启动：

```bash
./scripts/start-dev-wsl.sh
```

**生产：**
- 部署平台未检测到稳定配置。
- 若生产需要真实 Word 生成，必须提供 Windows Python、pywin32、Word/WPS COM、可写 `UPLOAD_DIR`、至少一个 LLM provider key、外部招标/模板网络访问。
- `/health`、`/health/ready`、`/health/live` 位于 `backend/main.py`，只表达应用进程层状态；`/health/ready` 中 `upload_dir_accessible` 当前是 TODO 占位，不代表真实目录权限或 Word COM 可用。

## 验证命令

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

*技术栈分析： 2026-06-08*
