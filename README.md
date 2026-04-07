# TenderWord

TenderWord 是面向招标文件生成与修改的前后端分离系统。当前仓库以 Windows + Word COM 作为完整运行前提，围绕"创建任务 -> 队列串行执行 -> SSE 推送 -> 下载 / 继续修改"组织前后端能力。

## 当前仓库现实

- 前端：Next.js 16、React 19、Tailwind CSS 4、Zustand
- 后端：FastAPI、LangGraph、pywin32
- 前端 UI 类型：`xjcg`、`gngk`、`gjgk`
- 后端 `form_type`：`xjcg_tender`、`gngk_zc_tender`、`gngk_cz_tender`、`gjgk_tender`
- `gngk` 会按 `fund_source_lx` 在前端转换阶段拆分为 `gngk_zc_tender` / `gngk_cz_tender`
- 真实 API 前缀：`/api`
- 真实工作台路由：`/tender`

代码是真源。README 只提供导航和启动说明；接口形状、SSE 事件、任务状态、前后端共享类型以代码为准。

## 核心能力

- 招标基础数据拉取：`/api/tender/{tender_no}`
- 文件上传：`/api/upload`、`/api/upload/multiple`
- 文档生成任务：`/api/generate`
- 任务状态 / 取消 / 心跳：`/api/tasks`
- SSE 进度流：`/api/stream/{task_id}`
- 生成文件下载：`/api/download/{file_path}`
- 会话心跳：`/api/conversations/{conversation_id}/heartbeat`
- 用户消息统一入口：`/api/user/stream`
- 模板候选与代理下载：`/api/template-candidates`

## 系统要求

| 组件 | 要求 |
|------|------|
| 操作系统 | Windows 10/11 或 Windows Server 2019+ |
| Python | 3.10+ |
| Node.js | 18+ |
| Office | Microsoft Word 或兼容 COM 的本地 Office 环境 |

默认端口：

- 前端：`8502`
- 后端：`8000`

## 快速开始

### 1. 准备后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

`backend/.env` 至少确认：

- `UPLOAD_DIR` 指向可写目录
- 至少配置一个可用的 LLM Key
- 如果需要 Swagger，设置 `DEBUG=true`

### 2. 准备前端

```powershell
cd frontend
npm install
copy .env.local.example .env.local
```

`frontend/.env.local` 支持配置多个后端地址，按当前页面主机名优先匹配：

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000,http://10.11.11.44:8000
```

### 3. 启动方式

推荐从仓库根目录执行脚本。

| 场景 | 命令 | 说明 |
|------|------|------|
| 日常开发联调 | `.\scripts\start-dev.ps1` | 启动后端热重载和前端 `next dev`，会弹出两个 PowerShell 窗口 |
| 停止服务 | `.\scripts\stop-build.ps1` | 停止 `.runtime\build` 记录的前后端进程并清理状态文件 |

如果你在 WSL 中工作，但仍要复用 Windows 侧的 Python / Node / Word COM 环境，可使用 `scripts/` 下的桥接脚本：

| 场景 | 命令 | 说明 |
|------|------|------|
| 日常开发联调（WSL 入口） | `./scripts/start-dev-wsl.sh` | 从 WSL 调起 Windows PowerShell 版 `start-dev.ps1` |

脚本启动前会检查：

- 脚本会自动将 `scripts/` 的上一级识别为仓库根目录；从仓库根目录执行最直观
- `backend/.venv/Scripts/python.exe` 存在
- `backend/.env`、`frontend/.env.local` 存在
- `frontend/node_modules` 存在
- `8000` / `8502` 端口未被占用

### 4. WSL 使用说明

- `scripts/start-dev-wsl.sh` 只是桥接包装器，本质上仍在 Windows 侧执行 `ps1` 脚本。
- 这类脚本仅用于开发便利，不代表 TenderWord 支持 Linux / WSL 原生运行。
- 完整文档生成、修改与 COM 相关能力仍然依赖 Windows + Word COM。
- 推荐从仓库根目录调用。

使用前提：

- 当前终端必须运行在 WSL 中。
- WSL 需要开启 Windows interop，至少能在 WSL 中找到 `pwsh.exe`、`cmd.exe`、`wslpath`。
- WSL wrapper 会优先使用 `pwsh.exe`（PowerShell 7）；当前仓库的 `ps1` 含有 UTF-8 中文内容，`powershell.exe`（Windows PowerShell 5.1）在部分环境里可能误读脚本源码。
- Windows 侧项目环境必须已经准备好：
  - `backend/.venv/Scripts/python.exe`
  - `backend/.venv` 必须由 Windows Python 创建，不能用 WSL 里的 `/usr/bin/python3 -m venv .venv`
  - `backend/.env`
  - `frontend/.env.local`
  - `frontend/node_modules`

推荐使用步骤：

1. 在 WSL 中进入仓库根目录。
2. 开发模式下执行 `./scripts/start-dev-wsl.sh`。

常用命令：

```bash
cd /home/wsq12/linux/code/TenderWord-linux-feat-wsq

# 开发联调：Windows 侧拉起后端窗口，当前 WSL 终端运行前端
./scripts/start-dev-wsl.sh
```

如果你之前在 WSL 中执行过 `python3 -m venv backend/.venv`，需要先在 Windows PowerShell 里重建后端虚拟环境：

```powershell
cd \\wsl.localhost\Ubuntu\home\wsq12\linux\code\TenderWord-linux-feat-wsq\backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

运行结果说明：

- `./scripts/start-dev-wsl.sh` 成功后，会由 Windows 侧弹出后端 PowerShell 窗口，并在当前 WSL 终端直接运行前端 `npm run dev`。
- 这样开发模式下的前端文件监听由 WSL/Linux 负责，避免 Windows 在 `\\wsl.localhost\...` 或映射盘路径上运行 `next dev` 时出现 Watchpack/UNC 监听异常。

如果脚本启动失败，优先检查：

- WSL 中是否能执行 `powershell.exe` / `pwsh.exe` 和 `cmd.exe`
- WSL 中是否能执行 `pwsh.exe`；如果只能执行 `powershell.exe`，可能会遇到脚本中文被误读的问题
- Windows 侧虚拟环境、前端依赖和 `.env` 文件是否已准备
- 端口 `8000` / `8502` 或你自定义的端口是否已被占用

### 5. 手动启动 fallback

后端：

```powershell
cd backend
.\.venv\Scripts\activate
python main.py
```

或热重载：

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

前端：

```powershell
cd frontend
npm run dev
```

生产构建式前端：

```powershell
cd frontend
npm ci
npm run build
npm run start
```

## 常用访问地址

- 首页：<http://localhost:8502>
- 工作台：<http://localhost:8502/tender>
- 后端健康检查：<http://localhost:8000/health>
- Swagger：<http://localhost:8000/docs>（仅 `DEBUG=true`）

## 类型与流程说明

前端和后端对"招标类型"的粒度不同，文档和代码都要分清这两层：

- 前端页面与表单注册使用 `TenderType`：`xjcg`、`gngk`、`gjgk`
- 后端生成入口使用 `FormType`：`xjcg_tender`、`gngk_zc_tender`、`gngk_cz_tender`、`gjgk_tender`
- `gngk` 在 `frontend/lib/formDataConverter.ts` 按 `fund_source_lx` 映射到自筹 / 财政两套 graph

当前关键链路：

1. 前端解析 URL 参数，确定页面类型与招标编号
2. 前端调用 `/api/tender/{tender_no}` 拉取基础数据
3. 上传模板 / 参数文件到 `/api/upload`
4. 前端将表单数据转换为 `GenerateRequest`
5. 后端创建任务并进入 `task_queue_manager`
6. 前端通过 `/api/stream/{task_id}` 订阅日志、进度、LLM 输出、完成 / 失败事件
7. 完成后通过 `/api/download/{file_path}` 下载结果文件

## 关键目录

```text
frontend/                     Next.js 前端
  app/                        页面入口（`/`、`/tender`）
  components/                 表单、聊天、布局和通用 UI
  lib/api.ts                  前端统一 API 封装
  lib/formDataConverter.ts    前端 UI 类型 -> 后端 form_type 映射
  stores/                     Zustand 状态管理
  types/                      前端共享类型
  utils/                      URL 参数与类型映射

backend/                      FastAPI + LangGraph 后端
  api/                        `/api` 路由
  graphs/                     LangGraph 工作流
  states/                     graph state 定义
  nodes/                      公共 / 类型特化节点
  prompts/                    Prompt Layer
  services/                   业务服务
  skills/                     task 型 skill runtime（当前含 rewrite）
  task/                       任务队列、取消、心跳
  util/word_util/             Word COM 工具封装
  tests/                      后端测试
  main.py                     FastAPI 入口

asset/                        长期知识包与规则沉淀
guide/                        本地 Git / worktree 操作说明，不是产品真源
scripts/
  start-dev.ps1               本地开发启动脚本
  stop-build.ps1              停止后台服务脚本
  start-dev-wsl.sh            WSL 开发联调入口脚本
AGENTS.md                     仓库级执行规范
```

## 开发与验证

前端：

```powershell
cd frontend
npm run lint
npm run type-check
npm run test
npm run test:e2e
```

后端：

```powershell
cd backend
python -m pytest tests -v
python scripts/diagnose_word.py
```

文档修改的最低验证建议：

- 确认 README 中提到的脚本、目录、环境模板文件真实存在
- 确认命令与端口和 `package.json` / `backend/main.py` 保持一致

## 常见排障

### PowerShell 阻止脚本执行

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop-build.ps1
```

如果是从 WSL 调用，优先使用：

```bash
./scripts/start-dev-wsl.sh
```

### 端口占用

```powershell
netstat -ano | findstr :8000
netstat -ano | findstr :8502
taskkill /PID <PID> /F
```

### build 模式日志位置

`.runtime\build\` 下会保留：

- `backend.stdout.log`
- `backend.stderr.log`
- `frontend.stdout.log`
- `frontend.stderr.log`

### README 和代码冲突

优先相信代码，并顺手修正文档。当前仓库没有顶层 `docs/` 目录；代码注释里仍有少量 `docs/api-contract.md` 一类历史引用，应按代码而不是按这些注释理解系统。

## 相关文件

- [AGENTS.md](./AGENTS.md)：仓库级智能体 / 工程约束
- [asset/README.md](./asset/README.md)：知识包索引
- [backend/main.py](./backend/main.py)：后端入口与健康检查
- [frontend/lib/api.ts](./frontend/lib/api.ts)：前端 API 真入口
