# backend/

**Generated:** 2026-03-03  
**Commit:** 998002b  
**Branch:** feat-wsq-h

FastAPI + LangGraph 后端，提供招标文档生成 API。

## STRUCTURE

```
backend/
├── api/                          # API 路由
│   ├── upload.py                 # 文件上传 (POST /api/upload)
│   ├── tender.py                 # 招标数据获取 (GET /api/tender/info/{tender_no})
│   ├── generate.py               # 文档生成 (POST /api/generate)
│   ├── tasks.py                  # 任务管理 (GET/DELETE /api/tasks/{task_id})
│   ├── stream.py                 # SSE 流式输出 (GET /api/stream/{task_id})
│   └── download.py               # 文件下载 (GET /api/download/{filename})
│
├── graphs/                       # LangGraph 工作流
│   ├── base_graph.py             # BaseGraph 基类 + CrossProcessFileLock + StandardTenderWorkflowGraph
│   ├── xjcg_tender_graph.py      # 询价采购 (XJCG) 工作流
│   └── gngk_tender_graph.py      # 公开招标 (GNGK) 工作流
│
├── nodes/                        # Graph 节点
│   ├── common_word_nodes/        # 通用节点 (10个，XJCG/GNGK 共享)
│   │   ├── __init__.py
│   │   ├── prepare_template.py           # 准备模板文件
│   │   ├── extract_tender_params.py      # 提取招标参数
│   │   ├── delete_tender_param.py        # 删除技术参数章节
│   │   ├── get_comments.py               # 提取送审稿批注
│   │   ├── copy_comments.py              # 复制批注到目标文档
│   │   ├── generate_polished_text.py     # 生成润色文本
│   │   ├── generate_comments.py          # 生成润色批注
│   │   ├── get_replacements_core.py      # 核心替换逻辑
│   │   ├── replace_content.py            # 执行内容替换
│   │   └── update_word.py                # 更新 Word 文档
│   │
│   ├── xjcg_word_nodes/          # 询价采购特有节点
│   │   ├── __init__.py
│   │   └── xjcg_get_replacements.py      # XJCG 替换占位符生成
│   │
│   └── gngk_word_nodes/          # 公开招标特有节点
│       ├── __init__.py
│       └── gngk_get_replacements.py      # GNGK 替换占位符生成
│
├── states/                       # TypedDict 状态定义
│   ├── __init__.py
│   ├── base_state.py             # BaseState + TenderGraphStateBase (共享字段)
│   ├── xjcg_tender_state.py      # XJCG 特有状态字段
│   └── gngk_tender_state.py      # GNGK 特有状态字段
│
├── util/                         # 共享工具库 (重构后统一位置)
│   ├── __init__.py
│   │
│   ├── word_util/                # Word COM 操作
│   │   ├── __init__.py
│   │   ├── word_com_manager.py           # Word COM 实例管理
│   │   ├── word_application_util.py      # Word 应用工具
│   │   ├── word_extraction_utils.py      # 文本提取工具
│   │   ├── word_document_inspector.py    # 文档检查工具
│   │   ├── word_diagnostics.py           # Word 诊断工具
│   │   ├── anchor_utils.py               # 锚点定位工具
│   │   └── word_constants.py             # Word 常量定义
│   │
│   ├── common_util/              # 通用工具
│   │   ├── __init__.py
│   │   ├── llm_stream_utils.py           # LLM 流式调用 (DeepSeek/Qwen/Doubao)
│   │   └── fetch_tender_data.py          # 招标数据获取
│   │
│   └── log_util/                 # 日志系统
│       ├── __init__.py
│       ├── progress_log.py               # 进度日志 (QueueHandler, 推送到SSE)
│       ├── execution_log.py              # 执行日志 (调试用途)
│       ├── sse_log_handler.py            # SSE 日志推送 Handler
│       └── log_cleanup.py                # 日志文件清理
│
├── task/                         # 任务队列管理
│   ├── __init__.py
│   └── task_queue_manager.py     # 公平锁 + 任务队列
│
├── core/                         # 核心组件
│   ├── __init__.py
│   └── sse_manager.py            # SSE 连接管理
│
├── config/                       # 配置
│   ├── __init__.py
│   ├── settings.py               # Pydantic Settings (环境变量)
│   └── tender_config.py          # 招标类型枚举和配置
│
├── models/                       # Pydantic 模型
│   ├── __init__.py
│   ├── common.py
│   ├── generate.py
│   ├── upload.py
│   ├── task.py
│   ├── tender.py
│   └── sse.py
│
├── services/                     # 业务逻辑
│   ├── __init__.py
│   ├── document_service.py
│   └── task_service.py
│
├── tests/                        # 测试文件
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_generate_comments.py
│   ├── test_get_replacements_core.py
│   ├── test_xjcg_tender_graph.py
│   └── generate_t8_t10_evidence.py
│
├── scripts/                      # 脚本工具
│   ├── __init__.py
│   └── diagnose_word.py          # Word COM 环境诊断
│
└── main.py                       # 应用入口 (create_application)
```

## CODE MAP

| 模块 | 类型 | 位置 | 职责 |
|------|------|------|------|
| `BaseGraph` | 抽象基类 | `graphs/base_graph.py` | Graph 基类，提供锁和进度追踪 |
| `StandardTenderWorkflowGraph` | 基类 | `graphs/base_graph.py` | 标准招标工作流模板 |
| `CrossProcessFileLock` | 工具类 | `graphs/base_graph.py` | Windows 跨进程文件锁 (msvcrt.locking) |
| `TaskQueueManager` | 单例类 | `task/task_queue_manager.py` | 公平任务队列，确保按顺序执行 |
| `TenderGraphStateBase` | TypedDict | `states/base_state.py` | 招标工作流共享状态字段 |
| `Settings` | Pydantic | `config/settings.py` | 环境变量配置管理 |
| `SSEManager` | 单例类 | `core/sse_manager.py` | SSE 连接管理和事件推送 |
| `SSELogHandler` | Handler | `util/log_util/sse_log_handler.py` | 将日志实时推送到前端 |
| `progress_log` | Logger | `util/log_util/progress_log.py` | 线程安全进度日志 |
| `execution_log` | Logger | `util/log_util/execution_log.py` | 执行日志（调试） |
| `wrap_node_with_progress` | 装饰器 | `graphs/base_graph.py` | 包装节点，自动上报进度 |

## WHERE TO LOOK

| 任务 | 位置 | 说明 |
|------|------|------|
| **添加新招标类型** | `graphs/`, `nodes/`, `states/` | 创建 Graph + 特有节点 + State |
| **修改 API 端点** | `api/*.py` | FastAPI 路由定义 |
| **修改数据模型** | `models/`, `states/` | Pydantic / TypedDict |
| **配置环境变量** | `config/settings.py` | Pydantic Settings |
| **Word 并发锁** | `graphs/base_graph.py` | CrossProcessFileLock |
| **Word 处理工具** | `util/word_util/` | COM 操作工具集 |
| **LLM 调用逻辑** | `util/common_util/llm_stream_utils.py` | 多模型流式输出 |
| **日志系统** | `util/log_util/` | 进度/执行/SSE日志 |
| **任务队列** | `task/task_queue_manager.py` | 公平锁机制 |
| **招标类型配置** | `config/tender_config.py` | 招标类型枚举 |

## CONVENTIONS

### Graph 开发约定

1. **继承 BaseGraph**: 所有 Graph 必须继承 `BaseGraph`
   ```python
   class MyGraph(BaseGraph):
       def build_graph(self): ...
       def get_state_class(self): ...
   ```

2. **实现抽象方法**:
   - `build_graph()` - 构建 graph 结构，返回 StateGraph
   - `get_state_class()` - 返回使用的 state 类 (Type[TypedDict])

3. **节点包装**: 使用 `self.wrap_node(name, func)` 包装节点函数
   - 自动追踪进度
   - 自动检查任务取消状态
   - 自动上报节点完成状态

4. **并发控制**: Word COM 操作前自动获取 `CrossProcessFileLock`
   - 通过 `invoke_with_timing_async` 自动管理
   - 双层锁：公平锁（队列顺序）+ 文件锁（跨进程互斥）

### State 定义约定

```python
class MyGraphState(TenderGraphStateBase, total=False):
    my_field: str
    # total=False 允许字段可选，提高灵活性
```

### 日志记录约定

- **进度日志**: `progress_log.info/debug()` - 用于任务进度，**会推送到前端**
- **执行日志**: `execution_log.info/debug()` - 用于调试，**写入文件不推送**
- **SSE 上下文**: 使用 `task_log_context(task_id)` 上下文管理器
  ```python
  from backend.util.log_util.sse_log_handler import task_log_context
  
  with task_log_context(task_id):
      progress_log.info("这条日志会推送到前端")
  ```

### 导入约定

- **标准导入**: `from backend.util.xxx import`
- **避免相对导入**: 使用绝对导入路径

### 异常处理

```python
# ✅ 正确
from backend.util.log_util.progress_log import progress_log

try:
    result = some_operation()
except Exception as e:
    progress_log.error(f"操作失败: {e}")
    raise

# ❌ 禁止
try:
    result = some_operation()
except:  # 空 except
    pass

# ❌ 禁止
print("错误信息")  # 使用 progress_log 替代
```

## ANTI-PATTERNS

| 禁止 | 原因 | 正确做法 |
|------|------|----------|
| **无锁 Word 操作** | 并发冲突，COM 错误 | 使用 `CrossProcessFileLock` |
| **同步阻塞** | 阻塞事件循环 | 节点函数用 `run_in_executor` 包装 |
| **空 `except:`** | 吞掉异常，难以调试 | `except Exception as e: logger.xxx()` |
| **`print()` 输出** | 无法推送到前端，难追踪 | 使用 `progress_log` |

## WORKFLOW

### 标准招标工作流 (StandardTenderWorkflowGraph)

```
START
  ↓
prepare_template ─────────────────→ extract_tender_params ──────────┐
  ↓                                                                 ↓
get_comments ─→ copy_comments ─→ comments_ready ←───────────────────┘
                                     ↓
                              word_operations_subgraph
                              (delete_tender_param → get_replacements → replace_content)
                                     ↓
generate_polished_text ────────────────────────────────────────────→ update_word → END
  ↓
generate_comments (可选，有送审稿时)
  ↓
comments_branch_done
```

### 并发执行流程

```
任务入队
  ↓
等待公平锁（按队列顺序）
  ↓
获取文件锁（跨进程互斥）
  ↓
执行 Word COM 操作
  ↓
释放锁，通知下一个任务
```

## COMMANDS

```bash
# 启动后端
cd backend && python main.py              # 启动服务 (port 8000)
cd backend && uvicorn backend.main:app --reload  # 热重载模式

# 日志查看
cd backend && cat logs/progress-$(date +%Y%m%d).log
cd backend && cat logs/execution-$(date +%Y%m%d).log

# 测试
cd backend && python -m pytest tests/ -v

# Word COM 诊断
cd backend && python scripts/diagnose_word.py
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

## REFACTORING NOTES

### 2026-03-03 重大变更 (commit 998002b)

1. **工具模块迁移**: 从根目录 `util/` 迁移至 `backend/util/`
2. **日志系统重构**: 分离 `progress_log` 和 `execution_log`，新增 `sse_log_handler`
3. **通用节点合并**: 将 XJCG/GNGK 通用逻辑合并到 `common_word_nodes/`
4. **配置集中**: 招标类型配置统一到 `backend/config/tender_config.py`

### 开发注意事项

- 所有工具模块导入必须使用 `from backend.util.xxx import`
- 日志记录使用 `progress_log` 而非 `print()`
- Word 操作必须通过 BaseGraph 的异步方法执行以确保并发安全
- 新增招标类型需要：Graph 类 + State 类 + 特有节点（如有）
