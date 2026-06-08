# 后端测试模式

**分析日期：** 2026-06-08

**范围：** `backend/tests/`、`backend/requirements.txt`、`backend/scripts/diagnose_word.py`、`docs/backend.md` 和与测试直接相关的后端实现文件。

**关键事实来源：**
- 测试配置与依赖：`backend/requirements.txt`、`backend/tests/conftest.py`
- API 与 service 测试：`backend/tests/api/test_generate_api.py`、`backend/tests/api/test_agent_run_api.py`、`backend/tests/api/test_template_candidates.py`、`backend/tests/services/test_document_service_task_result.py`、`backend/tests/services/test_agent_run_service.py`
- Graph、skill、node 测试：`backend/tests/graphs/test_generation_mode_branching.py`、`backend/tests/graphs/test_gngk_tender_graph.py`、`backend/tests/skills/test_task_skill_runtime.py`、`backend/tests/nodes/test_rewrite_nodes.py`、`backend/tests/nodes/test_tender_aware_word_dispatch.py`
- Word helper 与 agent/retrieval 测试：`backend/tests/helper/test_inline_style_ops.py`、`backend/tests/nodes/test_protected_fields_strict_matching.py`、`backend/tests/agents/test_generation_content_agent.py`、`backend/tests/agents/test_task_context_assistant_logging.py`、`backend/tests/retrieval/test_comment_bad_case_runtime.py`

## 测试框架

**运行器：**
- pytest `>=8.3.0`，声明在 `backend/requirements.txt`。
- pytest-asyncio `>=0.24.0`，声明在 `backend/requirements.txt`。
- 配置： 未检测到后端专用 `pytest.ini`、`pyproject.toml` 或 `setup.cfg`。

**断言库：**
- pytest 原生 `assert`。
- FastAPI `HTTPException`、Pydantic `model_validate()`、LangGraph 编译结果、局部 fake objects 按测试文件局部使用。

**运行命令：**

```bash
cd backend
python -m pytest tests -v              # 运行全部后端测试
python -m pytest tests/api -v          # 运行 API 测试
python -m pytest tests/graphs -v       # 运行 graph 测试
python -m pytest tests/nodes -v        # 运行 node 测试
```

Windows 虚拟环境：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -v
```

WSL/Linux 无 COM 虚拟环境：

```bash
cd backend
TMPDIR=/tmp TMP=/tmp TEMP=/tmp .venv-linux/bin/python -m pytest tests -v
```

Word COM 诊断：

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\diagnose_word.py
```

## 测试文件组织

**位置：**
- 测试集中在 `backend/tests/<scope>/`，不与源码 co-locate。
- `backend/tests/conftest.py` 只负责把项目根和 `backend/` 加入 `sys.path`，没有全局 fixture 注入。
- 当前检测到 72 个 `backend/tests/**/test_*.py` 文件。

**命名：**
- 所有提交测试使用 `test_*.py`。
- 测试函数使用 `test_<行为>_<期望>()`，例如 `test_stream_agent_run_returns_ndjson_stream()`、`test_agent_branch_uses_content_and_skips_generate_polished_text()`。
- 测试目录按后端关注点镜像：`api`、`agents`、`config`、`graphs`、`helper`、`logging`、`models`、`nodes`、`progress`、`prompts`、`retrieval`、`services`、`skills`、`util`。

**结构：**

```text
backend/tests/
├── agents/
├── api/
├── config/
├── graphs/
├── helper/
├── logging/
├── models/
├── nodes/
├── progress/
├── prompts/
├── retrieval/
├── services/
├── skills/
└── util/
```

## 测试结构

**测试套件组织：**

```python
@pytest.mark.asyncio
async def test_stream_agent_run_returns_ndjson_stream(monkeypatch) -> None:
    class FakeAgentRunService:
        async def stream(self, request, payload):
            assert payload.conversation_id == "conv-1"
            yield '{"event":"run_started","data":{"run_id":"run-1"}}\n'

    monkeypatch.setattr(agent_api, "get_agent_run_service", lambda: FakeAgentRunService())

    response = await agent_api.stream_agent_run(_Request(), payload)

    assert response.media_type == "application/x-ndjson"
```

**模式：**
- API 测试优先直接调用 router 函数并断言返回模型或 `HTTPException`，参考 `backend/tests/api/test_generate_api.py`、`backend/tests/api/test_template_candidates.py`。
- Service 测试通过 `__new__()`、依赖注入、局部 fake executor 或 `tmp_path` 避免真实队列、LLM 和 COM 副作用，参考 `backend/tests/services/test_document_service_task_result.py`、`backend/tests/services/test_agent_run_service.py`。
- Graph 测试构造最小 `StandardTenderWorkflowGraph` 子类，断言分支、节点顺序和 state patch，参考 `backend/tests/graphs/test_generation_mode_branching.py`。
- Word helper/node 测试用 fake COM document/range/paragraph/font 对象覆盖边界逻辑，参考 `backend/tests/helper/test_inline_style_ops.py`、`backend/tests/nodes/test_protected_fields_strict_matching.py`。
- Agent 和 prompt 测试优先断言协议文本、workspace 文件协议、事件 payload、scrub 行为，不调用真实模型，参考 `backend/tests/agents/test_generation_content_agent.py`。

## Mock 方式

**框架：** pytest `monkeypatch` + 局部 fake class/function + `tmp_path`。

**模式：**

```python
def fake_fetch_template_file(file_url: str):
    return SimpleNamespace(content=b"template-bytes", headers={"Content-Type": "application/octet-stream"})

monkeypatch.setattr(template_candidates_api, "fetch_template_file", fake_fetch_template_file)
```

```python
class _FakeDoc:
    def Range(self, start: int, end: int):
        return _FakeRangeView(self, start, end)
```

**需要 Mock：**
- 模拟 `backend/util/common_util/llm_stream_utils.py`、`backend/agents/generation/*`、`backend/nodes/skills_nodes/rewrite_nodes.py` 中的 LLM provider 调用和流式回调。
- 模拟招标详情和模板候选 HTTP 调用，例如 `requests.get` 和 `fetch_template_file()`。
- 模拟 `SSEManager` 发送、NDJSON stream、task callback 和 agent runner。
- 用 fake document、range、paragraph、font、table、find 覆盖 helper/node 的 Word COM 逻辑。
- 测试日志、审计和 workspace 输出时用 `tmp_path` 隔离文件写入。
- 测试编排逻辑时模拟 DeepAgents/LangChain agent factory。

**不要 Mock：**
- API/model shape 由 Pydantic 真实校验；保护契约的测试应使用真实 `GenerateRequest`、`AgentRunStreamRequest`、`TemplateCandidateSelectRequest`。
- 保护真实路由的测试不 mock graph registry 和 node binding，例如 `backend/tests/graphs/test_gngk_tender_graph.py`。
- 下载/上传安全测试不 mock path containment 逻辑。
- 前端、agent 或 JSON parser 依赖的 prompt 契约文本不 mock。
- 纯 helper 解析和归一化函数直接用确定性输入调用。

## 夹具与工厂

**测试数据：**

```python
payload = {
    "form_type": "xjcg_tender",
    "tender_data": {...},
    "file_paths": {
        "template": "D:/UploadFiles/template.docx",
        "tender_params": ["D:/UploadFiles/params.docx"],
    },
    "generation_mode": "workflow",
}
```

**位置：**
- `backend/tests/conftest.py` 只保留最小共享 setup。
- 大多数 fake Word/agent/test payload builder 都放在需要它们的测试文件内部，例如 `backend/tests/nodes/test_protected_fields_strict_matching.py` 中的 `_FakeDoc` 和 `backend/tests/agents/test_generation_content_agent.py` 中的 `FakeRunner`。
- 重复 payload 使用本地 factory helper，例如 `backend/tests/api/test_template_candidates.py` 中的 `build_select_request()`。

## 覆盖率

**要求：** 未检测到全局 coverage 阈值或 coverage 配置。

**查看覆盖率：**

```bash
cd backend
python -m pytest tests -v
```

后端配置中未检测到 coverage 插件命令。

## 测试类型

**单元测试：**
- 模型： `backend/tests/models/test_generate_request_generation_style.py`、`backend/tests/models/test_sse_agent_step.py`
- 配置： `backend/tests/config/test_settings_langsmith.py`、`backend/tests/config/test_tender_config_protected_fields.py`
- Helper： `backend/tests/helper/test_content_ops.py`、`backend/tests/helper/test_inline_style_ops.py`、`backend/tests/helper/test_paragraph_boundary_ops.py`
- Prompt： `backend/tests/prompts/test_generate_prompt_routing.py`、`backend/tests/prompts/test_comment_prompt_reference_contract.py`、`backend/tests/prompts/test_comment_prompt_bad_case_context.py`

**无 COM 集成风格测试：**
- API： `backend/tests/api/test_generate_api.py`、`backend/tests/api/test_agent_run_api.py`、`backend/tests/api/test_comment_supplement_api.py`、`backend/tests/api/test_template_candidates.py`、`backend/tests/api/test_tender_api.py`
- Service： `backend/tests/services/test_document_service_initial_state.py`、`backend/tests/services/test_document_service_task_result.py`、`backend/tests/services/test_agent_run_service.py`
- Graph： `backend/tests/graphs/test_generation_mode_branching.py`、`backend/tests/graphs/test_gngk_tender_graph.py`、`backend/tests/graphs/test_comment_supplement_graph.py`
- Skill/Node： `backend/tests/skills/test_task_skill_runtime.py`、`backend/tests/nodes/test_rewrite_nodes.py`、`backend/tests/nodes/test_tender_aware_word_dispatch.py`
- 检索：`backend/tests/retrieval/test_comment_bad_case_runtime.py`、`backend/tests/retrieval/test_comment_hybrid_retrieval_script.py`

**E2E 测试：**
- `backend/tests/` 下未检测到浏览器 E2E。
- 完整 Word COM E2E 需要在 Windows 环境中通过 `backend/scripts/diagnose_word.py` 或真实生成任务做人工/诊断验证。

## 常见模式

**异步测试：**

```python
@pytest.mark.asyncio
async def test_service_streams_events(monkeypatch):
    events = []
    async for event in service.stream(request, payload):
        events.append(event)
    assert events
```

**错误测试：**

```python
with pytest.raises(HTTPException) as exc_info:
    await api_function(payload)

assert exc_info.value.status_code == 400
assert exc_info.value.detail["error"]["code"]
```

```python
with pytest.raises(ValueError, match="缺少关键受保护字段"):
    helper_under_test(...)
```

**Graph 绑定测试：**

```python
assert GngkHwCzTenderGraph.NODE_UPDATE_WORD is gngk_hw_cz_update_word
assert document_service.GRAPH_REGISTRY["gngk_hw_cz_tender"] is GngkHwCzTenderGraph
```

**NDJSON 流测试：**

```python
lines = [line async for line in service.stream(request, payload)]
events = [json.loads(line) for line in lines]
assert [item["event"] for item in events] == ["run_started", "thinking_stage", "done"]
```

## COM 安全测试策略

- 能脱离 COM 的段落、范围、样式、字段、表格和字符串逻辑必须拆到 `backend/helper/word_helper/` 并用 fake objects 测试。
- `backend/util/word_util/` 的真实 COM 生命周期通过 Windows 诊断或人工闭环验证。
- WSL/Linux 运行 pytest 只能证明 no-COM 逻辑，不证明 Word/WPS COM 真实可用。
- Direct-replace 相关测试重点覆盖锚点范围、删除边界、显式空行、Markdown 表格、样式回填、批注写回硬失败；参考 `backend/tests/nodes/test_gngk_hw_cz_direct_replace_word.py`、`backend/tests/nodes/test_common_update_word_split.py`、`backend/tests/nodes/test_comment_writeback.py`。

## 按变更类型选择测试

- API/model 变更：运行 `backend/tests/api/`、`backend/tests/models/` 和受影响的 service 测试。
- Graph/type 路由变更：运行 `backend/tests/graphs/` 和 `backend/tests/services/test_document_service_initial_state.py`。
- Word helper 变更：运行相关 `backend/tests/helper/`，再运行受影响的 `backend/tests/nodes/`。
- Word node 变更：先运行聚焦的 `backend/tests/nodes/test_<node>.py`，路由变化时再运行 graph/service 测试。
- Prompt 变更：运行 `backend/tests/prompts/` 和调用方测试。
- Content agent 或 `agent_step`：运行 `backend/tests/agents/test_generation_content_agent.py`、`backend/tests/nodes/test_content_agent_generate.py`、`backend/tests/services/test_sse_manager_agent_step.py`、`backend/tests/services/test_document_service_agent_step.py`。
- 补充批注：运行 `backend/tests/api/test_comment_supplement_api.py`、`backend/tests/graphs/test_comment_supplement_graph.py`、`backend/tests/services/test_document_service_comment_supplement.py`、`backend/tests/nodes/test_comment_agent_writeback_node.py`。
- Agent run / 上传 rewrite：运行 `backend/tests/api/test_agent_run_api.py`、`backend/tests/services/test_agent_run_service.py`、`backend/tests/agents/test_task_context_assistant_tools.py`、`backend/tests/progress/test_uploaded_rewrite_progress_tracking.py`。
- 模板候选：运行 `backend/tests/api/test_template_candidates.py`；如果 `backend/util/common_util/template_candidates.py` 变化，也运行对应 utility 测试。
- LLM stream 工具：运行 `backend/tests/util/test_llm_stream_utils.py`。
- Retrieval / bad case prompt：运行 `backend/tests/retrieval/` 和 `backend/tests/prompts/test_comment_prompt_bad_case_context.py`。

## 测试覆盖缺口

- 真实 `.doc/.docx` + Word COM 端到端覆盖依赖 Windows + Word/WPS COM。
- 未检测到针对 Qdrant/embedding 的持久外部服务集成测试；`backend/scripts/test_comment_hybrid_retrieval.py` 是诊断脚本，不属于主 pytest 套件。
- `backend/tests/` 下未检测到浏览器 E2E。
- Task/SSE/文件下载的完整跨前端流程需要前端验证或真实本地应用验证。

---

*后端测试分析：2026-06-08*
