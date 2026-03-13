# TenderWord

TenderWord 是一个运行在 Windows 环境下的招标文档智能处理系统，当前采用前后端分离架构：

- 前端：Next.js 16、React 19、Tailwind 4、Zustand
- 后端：FastAPI、LangGraph、pywin32
- 当前已落地招标类型：`xjcg_tender`、`gngk_tender`
- 当前真实 API 前缀：`/api`
- 当前真实关键链路：创建任务 -> 任务队列 -> SSE 推送 -> 生成完成/失败 -> 下载

## 系统要求

| 组件 | 要求 |
|------|------|
| 操作系统 | Windows 10/11 或 Windows Server 2019+ |
| Python | 3.10+ |
| Node.js | 18.x LTS 或更高版本 |
| Office | Microsoft Word / WPS 2016+ |

默认端口：

- 前端：`8502`
- 后端：`8000`

## 快速开始

### 1. 准备后端依赖

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

`backend/.env` 至少要保证：

- 上传目录可写，例如 `UPLOAD_DIR=D:/UploadFiles`
- 至少配置一个可用的 LLM 提供商密钥
- `DEBUG=true` 时才会暴露 Swagger 文档 `/docs`

### 2. 准备前端依赖

```powershell
cd frontend
npm install
copy .env.local.example .env.local
```

`frontend/.env.local` 当前模板支持多个后端地址，使用英文逗号分隔：

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000,http://10.11.11.44:8000
```

前端会按当前页面主机名优先选择合适的后端地址。

### 3. 选择脚本

| 场景 | 脚本 | 前端实际执行命令 | 适用说明 |
|------|------|------------------|----------|
| 日常开发联调 | `.\start-dev.ps1` | `npm run dev` | 保留热更新，适合平时改代码和联调 |
| 部署态本机启动 | `.\start-build.ps1` | `npm ci` -> `npm run build` -> `npm run start` | 适合本机按“接近部署”的方式后台拉起前后端 |

两套脚本都会：

- 要求从仓库根目录执行
- 检查 `python`、`npm`、`backend/.env`、`frontend/.env.local`
- 检查 `8000` 和 `8502` 端口是否已被占用
- 在真正拉起窗口前执行后端 Python 预检查

两套脚本的差异：

- `start-dev.ps1` 会弹出两个独立 PowerShell 窗口，适合盯着日志联调
- `start-dev.ps1` 只要求 `frontend/node_modules` 已存在，不会自动安装前端依赖
- `start-build.ps1` 不弹窗口，而是在后台拉起前后端进程
- `start-build.ps1` 固定使用 `backend\.venv\Scripts\python.exe` 作为后端解释器，不依赖当前终端里激活了哪个 Python
- `start-build.ps1` 会主动执行 `npm ci`，然后继续 `npm run build` 和 `npm run start`
- `start-build.ps1` 会把 PID、状态文件和日志写到 `.runtime\build\`
- `start-build.ps1` 启动后会轮询健康检查；任一服务启动失败，会自动停止另一边，避免半启动

需要 build 前端时，不要使用 `.\start-dev.ps1`，直接执行：

```powershell
.\start-build.ps1
```

典型场景包括：

- 想按接近生产的方式启动前端，而不是 `next dev`
- 想确认 `npm run build` 能否通过
- 修改了前端代码后，想验证生产构建是否正常
- 修改了 `NEXT_PUBLIC_*` 环境变量后，需要重新构建前端
- 想排查“开发模式正常、生产构建异常”的问题

`start-build.ps1` 现在已经比普通开发脚本更接近部署脚本，原因是它具备：

- 固定解释器路径
- 后台非交互启动
- 日志落盘
- PID 记录
- 健康检查
- 配套停止脚本 `.\stop-build.ps1`

但它仍然不是完整的生产部署方案，因为它还没有覆盖：

- Windows Service / NSSM 注册
- 开机自启
- 反向代理和域名配置
- 系统级监控、自动重启、权限隔离

### 4. 如何运行脚本

推荐按下面顺序执行：

1. 进入仓库根目录

   ```powershell
   cd D:\CompanyProject\TenderWord-feat-h
   ```

2. 如果你使用虚拟环境，先激活后端 Python 环境

   ```powershell
   .\backend\.venv\Scripts\activate
   ```

3. 根据场景选择一个脚本

   ```powershell
   .\start-dev.ps1
   ```

   或

   ```powershell
   .\start-build.ps1
   ```

   如果你的目标是“要 build 前端再启动”，这里就只执行 `.\start-build.ps1`。

4. 如果本机 PowerShell 执行策略阻止脚本运行，改用显式调用

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\start-dev.ps1
   powershell -NoProfile -ExecutionPolicy Bypass -File .\start-build.ps1
   ```

`start-dev.ps1` 启动成功后，会弹出两个独立窗口：

- 后端窗口：运行 `python main.py`
- 前端窗口：运行 `npm run dev`

`start-build.ps1` 启动成功后，不会弹出新窗口；它会在后台启动进程，并在当前终端打印：

- 后端 PID
- 前端 PID
- 访问地址
- `.runtime\build` 运行时目录
- 日志文件路径
- 停止命令 `.\stop-build.ps1`

部署态脚本的命令语义：

```powershell
cd D:\CompanyProject\TenderWord-feat-h
```

- 启动服务：

  ```powershell
.\start-build.ps1
  ```

  这条命令已经包含前端构建，不需要再手动先执行一次 `npm run build`。

- 停止服务：

  ```powershell
.\stop-build.ps1
  ```

- 重启服务：

  ```powershell
.\stop-build.ps1
.\start-build.ps1
  ```

如果是“把服务拉起来并持续运行”，只需要执行一次：

```powershell
.\start-build.ps1
```

如果前端代码或 `NEXT_PUBLIC_*` 环境变量已经改过，想重新按构建模式启动，使用：

```powershell
.\stop-build.ps1
.\start-build.ps1
```

### 5. 访问地址

- 前端首页：<http://localhost:8502>
- 招标工作台：<http://localhost:8502/tender>
- 后端健康检查：<http://localhost:8000/health>
- Swagger 文档：<http://localhost:8000/docs>（仅 `DEBUG=true` 时可用）

## 手动启动 fallback

如果你不想使用脚本，可以按场景手动执行。

### 开发联调模式

后端：

```powershell
cd backend
python main.py
```

后端热重载开发模式：

```powershell
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

前端：

```powershell
cd frontend
npm run dev
```

### 前端构建启动模式

后端：

```powershell
cd backend
.\.venv\Scripts\python.exe -u main.py
```

前端：

```powershell
cd frontend
npm ci
npm run build
npm run start
```

停止服务：

- 一键脚本启动时：在两个子窗口中按 `Ctrl+C`，或直接关闭子窗口
- 部署态脚本启动时：执行 `.\stop-build.ps1`
- 手动启动时：在当前终端按 `Ctrl+C`

## 项目结构

```text
frontend/                     Next.js 前端
  app/                        页面入口（首页、/tender）
  components/                 表单、聊天与通用 UI
  lib/api.ts                  前端统一请求封装
  stores/                     Zustand store
  types/                      前端共享类型
  utils/                      tender type 映射等工具

backend/                      FastAPI + LangGraph 后端
  api/                        `/api` 路由
  graphs/                     LangGraph 工作流
  states/                     graph state
  nodes/                      公共/类型特化节点
  prompts/                    Prompt Layer
  services/                   业务服务
  task/                       任务队列与取消
  util/word_util/             Word COM 工具
  main.py                     FastAPI 入口

assert/                       类型规则包与能力知识包
docs/                         部署和补充文档
start-dev.ps1                 本地一键启动脚本
start-build.ps1               部署态本机启动脚本
stop-build.ps1                部署态停止脚本
AGENTS.md                     Agent 执行规范
```

## 关键开发入口

真实接口和目录以代码为准，README 只做导航，不作为接口真源。

| 能力 | 真实入口 |
|------|----------|
| 健康检查 | `backend/main.py` 中的 `/health`、`/health/ready`、`/health/live` |
| 生成任务 | `backend/api/generate.py` -> `/api/generate` |
| 任务状态/取消/心跳 | `backend/api/tasks.py` -> `/api/tasks` |
| SSE | `backend/api/stream.py` -> `/api/stream/{task_id}` |
| 下载 | `backend/api/download.py` -> `/api/download` |
| 上传 | `backend/api/upload.py` -> `/api/upload` |
| 招标基础数据 | `backend/api/tender.py` -> `/api/tender/{tender_no}` |
| 用户消息路由 / 会话 | `backend/api/user.py` -> `/api/user/stream`、`backend/api/conversations.py` |

当前已支持的 LLM 模型：

- `deepseek`
- `qwen`
- `doubao`

## 基本使用流程

1. 打开 <http://localhost:8502/tender>
2. 选择招标类型：`xjcg_tender` 或 `gngk_tender`
3. 填写招标编号和项目信息
4. 上传模板与参数文件
5. 选择模型并发起生成
6. 在右侧对话/日志区域观察 SSE 进度
7. 任务完成后下载生成文件

支持通过 URL 参数进入工作台并自动映射招标类型，例如：

```text
http://localhost:8502/tender?tender_lx=0&purchase_method=5&fund_lx=0&tenderno=ZBGG-2024-001
```

实际 URL 参数映射以 `frontend/utils/tenderTypeMapper.ts` 为准。

## 常见问题

### PowerShell 提示禁止执行脚本

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-dev.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-build.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\stop-build.ps1
```

如果你希望只对当前终端放开，也可以临时执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\start-dev.ps1
```

### 端口被占用

```powershell
netstat -ano | findstr :8000
netstat -ano | findstr :8502
taskkill /PID <PID> /F
```

`start-dev.ps1` 会在启动前直接报出占用端口的 PID。

### 缺少环境文件或依赖

如果脚本提示以下问题，请先修复再重试：

- `backend/.env` 不存在：从 `backend/.env.example` 复制
- `frontend/.env.local` 不存在：从 `frontend/.env.local.example` 复制
- `frontend/node_modules` 不存在：进入 `frontend` 执行 `npm install`
- `python` 或 `npm` 不存在：先安装/激活对应运行环境
- `start-build.ps1` 固定要求 `backend\.venv\Scripts\python.exe` 存在
- `start-build.ps1` 会执行 `npm ci`：它会按 `package-lock.json` 重装前端依赖

### 后端预检查失败

脚本会在真正启动前执行：

```powershell
python -c "import asyncio; import fastapi; import uvicorn; import pydantic_settings; import backend.main"
```

如果这里失败，说明当前 Python 环境或本机运行环境还不满足后端启动条件。常见排查方向：

- `backend\.venv` 尚未创建或依赖未装完整
- `requirements.txt` 依赖未安装完整
- 本机 Python/Windows 网络栈存在异常，例如 `_overlapped` / `WinError 10106`

### 如何停止 `start-build.ps1` 启动的服务

```powershell
.\stop-build.ps1
```

它会：

- 读取 `.runtime\build\backend.pid` 和 `.runtime\build\frontend.pid`
- 停止对应进程树
- 清理 PID 和状态文件
- 保留日志文件，便于排障

`.\stop-build.ps1` 不是“服务已经关闭后再运行”的脚本，而是“你想关闭这套后台服务时”执行的停止命令。

### `start-build.ps1` 的日志在哪里

默认写在：

```text
.runtime/build/backend.stdout.log
.runtime/build/backend.stderr.log
.runtime/build/frontend.stdout.log
.runtime/build/frontend.stderr.log
```

如果部署态启动失败，优先看这些日志文件。

### 前端无法连接后端

优先检查：

1. `backend` 是否真的已经启动并通过 `http://localhost:8000/health`
2. `frontend/.env.local` 中的 `NEXT_PUBLIC_API_URL` 是否包含当前实际访问的后端地址
3. `backend/.env` 中的 `CORS_ORIGINS` 是否包含前端地址

### Swagger 文档打不开

这是预期行为。后端只有在 `backend/.env` 中设置 `DEBUG=true` 时才暴露：

- `/docs`
- `/redoc`
- `/openapi.json`

## 相关文档

- [AGENTS.md](AGENTS.md)：项目 agent 执行规范
- [docs/deployment.md](docs/deployment.md)：部署说明
- [docs/Word_COM_问题排查指南.md](docs/Word_COM_问题排查指南.md)：Word COM 排障
- [assert/prompt_layer_knowledge_pack.md](assert/prompt_layer_knowledge_pack.md)：Prompt Layer 专项知识包

## 说明

- 本项目完整运行依赖 Windows + Word COM
- README 只提供启动与导航信息，真实接口、SSE 事件、任务状态与共享类型以代码为准
- 如 README 与代码冲突，请优先相信代码，并顺手修正 README
