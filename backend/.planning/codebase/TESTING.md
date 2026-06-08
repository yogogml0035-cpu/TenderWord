# 后端测试事实地图

**分析日期：** 2026-06-08

**范围：** `backend/tests/`、`backend/requirements.txt` 和后端验证命令。

## Test Framework

**Runner:**
- pytest `>=8.3.0`
- Config: 未检测到后端专用 `pytest.ini`、`pyproject.toml` 或 `setup.cfg`。

**Assertion Library:**
- pytest 原生 `assert`。
- Pydantic model validation、FastAPI `TestClient`、monkeypatch/fake objects 按测试文件局部使用。

**Run Commands:**

```bash
cd backend
python -m pytest tests -v              # Run all tests with the active Python
python -m pytest tests/api -v          # Run API tests
python -m pytest tests/graphs -v       # Run graph tests
python -m pytest tests/nodes -v        # Run node tests
```

Windows venv:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -v
```

WSL/Linux no-COM venv:

```bash
cd backend
TMPDIR=/tmp TMP=/tmp TEMP=/tmp .venv-linux/bin/python -m pytest tests -v
```

Word COM diagnostic:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\diagnose_word.py
```

## Test File Organization

**Location:**
- Tests live under `backend/tests/<module_scope>/`.
- Test files are not co-located with source files.

**Naming:**
- `test_*.py` for all committed tests.
- Scope directory names mirror source concerns: `api`、`agents`、`config`、`graphs`、`helper`、`logging`、`models`、`nodes`、`progress`、`prompts`、`services`、`skills`、`util`。

**Structure:**

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
├── services/
├── skills/
└── util/
```

## Test Structure

**Suite Organization:**

```python
def test_generation_mode_agent_uses_content_agent(monkeypatch):
    # arrange: patch expensive dependencies / fake graph node
    # act: invoke service or graph branch
    # assert: state, node binding, event, or response contract
    assert ...
```

**Patterns:**
- Use focused unit tests for model validators, prompt strings, helper pure logic and graph routing.
- Use monkeypatch for LLM, HTTP, SSE and filesystem side effects.
- Use fake Word document/range/paragraph objects for no-COM helper and node tests.
- Use service-level tests for task creation state, task result shape, comment supplement and `agent_step` forwarding.
- Use graph-level tests to lock class attribute node binding and branch selection.

## Mocking

**Framework:** pytest monkeypatch + local fake classes/functions.

**Patterns:**

```python
def fake_create_deep_agent(*args, **kwargs):
    return FakeAgent()

monkeypatch.setattr(
    "backend.agents.task_context_assistant.factory.create_deep_agent",
    fake_create_deep_agent,
)
```

```python
class FakeRange:
    Text = "..."

result = helper_under_test(FakeRange())
assert result is not None
```

**What to Mock:**
- LLM provider calls in `backend/util/common_util/llm_stream_utils.py` and agent model factory.
- `requests.get` for tender data and template candidates.
- `SSEManager` sends and callbacks.
- Word COM objects for helper/node logic.
- Filesystem writes via tmp path where practical.
- DeepAgents/LangChain agent factories.

**What NOT to Mock:**
- Pydantic validation for API shape.
- Graph registry and node binding where the test protects real routing.
- Path containment logic in downloads/uploads.
- Prompt contract literals when frontend/agent parsing relies on them.

## Fixtures and Factories

**Test Data:**

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

**Location:**
- Shared fixtures live in `backend/tests/conftest.py`.
- Most fake Word/agent/test payload factories are local to the test file that needs them.

## Coverage

**Requirements:** No global coverage threshold detected.

**View Coverage:**

```bash
cd backend
python -m pytest tests -v
```

Coverage plugin command not detected in backend config.

## Test Types

**Unit Tests:**
- Models: `backend/tests/models/test_generate_request_generation_style.py`, `backend/tests/models/test_sse_agent_step.py`
- Config: `backend/tests/config/test_settings_langsmith.py`, `backend/tests/config/test_tender_config_protected_fields.py`
- Helpers: `backend/tests/helper/test_content_ops.py`, `backend/tests/helper/test_inline_style_ops.py`, `backend/tests/helper/test_paragraph_boundary_ops.py`
- Prompts: `backend/tests/prompts/test_generate_prompt_routing.py`, `backend/tests/prompts/test_comment_prompt_reference_contract.py`

**Integration-Style Tests Without COM:**
- API: `backend/tests/api/test_generate_api.py`, `backend/tests/api/test_agent_run_api.py`, `backend/tests/api/test_comment_supplement_api.py`, `backend/tests/api/test_template_candidates.py`
- Services: `backend/tests/services/test_document_service_initial_state.py`, `backend/tests/services/test_document_service_task_result.py`, `backend/tests/services/test_agent_run_service.py`
- Graphs: `backend/tests/graphs/test_generation_mode_branching.py`, `backend/tests/graphs/test_gngk_tender_graph.py`, `backend/tests/graphs/test_comment_supplement_graph.py`
- Nodes: `backend/tests/nodes/test_rewrite_nodes.py`, `backend/tests/nodes/test_gngk_hw_cz_direct_replace_word.py`, `backend/tests/nodes/test_update_word_inline_style_writeback.py`

**E2E Tests:**
- Browser E2E not detected under `backend/tests/`.
- Full Word COM E2E is manual/diagnostic via Windows environment and `backend/scripts/diagnose_word.py` or real generation task.

## Key Test Coverage by Area

**API:**
- `backend/tests/api/test_generate_api.py`
- `backend/tests/api/test_agent_run_api.py`
- `backend/tests/api/test_comment_supplement_api.py`
- `backend/tests/api/test_template_candidates.py`
- `backend/tests/api/test_tender_api.py`

**Agents:**
- `backend/tests/agents/test_generation_content_agent.py`
- `backend/tests/agents/test_comment_agent.py`
- `backend/tests/agents/test_task_context_assistant_factory.py`
- `backend/tests/agents/test_task_context_assistant_tools.py`
- `backend/tests/agents/test_task_context_assistant_logging.py`

**Graphs:**
- `backend/tests/graphs/test_generation_mode_branching.py`
- `backend/tests/graphs/test_generation_mode_workflow.py`
- `backend/tests/graphs/test_xjcg_generation_mode_agent.py`
- `backend/tests/graphs/test_gngk_hw_zc_generation_mode_agent.py`
- `backend/tests/graphs/test_gngk_hw_cz_generation_mode_agent.py`
- `backend/tests/graphs/test_gngk_fw_zc_generation_mode_agent.py`
- `backend/tests/graphs/test_gngk_fw_cz_generation_mode_agent.py`
- `backend/tests/graphs/test_gjgk_generation_mode_agent.py`
- `backend/tests/graphs/test_gngk_tender_graph.py`
- `backend/tests/graphs/test_gjgk_tender_graph.py`
- `backend/tests/graphs/test_comment_supplement_graph.py`

**Word Helpers and Nodes:**
- `backend/tests/helper/test_inline_style_ops.py`
- `backend/tests/helper/test_protected_fields_strict_matching.py` is not in helper directory; strict matching test is `backend/tests/nodes/test_protected_fields_strict_matching.py`
- `backend/tests/nodes/test_gngk_hw_cz_direct_replace_word.py`
- `backend/tests/nodes/test_common_update_word_split.py`
- `backend/tests/nodes/test_comment_writeback.py`
- `backend/tests/nodes/test_word_insert_html_breaks.py`
- `backend/tests/nodes/test_tender_aware_word_dispatch.py`

**Progress/SSE/Task:**
- `backend/tests/services/test_sse_manager_agent_step.py`
- `backend/tests/services/test_document_service_agent_step.py`
- `backend/tests/services/test_task_service_task_kind.py`
- `backend/tests/progress/test_uploaded_rewrite_progress_tracking.py`

**Skills:**
- `backend/tests/skills/test_task_skill_runtime.py`
- `backend/tests/skills/test_task_skill_instructions.py`

**Utilities:**
- `backend/tests/util/test_fetch_tender_data.py`
- `backend/tests/util/test_llm_stream_utils.py`

## Common Patterns

**Async Testing:**

```python
@pytest.mark.asyncio
async def test_service_streams_event(monkeypatch):
    events = []
    async for event in service.stream(request, payload):
        events.append(event)
    assert events
```

**Error Testing:**

```python
with pytest.raises(ValueError):
    ModelOrHelper(...)
```

```python
response = client.post("/api/comment-supplement", json=payload)
assert response.status_code == 400
assert response.json()["detail"]["error"]["code"]
```

**Graph Binding Testing:**

```python
assert GngkHwCzTenderGraph.NODE_UPDATE_WORD is gngk_hw_cz_update_word
assert GRAPH_REGISTRY["gngk_hw_cz_tender"] is GngkHwCzTenderGraph
```

## COM Safety Testing Strategy

- 能脱离 COM 的段落、范围、样式、字段、表格和字符串逻辑必须拆到 `backend/helper/word_helper/` 并用 fake objects 测试。
- `backend/util/word_util/` 的真实 COM 生命周期通过 Windows 诊断或人工闭环验证。
- WSL/Linux 运行 pytest 只能证明 no-COM 逻辑，不证明 Word/WPS COM 真实可用。
- Direct-replace 相关测试重点覆盖锚点范围、删除边界、显式空行、Markdown 表格、样式回填、批注写回硬失败。

## Test Selection by Change Type

- API/model change: run `backend/tests/api/`、`backend/tests/models/` and affected service tests.
- Graph/type routing change: run `backend/tests/graphs/` and `backend/tests/services/test_document_service_initial_state.py`.
- Word helper change: run relevant `backend/tests/helper/` plus affected `backend/tests/nodes/`.
- Word node change: run focused `backend/tests/nodes/test_<node>.py`, then graph/service tests when routing changes.
- Prompt change: run `backend/tests/prompts/` and caller tests.
- Content agent or `agent_step`: run `backend/tests/agents/test_generation_content_agent.py`, `backend/tests/nodes/test_content_agent_generate.py`, `backend/tests/services/test_sse_manager_agent_step.py`, `backend/tests/services/test_document_service_agent_step.py`.
- Comment supplement: run `backend/tests/api/test_comment_supplement_api.py`, `backend/tests/graphs/test_comment_supplement_graph.py`, `backend/tests/services/test_document_service_comment_supplement.py`, `backend/tests/nodes/test_comment_agent_writeback_node.py`.
- Agent run / uploaded rewrite: run `backend/tests/api/test_agent_run_api.py`, `backend/tests/services/test_agent_run_service.py`, `backend/tests/agents/test_task_context_assistant_tools.py`, `backend/tests/progress/test_uploaded_rewrite_progress_tracking.py`.
- Template candidates: run `backend/tests/api/test_template_candidates.py`.
- LLM stream utility: run `backend/tests/util/test_llm_stream_utils.py`.

## Test Coverage Gaps

- Real `.doc/.docx` + Word COM end-to-end coverage depends on Windows + Word/WPS COM.
- No detected persistent external service integration tests for Qdrant/embedding; `backend/scripts/test_comment_hybrid_retrieval.py` is a diagnostic/experimental script, not a pytest suite or production-path test.
- No detected browser E2E under backend tests.
- Task/SSE/file download full cross-frontend flow requires frontend validation or real local app.

---

*后端测试分析：2026-06-08*
