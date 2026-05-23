# 后端结构事实地图

**分析日期：** 2026-05-23

**范围：** `backend/` 源码、测试与后端相关启动脚本。

## 目录布局

```text
backend/
├── api/                  # FastAPI routers
├── config/               # settings 与招标类型配置
├── core/                 # SSE 等核心运行基础设施
├── graphs/               # LangGraph graph 类
├── helper/word_helper/   # Word 业务 helper
├── models/               # Pydantic API / runtime 模型
├── nodes/                # graph 节点
├── prompts/              # Prompt Layer
├── scripts/              # 后端诊断脚本
├── services/             # API 与 graph 之间的业务编排
├── skills/               # rewrite / edit task skill runtime
├── states/               # TypedDict graph state
├── task/                 # 任务队列
├── tests/                # pytest 测试
├── util/                 # 技术工具层
├── main.py               # FastAPI 入口
└── requirements.txt      # 后端依赖
```

## 目录职责

| 目录 | 当前职责 |
| --- | --- |
| `backend/api/` | `/api` router：生成、edit、任务、SSE、用户流式、会话心跳、上传、下载、招标详情、模板候选。 |
| `backend/models/` | `GenerateRequest`、`EditTaskRequest`、任务状态、SSE 事件、上传与模板候选模型。 |
| `backend/services/` | `DocumentService`、任务状态展示、会话快照、用户路由、模板候选 AI 重排。 |
| `backend/task/` | `TaskQueueManager`、任务实体、进度、取消、心跳。 |
| `backend/core/` | `SSEManager` 与 SSE 客户端/事件缓存。 |
| `backend/graphs/` | 标准 tender graph、rewrite/edit skill graph、user graph、base graph 锁与进度包装。 |
| `backend/states/` | 公共和类型专属 graph state。 |
| `backend/nodes/common_word_nodes/` | 共享 Word 节点：准备模板、抽参、替换、生成、批注、写回等。 |
| `backend/nodes/gngk_word_nodes/` | 国内公开特化节点；包含 `gngk_hw_cz` direct-replace delete/update。 |
| `backend/nodes/gjgk_word_nodes/` | 国际公开特化节点。 |
| `backend/nodes/xjcg_word_nodes/` | 询价采购特化 replacement 节点。 |
| `backend/nodes/skills_nodes/` | rewrite/edit task skill 节点与类型感知 Word dispatch。 |
| `backend/helper/word_helper/` | 可复用 Word 业务逻辑：边界、正文插入、cleanup、受保护字段、样式回填。 |
| `backend/util/word_util/` | COM 生命周期、Word 常量、锚点工具、底层插入与诊断。 |
| `backend/util/common_util/` | LLM 流式、招标详情 HTTP、模板候选 HTTP、上传存储、招标编号。 |
| `backend/util/log_util/` | 进度日志、执行日志、prompt 日志、skill audit、SSE 日志桥。 |
| `backend/prompts/` | generate、comment、routing、skill、模板候选重排 prompt。 |
| `backend/skills/` | task skill 声明、loader、registry、rewrite/edit workflow。 |
| `backend/tests/` | 按模块范围归档的 pytest 测试。 |

## 关键文件位置

### 运行入口

- `backend/main.py`：FastAPI app、router 注册、CORS、日志监听、SSE loop 绑定和健康检查。
- `backend/config/settings.py`：环境变量、端口、LLM provider、上传目录、SSE 保留、任务心跳、模板候选配置。
- `backend/config/tender_config.py`：锚点、字号、content start/update mode、受保护字段 profile、family 收敛。

### API 与服务

- `backend/api/generate.py`：`POST /api/generate`。
- `backend/api/edit.py`：`POST /api/edit`。
- `backend/api/user.py`：`POST /api/user/stream` NDJSON。
- `backend/api/tasks.py`：任务查询、取消、心跳。
- `backend/api/stream.py`：任务 SSE。
- `backend/api/template_candidates.py`：模板候选代理、下载、选择。
- `backend/services/document_service.py`：生成/rewrite/edit 的任务创建和 graph 执行编排。
- `backend/services/user_routing_service.py`：普通聊天与 rewrite 判路。
- `backend/services/template_candidate_ranking_service.py`：候选同优先级 AI 重排。

### Graph、State 与 Node

- `backend/graphs/base_graph.py`：`BaseGraph`、`StandardTenderWorkflowGraph`、跨进程锁、进度包装、取消检查。
- `backend/graphs/xjcg_tender_graph.py`：询价采购节点绑定。
- `backend/graphs/gngk_hw_zc_tender_graph.py`：国内公开货物自筹主干。
- `backend/graphs/gngk_hw_cz_tender_graph.py`：财政货物 graph，覆写 direct-replace delete/update。
- `backend/graphs/gngk_fw_zc_tender_graph.py`：服务自筹特化 delete/replacement/update。
- `backend/graphs/gngk_fw_cz_tender_graph.py`：服务财政 graph，当前继承共享主干。
- `backend/graphs/gjgk_tender_graph.py`：国际公开 graph，含自定义 Word 操作和 post-update 顺序。
- `backend/graphs/skill_graph.py`：rewrite/edit skill workflow 执行。
- `backend/graphs/user_graph.py`：用户消息路由。

### Word helper 与工具层

- `backend/helper/word_helper/content_ops.py`：正文写回、段落复用与插入。
- `backend/helper/word_helper/paragraph_boundary_ops.py`：真实段落边界处理。
- `backend/helper/word_helper/delete_ops.py`：锁感知删除。
- `backend/helper/word_helper/protected_fields.py`：受保护字段严格扫描与 profile 校验。
- `backend/helper/word_helper/inline_style_ops.py`：样式回填摘要。
- `backend/util/word_util/anchor_utils.py`：锚点查找和正文范围解析。
- `backend/util/word_util/word_application_util.py`：Word COM app/document 生命周期。
- `backend/util/word_util/word_com_manager.py`：COM 级锁与重试。
- `backend/util/word_util/word_insert_text.py`：底层文本/单元格插入规范化。

### 测试

- `backend/tests/api/`：API 层。
- `backend/tests/config/`：配置与 profile。
- `backend/tests/graphs/`：graph 注册与节点绑定。
- `backend/tests/helper/`：Word helper。
- `backend/tests/nodes/`：Word 节点与 skill 节点。
- `backend/tests/prompts/`：prompt 契约。
- `backend/tests/services/`：service 编排。
- `backend/tests/util/`：通用工具。

## 命名约定

- 后端测试文件必须是 `test_*.py`，并放在 `backend/tests/<module_scope>/`。
- 类型专属节点模块、导出 callable 和包级 re-export 使用类型前缀，例如 `gngk_hw_cz_update_word`。
- 通用节点名只放在 `backend/nodes/common_word_nodes/`。
- graph 类使用 PascalCase，例如 `GngkHwCzTenderGraph`。
- `FormType` 字符串使用 `<type>_tender`，例如 `gngk_hw_cz_tender`。
- 运行态 `tender_type` 使用无 `_tender` 后缀的类型名，例如 `gngk_hw_cz`。

## 新代码放置规则

- 新 API：放 `backend/api/`，模型同步放 `backend/models/`，编排优先放 `backend/services/`。
- 新生成类型：先补 `backend/models/generate.py`、`backend/config/tender_config.py`、`backend/graphs/`、`backend/states/`、`backend/services/document_service.py`。
- 新 Word 业务逻辑：两个以上类型会复用时放 `backend/helper/word_helper/`。
- 新 COM 技术工具：放 `backend/util/word_util/`。
- 新 prompt：放 `backend/prompts/`，同时补 prompt 契约测试。
- 新 task skill：放 `backend/skills/<skill>/`，并通过 loader/registry fail-fast。
- 新测试：按 API、config、graph、helper、node、prompt、service、util 等范围归档。

## 特殊目录

- `backend/.planning/codebase/`：后端事实地图，只做结构和风险导航，不替代代码真源。
- `backend/.venv/`：Windows 后端虚拟环境，不能在 WSL 中复用。
- `backend/.venv-linux/`：WSL/Linux 后端测试虚拟环境。
- `backend/skills/*/SKILL.md`：task skill 的声明真源。

---

*后端结构分析：2026-05-23*
