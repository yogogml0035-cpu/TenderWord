# TenderWord

TenderWord 是一个前后端分离的招标文档生成系统。完整功能依赖 Windows + Word COM。

这份 README 只保留新机器首次安装最需要的流程：

- 方案 A：仓库克隆在 WSL 中，前端在 WSL 安装和运行，后端通过 Windows Python + Word COM 启动
- 方案 B：仓库直接克隆在 Windows 中，前后端都在 Windows 安装和启动

如果 README 和代码冲突，以代码为准。

## 准备条件

- Windows 10/11
- 本机已安装 Microsoft Word 或兼容 COM 的 Office 环境
- Windows Python 3.10+
- Node.js 20.9+，推荐 Node 20 LTS
- 端口 `8000`、`8502` 未被占用

前端当前真实约束：

- `frontend/package.json` 要求 `Node >= 20.9.0`
- `frontend/.npmrc` 固定使用 `https://registry.npmjs.org/`
- fresh clone 推荐使用 `npm ci`

## 方案 A：仓库克隆在 WSL 中

这是当前更推荐的开发方式。

- 前端依赖和 `npm run dev` 放在 WSL/Linux
- 后端依赖和 Word COM 放在 Windows
- 启动入口使用 `./scripts/start-dev-wsl.sh`

### 1. 在 WSL 中安装前端

```bash
cd /home/<your-user>/path/to/TenderWord-WSL/frontend

# 如果你使用 nvm/fnm，可以先切到 Node 20
# nvm use

node -v

npm ci
cp .env.local.example .env.local
```

默认情况下，`frontend/.env.local` 里的 `NEXT_PUBLIC_API_URL` 保持 `http://localhost:8000` 即可；如果你有局域网访问需求，再按需修改。

### 2. 在 Windows PowerShell 中安装后端

仓库虽然在 WSL 中，但后端虚拟环境必须由 Windows Python 创建，不能用 WSL 的 Python 创建。

```powershell
cd \\wsl.localhost\<WSL发行版名>\home\<your-user>\path\to\TenderWord-WSL\backend
py -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
copy .env.example .env
```

`backend/.env` 至少确认两类配置：

- `UPLOAD_DIR` 指向 Windows 下可写目录，例如 `D:/UploadFiles`
- 至少配置一个可用的 LLM Key，例如 `DEEPSEEK_API_KEY`

### 3. 从 WSL 启动项目

```bash
cd /home/<your-user>/path/to/TenderWord-WSL
./scripts/start-dev-wsl.sh
```

这个脚本会做两件事：

- 在 Windows 侧启动后端
- 在当前 WSL 终端启动前端 `npm run dev`

首次使用时的重要说明：

- 如果你在 WSL 里直接调用 Windows 侧 `start-dev.ps1`，可能会遇到“权限不够”“禁止运行脚本”或 `ExecutionPolicy` 相关报错
- 在 WSL 中不要把 `start-dev.ps1` 当成首选入口
- 正确做法是直接使用 `./scripts/start-dev-wsl.sh`
- 该脚本内部会通过 Windows `pwsh.exe` / `powershell.exe` 以 `-ExecutionPolicy Bypass` 调起 `start-dev.ps1`

### 4. 访问地址

- 前端首页：<http://localhost:8502>
- 前端工作台：<http://localhost:8502/tender>
- 后端健康检查：<http://localhost:8000/health>

## 方案 B：仓库直接克隆在 Windows 中

如果你不打算把仓库放在 WSL，可以直接在 Windows 里完成全部安装和启动。

### 1. 安装后端

```powershell
cd <repo>\backend
py -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
copy .env.example .env
```

`backend/.env` 至少确认：

- `UPLOAD_DIR` 指向 Windows 下可写目录
- 至少配置一个可用的 LLM Key

### 2. 安装前端

```powershell
cd <repo>\frontend
npm ci
copy .env.local.example .env.local
```

如果 `node -v` 小于 `20.9.0`，先升级 Node，再执行 `npm ci`。

### 3. 从 Windows 启动项目

推荐命令：

```powershell
cd <repo>
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
```

如果你的 PowerShell 已允许本地脚本执行，也可以直接：

```powershell
cd <repo>
.\scripts\start-dev.ps1
```

### 4. 访问地址

- 前端首页：<http://localhost:8502>
- 前端工作台：<http://localhost:8502/tender>
- 后端健康检查：<http://localhost:8000/health>

## 常见问题

### 1. WSL 里第一次启动提示权限不够

现象通常是：

- 在 WSL 中直接执行 Windows 侧 `start-dev.ps1`
- PowerShell 报“权限不足”“禁止运行脚本”或 `ExecutionPolicy` 错误

处理方式：

```bash
./scripts/start-dev-wsl.sh
```

### 2. 前端安装失败

优先检查：

- `node -v` 是否不低于 `20.9.0`
- 当前目录是否是 `frontend/`
- 是否使用了 `npm ci`
- `npm config get registry` 是否输出 `https://registry.npmjs.org/`

### 3. 启动脚本报缺少文件

启动前这几个文件必须已经存在：

- `backend/.venv/Scripts/python.exe`
- `backend/.env`
- `frontend/node_modules`
- `frontend/.env.local`

## 相关入口

- 前端入口：[frontend/package.json](/home/hsikey/CompanyProject/TenderWord-WSL/frontend/package.json)
- 后端入口：[backend/main.py](/home/hsikey/CompanyProject/TenderWord-WSL/backend/main.py)
- Windows 启动脚本：[scripts/start-dev.ps1](/home/hsikey/CompanyProject/TenderWord-WSL/scripts/start-dev.ps1)
- WSL 启动脚本：[scripts/start-dev-wsl.sh](/home/hsikey/CompanyProject/TenderWord-WSL/scripts/start-dev-wsl.sh)
