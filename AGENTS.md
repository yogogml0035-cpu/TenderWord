# PROJECT KNOWLEDGE BASE

**Generated:** 2026-03-01
**Commit:** 9e94cf4
**Branch:** feat-wsq-h

## OVERVIEW

TenderWord - 招标文档智能处理系统。基于 **Next.js 16 + FastAPI + LangGraph** 的前后端分离架构，支持多种招标类型文档的智能生成。依赖 Windows Word COM 进行文档处理。

## STRUCTURE

```
feat-wsq-h/
├── frontend/           # Next.js 16 前端 (React 19 + Tailwind 4)
├── backend/            # FastAPI 后端 (LangGraph 工作流引擎)
│   └── util/           # 共享工具库 (Word COM, LLM, 日志)
├── docs/               # 部署文档
└── .env                # 环境变量配置
```

## WHERE TO LOOK

| 任务 | 位置 | 说明 |
|------|------|------|
| 添加新招标类型 | `backend/graphs/`, `backend/nodes/` | 创建新 Graph + 节点 |
| 修改 API 端点 | `backend/api/` | FastAPI 路由 |
| 修改前端表单 | `frontend/components/forms/` | React 表单组件 |
| 修改 Word 处理 | `backend/util/word_util/` | Word COM 操作 |
| LLM 调用逻辑 | `backend/util/common_util/llm_stream_utils.py` | 多模型支持 |
| 环境配置 | `backend/config/settings.py` | Pydantic Settings |

## CODE MAP

| 模块 | 类型 | 位置 | 职责 |
|------|------|------|------|
| `BaseGraph` | 基类 | `backend/graphs/base_graph.py` | LangGraph 工作流基类，跨进程锁 |
| `StandardTenderWorkflowGraph` | 基类 | `backend/graphs/base_graph.py` | 标准招标工作流模板 |
| `CrossProcessFileLock` | 工具 | `backend/graphs/base_graph.py` | Windows 文件锁，保护 Word COM |
| `Settings` | 配置 | `backend/config/settings.py` | Pydantic 环境变量 |
| `useAppStore` | 状态 | `frontend/stores/useAppStore.ts` | Zustand 全局状态 |

## CONVENTIONS

### 后端 (Python)
- **入口点**: `backend/main.py` 使用工厂模式 `create_application()`
- **状态管理**: LangGraph TypedDict (`backend/states/`)
- **节点命名**: `xjcg_*.py` = 询价采购, `gngk_*.py` = 公开招标
- **导入约定**: 使用 `from backend.util.xxx import` 标准导入

### 前端 (TypeScript)
- **路径别名**: `@/*` 映射到项目根目录
- **状态管理**: Zustand + persist middleware
- **样式**: Tailwind CSS 4 + CSS 变量主题
- **命名**: 组件 PascalCase, hooks camelCase

## ANTI-PATTERNS (THIS PROJECT)

| 禁止 | 原因 | 位置 |
|------|------|------|
| 中文 npm 镜像 | 供应链风险 | `frontend/package-lock.json` |
| 无 CI/CD | 手动部署风险 | 项目缺失 |

## UNIQUE STYLES

### LangGraph 节点系统
- 节点按招标类型分组：`common_word_nodes/` (共享), `xjcg_word_nodes/`, `gngk_word_nodes/`
- 每个 Graph 继承 `BaseGraph`，实现 `build_graph()` 和 `get_state_class()`
- 节点函数通过 `wrap_node_with_progress()` 包装，自动追踪进度

### Word COM 并发控制
- 使用 `CrossProcessFileLock` (msvcrt.locking) 保护 Word 操作
- 任务队列实现公平锁 (`task_queue_manager.py`)
- 单进程串行执行 Word 操作

## COMMANDS

```bash
# 后端
cd backend && python main.py              # 启动后端 (port 8000)
cd backend && uvicorn backend.main:app --reload

# 前端
cd frontend && npm run dev                # 启动前端 (port 3000)
cd frontend && npm run build              # 生产构建
cd frontend && npm run test:e2e           # E2E 测试

# 类型检查
cd frontend && npm run lint               # ESLint
cd frontend && npm run format:check       # Prettier
```

## NOTES

1. **Windows 必需**: 依赖 Word COM，无法在 Linux/macOS 运行
2. **端口**: 前端 3000, 后端 8000 (CORS 已配置)
3. **上传目录**: `D:/UploadFiles` (硬编码)
4. **LLM 模型**: 支持 DeepSeek、Qwen、Doubao (通过环境变量配置)
