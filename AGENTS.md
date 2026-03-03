# PROJECT KNOWLEDGE BASE

**Generated:** 2026-03-03
**Commit:** 998002b
**Branch:** feat-wsq-h

## OVERVIEW

TenderWord - 招标文档智能处理系统。基于 **Next.js 16 + FastAPI + LangGraph** 的前后端分离架构，支持多种招标类型文档的智能生成。依赖 Windows Word COM 进行文档处理。

### 核心特性
- **LangGraph 工作流引擎**：支持询价采购(XJCG)和公开招标(GNGK)两种招标类型
- **实时日志流**：通过 SSE 推送任务进度和 LLM 生成内容
- **并发控制**：跨进程文件锁 + 公平任务队列确保 Word COM 操作安全
- **多模型支持**：DeepSeek、Qwen(DashScope)、Doubao(ARK)

## STRUCTURE

```
feat-wsq-h/
├── frontend/              # Next.js 16 前端 (React 19 + Tailwind 4)
│   ├── app/               # App Router
│   ├── components/
│   │   ├── forms/         # 表单组件 (XjcgTenderForm, GngkTenderForm)
│   │   └── layout/        # 布局组件 (Header, Sidebar, MainLayout)
│   ├── stores/            # Zustand 状态管理
│   ├── hooks/             # React Hooks (useSSE)
│   └── types/             # TypeScript 类型定义
│
├── backend/               # FastAPI 后端 (LangGraph 工作流引擎)
│   ├── api/               # API 路由
│   │   ├── upload.py      # 文件上传
│   │   ├── tender.py      # 招标数据获取
│   │   ├── generate.py    # 文档生成
│   │   ├── tasks.py       # 任务管理
│   │   ├── stream.py      # SSE 流式输出
│   │   └── download.py    # 文件下载
│   │
│   ├── graphs/            # LangGraph 工作流
│   │   ├── base_graph.py  # BaseGraph 基类 + CrossProcessFileLock
│   │   ├── xjcg_tender_graph.py  # 询价采购工作流
│   │   └── gngk_tender_graph.py  # 公开招标工作流
│   │
│   ├── nodes/             # Graph 节点
│   │   ├── common_word_nodes/    # 通用节点 (10个)
│   │   │   ├── prepare_template.py
│   │   │   ├── extract_tender_params.py
│   │   │   ├── delete_tender_param.py
│   │   │   ├── get_comments.py
│   │   │   ├── copy_comments.py
│   │   │   ├── generate_polished_text.py
│   │   │   ├── generate_comments.py
│   │   │   ├── get_replacements_core.py
│   │   │   ├── replace_content.py
│   │   │   └── update_word.py
│   │   ├── xjcg_word_nodes/      # 询价采购特有节点
│   │   └── gngk_word_nodes/      # 公开招标特有节点
│   │
│   ├── states/            # TypedDict 状态定义
│   │   ├── base_state.py           # BaseState + TenderGraphStateBase
│   │   ├── xjcg_tender_state.py
│   │   └── gngk_tender_state.py
│   │
│   ├── util/              # 共享工具库 (重构后统一位置)
│   │   ├── word_util/     # Word COM 操作
│   │   │   ├── word_com_manager.py
│   │   │   ├── word_application_util.py
│   │   │   ├── word_extraction_utils.py
│   │   │   ├── word_document_inspector.py
│   │   │   ├── word_diagnostics.py
│   │   │   ├── anchor_utils.py
│   │   │   └── word_constants.py
│   │   ├── common_util/   # 通用工具
│   │   │   ├── llm_stream_utils.py
│   │   │   └── fetch_tender_data.py
│   │   └── log_util/      # 日志系统
│   │       ├── progress_log.py      # 进度日志 (QueueHandler)
│   │       ├── execution_log.py     # 执行日志
│   │       ├── sse_log_handler.py   # SSE 日志推送
│   │       └── log_cleanup.py       # 日志清理
│   │
│   ├── task/              # 任务队列管理
│   │   └── task_queue_manager.py    # 公平锁 + 任务队列
│   │
│   ├── core/              # 核心组件
│   │   └── sse_manager.py           # SSE 连接管理
│   │
│   ├── config/            # 配置
│   │   ├── settings.py              # Pydantic Settings
│   │   └── tender_config.py         # 招标类型配置
│   │
│   ├── models/            # Pydantic 模型
│   ├── services/          # 业务逻辑
│   └── main.py            # 应用入口 (create_application)
│
├── docs/                  # 部署文档
│   ├── deployment.md
│   └── API_CONTRACT.md
│
├── assert/                # 项目文档
│   └── gngk_xjcg_graph_postmortem.md
│
└── .env                   # 环境变量配置
```

## WHERE TO LOOK

| 任务 | 位置 | 说明 |
|------|------|------|
| **添加新招标类型** | `backend/graphs/`, `backend/nodes/`, `backend/states/` | 创建新 Graph + 节点 + State |
| **修改 API 端点** | `backend/api/*.py` | FastAPI 路由 |
| **修改前端表单** | `frontend/components/forms/` | React 表单组件 |
| **修改 Word 处理** | `backend/util/word_util/` | Word COM 操作 |
| **修改 LLM 调用** | `backend/util/common_util/llm_stream_utils.py` | 多模型流式输出 |
| **修改日志系统** | `backend/util/log_util/` | 进度日志、执行日志、SSE Handler |
| **修改任务队列** | `backend/task/task_queue_manager.py` | 公平锁机制 |
| **环境配置** | `backend/config/settings.py` | Pydantic Settings |
| **前端状态** | `frontend/stores/useAppStore.ts` | Zustand 全局状态 |
| **招标类型配置** | `backend/config/tender_config.py` | 招标类型枚举和配置 |

## CODE MAP

| 模块 | 类型 | 位置 | 职责 |
|------|------|------|------|
| `BaseGraph` | 基类 | `backend/graphs/base_graph.py` | LangGraph 工作流基类，提供跨进程锁和进度追踪 |
| `StandardTenderWorkflowGraph` | 基类 | `backend/graphs/base_graph.py` | 标准招标工作流模板，定义通用节点链 |
| `CrossProcessFileLock` | 工具 | `backend/graphs/base_graph.py` | Windows 文件锁 (msvcrt.locking)，保护 Word COM |
| `TaskQueueManager` | 服务 | `backend/task/task_queue_manager.py` | 公平任务队列，确保按顺序执行 |
| `Settings` | 配置 | `backend/config/settings.py` | Pydantic Settings，管理环境变量 |
| `TenderGraphStateBase` | 状态 | `backend/states/base_state.py` | 招标工作流基础状态类 |
| `SSEManager` | 服务 | `backend/core/sse_manager.py` | SSE 连接管理和事件推送 |
| `SSELogHandler` | Handler | `backend/util/log_util/sse_log_handler.py` | 将日志实时推送到前端 |
| `progress_log` | Logger | `backend/util/log_util/progress_log.py` | 线程安全进度日志 (QueueHandler) |
| `execution_log` | Logger | `backend/util/log_util/execution_log.py` | 执行日志，用于调试 |
| `useAppStore` | Store | `frontend/stores/useAppStore.ts` | Zustand 全局状态，包含招标类型、任务进度 |
| `wrap_node_with_progress` | 装饰器 | `backend/graphs/base_graph.py` | 包装节点函数，自动上报进度和检查取消 |

## CONVENTIONS

### 后端 (Python)

#### 项目结构约定
- **入口点**: `backend/main.py` 使用工厂模式 `create_application()`
- **状态管理**: LangGraph TypedDict，继承 `BaseState` (`backend/states/`)
- **节点组织**: 
  - `common_word_nodes/` - 招标类型通用节点
  - `xjcg_word_nodes/` - 询价采购特有节点
  - `gngk_word_nodes/` - 公开招标特有节点
- **节点命名**: `xjcg_*.py` = 询价采购, `gngk_*.py` = 公开招标
- **导入约定**: 使用 `from backend.util.xxx import` 标准导入

#### Graph 开发约定
1. **继承 BaseGraph**: 所有 Graph 必须继承 `BaseGraph`
2. **实现抽象方法**: 
   - `build_graph()` - 构建 graph 结构
   - `get_state_class()` - 返回使用的 state 类
3. **节点包装**: 使用 `self.wrap_node(name, func)` 包装节点函数，自动追踪进度
4. **并发控制**: Word COM 操作前自动获取 `CrossProcessFileLock`（通过 `invoke_with_timing_async`）
5. **异常处理**: 使用 `progress_log.error/debug` 替代 `print()`，禁止空 `except:`

#### State 定义约定
```python
class MyGraphState(TenderGraphStateBase, total=False):
    my_field: str
    # total=False 允许字段可选
```

#### 日志记录约定
- **进度日志**: `progress_log.info/debug()` - 用于任务进度，会推送到前端
- **执行日志**: `execution_log.info/debug()` - 用于调试，写入文件不推送
- **SSE 日志**: 使用 `task_log_context(task_id)` 上下文管理器

### 前端 (TypeScript)

#### 项目结构约定
- **路径别名**: `@/*` 映射到项目根目录
- **状态管理**: Zustand + persist middleware，Store 文件用 `useXxxStore.ts`
- **组件组织**: 按功能域分目录（forms/, layout/），非按类型分
- **样式**: Tailwind CSS 4 + CSS 变量主题，不使用 `tailwind.config.ts`
- **类型导出**: `types/index.ts` 统一导出，组件就近定义 Props
- **命名**: 组件 PascalCase, hooks camelCase

#### API 调用约定
- 使用封装好的 API 方法，不直接调用 `fetch`
- SSE 连接使用 `useSSE` hook

## ANTI-PATTERNS (THIS PROJECT)

| 禁止 | 原因 | 位置 |
|------|------|------|
| **中文 npm 镜像** | 供应链风险 | `frontend/package-lock.json` |
| **无锁 Word 操作** | 必须先用 `CrossProcessFileLock` 保护 | `backend/graphs/base_graph.py` |
| **同步阻塞** | 节点函数用 `run_in_executor` 包装 | `backend/nodes/` |
| **空 `except:`** | 使用 `except Exception as e: logger.xxx()` | 所有 Python 文件 |
| **`print()` 输出** | 使用 `progress_log` 或 `execution_log` | 所有 Python 文件 |
| **`use client` 滥用** | 增加客户端 bundle，检查必要性 | `frontend/components/` |
| **无 CI/CD** | 手动部署风险 | 项目缺失 |

## UNIQUE STYLES

### LangGraph 节点系统

#### 节点分组
- `common_word_nodes/` - 通用节点（10个）：prepare_template, extract_tender_params, delete_tender_param, get_comments, copy_comments, generate_polished_text, generate_comments, get_replacements_core, replace_content, update_word
- `xjcg_word_nodes/` - 询价采购特有：xjcg_get_replacements
- `gngk_word_nodes/` - 公开招标特有：gngk_get_replacements

#### Graph 结构
每个 Graph 继承 `StandardTenderWorkflowGraph`，它定义了标准工作流：
1. **准备阶段**: prepare_template → extract_tender_params
2. **批注分支**: get_comments → copy_comments（可选，需上传送审稿）
3. **Word 操作子图**: delete_tender_param → get_replacements → replace_content
4. **润色分支**: generate_polished_text → generate_comments（可选）
5. **更新文档**: update_word

#### 进度追踪
- 节点函数通过 `wrap_node_with_progress()` 包装
- 自动上报进度到 `TaskQueueManager`
- 支持任务取消检查（`_check_cancellation`）

### Word COM 并发控制

#### 双层锁机制
1. **公平锁** (`TaskQueueManager`): 确保任务按队列顺序执行
2. **文件锁** (`CrossProcessFileLock`): 使用 Windows `msvcrt.locking` 实现跨进程互斥

#### 执行流程
```
任务入队 → 等待公平锁（按顺序）→ 获取文件锁 → 执行 Word COM 操作 → 释放锁
```

### 日志系统架构

#### 三层日志
1. **标准日志**: FastAPI/uvicorn 的 JSON 格式日志
2. **进度日志** (`progress_log`): 
   - QueueHandler + QueueListener 确保线程安全
   - 推送到 SSE，前端实时显示
   - 写入 `backend/logs/progress-YYYYMMDD.log`
3. **执行日志** (`execution_log`):
   - 用于调试，不推送到前端
   - 写入 `backend/logs/execution-YYYYMMDD.log`

#### SSE 日志推送
- 使用 `task_log_context(task_id)` 上下文管理器
- 只推送 INFO 及以上级别日志
- 通过 `SSELogHandler` 发送到 `SSEManager`

### SSE 实时通信

#### 事件类型
- `log`: 普通日志消息
- `llm`: LLM 生成内容流
- `progress`: 进度更新（节点完成状态）
- `done`: 任务完成
- `error`: 错误信息

#### 断线重连
- 支持 `Last-Event-ID` 请求头
- 服务端从该事件ID之后继续发送
- 心跳机制：每 15 秒发送 `: heartbeat`

## COMMANDS

### 后端

```bash
# 启动后端
cd backend && python main.py              # 启动后端 (port 8000)
cd backend && uvicorn backend.main:app --reload  # 热重载模式

# 日志查看
cd backend && cat logs/progress-$(date +%Y%m%d).log
cd backend && cat logs/execution-$(date +%Y%m%d).log

# 测试
cd backend && python -m pytest tests/ -v
```

### 前端

```bash
# 开发
cd frontend && npm run dev                # 启动前端 (port 3000)

# 构建
cd frontend && npm run build              # 生产构建
cd frontend && npm run start              # 启动生产服务器

# 类型检查
cd frontend && npm run lint               # ESLint
cd frontend && npm run format             # Prettier 格式化
cd frontend && npm run format:check       # Prettier 检查

# 测试
cd frontend && npm run test:e2e           # Playwright E2E 测试
```

### 诊断工具

```bash
# Word COM 环境诊断
cd backend && python scripts/diagnose_word.py

# 查看任务队列状态
# 访问 http://localhost:8000/api/tasks/queue

# 健康检查
# 访问 http://localhost:8000/health
```

## API ENDPOINTS

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/api/upload` | 文件上传 |
| GET | `/api/tender/info/{tender_no}` | 获取招标信息 |
| POST | `/api/generate` | 生成招标文档 |
| GET | `/api/tasks/{task_id}` | 获取任务状态 |
| DELETE | `/api/tasks/{task_id}` | 取消任务 |
| GET | `/api/tasks/queue` | 获取队列状态 |
| GET | `/api/stream/{task_id}` | SSE 流式输出 |
| GET | `/api/download/{filename}` | 下载文件 |
| GET | `/health` | 健康检查 |

## NOTES

1. **Windows 必需**: 依赖 Word COM，无法在 Linux/macOS 运行
2. **端口**: 前端 3000, 后端 8000 (CORS 已配置)
3. **上传目录**: `D:/UploadFiles` (在 `settings.py` 中配置)
4. **日志目录**: `backend/logs/` (自动创建)
5. **LLM 模型**: 支持 DeepSeek、Qwen、Doubao (通过环境变量配置)
6. **并发限制**: Word COM 操作串行执行，支持多任务排队
7. **招标类型**: 当前支持 XJCG(询价采购) 和 GNGK(公开招标)

## REFACTORING NOTES (2026-03-03)

### 最近重大变更 (commit 998002b)
1. **工具模块迁移**: 从根目录 `util/` 迁移至 `backend/util/`，统一后端代码结构
2. **日志系统重构**: 分离 `progress_log` 和 `execution_log`，新增 `sse_log_handler`
3. **通用节点合并**: 将 XJCG/GNGK 通用逻辑合并到 `common_word_nodes/`
4. **配置集中**: 招标类型配置统一到 `backend/config/tender_config.py`
5. **前端状态更新**: 更新组件类名和状态类型定义
6. **文件清理**: 删除根级别过时模块，更新环境配置示例
7. **文档完善**: 添加项目结构文档 (AGENTS.md)

### 开发注意事项
- 所有工具模块导入必须使用 `from backend.util.xxx import`
- 日志记录使用 `progress_log` 而非 `print()`
- Word 操作必须通过 BaseGraph 的异步方法执行以确保并发安全
- 新增招标类型需要：Graph 类 + State 类 + 特有节点（如有）
