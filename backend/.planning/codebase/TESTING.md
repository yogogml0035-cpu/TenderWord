# 后端测试事实地图

**分析日期：** 2026-05-31

**范围：** `backend/tests/` 与后端验证命令。

## 测试框架

- 框架：pytest。
- async 支持：pytest-asyncio。
- 入口：从 `backend/` 运行 `python -m pytest tests -v`。
- 共享 fixture：`backend/tests/conftest.py`。

## 测试文件组织

```text
backend/tests/
├── api/        # API route 行为
├── agents/     # DeepAgents 内容智能体运行时
├── config/     # tender_config 等配置约束
├── graphs/     # graph 注册、节点绑定、流程路由
├── helper/     # Word helper 纯逻辑
├── logging/    # audit/progress/execution log 路径
├── models/     # Pydantic 模型校验
├── nodes/      # Word 节点、skill 节点
├── progress/   # 进度追踪
├── prompts/    # prompt 文案与机器契约
├── services/   # service 编排
├── skills/     # task skill loader/声明
└── util/       # 通用工具
```

新增或重命名测试必须使用 `test_*.py`，不要放在 `backend/tests/` 根目录。

## 关键测试覆盖

- API：`backend/tests/api/test_generate_api.py`、`backend/tests/api/test_tender_api.py`。
- 类型配置：`backend/tests/config/test_tender_config_protected_fields.py`。
- graph 路由：`backend/tests/graphs/test_gngk_tender_graph.py`、`backend/tests/graphs/test_gjgk_tender_graph.py`。
- generation mode：`backend/tests/graphs/test_generation_mode_branching.py`、`test_generation_mode_workflow.py` 和各类型 `test_*_generation_mode_agent.py`。
- 内容智能体：`backend/tests/agents/test_generation_content_agent.py`、`backend/tests/nodes/test_content_agent_generate.py`。
- Word helper：`backend/tests/helper/test_content_ops.py`、`test_delete_ops.py`、`test_paragraph_boundary_ops.py`、`test_inline_style_ops.py`。
- 节点：`backend/tests/nodes/test_gngk_hw_cz_direct_replace_word.py`、`test_gngk_fw_zc_update_word.py`、`test_common_update_word_split.py`、`test_comment_writeback.py`。
- prompt：`backend/tests/prompts/test_generate_prompt_routing.py`、`test_comment_prompt_reference_contract.py`。
- service：`backend/tests/services/test_document_service_initial_state.py`、`test_document_service_task_result.py`、`test_user_routing_service.py`。
- agent_step SSE：`backend/tests/models/test_sse_agent_step.py`、`backend/tests/services/test_sse_manager_agent_step.py`、`backend/tests/services/test_document_service_agent_step.py`。
- 补充批注任务：`backend/tests/api/test_comment_supplement_api.py`、`backend/tests/graphs/test_comment_supplement_graph.py`、`backend/tests/services/test_document_service_comment_supplement.py`、`backend/tests/nodes/test_comment_agent_writeback_node.py`。

## Mock 与 fixture 模式

- Word COM 相关单测优先使用 fake document/range/paragraph 对象覆盖业务逻辑。
- LLM、HTTP、SSE 和文件系统副作用用 monkeypatch 或临时目录隔离。
- 真实 Word COM 只用于必要集成验收；当前多数后端测试不要求本机 Word。
- gngk graph 路由测试应同时断言 `GRAPH_REGISTRY` 和各兄弟类型节点绑定，避免继承链变更误扩散。
- generation mode 测试要同时证明默认 `workflow` 不触发 `content_agent`，以及 `agent` 分支产出的 `polished_text` 会继续进入各类型既有写回主干。

## COM 安全测试策略

- 能从 Word COM 中拆出的逻辑应进入 `backend/helper/word_helper/` 并用 fake 对象测试。
- `backend/util/word_util/` 的底层 COM 生命周期可用诊断脚本或 Windows 环境集成验证。
- WSL 下只能作为无 COM 替代验证，不能声称完成真实 Word 生成闭环。
- 对 direct-replace 类型，测试至少覆盖锚点范围、删除边界、写回正文、显式空行、Markdown 表格、样式回填摘要和批注硬失败契约。

## 覆盖缺口

- 真实 `.doc/.docx` + Word COM 端到端覆盖仍依赖人工或 Windows 环境。
- 任务队列、SSE、下载链路虽然有单元覆盖，但完整跨端 E2E 需要前端 Playwright 或手工环境。
- 外部模板候选和招标详情接口应继续通过 mock 测试，不依赖真实外部服务。

## 验证命令

后端常规验证：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -v
```

Word COM 诊断：

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\diagnose_word.py
```

WSL 无 COM 单测：

```bash
cd backend
TMPDIR=/tmp TMP=/tmp TEMP=/tmp .venv-linux/bin/python -m pytest tests -v
```

文档变更：

```bash
git diff --check
```

## 按变更类型选择测试

- API / 模型：相关 `backend/tests/api/`、`backend/tests/models/`，必要时全量 pytest。
- graph / 类型路由：`backend/tests/graphs/`、`backend/tests/services/test_document_service_initial_state.py`。
- Word helper：`backend/tests/helper/` 与使用该 helper 的节点测试。
- Word 节点：相关 `backend/tests/nodes/`，必要时全量 pytest。
- prompt：`backend/tests/prompts/` 与调用该 prompt 的节点/service 测试。
- content_agent / agent_step：`backend/tests/agents/`、`backend/tests/nodes/test_content_agent_generate.py`、`backend/tests/services/test_sse_manager_agent_step.py`、`backend/tests/services/test_document_service_agent_step.py`。
- comment_supplement：补充批注 API、graph、service 和 `comment_agent` 写回节点测试。
- 任务/SSE：`backend/tests/services/`、`backend/tests/progress/`、相关 API 测试。

---

*后端测试分析：2026-05-31*
