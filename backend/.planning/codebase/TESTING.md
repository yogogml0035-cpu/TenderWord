# 后端测试模式

**分析日期：** 2026-06-09

**范围：** `backend/tests/`、`backend/requirements.txt`、`backend/scripts/diagnose_word.py`、`docs/backend.md`、`docs/interfaces-runtime.md`、`docs/knowledge-validation.md` 和与测试直接相关的后端实现文件。`backend/.env` 文件存在，但不得读取或引用内容。

**关键事实来源：**
- 测试配置与依赖：`backend/requirements.txt`、`backend/tests/conftest.py`
- API 与模型测试：`backend/tests/api/test_generate_api.py`、`backend/tests/api/test_agent_run_api.py`、`backend/tests/api/test_template_candidates.py`、`backend/tests/models/test_generate_request_generation_style.py`
- Service 与任务测试：`backend/tests/services/test_document_service_initial_state.py`、`backend/tests/services/test_document_service_task_result.py`、`backend/tests/services/test_agent_run_service.py`
- Graph、rewrite、进度测试：`backend/tests/graphs/test_generation_mode_branching.py`、`backend/tests/graphs/test_gngk_tender_graph.py`、`backend/tests/nodes/test_rewrite_nodes.py`、`backend/tests/progress/test_uploaded_rewrite_progress_tracking.py`
- Word helper 与隐私审计测试：`backend/tests/helper/test_inline_style_ops.py`、`backend/tests/nodes/test_uploaded_rewrite_inline_style_context.py`、`backend/tests/agents/test_task_context_assistant_logging.py`

## 测试框架

**运行器：**
- pytest `>=8.3.0`，声明在 `backend/requirements.txt`。
- pytest-asyncio `>=0.24.0`，声明在 `backend/requirements.txt`。
- 配置：未检测到后端专用 `pytest.ini`、`pyproject.toml`、`setup.cfg` 或 `tox.ini`。

**断言库：**
- pytest 原生 `assert`。
- FastAPI `HTTPException`、Pydantic `model_validate()` / `ValidationError`、LangGraph 编译图和局部 fake object 按测试文件局部使用。

**运行命令：**

```bash
cd backend
python -m pytest tests -v
python -m pytest tests/api -v
python -m pytest tests/models tests/services -v
python -m pytest tests/graphs tests/nodes -v
```

Windows 虚拟环境：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -v
.\.venv\Scripts\python.exe scripts\diagnose_word.py
```

WSL/Linux 无 COM 验证：

```bash
cd backend
TMPDIR=/tmp TMP=/tmp TEMP=/tmp .venv-linux/bin/python -m pytest tests -v
```

## 测试文件组织

**位置：**
- 测试集中在 `backend/tests/<scope>/`，不与源码 co-locate。
- `backend/tests/conftest.py` 只把项目根和 `backend/` 加入 `sys.path`，没有全局业务 fixture。
- `backend/tests/` 下检测到 72 个 `test_*.py` 文件。

**命名：**
- 测试文件使用 `test_*.py`。
- 测试函数使用 `test_<行为>_<期望>()`，例如 `test_stream_agent_run_returns_ndjson_stream()`、`test_uploaded_rewrite_and_rewrite_initial_state_do_not_receive_generation_style()`。
- 目录按后端关注点归档：`api`、`agents`、`config`、`graphs`、`helper`、`logging`、`models`、`nodes`、`progress`、`prompts`、`retrieval`、`services`、`skills`、`util`。

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

**API 测试模式：**

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

**Service/model 测试模式：**

```python
service = object.__new__(DocumentService)
state = service._build_initial_state(request, task_id="task-1")

assert state["template_path"] == "D:/UploadFiles/template.docx"
assert "generation_style" not in rewrite_state
```

**Graph 测试模式：**

```python
class _GenerationModeGraph(StandardTenderWorkflowGraph):
    STATE_CLS = TenderGraphStateBase
    NODE_GENERATE_POLISHED_TEXT = _generate_node
    NODE_CONTENT_AGENT_GENERATE = _content_node
    NODE_UPDATE_WORD = _update_node

result = _GenerationModeGraph().compile().invoke({"generation_mode": "workflow"})
assert "content_agent" not in calls
```

**Word helper 测试模式：**

```python
class _FakeDoc:
    def Range(self, start: int, end: int):
        return _FakeRange(start, end)

result = style_ops.apply_inline_style_fragments(
    doc=_FakeDoc(),
    inline_style_fragments=[fragment],
    bound_start=0,
    bound_end=120,
    log_parts=[],
)
```

## Mock 方式

**框架：** pytest `monkeypatch` + 局部 fake class/function + `tmp_path`。

**需要 Mock：**
- LLM provider、流式回调和 agent runner；参考 `backend/tests/nodes/test_rewrite_nodes.py`、`backend/tests/agents/test_generation_content_agent.py`。
- 外部 HTTP 调用和模板候选下载，例如 `fetch_template_file()`、`requests.get`；参考 `backend/tests/api/test_template_candidates.py`。
- `SSEManager` 发送、NDJSON stream、task callback 和 task service；参考 `backend/tests/services/test_sse_manager_agent_step.py`、`backend/tests/agents/test_task_context_assistant_tools.py`。
- Word COM document/range/paragraph/font/table/find 对象；参考 `backend/tests/helper/test_inline_style_ops.py`、`backend/tests/nodes/test_uploaded_rewrite_inline_style_context.py`。
- 文件写入、审计日志和 workspace 输出用 `tmp_path` 隔离；参考 `backend/tests/agents/test_task_context_assistant_logging.py`。

**不要 Mock：**
- API/model shape 保护测试使用真实 Pydantic model，例如 `GenerateRequest`、`AgentRunStreamRequest`、`TemplateCandidateSelectRequest`。
- Graph registry 和节点绑定测试使用真实 class attribute 与 registry；参考 `backend/tests/graphs/test_gngk_tender_graph.py`。
- 下载/上传安全测试不 mock path containment 和文件类型校验本身。
- Prompt 契约文本、rewrite 保护字段 prompt、agent event payload 解析不 mock。
- 纯 helper 解析、归一化、匹配函数直接用确定性输入调用。

## 夹具与工厂

**共享 setup：**
- `backend/tests/conftest.py` 只维护 import path setup；新增共享 fixture 前先确认多个测试文件都需要。
- 多数 fake object 和 payload builder 放在测试文件内部，避免隐藏依赖。

**本地 factory：**

```python
def build_select_request(shener: str | None = "http://10.11.1.224/template.docx"):
    return TemplateCandidateSelectRequest(candidate=TemplateCandidateSelectPayload(...))
```

```python
def build_request(*, template: str | None, generation_mode=GenerationMode.WORKFLOW):
    return GenerateRequest(
        form_type=FormType.GJGK_TENDER,
        tender_data=TenderData(...),
        file_paths={"template": template, "tender_params": ["D:/UploadFiles/params.docx"]},
        generation_mode=generation_mode,
    )
```

**临时文件：**
- 使用 `tmp_path` 创建测试 docx 占位、审计日志和输出文件；不要写入真实 `settings.UPLOAD_DIR`。
- 测试路径可使用 `D:/UploadFiles/...` 作为字符串契约，但不要求真实文件存在，除非测试目标是文件存在性。

## 请求/任务模型测试

- `GenerateRequest` 字段默认值和枚举接受值由 `backend/tests/models/test_generate_request_generation_style.py` 覆盖。
- `GenerateRequest.file_paths` 只接受 `template` 与 `tender_params`，并由 `backend/tests/services/test_document_service_initial_state.py` 断言不产生旧 `source_document_path`。
- `TaskKind`、任务状态、任务结果和 task public summary 由 `backend/tests/services/test_task_service_task_kind.py`、`backend/tests/services/test_document_service_task_result.py`、`backend/tests/agents/test_task_context_assistant_tools.py` 覆盖。
- NDJSON agent run 响应头和事件解析由 `backend/tests/api/test_agent_run_api.py` 覆盖。

## Generate 与 Rewrite 边界测试

- generate-only 字段测试集中在 `backend/tests/models/test_generate_request_generation_style.py` 和 `backend/tests/services/test_document_service_initial_state.py`。
- rewrite state 不接收 `generation_style` / `generation_mode` 的约束由 `test_uploaded_rewrite_and_rewrite_initial_state_do_not_receive_generation_style()` 覆盖。
- 上传文件 rewrite 的 `rewrite_source="uploaded_file"`、工作副本、样式和批注抽取由 `backend/tests/nodes/test_uploaded_rewrite_inline_style_context.py` 覆盖。
- rewrite workflow 公开节点名和 tender-aware dispatch 由 `backend/tests/nodes/test_tender_aware_word_dispatch.py` 覆盖。
- 上传 rewrite 进度节点必须加入 `TRACKED_PROGRESS_NODES`，由 `backend/tests/progress/test_uploaded_rewrite_progress_tracking.py` 覆盖。

## Word Helper 与 COM 测试策略

- 能脱离 COM 的段落、范围、受保护字段、语义归一化、inline style、comment writeback 和 cleanup 逻辑必须拆到 `backend/helper/word_helper/` 并用 fake objects 测试。
- Graph/node 单元测试不启动真实 Word；使用 fake `create_word_application()`、`open_document_with_retry()`、`WordDocumentInspector` 和 `_FakeDoc`。
- `backend/util/word_util/` 的真实 COM 生命周期通过 Windows 诊断脚本或真实生成任务验证。
- WSL/Linux pytest 只能证明 no-COM 逻辑，不证明 Word/WPS COM 可用。
- Direct-replace 和受保护字段边界优先覆盖缺字段、乱序、非法区间、字段值区写入阻断、显式空行和样式回填摘要；参考 `backend/tests/nodes/test_gngk_hw_cz_direct_replace_word.py`、`backend/tests/nodes/test_gngk_fw_zc_update_word.py`、`backend/tests/nodes/test_common_update_word_split.py`。

## 覆盖率

**要求：** 未检测到 coverage 阈值或 coverage 配置。

**查看覆盖率：**

```bash
cd backend
python -m pytest tests -v
```

`backend/requirements.txt` 未声明 coverage 插件；如需覆盖率，先补充项目约定和依赖。

## 测试类型

**单元测试：**
- 模型：`backend/tests/models/test_generate_request_generation_style.py`、`backend/tests/models/test_sse_agent_step.py`
- 配置：`backend/tests/config/test_settings_langsmith.py`、`backend/tests/config/test_tender_config_protected_fields.py`
- Helper：`backend/tests/helper/test_content_ops.py`、`backend/tests/helper/test_inline_style_ops.py`、`backend/tests/helper/test_paragraph_boundary_ops.py`
- Prompt：`backend/tests/prompts/test_generate_prompt_routing.py`、`backend/tests/prompts/test_comment_prompt_reference_contract.py`

**无 COM 集成风格测试：**
- API：`backend/tests/api/test_generate_api.py`、`backend/tests/api/test_agent_run_api.py`、`backend/tests/api/test_comment_supplement_api.py`、`backend/tests/api/test_template_candidates.py`
- Service：`backend/tests/services/test_document_service_initial_state.py`、`backend/tests/services/test_document_service_task_result.py`、`backend/tests/services/test_agent_run_service.py`
- Graph：`backend/tests/graphs/test_generation_mode_branching.py`、`backend/tests/graphs/test_gngk_tender_graph.py`、`backend/tests/graphs/test_comment_supplement_graph.py`
- Skill/Node：`backend/tests/skills/test_task_skill_runtime.py`、`backend/tests/nodes/test_rewrite_nodes.py`、`backend/tests/nodes/test_tender_aware_word_dispatch.py`
- Retrieval：`backend/tests/retrieval/test_comment_bad_case_runtime.py`、`backend/tests/retrieval/test_comment_hybrid_retrieval_script.py`

**E2E 测试：**
- `backend/tests/` 下未检测到浏览器 E2E。
- 完整 Word COM E2E 需要 Windows + Word/WPS COM，通过 `backend/scripts/diagnose_word.py` 或真实生成任务验证。

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

**参数化测试：**

```python
@pytest.mark.parametrize(("form_type", "expected_before", "expected_after"), [...])
def test_default_anchors(form_type, expected_before, expected_after):
    ...
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
assert events[0]["event"] == "run_started"
```

## 按变更类型选择测试

- API/model 变更：运行 `python -m pytest tests/api tests/models -v`，并加上受影响的 service 测试。
- 任务状态、SSE、`TaskKind` 变更：运行 `backend/tests/api/test_agent_run_api.py`、`backend/tests/services/test_task_service_task_kind.py`、`backend/tests/services/test_sse_manager_agent_step.py`、`backend/tests/services/test_document_service_task_result.py`。
- Graph/type 路由变更：运行 `python -m pytest tests/graphs -v` 和 `backend/tests/services/test_document_service_initial_state.py`。
- Generate-only 字段、生成模式、批注开关、样式回填变更：运行 `backend/tests/models/test_generate_request_generation_style.py`、`backend/tests/services/test_document_service_initial_state.py`、`backend/tests/graphs/test_generation_mode_branching.py`。
- Rewrite / uploaded file rewrite 变更：运行 `backend/tests/api/test_agent_run_api.py`、`backend/tests/services/test_agent_run_service.py`、`backend/tests/agents/test_task_context_assistant_tools.py`、`backend/tests/nodes/test_rewrite_nodes.py`、`backend/tests/nodes/test_uploaded_rewrite_inline_style_context.py`、`backend/tests/progress/test_uploaded_rewrite_progress_tracking.py`。
- Word helper 变更：运行相关 `backend/tests/helper/`，再运行受影响的 `backend/tests/nodes/`。
- Word node/direct-replace 变更：运行聚焦的 `backend/tests/nodes/test_<node>.py`，路由变化时再运行 `backend/tests/graphs/`。
- Prompt 或 LLM stream 变更：运行 `backend/tests/prompts/`、`backend/tests/util/test_llm_stream_utils.py` 和调用方测试。
- 补充批注变更：运行 `backend/tests/api/test_comment_supplement_api.py`、`backend/tests/graphs/test_comment_supplement_graph.py`、`backend/tests/services/test_document_service_comment_supplement.py`、`backend/tests/nodes/test_comment_agent_writeback_node.py`。
- 模板候选变更：运行 `backend/tests/api/test_template_candidates.py`；如改 `backend/util/common_util/template_candidates.py`，加跑对应 util 测试。
- Retrieval / bad case prompt 变更：运行 `backend/tests/retrieval/` 和 `backend/tests/prompts/test_comment_prompt_bad_case_context.py`。

## 测试覆盖缺口

- 真实 `.doc/.docx` + Word COM 端到端覆盖依赖 Windows + Word/WPS COM。
- 未检测到针对 Qdrant/embedding 的持久外部服务集成测试；`backend/scripts/test_comment_hybrid_retrieval.py` 是诊断脚本，不属于主 pytest 套件。
- `backend/tests/` 下未检测到浏览器 E2E。
- Task/SSE/文件下载的完整跨前端流程需要前端或真实本地应用验证。

---

*后端测试分析：2026-06-09*
