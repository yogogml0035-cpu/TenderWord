# TenderWord

本 README 面向部署者和日常使用者：说明如何在新机器上安装、配置、启动和验收 TenderWord。项目功能与内部实现请以代码和 [系统地图](coding_maps/SYSTEM_MAP.md) 为准。

完整的文档生成、改写和批注写回依赖 **Windows Python + pywin32 + 本机 Microsoft Word 或兼容 COM 的 WPS 环境**。仅启动前端或后端健康检查，并不能证明 Word 自动化可用。

> 当前仓库提供的是 Windows 本机 / 内网环境的运行入口；未提供 Docker、docker-compose、反向代理、Windows 服务注册或生产 CI 配置。后端任务和会话状态保存在进程内，不能按无状态服务横向扩容。

## 1. 支持的安装环境

本文档只说明 **Windows 原生安装与运行**：前端、后端、Python 虚拟环境和 Word COM 均在同一台 Windows 机器上运行。推荐使用 `scripts\start-dev-win.ps1` 启动开发环境。

## 2. 前置条件

- Windows 10/11。
- Microsoft Word；也可使用已注册 COM 自动化接口的 WPS，但应先通过下文 Word 诊断。
- Windows Python **3.12**（项目基线）。启动脚本会尝试兼容 Python 3.11+，但完整验收应使用 3.12。
- Node.js `>=20.9.0`，推荐 Node 20 LTS。
- npm（前端唯一支持的包管理器；不要改用 yarn 或 pnpm）。
- Git，以及可写、可长期保存的上传与产物目录。
- 未被占用的端口：后端 `8000`，前端 `8502`。
- 至少一个可用的 LLM 服务商配置；首次生成所选服务商必须有对应密钥。

### 安装前检查

在 Windows PowerShell 中执行：

```powershell
py -3.12 --version
node --version
npm --version
Get-NetTCPConnection -LocalPort 8000,8502 -State Listen -ErrorAction SilentlyContinue
```

最后一条命令没有输出时，通常表示两个端口尚未被占用。若已有监听进程，请先确认并停止该进程，或按实际端口同步调整前后端配置与启动命令。

## 3. 获取代码并创建本地配置

以下示例假设仓库已克隆到本机；`<repo>` 表示仓库根目录。请勿把本机配置文件、密钥或生成文件提交到 Git。

```powershell
Set-Location <repo>

if (-not (Test-Path backend\.env)) {
  Copy-Item backend\.env.example backend\.env
}

if (-not (Test-Path frontend\.env.local)) {
  Copy-Item frontend\.env.local.example frontend\.env.local
}

New-Item -ItemType Directory -Force D:\TenderWordData\uploads
```

`backend/.env.example` 和 `frontend/.env.local.example` 是配置键与格式的模板；只在首次创建本地配置时复制，不要用模板覆盖已经填写好的本地文件。

### 配置文件格式

- 一行一个 `KEY=value`。
- 布尔值使用 `true` 或 `false`。
- 数字不需要引号。
- 列表必须使用 JSON 数组，例如 `CORS_ORIGINS=["http://localhost:8502"]`。
- Windows 路径建议使用正斜杠，例如 `D:/TenderWordData/uploads`。
- 配置模块会忽略未知键；拼写错误不会自动报错，因此应严格使用下文列出的键名。

## 4. 后端环境变量

先完成“必填配置”，再按是否接入外部招标数据、模板候选、检索和追踪服务补充可选配置。下面的示例只展示格式，任何密钥值只应填写在本机配置文件中。

### 4.1 最小可用配置

```dotenv
DEBUG=false
UPLOAD_DIR=D:/TenderWordData/uploads
CORS_ORIGINS=["http://localhost:8502","http://127.0.0.1:8502"]

# 从下列服务商中选择至少一个，并在本机填写对应值。
DEEPSEEK_API_KEY=<本机配置的服务商密钥>
```

若界面选择了 Qwen 或 Doubao，则还必须配置对应服务商的密钥；仅填写 DeepSeek 配置不能让另外两个服务商正常调用。

| 配置键 | 默认值 / 格式 | 是否需要配置 | 用途与注意事项 |
| --- | --- | --- | --- |
| `UPLOAD_DIR` | Windows 可写绝对路径 | **是** | 上传文件、模板选择结果和生成产物都保存在这里。为其预留磁盘空间并纳入备份；改动后重启后端。 |
| `DEBUG` | `false` | 建议显式设置 | `true` 会启用 `/docs`、`/openapi.json` 并增加调试输出；长期运行环境应保持 `false`。 |
| `CORS_ORIGINS` | JSON URL 数组 | 同源本机可沿用模板；跨主机时必改 | 必须包含浏览器实际访问前端的 origin（协议、主机、端口均要一致）。不要为了排错把它放宽为任意来源。 |
| `MAX_UPLOAD_SIZE` | `104857600`（字节） | 按需 | 单文件大小上限，默认 100 MB。 |
| `ALLOWED_EXTENSIONS` | JSON 扩展名数组 | 按需 | 默认允许 `.docx`、`.doc`、`.pdf`、`.txt`、`.xlsx`、`.xls`。覆盖时必须保留实际要上传的扩展名。 |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | 按需 | 仅通过 `backend/main.py` 入口启动时生效。开发脚本固定使用 `0.0.0.0:8000`，不要只改这两个值就期待脚本切换端口。 |

### 4.2 LLM 服务商配置

至少配置将要在界面中选择的一个服务商。`*_BASE_URL` 和 `*_MODEL` 有默认值，只有使用私有网关、兼容网关或指定模型时才需要覆盖。

| 服务商 | 必填密钥键 | 可选地址与模型键 | 默认模型 |
| --- | --- | --- | --- |
| DeepSeek | `DEEPSEEK_API_KEY` | `DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL` | `deepseek-v4-flash` |
| Qwen / DashScope | `DASHSCOPE_API_KEY` | `DASHSCOPE_BASE_URL`、`QWEN_MODEL` | 代码默认 `Qwen/Qwen3.6-35B-A3B`；配置模板当前指定 `qwen-plus` |
| Doubao / ARK | `ARK_API_KEY` | `ARK_BASE_URL`、`DOUBAO_MODEL` | `doubao-seed-1-6-251015` |

通用参数：

| 配置键 | 默认值 | 何时调整 |
| --- | --- | --- |
| `LLM_STREAM_TIMEOUT_SECONDS` | `20` | 内网网关、长响应或服务商延迟导致流式请求超时时再适度调大。 |
| `TEMPLATE_CANDIDATE_RANKING_LLM_PROVIDER` | `deepseek` | 使用模板候选 AI 排序且希望改用其他已配置服务商时设置为 `deepseek`、`qwen` 或 `doubao`。 |

### 4.3 外部招标数据与模板候选（按需）

不接入这些外部服务时，仍可通过手动上传文件使用项目；自动查询招标信息或模板候选会不可用或返回外部服务错误。

| 配置键 | 是否需要 | 格式与注意事项 |
| --- | --- | --- |
| `TENDER_DATA_API_URL` | 使用招标编号自动查询时 | 完整的内部或受信任 HTTPS/HTTP 接口地址。 |
| `TEMPLATE_CANDIDATE_API_URL` | 使用模板候选时 | 完整的候选列表接口地址。 |
| `TEMPLATE_CANDIDATE_ALLOWED_HOSTS` | 使用模板候选时 | JSON 主机名/IP 数组，例如 `["templates.internal.example"]`。这里只填下载 URL 的**主机名**，不填协议、路径或通配符。它是下载代理的安全白名单。 |
| `EXTERNAL_REQUEST_TIMEOUT_SECONDS` | 按需 | 外部 HTTP 请求超时，默认 `15` 秒。 |

### 4.4 批注检索（可选）

批注 bad-case 检索优先使用 Qdrant 与 embedding；任一环节不可用时会降级为本地 BM25，不会阻止一般生成任务。

| 配置键 | 何时配置 | 说明 |
| --- | --- | --- |
| `QDRANT_URL` | 使用 Qdrant 向量检索时 | 默认 `http://127.0.0.1:6333`。 |
| `QDRANT_API_KEY` | Qdrant 启用鉴权时 | 本机填写；未启用鉴权可不设置。 |
| `COMMENT_BAD_CASE_COLLECTION` | 使用非默认集合时 | 默认 `tenderword_comment_bad_cases_demo`。 |
| `EMBEDDING_API_KEY` | 使用向量检索时 | 必填；若未设置，运行时会尝试使用 `DASHSCOPE_API_KEY`。 |
| `EMBEDDING_BASE_URL` / `SILICONFLOW_BASE_URL` | 使用非默认 embedding 网关时 | 优先读取 `EMBEDDING_BASE_URL`，未设置时回退到 `SILICONFLOW_BASE_URL`。 |
| `EMBEDDING_MODEL` / `EMBEDDING_DIMENSIONS` | 服务商模型要求时 | 默认模型为 `BAAI/bge-large-zh-v1.5`；维度留空时由服务端处理。 |

`EMBEDDING_PROVIDER` 虽出现在模板中，但当前检索运行时不读取它；请通过地址、模型和密钥键完成实际配置。

### 4.5 LangSmith、日志、锁与任务参数（通常保持默认）

| 分组 | 配置键 | 默认 / 处理建议 |
| --- | --- | --- |
| LangSmith 追踪 | `LANGSMITH_TRACING`、`LANGSMITH_ENDPOINT`、`LANGSMITH_API_KEY`、`LANGSMITH_PROJECT` | 默认关闭。只有已接入 LangSmith 时才启用；密钥仅保存在本机。 |
| 日志 | `LOG_DIR`、`LOG_QUEUE_MAXSIZE`、`PROGRESS_LOG_BACKUP_COUNT`、`EXECUTION_LOG_BACKUP_COUNT`、`LOG_ROTATION_WHEN`、`LOG_CLEANUP_MAX_MB` | 默认日志目录为后端工作目录下的 `logs`，启动时按 200 MB 上限清理。需要独立日志盘或更长保留期时再调整。 |
| Word 跨进程锁 | `LOCK_FILE_PATH`、`LOCK_TIMEOUT`、`LOCK_WAIT_TIMEOUT` | 单个后端进程通常无需设置。不要通过启动多个后端实例提高吞吐量：任务、SSE 和会话状态不是共享存储。 |
| SSE | `SSE_MAX_EVENTS_PER_TASK`、`SSE_EVENT_TTL`、`SSE_HEARTBEAT_INTERVAL` | 默认分别为 `1000`、`3600` 秒、`15` 秒。仅在代理超时或长任务重连问题已定位后调整。 |
| 任务运行 | `TASK_TOTAL_NODES`、`TASK_HEARTBEAT_TIMEOUT`、`TASK_CLEANUP_INTERVAL` | 默认分别为 `7`、`15` 秒、`5` 秒。它们影响进度与内存任务清理，不是常规部署开关。 |
| 高级 CORS | `CORS_ALLOW_CREDENTIALS`、`CORS_ALLOW_METHODS`、`CORS_ALLOW_HEADERS` | 默认已覆盖浏览器、上传和 SSE 所需头。除非有明确代理需求，否则不要覆盖。 |

完整字段定义见 [backend/config/settings.py](backend/config/settings.py)，配置样例见 [backend/.env.example](backend/.env.example)。

## 5. 前端环境变量

前端没有需要保密的运行密钥。唯一需要关注的项目配置是 `NEXT_PUBLIC_API_URL`：它会同时影响浏览器 API 地址、Next.js 的 `/api` 转发目标和开发期允许的访问来源。

### 本机单机部署

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 前后端分机或局域网访问

```dotenv
NEXT_PUBLIC_API_URL=http://<后端主机>:8000
```

也可以提供多个候选地址，使用英文逗号分隔；浏览器会优先选择与当前页面主机名匹配的地址：

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000,http://<后端主机>:8000
```

修改此配置后必须重启前端；执行过 `npm run build` 的环境还需要重新构建。若前后端不在同一 origin，还要让后端 `CORS_ORIGINS` 包含实际前端地址，例如 `http://<前端主机>:8502`。

## 6. Windows 安装与启动

### 6.1 安装后端依赖

在仓库根目录执行：

```powershell
py -3.12 -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

若 `py -3.12` 不可用，先安装 Python 3.12，再继续创建虚拟环境。

### 6.2 安装前端依赖

```powershell
Set-Location <repo>\frontend
npm ci
Set-Location ..
```

`npm ci` 会严格按锁文件安装依赖，适合首次安装和修复依赖。项目的 `frontend/.npmrc` 固定 npm registry 并启用 Node 版本检查。

### 6.3 诊断 Word COM

在启动完整服务前运行：

```powershell
Set-Location <repo>
.\backend\.venv\Scripts\python.exe backend\scripts\diagnose_word.py
```

诊断失败时，先修复 Windows Python、`pywin32`、Word/WPS 安装或 COM 注册，再进行实际生成验收。

### 6.4 一键启动开发环境

```powershell
Set-Location <repo>
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-dev-win.ps1
```

脚本会检查本地配置、端口、Windows Python 虚拟环境和前端原生依赖，然后分别打开后端与前端窗口。停止时在两个子窗口按 `Ctrl+C`，或直接关闭窗口。

只启动后端用于排障：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-dev-win.ps1 -BackendOnly
```

### 6.5 分别启动（排障用）

```powershell
Set-Location <repo>\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

另开一个 PowerShell：

```powershell
Set-Location <repo>\frontend
npm run dev
```

开发入口固定使用 `8000` 和 `8502`。如果需要让 `HOST`、`PORT` 配置参与后端监听，请从 `backend/` 目录运行 `.\.venv\Scripts\python.exe main.py`，并自行确保前端 API 地址与 CORS 设置同步。

## 7. 访问、首次验收与日常使用

启动成功后访问：

- 工作台：<http://localhost:8502/tender>
- 后端健康检查：<http://localhost:8000/health>
- 调试文档：<http://localhost:8000/docs>（仅当 `DEBUG=true`）

建议按以下顺序完成首次验收：

1. 打开 `/health`，确认返回 `status: "ok"`。
2. 打开工作台，确认页面可加载且没有 API 连接错误。
3. 上传最小可用的模板和参数文件，或在已配置外部服务时查询招标信息 / 选择模板。
4. 选择已配置密钥对应的模型，提交一个实际生成任务并等待下载入口出现。
5. 打开下载结果，确认 Word 内容可读取、写回与批注符合预期。

`/health` 只证明 API 进程存活；`/health/ready` 也不能证明上传目录、LLM、外部 HTTP 或 Word COM 真实可用。因此，第 4、5 步是完整环境的必要验收。

日常操作只需从工作台上传或选择文件、提交任务、等待进度结束并从下载入口获取结果。服务重启会中断正在执行的任务，且进程内任务 / 会话状态不会恢复；重要产物请从 `UPLOAD_DIR` 备份。

## 8. 长期运行与安全边界

- 仅应部署在受信任的本机或受控内网。当前仓库未提供登录、鉴权或多租户隔离能力，不能直接暴露到公共互联网。
- `UPLOAD_DIR` 包含用户上传文件和生成结果，应设置访问权限、备份策略和足够的磁盘空间。
- 本机配置文件中的服务商密钥、外部地址和追踪配置不得进入版本库、日志、截图或工单。
- 不要为并发而启动多个后端实例。锁只保护 Word COM 临界区；任务队列、SSE 缓冲与会话状态仍是单进程内存数据。
- `scripts/start-dev-win.ps1` 是开发入口，包含热加载。仓库未提供可直接用于生产的服务守护、反向代理和 TLS 配置；若要长期托管，应先补齐网络隔离、身份认证、备份、监控与 Windows COM 运行账户验证。

前端的构建与启动命令如下，适用于已完成上述网络与运行账户设计的内部环境：

```powershell
Set-Location <repo>\frontend
npm run build
npm run start
```

后端若以非热加载方式运行，可从 `backend/` 目录使用本地 Windows 虚拟环境启动 `main.py`；该入口读取 `HOST`、`PORT` 和 `DEBUG`。在将它注册为系统服务前，必须先在目标运行账户下完成 Word COM 诊断和实际生成验收。

## 9. 常见问题

| 现象 | 优先检查 | 处理方式 |
| --- | --- | --- |
| 启动脚本提示缺少配置文件 | `backend/.env`、`frontend/.env.local` 是否存在 | 从对应 `*.example` 复制一次，再填写必要配置。 |
| 前端能打开但请求后端失败 | `NEXT_PUBLIC_API_URL`、`CORS_ORIGINS`、端口、防火墙 | 两侧地址必须可达且协议/主机/端口一致；改配置后重启前端和后端。 |
| `/health` 正常但实际生成失败 | Word COM、LLM 服务商配置、`UPLOAD_DIR` 权限 | 运行 Word 诊断，确认当前模型对应密钥存在，并确认目录可写。 |
| `/docs` 返回 404 | `DEBUG` 为 `false` | 这是正常的长期运行配置；仅排障时短暂设为 `true` 并重启后端。 |
| 自动查询招标或模板候选失败 | 外部接口 URL、网络、白名单 | 核对 `TENDER_DATA_API_URL`、`TEMPLATE_CANDIDATE_API_URL`、`TEMPLATE_CANDIDATE_ALLOWED_HOSTS` 与网络连通性。 |
| 8000 或 8502 端口被占用 | 现有本地进程 | 先停止确认无用的进程，再重启；不要同时运行两套开发脚本。 |
| 重启后浏览器显示任务中断 | 后端重启 | 当前任务与 SSE 状态在内存中，重启后无法恢复；重新提交任务。 |

## 10. 相关入口

- [后端配置定义](backend/config/settings.py)
- [后端配置模板](backend/.env.example)
- [前端配置模板](frontend/.env.local.example)
- [Windows 启动脚本](scripts/start-dev-win.ps1)
- [Word COM 诊断脚本](backend/scripts/diagnose_word.py)
- [后端架构与运行约定](docs/backend.md)
- [前端架构与运行约定](docs/frontend.md)
