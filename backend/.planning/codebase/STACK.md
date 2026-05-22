# Technology Stack

**Analysis Date:** 2026-05-22

**Scope:** Backend only: `backend/`, plus root setup and validation files `README.md`, `scripts/start-dev.ps1`, and `scripts/start-dev-wsl.sh`.

## Languages

**Primary:**
- Python 3.10+ - FastAPI service, LangGraph workflows, task queue, Word COM automation, and pytest tests live under `backend/`; the Python version requirement is stated in `README.md`.

**Secondary:**
- PowerShell - Windows backend startup, virtualenv validation, port checks, and `uvicorn` launch are handled by `scripts/start-dev.ps1`.
- Bash - WSL startup delegates backend execution to Windows PowerShell while keeping the backend Windows/Word COM runtime in `scripts/start-dev-wsl.sh`.
- Markdown - backend task skill definitions are stored as `SKILL.md` files in `backend/skills/rewrite/SKILL.md` and `backend/skills/edit/SKILL.md`.

## Runtime

**Environment:**
- Windows Python is the required backend runtime because Word automation depends on pywin32 and Microsoft Word or compatible COM registration, as documented in `README.md`, declared conditionally in `backend/requirements.txt`, and diagnosed by `backend/scripts/diagnose_word.py`.
- The FastAPI app object is `backend.main:app`; direct execution runs `uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)` in `backend/main.py`.
- Local development defaults to backend port `8000`; this is configured by `backend/config/settings.py`, documented in `README.md`, and enforced by `scripts/start-dev.ps1`.

**Package Manager:**
- pip with a Python virtual environment is the backend install path; `README.md` and `scripts/start-dev.ps1` both expect `backend/.venv/Scripts/python.exe`, and dependencies are installed from `backend/requirements.txt`.
- Lockfile: no backend lockfile is present in scope; `backend/requirements.txt` is the backend dependency manifest used by `README.md` and `scripts/start-dev.ps1`.

## Frameworks

**Core:**
- FastAPI `>=0.115.0` - API app creation, CORS, exception handling, health checks, and router registration are in `backend/main.py`; the dependency is declared in `backend/requirements.txt`.
- Uvicorn `>=0.32.0` - ASGI server for local backend runtime; direct startup is in `backend/main.py`, and dev startup is in `scripts/start-dev.ps1`.
- Pydantic `>=2.9.0` - request and response models are in `backend/models/generate.py`, `backend/models/task.py`, `backend/models/sse.py`, and `backend/models/template_candidates.py`; the dependency is declared in `backend/requirements.txt`.
- Pydantic Settings `>=2.6.0` - environment-backed application settings are centralized in `backend/config/settings.py`; the dependency is declared in `backend/requirements.txt`.
- LangGraph `>=0.2.0` - generation, rewrite/edit task skills, and user routing workflows use `StateGraph` in `backend/graphs/base_graph.py`, `backend/graphs/skill_graph.py`, and `backend/graphs/user_graph.py`; the dependency is declared in `backend/requirements.txt`.

**Testing:**
- pytest `>=8.3.0` and pytest-asyncio `>=0.24.0` - backend tests live under `backend/tests/`, async tests use `pytest.mark.asyncio` in `backend/tests/api/test_generate_api.py`, and the test environment is configured by `backend/tests/conftest.py`.

**Build/Dev:**
- `python-dotenv` and Pydantic Settings - `backend/config/settings.py` loads `backend/.env` and references `backend/.env.example`; the dependency is declared in `backend/requirements.txt`.
- `python-multipart` - FastAPI file upload support for `UploadFile` endpoints in `backend/api/upload.py`; the dependency is declared in `backend/requirements.txt`.
- pywin32 `>=306` on Windows - Word COM automation imports `pythoncom` and `win32com.client` in `backend/util/word_util/word_application_util.py` and `backend/util/word_util/word_diagnostics.py`; the dependency is conditionally declared in `backend/requirements.txt`.

## Key Dependencies

**Critical:**
- `fastapi`, `uvicorn[standard]`, `pydantic`, and `pydantic-settings` - API runtime and configuration stack for `backend/main.py`, `backend/api/generate.py`, `backend/api/tasks.py`, `backend/api/user.py`, `backend/api/template_candidates.py`, and `backend/config/settings.py`; versions are declared in `backend/requirements.txt`.
- `langgraph` and `langchain-core` - graph execution foundation for `backend/graphs/base_graph.py`, `backend/graphs/skill_graph.py`, and `backend/graphs/user_graph.py`; versions are declared in `backend/requirements.txt`.
- `openai` and `httpx` - OpenAI-compatible streaming clients for DeepSeek, Doubao/ARK, and Qwen/DashScope in `backend/util/common_util/llm_stream_utils.py` and `backend/services/chat_stream_service.py`; versions are declared in `backend/requirements.txt`.
- `pywin32` - Microsoft Word COM lifecycle, document open/save/close, diagnostics, and retry handling in `backend/util/word_util/word_application_util.py`, `backend/util/word_util/word_com_manager.py`, and `backend/util/word_util/word_diagnostics.py`; the dependency is declared in `backend/requirements.txt`.
- `requests` - external tender-data and template-candidate HTTP integrations import and call `requests` in `backend/util/common_util/fetch_tender_data.py`, `backend/util/common_util/template_candidates.py`, and `backend/api/template_candidates.py`; this package is used in code but is not listed in `backend/requirements.txt`.

**Infrastructure:**
- `python-multipart` - required by upload endpoints using `fastapi.UploadFile` in `backend/api/upload.py`; declared in `backend/requirements.txt`.
- `python-dotenv` - used through Pydantic Settings env-file loading in `backend/config/settings.py`; declared in `backend/requirements.txt`.
- `structlog` - declared in `backend/requirements.txt`, while active backend logging uses stdlib `logging` in `backend/main.py`, `backend/util/log_util/progress_log.py`, and `backend/util/log_util/execution_log.py`.
- `python-jose[cryptography]` and `passlib[bcrypt]` - declared in `backend/requirements.txt`; no auth route or dependency is present in the reviewed backend API registration in `backend/main.py`, `backend/api/generate.py`, `backend/api/tasks.py`, `backend/api/user.py`, or `backend/api/template_candidates.py`.

## Configuration

**Environment:**
- Backend settings are centralized in `backend/config/settings.py` with `SettingsConfigDict(env_file=[backend/.env], case_sensitive=True, extra="ignore")`.
- `backend/.env` and `backend/.env.example` are backend environment files; `backend/config/settings.py` defines `BACKEND_ENV_FILE` and `BACKEND_ENV_EXAMPLE_FILE`, and `README.md` instructs developers to copy `.env.example` to `.env`.
- Runtime host, port, debug mode, CORS, LLM providers, upload limits, external tender/template endpoints, template host allowlist, lock timing, log retention, SSE retention, and task heartbeat settings are all declared in `backend/config/settings.py`.
- LLM provider selection is represented by `LLMModel` in `backend/models/generate.py` and by `MODEL_CONFIGS` in `backend/util/common_util/llm_stream_utils.py`.

**Build:**
- Backend dependency installation is `pip install -r requirements.txt` from `backend/requirements.txt`, as shown in `README.md`.
- Backend startup checks import `asyncio`, `fastapi`, `uvicorn`, `pydantic_settings`, and `backend.main` before launch in `scripts/start-dev.ps1`.
- Development reload watches only backend source subdirectories such as `api`, `config`, `core`, `graphs`, `helper`, `models`, `nodes`, `prompts`, `services`, `skills`, `states`, `task`, and `util` in `scripts/start-dev.ps1`.

## Platform Requirements

**Development:**
- Use Windows Python for the backend virtualenv because `README.md`, `scripts/start-dev.ps1`, and `scripts/start-dev-wsl.sh` all require `backend/.venv/Scripts/python.exe`.
- Use Microsoft Word or compatible COM Office registration for full document generation; this is required by `README.md` and validated by `backend/util/word_util/word_diagnostics.py`.
- Run backend verification with `python -m pytest tests -v` from `backend/`, as documented in `AGENTS.md` and supported by `backend/tests/conftest.py`.
- Run Word COM environment diagnostics with `python scripts/diagnose_word.py` from `backend/`, as documented in `AGENTS.md` and implemented in `backend/scripts/diagnose_word.py`.

**Production:**
- Production hosting is not defined in backend-scoped files; the deployable ASGI entry remains `backend.main:app` in `backend/main.py`.
- The backend stores runtime files in configured local paths, including uploads from `settings.UPLOAD_DIR` in `backend/util/common_util/upload_storage.py`, logs under `settings.LOG_DIR` in `backend/util/log_util/progress_log.py` and `backend/util/log_util/execution_log.py`, and prompt/audit artifacts under `backend/prompts_log` via `backend/util/log_util/prompt_log.py` and `backend/util/log_util/skill_audit_log.py`.

---

*Stack analysis: 2026-05-22*
