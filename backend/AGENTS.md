# backend/

FastAPI + LangGraph 后端，提供招标文档生成 API。

## STRUCTURE

```
backend/
├── api/                 # API 路由 (generate, stream, tasks, tender, upload)
├── graphs/              # LangGraph 工作流
│   ├── base_graph.py    # BaseGraph 基类 + CrossProcessFileLock
│   ├── xjcg_tender_graph.py   # 询价采购
│   └── gngk_tender_graph.py   # 公开招标
├── nodes/               # Graph 节点
│   ├── common_word_nodes/     # 通用节点
│   ├── xjcg_word_nodes/       # 询价采购节点
│   └── gngk_word_nodes/       # 公开招标节点
├── util/                # 共享工具库 (Word COM, LLM, 日志)
├── states/              # TypedDict 状态定义
├── models/              # Pydantic 模型
├── services/            # 业务逻辑
├── config/              # 配置 (settings.py)
└── main.py              # 入口，create_application()
```

## WHERE TO LOOK

| 任务 | 位置 |
|------|------|
| 添加新招标类型 | `graphs/`, `nodes/` |
| 修改 API 端点 | `api/*.py` |
| 修改数据模型 | `models/`, `states/` |
| 配置环境变量 | `config/settings.py` |
| Word 并发锁 | `graphs/base_graph.py` |
| Word 处理工具 | `util/word_util/` |
| LLM 调用逻辑 | `util/common_util/` |
## CONVENTIONS

- **状态**: 所有 State 继承 TypedDict，定义在 `states/`
- **Graph 继承**: 必须继承 `BaseGraph`，实现 `get_state_class()` 和 `build_graph()`
- **节点包装**: 使用 `wrap_node_with_progress()` 包装，自动上报进度
- **锁机制**: Word COM 操作前获取 `CrossProcessFileLock`，超时 300 秒
- **导入约定**: 使用 `from backend.util.xxx import` 标准导入
- **异常处理**: 使用 `logger.error/debug` 替代 `print()` 和空 `except:`
## ANTI-PATTERNS

| 禁止 | 位置 |
|------|------|
| 无锁 Word 操作 | 必须先用 `CrossProcessFileLock` |
| 同步阻塞 | 节点函数用 `run_in_executor` 包装 |
| 空 `except:` | 使用 `except Exception as e: logger.xxx()` |
## COMMANDS

```bash
cd backend && python main.py              # 开发启动 (port 8000)
uvicorn backend.main:app --reload         # 热重载模式
```
