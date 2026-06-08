# 后端技术栈事实地图

**分析日期：** 2026-06-08

**范围：** `backend/` 子项目、后端依赖、后端运行脚本入口和测试命令。`backend/.env` 文件存在但不读取内容。

## Languages

**Primary:**
- Python 3.10+ - FastAPI API、LangGraph、DeepAgents/LangChain agent、Word COM 自动化、任务队列、pytest 测试；证据在 `backend/requirements.txt`、`backend/main.py`、`backend/graphs/`。

**Secondary:**
- Markdown - task skill 声明和 codebase facts；证据在 `backend/skills/rewrite/SKILL.md`、`backend/.planning/codebase/`。
- PowerShell - Windows 开发启动脚本；证据在根级 `scripts/start-dev.ps1`。
- Bash - WSL 开发启动脚本；证据在根级 `scripts/start-dev-wsl.sh`。

## Runtime

**Environment:**
- Windows Python 是完整 Word 生成运行时；Word COM 依赖 `pywin32` 和本机 Word/WPS COM 注册，证据在 `backend/requirements.txt` 和 `backend/util/word_util/`。
- WSL/Linux Python 可运行无 COM 单元测试；不要把 WSL 测试等同于真实 Word 写回闭环。
- FastAPI/ASGI 本地端口默认来自 `backend/config/settings.py`，默认 `PORT=8000`。

**Package Manager:**
- pip / venv - 依赖真源是 `backend/requirements.txt`。
- Lockfile: 未检测到后端 lockfile。
- Windows venv: `backend/.venv/`。
- WSL/Linux venv: `backend/.venv-linux/`。

## Frameworks

**Core:**
- FastAPI `>=0.115.0` - HTTP API、SSE route、Pydantic 请求校验；证据在 `backend/main.py`、`backend/api/`。
- Uvicorn `>=0.32.0` - ASGI 服务运行；证据在 `backend/requirements.txt` 和 `backend/main.py`。
- Pydantic `>=2.9.0` - API models、field/model validators；证据在 `backend/models/`。
- Pydantic Settings `>=2.6.0` - 环境配置加载；证据在 `backend/config/settings.py`。
- LangGraph `>=0.2.0` - 生成、rewrite、补充批注 workflow；证据在 `backend/graphs/`。
- LangChain Core / LangChain OpenAI / LangChain DeepSeek - LLM 和 agent 基础；证据在 `backend/requirements.txt`、`backend/agents/`。
- DeepAgents `>=0.6.4` - content agent 和 task context assistant；证据在 `backend/agents/generation/content_agents.py`、`backend/agents/task_context_assistant/factory.py`。

**Testing:**
- pytest `>=8.3.0` - 后端测试 runner；证据在 `backend/tests/`。
- pytest-asyncio `>=0.24.0` - async service/API 测试；证据在 `backend/requirements.txt` 和 async 测试文件。

**Build/Dev:**
- `python-multipart` - FastAPI 文件上传；证据在 `backend/api/upload.py`。
- `python-dotenv` - `.env` 读取辅助；证据在 `backend/config/settings.py`、`backend/retrieval/config.py`。
- `structlog` - 依赖已声明；主要日志实现使用 stdlib `logging` 和自有 log util，证据在 `backend/main.py`、`backend/util/log_util/`。

## Key Dependencies

**Critical:**
- `pywin32>=306; platform_system == "Windows"` - Word COM 自动化能力，核心路径 `backend/util/word_util/`。
- `openai>=1.0.0` - OpenAI-compatible LLM streaming，核心路径 `backend/util/common_util/llm_stream_utils.py`。
- `volcengine-python-sdk[ark]>=1.0.0` - Doubao/ARK provider 依赖，配置在 `backend/config/settings.py`。
- `httpx>=0.27.0` - LLM streaming、Qdrant store、chat stream HTTP；证据在 `backend/util/common_util/llm_stream_utils.py`、`backend/retrieval/qdrant_store.py`。
- `requests>=2.32.0` - 招标详情和模板候选外部 HTTP；证据在 `backend/util/common_util/fetch_tender_data.py`、`backend/util/common_util/template_candidates.py`。
- `aiohttp>=3.11.0` - HTTP client 依赖已声明；具体调用以源码为准。

**Infrastructure:**
- `python-jose[cryptography]`、`passlib[bcrypt]` - 认证相关依赖已声明；`backend/main.py` 注册的业务 routers 未检测到统一认证层。
- `langchain-openai` - `ChatOpenAI` model factory；证据在 `backend/agents/generation/model_factory.py`。
- `deepagents` - content generation agent 和 task context assistant；证据在 `backend/agents/generation/`、`backend/agents/task_context_assistant/`。

## Configuration

**Environment:**
- 配置类：`backend/config/settings.py`。
- 示例文件：`backend/.env.example`。
- 私有本地配置：`backend/.env` 存在，不能读取、打印或写入文档。
- Pydantic settings 默认从 `backend/.env` 读取；`extra="ignore"`。
- 招标类型配置不在 `.env`，真源是 `backend/config/tender_config.py`。

**Key Config Areas:**
- App/server/CORS: `APP_NAME`、`APP_VERSION`、`DEBUG`、`HOST`、`PORT`、`CORS_*`。
- LLM providers: `DEEPSEEK_*`、`ARK_*`、`DASHSCOPE_*`、`QWEN_MODEL`、`DOUBAO_MODEL`、`LLM_STREAM_TIMEOUT_SECONDS`。
- Optional tracing: `LANGSMITH_*`，应用方法在 `Settings.apply_langsmith_environment()`。
- File upload: `UPLOAD_DIR`、`MAX_UPLOAD_SIZE`、`ALLOWED_EXTENSIONS`。
- External tender/template APIs: `TENDER_DATA_API_URL`、`TEMPLATE_CANDIDATE_API_URL`、`TEMPLATE_CANDIDATE_ALLOWED_HOSTS`、`EXTERNAL_REQUEST_TIMEOUT_SECONDS`。
- Locks/tasks/SSE/logs: `LOCK_*`、`TASK_*`、`SSE_*`、`LOG_*`。
- Retrieval: `QDRANT_URL`、`QDRANT_API_KEY`、`COMMENT_BAD_CASE_COLLECTION`、`EMBEDDING_*`，读取点在 `backend/retrieval/config.py`。

**Build:**
- Build config files: 未检测到后端专用 `pyproject.toml`、`pytest.ini`、`ruff.toml`、`mypy.ini`。
- Formatting/linting config: 未检测到后端专用配置文件。
- Test config: pytest 依赖存在，测试组织由 `backend/tests/` 结构体现。

## Platform Requirements

**Development:**
- Windows 10/11 + Python 3.10+ + `backend/.venv/` 用于完整 Word COM。
- WSL/Linux + `backend/.venv-linux/` 可跑无 COM 单测。
- `backend/requirements.txt` 是安装依赖真源。
- 本地运行入口：

```powershell
cd backend
.\.venv\Scripts\python.exe main.py
```

或从仓库根目录：

```powershell
.\scripts\start-dev.ps1
```

WSL 协作入口：

```bash
./scripts/start-dev-wsl.sh
```

**Production:**
- 部署平台未检测到稳定配置。
- 生产若需要真实生成 Word，必须提供 Windows Python、pywin32、Word/WPS COM、可写上传目录、LLM provider keys、外部招标/模板网络访问。
- `/health` 和 `/health/ready` 只能表达应用进程层面就绪；`backend/main.py` 中 readiness 的 `upload_dir_accessible` 是 TODO 占位，不代表真实目录权限或 Word COM 可用。

## Verification Commands

**Backend unit tests on Windows:**

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -v
```

**Word COM diagnostic on Windows:**

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\diagnose_word.py
```

**No-COM backend tests on WSL/Linux:**

```bash
cd backend
TMPDIR=/tmp TMP=/tmp TEMP=/tmp .venv-linux/bin/python -m pytest tests -v
```

**Document-only checks:**

```bash
git diff --check
```

---

*后端技术栈分析：2026-06-08*
