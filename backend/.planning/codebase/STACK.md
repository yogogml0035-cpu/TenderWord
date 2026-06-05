# 后端技术栈事实地图

**分析日期：** 2026-06-05

**范围：** `backend/`、后端依赖、后端启动/验证相关根脚本。

## 语言与运行时

- **Python 3.10+**：FastAPI、LangGraph、任务队列、Word COM 自动化和 pytest 测试。
- **PowerShell**：Windows 启动入口 `scripts/start-dev.ps1`，负责虚拟环境、端口和 uvicorn 启动检查。
- **Bash**：WSL 启动入口 `scripts/start-dev-wsl.sh`，前端在 WSL 运行，后端委托 Windows PowerShell。
- **Markdown**：`backend/skills/rewrite/SKILL.md` 是 task skill 声明。

完整后端生成能力必须运行在 Windows Python 上，因为 Word COM 依赖 pywin32 与本机 Office COM 注册。WSL 可以承担无 COM 的后端单测，但不能替代真实 Word 生成验收。

## 依赖管理

- 依赖清单位于 `backend/requirements.txt`。
- Windows 启动脚本默认检查 `backend/.venv/Scripts/python.exe`。
- WSL 下后端测试应使用独立的 `backend/.venv-linux`。
- 当前后端没有 lockfile；依赖版本以 `requirements.txt` 为安装真源。

## 核心框架

| 技术 | 用途 | 证据 |
| --- | --- | --- |
| FastAPI | API router、请求校验、异常处理、健康检查 | `backend/main.py`, `backend/api/` |
| Uvicorn | ASGI 本地服务 | `backend/main.py`, `scripts/start-dev.ps1` |
| Pydantic v2 | 请求/响应模型、枚举、字段校验 | `backend/models/` |
| Pydantic Settings | `.env` 配置加载 | `backend/config/settings.py` |
| LangGraph | 生成、rewrite 和补充批注工作流 | `backend/graphs/` |
| DeepAgents | `generation_mode=agent` 的内容生成主/子智能体运行时 | `backend/agents/generation/` |
| LangChain agents | `comment_agent` 批注校验/写回工具运行时 | `backend/agents/comments/` |
| pywin32 | Word COM 自动化 | `backend/util/word_util/` |
| OpenAI-compatible SDK | DeepSeek、Doubao/ARK、Qwen/DashScope 流式调用 | `backend/util/common_util/llm_stream_utils.py` |
| pytest / pytest-asyncio | 后端单测与 async 测试 | `backend/tests/` |

## 关键依赖

- `fastapi`、`uvicorn[standard]`、`pydantic`、`pydantic-settings`：API 与配置基础。
- `langgraph`、`langchain-core`、`langchain-deepseek`、`langchain-openai`：graph、DeepAgents 和 LLM 相关工作流基础。
- `deepagents`：内容生成智能体运行时。
- `openai`、`volcengine-python-sdk[ark]`、`httpx`、`aiohttp`、`requests`：LLM 与 HTTP 调用。
- `python-multipart`：文件上传。
- `python-dotenv`：环境变量辅助。
- `pywin32`：Windows 上的 Word COM。
- `structlog`：依赖中声明；当前主要日志实现仍以 stdlib logging 和自有 log util 为主。
- `requests`：招标详情和模板候选 HTTP 调用；依赖已显式列入 `requirements.txt`。

## 配置

- 配置真源：`backend/config/settings.py`。
- 示例配置：`backend/.env.example`。
- 本地私有配置：`backend/.env`，不得提交或打印。
- 关键配置范围包括：host/port、CORS、LLM provider、上传目录、模板候选接口和白名单、锁超时、日志保留、SSE 保留、任务心跳、LLM 流式超时。
- 招标类型配置不在 `.env` 中，位于 `backend/config/tender_config.py`。

## 本地运行

```powershell
cd backend
.\.venv\Scripts\python.exe main.py
```

或从仓库根目录：

```powershell
.\scripts\start-dev.ps1
```

WSL 推荐从仓库根目录：

```bash
./scripts/start-dev-wsl.sh
```

## 验证命令

Windows 后端：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -v
.\.venv\Scripts\python.exe scripts\diagnose_word.py
```

WSL 后端无 COM 单测：

```bash
cd backend
TMPDIR=/tmp TMP=/tmp TEMP=/tmp .venv-linux/bin/python -m pytest tests -v
```

## 平台要求

- 完整功能：Windows 10/11、Python 3.10+、Microsoft Word 或兼容 COM 的 Office 环境。
- 默认后端端口：`8000`。
- 上传目录和日志目录由 `backend/config/settings.py` 解析。
- WSL 下不要复用 Windows `.venv`；Windows 启动也不要复用 Linux 原生依赖。

---

*后端技术栈分析：2026-06-05*
