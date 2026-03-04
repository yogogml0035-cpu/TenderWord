# TenderWord - 招标文档智能处理系统

基于 **Next.js + FastAPI + LangGraph** 的招标文档智能处理系统。采用前后端分离架构，支持多种招标类型文档的智能生成。

## 🏗️ 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (Next.js)                     │
│                     http://localhost:8502                   │
├─────────────────────────────────────────────────────────────┤
│  • React 19 + TypeScript                                    │
│  • Tailwind CSS 4                                           │
│  • App Router                                               │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ HTTP API
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                      │
│                     http://localhost:8000                   │
├─────────────────────────────────────────────────────────────┤
│  • FastAPI + Uvicorn                                        │
│  • LangGraph 工作流引擎                                     │
│  • LLM 集成 (DeepSeek/Qwen/Doubao)                          │
│  • Word COM 文档处理                                        │
└─────────────────────────────────────────────────────────────┘
```

## 📋 目录

- [系统要求](#系统要求)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [API 端点](#api-端点)
- [环境变量配置](#环境变量配置)
- [部署指南](#部署指南)
- [使用说明](#使用说明)
- [开发指南](#开发指南)
- [常见问题](#常见问题)

## 💻 系统要求

| 组件 | 版本要求 | 说明 |
|------|---------|------|
| Windows | 10/11 或 Server 2019+ | 必需，用于 Word COM |
| Python | 3.10+ | 后端运行环境 |
| Node.js | 18.x LTS | 前端构建和运行 |
| Microsoft Word / WPS | 2016+ | 必需，用于处理 Word 文档 |

### 端口分配

| 服务 | 端口 | 用途 |
|------|------|------|
| 前端应用 | 8502 | Next.js 应用 |
| 后端 API | 8000 | FastAPI 服务 |

## 🚀 快速开始

### 最直接启动

后端（推荐）：

```powershell
cd backend
python main.py
```

后端（热重载，适合开发）：

```powershell
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

前端：

```powershell
# 本地开发（热更新，改代码立刻生效）
cd frontend
npm install
npm run dev

# 生产部署（构建 + 启动；重新部署必须重新 build）
cd frontend
npm ci
npm run build
npm run start
```

两者区别：

- `npm run dev`：开发模式启动（热更新、调试友好）。适合本机开发/联调，不适合作为线上部署方式。
- `npm run build` + `npm run start`：生产模式（先构建产物，再启动服务）。适合服务器部署；每次代码变更或环境变量（尤其 `NEXT_PUBLIC_*`）变更，都需要重新执行 `build` 才会生效。
- `npm install` vs `npm ci`：`ci` 会严格按 `package-lock.json` 安装（更稳定，推荐用于 CI/服务器）；`install` 更适合日常开发。

### 1. 克隆项目

```powershell
cd D:\CompanyProject
git clone <repository-url> feat-wsq-h
cd feat-wsq-h
```

### 2. 后端部署

```powershell
cd backend

# 创建虚拟环境
python -m venv .venv
.\.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
copy ..\.env.example ..\.env
# 编辑 .env 文件填入配置

# 启动后端服务（以下两种方式任选其一）

# 方式1: 直接运行（推荐，已修复模块导入问题）
python main.py

# 方式2: 使用 uvicorn（热重载模式，适合开发）
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```


### 3. 前端部署

```powershell
cd frontend

# 安装依赖（开发可用 npm install；服务器/CI 推荐 npm ci）
npm install

# 配置环境变量
copy .env.example .env.local
# 编辑 .env.local 文件

# 启动方式二选一：
#
# 方式1：开发模式（热更新，适合本地开发/联调）
cd frontend
npm install
npm run dev

# 方式2：生产部署（构建 + 启动；部署到服务器时用这个）
# 注意：NEXT_PUBLIC_* 属于“构建时注入”，改了环境变量也要重新 build
# npm ci
# npm run build
# npm run start
```

### 4. 访问应用

- 前端界面: http://localhost:8502/chat
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

## 📁 项目结构

```
feat-wsq-h/
├── frontend/                 # Next.js 前端
│   ├── app/                  # App Router 页面
│   │   ├── layout.tsx
│   │   ├── page.tsx          # 主页面
│   │   └── api/              # API 路由
│   ├── components/           # React 组件
│   │   ├── forms/            # 表单组件
│   │   └── ui/               # UI 组件
│   ├── lib/                  # 工具函数
│   ├── hooks/                # React Hooks
│   ├── store/                # Zustand 状态管理
│   ├── types/                # TypeScript 类型定义
│   ├── public/               # 静态资源
│   ├── .env.example          # 环境变量模板
│   └── package.json
│
├── backend/                  # FastAPI 后端
│   ├── api/                  # API 路由
│   │   ├── routes/
│   │   └── dependencies.py
│   ├── core/                 # 核心配置
│   │   ├── config.py
│   │   └── security.py
│   ├── graphs/               # LangGraph 工作流
│   │   ├── base_graph.py
│   │   └── xjcg_tender_graph.py
│   ├── nodes/                # Graph 节点
│   │   ├── common/
│   │   └── xjcg_word_nodes/
│   ├── states/               # Graph 状态
│   ├── services/             # 业务逻辑
│   ├── models/               # 数据模型
│   ├── util/                 # 工具函数
│   ├── main.py               # 应用入口
│   └── requirements.txt
│
├── docs/                     # 文档
│   ├── deployment.md         # 部署文档
│   └── Word_COM_问题排查指南.md
│
├── .env.example              # 后端环境变量模板
└── README.md                 # 本文档
```

## 🔌 API 端点

### 核心 API

| 方法 | 端点 | 描述 | 认证 |
|------|------|------|------|
| GET | `/health` | 健康检查 | 否 |
| POST | `/api/v1/tender/generate` | 生成招标文档 | 否 |
| POST | `/api/v1/tender/upload` | 上传文件 | 否 |
| GET | `/api/v1/tender/status/{task_id}` | 查询任务状态 | 否 |
| GET | `/api/v1/tender/download/{filename}` | 下载生成的文档 | 否 |

### API 示例

**生成招标文档:**

```bash
curl -X POST http://localhost:8000/api/v1/tender/generate \
  -H "Content-Type: application/json" \
  -d '{
    "tender_no": "ZBGG-2024-001",
    "tender_type": "xjcg",
    "template_file": "template.docx",
    "param_files": ["params.xlsx"],
    "model": "deepseek"
  }'
```

**完整 API 文档:** http://localhost:8000/docs (Swagger UI)

## 🔧 环境变量配置

### 后端环境变量 (.env)

```bash
# 应用基础配置
APP_NAME=TenderWord API
APP_VERSION=1.0.0
DEBUG=false
HOST=0.0.0.0
PORT=8000

# CORS 配置
CORS_ORIGINS=["http://localhost:8502","http://127.0.0.1:8502","http://localhost:3000","http://127.0.0.1:3000"]

# LLM 提供商配置（至少配置一个）
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_API_KEY=your-api-key-here
DEEPSEEK_MODEL=deepseek-chat

ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ARK_API_KEY=your-api-key-here
DOUBAO_MODEL=doubao-seed-1-6-251015

DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_API_KEY=your-api-key-here
QWEN_MODEL=qwen-plus

# 文件上传配置
UPLOAD_DIR=D:/UploadFiles
MAX_UPLOAD_SIZE=104857600
```

### 前端环境变量 (.env.local)

```bash
# API 配置
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 📚 部署指南

详细的部署说明请参考: [docs/deployment.md](docs/deployment.md)

### Windows 服务部署 (生产环境)

使用 NSSM 将后端配置为 Windows 服务:

```powershell
# 创建服务
cd D:\Tools\nssm\win64
.\nssm install TenderWord-API

# 配置:
# Path: D:\CompanyProject\feat-wsq-h\backend\.venv\Scripts\python.exe
# Startup directory: D:\CompanyProject\feat-wsq-h\backend
# Arguments: main.py
#
# 或使用 uvicorn 方式:
# Arguments: -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 启动服务
.\nssm start TenderWord-API
```

## 📝 使用说明

### 基本使用流程

1. 访问前端页面 http://localhost:8502
2. 点击首页的 **"进入聊天模式"** 按钮，进入三栏式操作界面
3. 在左侧招标类型栏选择招标类型（询价采购 / 国内公开）
4. 在中间表单区域：
   - 输入招标编号，系统自动获取项目信息
   - 上传招标文件模板（Word 文件）
   - 上传技术参数文件（支持多文件上传）
   - 选择生成模型（DeepSeek / Qwen / Doubao）
5. 点击"开始生成"按钮，右侧聊天面板将实时显示生成进度和日志
6. 生成完成后，在聊天面板中查看结果并下载生成的招标文档

### 直接访问聊天页面

可以直接通过以下地址进入三栏聊天模式：

```
http://localhost:8502/chat
```

### URL 参数路由

系统支持通过 URL 参数直接进入聊天模式并自动选择招标类型:

```
http://localhost:8502/chat?tender_lx=0&purchase_method=5&fund_lx=0&tenderno=ZBGG-2024-001
```

**页面路由:**

- `/` - 首页（欢迎页面，点击进入聊天模式）
- `/chat` - 三栏聊天模式（左栏类型选择 / 中栏表单 / 右栏对话）

**参数说明:**
- `tender_lx`: 招标类型（0=询价, 1=国内公开, 2=邀请招标）
- `purchase_method`: 采购方式（5=询价采购, 1=国内公开, 2=邀请招标）
- `fund_lx`: 资金类型（0=国内, 1=国际）
- `tenderno`: 招标编号（可选，自动填充并获取数据）

**界面说明:**
- **左侧栏**: 招标类型选择，点击切换不同招标类型表单
- **中间栏**: 表单区域，填写招标编号、上传文件、选择模型
- **右侧栏**: 聊天面板，实时显示生成进度、日志和下载按钮
- 上传目录固定在 `D:/UploadFiles`，若同名文件存在会自动在文件名后加时间戳
- 支持多用户并发使用，系统会自动排队处理
## 🛠️ 开发指南

### 添加新的 Graph

1. 在 `backend/states/` 创建 State 类
2. 在 `backend/graphs/` 创建 Graph 类
3. 在 `backend/graphs/__init__.py` 导出 Graph

示例:
```python
# backend/graphs/my_graph.py
from graphs.base_graph import BaseGraph
from states import MyGraphState
from langgraph.graph import StateGraph, START, END

class MyGraph(BaseGraph):
    def get_state_class(self):
        return MyGraphState
    
    def build_graph(self):
        builder = StateGraph(MyGraphState)
        # ... 添加节点和边
        return builder
```

### 添加新的表单

1. 在 `frontend/components/forms/` 创建表单组件
2. 在 `backend/forms/` 创建对应的表单类
3. 在 `backend/config/form_config.py` 注册表单配置

### 添加 API 端点

```python
# backend/api/routes/my_route.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/my-feature")

@router.post("/action")
async def my_action(data: MySchema):
    # 实现逻辑
    return {"result": "success"}
```

## ❓ 常见问题

### Word COM 相关问题

**错误：无法创建 Word 应用程序实例**
- 运行 `python diagnose_word.py` 检查环境
- 确保已安装 Microsoft Word 或 WPS Office
- 检查 pywin32 是否正确安装：`pip install pywin32`
- 详细排查指南：[Word COM 问题排查指南](docs/Word_COM_问题排查指南.md)

### 端口占用问题

```powershell
# 检查端口占用
netstat -ano | findstr :8000

# 终止占用进程
taskkill /PID <进程ID> /F
```

### 前端无法连接后端

```powershell
# 检查后端服务是否运行
Invoke-WebRequest -Uri http://localhost:8000/health

# 检查 CORS 配置
# 确保 .env 中的 CORS_ORIGINS 包含前端地址 http://localhost:8502
```

### 并发相关问题

- 系统已实现自动排队机制，无需担心
- 如果出现长时间等待，检查是否有任务卡住
- 可以在界面上取消卡住的任务

### 文件上传失败

```powershell
# 检查上传目录是否存在
Test-Path D:\UploadFiles

# 确保应用进程对目录有读写权限
```

## 🛡️ 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | Next.js 16, React 19, TypeScript, Tailwind CSS 4 |
| **后端** | FastAPI, Python 3.10+, LangGraph |
| **LLM** | DeepSeek, Qwen, Doubao |
| **文档处理** | pywin32 (Word COM) |
| **状态管理** | Zustand |
| **部署** | Windows Service (NSSM) |

## 📖 相关文档

- [部署文档](docs/deployment.md) - 详细部署指南
- [Word COM 问题排查指南](docs/Word_COM_问题排查指南.md) - Word COM 环境排查
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [Next.js 文档](https://nextjs.org/docs)

## 📄 许可证

[添加许可证信息]

## 📞 联系方式

[添加联系方式]

---

**注意:** 本项目需要 Windows 环境才能完整运行，因为依赖 Microsoft Word COM 组件处理 Word 文档。
