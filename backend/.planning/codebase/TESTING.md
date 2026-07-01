# 后端测试模式

**分析日期：** 2026-06-29

**范围：** `backend/tests/`、`backend/requirements.txt`、`backend/scripts/diagnose_word.py`、`docs/backend.md`、`docs/interfaces-runtime.md`、`docs/knowledge-validation.md` 和与测试直接相关的后端实现文件。`backend/.env` 文件存在，但不得读取或引用内容。

**关键事实来源：**
- 测试配置与依赖：`backend/requirements.txt`、`backend/tests/conftest.py`
- API 与模型测试：`backend/tests/api/test_generate_api.py`、`backend/tests/api/test_agent_run_api.py`、`backend/tests/api/test_tender_api.py`、`backend/tests/api/test_template_candidates.py`、`backend/tests/models/test_generate_request_generation_style.py`
- Service 与任务测试：`backend/tests/services/test_document_service_initial_state.py`、`backend/tests/services/test_document_service_task_result.py`、`backend/tests/services/test_agent_run_service.py`、`backend/tests/services/test_document_service_llm_snapshot.py`
- Graph、rewrite、进度测试：`backend/tests/graphs/test_generation_mode_branching.py`、`backend/tests/graphs/test_gngk_tender_graph.py`、`backend/tests/nodes/test_rewrite_nodes.py`、`backend/tests/progress/test_uploaded_rewrite_progress_tracking.py`
- Word helper 与隐私审计测试：`backend/tests/helper/test_inline_style_ops.py`、`backend/tests/nodes/test_uploaded_rewrite_inline_style_context.py`、`backend/tests/agents/test_task_context_assistant_logging.py`、`backend/tests/agents/test_content_sanitizer.py`
- Prompt、LLM 与 retrieval 测试：`backend/tests/prompts/test_generate_prompt_routing.py`、`backend/tests/util/test_llm_stream_utils.py`、`backend/tests/agents/test_table_placeholder_utils.py`、`backend/tests/retrieval/test_comment_bad_case_runtime.py`、`backend/tests/retrieval/test_qdrant_store.py`

## 测试框架

**运行器：**
- pytest `>=8.3.0`，声明在 `backend/requirements.txt`。
- pytest-asyncio `>=0.24.0`，声明在 `backend/requirements.txt`；异步测试以 `@pytest.mark.asyncio` 逐个标注（未配置全局 `asyncio_mode`）。
- 配置：未检测到后端专用 `pytest.ini`、`pyproject.toml`、`setup.cfg` 或 `tox.ini`；也未检测到 `pytest-cov`、`coverage` 插件或自定义 marker 声明。全仓只有一个 `backend/tests/conftest.py`。

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
python -m pytest tests/prompts tests/util tests/retrieval -v
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
- `backend/tests/` 下检测到 82 个 `test_*.py` 文件。

**命名：**
- 测试文件使用 `test_*.py`。
- 测试函数使用 `test_<行为>_<期望>()`，例如 `test_stream_agent_run_returns_ndjson_stream()`、`test_uploaded_rewrite_and_rewrite_initial_state_do_not_receive_generation_style()`。
- 目录按后端关注点归档：`api`、`agents`、`config`、`graphs`、`helper`、`logging`、`models`、`nodes`、`progress`、`prompts`、`retrieval`、`services`、`skills`、`util`。

**结构：**

```text
backend/tests/
├── agents/        (7)
├── api/           (5)
├── config/        (2)
├── graphs/        (11)
├── helper/        (6)
├── logging/       (1)
├── models/        (3)
├── nodes/         (25)
├── progress/      (1)
├── prompts/       (3)
├── retrieval/     (5)
├── services/      (8)
├── skills/        (2)
└── util/          (3)
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
    response = await agent_api.stream_agent_run(
        _Request(),
        AgentRunStreamRequest.model_validate({
            "conversation_id": "conv-1",
            "message": "请改写第三包",
            "selected_skills": ["rewrite"],
            "context_snapshot": {"rewrite_available": True, "uploaded_files": []},
        }),
    )
    assert response.media_type == "application/x-ndjson"
```

**Service/model 测试模式：**

```python
service = object.__new__(DocumentService)
state = service._build_initial_state(request, task_id="task-1")

assert state["template_path"] == "D:/UploadFiles/template.docx"
assert "generation_style" not in rewrite_state
```

**LLM 快照契约测试模式（`test_document_service_llm_snapshot.py`）：**

```python
relay = _LLMSnapshotRelay(
    task_id="task-1",
    model_provider="deepseek",
    callback=SSECallback("task-1"),
    sse_manager=_FakeSSEManager(),
    node=TASK_KIND_TO_LLM_NODE["generate"],
    min_interval_seconds=0,
)
relay.on_snapshot("draft snapshot")
relay.flush("final snapshot")
events = callback.get_events()
assert [event.event for event in events] == [SSEEventType.LLM, SSEEventType.LLM]
assert events[0].data["content_mode"] == "snapshot"
assert events[1].data["is_complete"] is True
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

**框架：** pytest `monkeypatch` + 局部 fake class/function + `tmp_path`。异步 endpoint 用 `_Request`/`_FakeService` 直接 await；SSE/NDJSON 用异步生成器 yield 字符串行。

**需要 Mock：**
- LLM provider、流式回调和 agent runner；参考 `backend/tests/nodes/test_rewrite_nodes.py`、`backend/tests/agents/test_generation_content_agent.py`。LLM stream util 测试只 mock provider client / heartbeat / settings 属性，不 mock `MODEL_CONFIGS` 默认值。
- 外部 HTTP 调用：招标数据获取 mock `fetch_tender_data`，模板候选下载 mock `fetch_template_file()` / `requests.get`；参考 `backend/tests/api/test_tender_api.py`、`backend/tests/api/test_template_candidates.py`。
- `SSEManager` 发送（`send_progress_threadsafe` / `send_llm_output_threadsafe`）、NDJSON stream、task callback 和 task service；参考 `backend/tests/services/test_sse_manager_agent_step.py`、`backend/tests/services/test_document_service_llm_snapshot.py`、`backend/tests/agents/test_task_context_assistant_tools.py`。
- Word COM document/range/paragraph/font/table/find 对象；参考 `backend/tests/helper/test_inline_style_ops.py`、`backend/tests/nodes/test_uploaded_rewrite_inline_style_context.py`。
- 文件写入、审计日志和 workspace 输出用 `tmp_path` 隔离；参考 `backend/tests/agents/test_task_context_assistant_logging.py`、`backend/tests/logging/test_task_audit_log_paths.py`、`backend/tests/nodes/test_rewrite_audit_logging.py`。
- 进度追踪测试用 `autouse` fixture 重置 `TaskQueueManager` 状态并 stub `sse_manager.send_progress_threadsafe`；参考 `backend/tests/progress/test_uploaded_rewrite_progress_tracking.py`（fixture 定义在测试文件内，不在 conftest）。

**不要 Mock：**
- API/model shape 保护测试使用真实 Pydantic model，例如 `GenerateRequest`、`AgentRunStreamRequest`、`TemplateCandidateSelectRequest`。
- Graph registry 和节点绑定测试使用真实 class attribute 与 registry；参考 `backend/tests/graphs/test_gngk_tender_graph.py`。
- 下载/上传安全测试不 mock path containment 和文件类型校验本身。
- Prompt 契约文本、rewrite 保护字段 prompt、agent event payload 解析不 mock。
- 纯 helper 解析、归一化、匹配、内容清洗函数直接用确定性输入调用（如 `sanitize_generated_content` / `looks_like_procurement_content`）。
- 结构化表占位符、`generation_style` 路由、LLM provider 配置和超时行为使用真实 helper/model/config 默认值，只 mock 外部 I/O 或 provider client。

## 夹具与工厂

**共享 setup：**
- `backend/tests/conftest.py` 只维护 import path setup；新增共享 fixture 前先确认多个测试文件都需要。
- 多数 fake object、payload builder、`autouse` 清理 fixture 放在测试文件内部，避免隐藏依赖（参考 `isolate_task_queue` / `stub_progress_sse`）。

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

- `GenerateRequest` 字段默认值和枚举接受值由 `backend/tests/models/test_generate_request_generation_style.py` 覆盖；`file_paths.tender_params` 的 string / 对象双形态由 `backend/tests/models/test_generate_request_tender_params.py` 覆盖。
- `GenerateRequest.file_paths` 只接受 `template` 与 `tender_params`，并由 `backend/tests/services/test_document_service_initial_state.py` 断言不产生旧 `source_document_path`。
- `TaskKind`、任务状态、任务结果和 task public summary 由 `backend/tests/services/test_task_service_task_kind.py`、`backend/tests/services/test_document_service_task_result.py`、`backend/tests/agents/test_task_context_assistant_tools.py` 覆盖。
- NDJSON agent run 响应头和事件解析由 `backend/tests/api/test_agent_run_api.py` 覆盖（含 `Cache-Control: no-cache`、`media_type="application/x-ndjson"`、必填 `context_snapshot`）。
- `GET /api/tender/{tender_no}` 的 `ifzgcg` 透传、`investment` 数值强转字符串、不支持的采购方式返回非阻断 `warning`，由 `backend/tests/api/test_tender_api.py` 覆盖。

## Generate 与 Rewrite 边界测试

- generate-only 字段测试集中在 `backend/tests/models/test_generate_request_generation_style.py` 和 `backend/tests/services/test_document_service_initial_state.py`。
- rewrite state 不接收 `generation_style` / `generation_mode` 的约束由 `test_uploaded_rewrite_and_rewrite_initial_state_do_not_receive_generation_style()` 覆盖。
- 上传文件 rewrite 的 `rewrite_source="uploaded_file"`、工作副本、样式和批注抽取由 `backend/tests/nodes/test_uploaded_rewrite_inline_style_context.py` 覆盖。
- rewrite workflow 公开节点名（`REWRITE_NODE_NAMES`）和 tender-aware dispatch 由 `backend/tests/nodes/test_tender_aware_word_dispatch.py` 覆盖。
- 上传 rewrite 进度节点必须加入 `TRACKED_PROGRESS_NODES`，受检集合 `UPLOADED_REWRITE_PROGRESS_NODES`，由 `backend/tests/progress/test_uploaded_rewrite_progress_tracking.py`（含 `autouse` fixture）覆盖。
- Agent run 对上传文件 rewrite 上下文的预检、`needs_input`、`task_accepted` 和错误终态由 `backend/tests/api/test_agent_run_api.py`、`backend/tests/services/test_agent_run_service.py` 覆盖。

## Prompt、LLM 与 Retrieval 测试策略

- Prompt routing 使用真实 `GeneratePromptInput` 和 prompt builder；`backend/tests/prompts/test_generate_prompt_routing.py` 保护 `generation_style="param"` 与模板模式分派。
- 结构化表占位符使用真实 `backend/agents/generation/table_placeholder_utils.py`；`backend/tests/agents/test_table_placeholder_utils.py`、`backend/tests/agents/test_generation_content_agent.py` 和 `backend/tests/helper/test_text_parsing_table_placeholder.py` 覆盖占位符提取、审核不再对缺失占位符报 finding、以及写回层对未命中 sidecar 占位符/投影表的静默丢弃语义。
- LLM 内容清洗契约（剥离 AI 客套语 / Markdown / 填充占位句、保留 `[[TABLE:id]]` / 技术符号 / 重要性标识、空输入与纯噪声返回空）由 `backend/tests/agents/test_content_sanitizer.py` 覆盖。
- LLM stream 测试只 mock provider client、heartbeat 或 settings 属性；`backend/tests/util/test_llm_stream_utils.py` 覆盖 `LLM_STREAM_TIMEOUT_SECONDS`、provider extra body 和 chat stream 终态、`LLMTimeoutError` 与 `ensure_llm_env()` 配置缺失错误（错误信息只含配置键）。
- Retrieval 测试以本地 Markdown bad case、fake embedding/Qdrant client 和 `tmp_path` 为主；`backend/tests/retrieval/test_comment_bad_case_runtime.py` 覆盖 hybrid / BM25 fallback，`backend/tests/retrieval/test_qdrant_store.py` 覆盖 Qdrant client proxy 行为。
- 批注 bad case 检索失败只断言降级、warning 或审计 JSON，不要求外部 Qdrant 服务在线。

## Word Helper 与 COM 测试策略

- 能脱离 COM 的段落、范围、受保护字段、语义归一化、inline style、comment writeback 和 cleanup 逻辑必须拆到 `backend/helper/word_helper/` 并用 fake objects 测试。
- Graph/node 单元测试不启动真实 Word；使用 fake `create_word_application()`、`open_document_with_retry()`、`WordDocumentInspector` 和 `_FakeDoc`。
- `backend/util/word_util/` 的真实 COM 生命周期通过 Windows 诊断脚本或真实生成任务验证。
- WSL/Linux pytest 只能证明 no-COM 逻辑，不证明 Word/WPS COM 可用。
- Direct-replace 和受保护字段边界优先覆盖缺字段、乱序、非法区间、字段值区写入阻断、显式空行和样式回填摘要；参考 `backend/tests/nodes/test_gngk_hw_cz_direct_replace_word.py`、`backend/tests/nodes/test_gngk_fw_zc_update_word.py`、`backend/tests/nodes/test_common_update_word_split.py`。

## Word COM 闭环验证门槛

- 完整 Word 生成 / rewrite 写回验收**必须在 Windows + 本机 Word 或 WPS COM 环境**：`pywin32`（`backend/requirements.txt` 中 `platform_system == "Windows"` 才安装）+ 真实 Office/WPS 安装。
- `backend/tests/` 全套 pytest（含 WSL/Linux）**只能证明 no-COM 的业务逻辑**（model、prompt、helper fake、graph 编译、进度/审计 JSON、SSE/NDJSON shape），**不能证明** Word/WPS COM 可用或真实 `.doc/.docx` 写回正确。
- Windows 侧 COM 可用性诊断入口：`backend/scripts/diagnose_word.py`（`.\.venv\Scripts\python.exe scripts\diagnose_word.py`）。真实生成任务也作为闭环验证手段。
- 环境隔离说明：WSL/Linux 跑 pytest 前需 `TMPDIR=/tmp TMP=/tmp TEMP=/tmp` 规避 Windows 临时目录；非 Windows 不安装 `pywin32`，任何 `import win32com` 的路径都走不到。

## 覆盖率

**要求：** 未检测到 coverage 阈值或 coverage 配置；`backend/requirements.txt` 未声明 `coverage` / `pytest-cov`。

**查看覆盖率：** 当前没有内置覆盖率命令；如需覆盖率，先补充项目约定、依赖和阈值，再运行带 `--cov` 的 pytest。

## 测试类型

**单元测试：**
- 模型：`backend/tests/models/test_generate_request_generation_style.py`、`backend/tests/models/test_generate_request_tender_params.py`、`backend/tests/models/test_sse_agent_step.py`
- 配置：`backend/tests/config/test_settings_langsmith.py`、`backend/tests/config/test_tender_config_protected_fields.py`
- Helper：`backend/tests/helper/test_content_ops.py`、`backend/tests/helper/test_inline_style_ops.py`、`backend/tests/helper/test_paragraph_boundary_ops.py`
- Prompt：`backend/tests/prompts/test_generate_prompt_routing.py`、`backend/tests/prompts/test_comment_prompt_reference_contract.py`
- 清洗/占位符：`backend/tests/agents/test_content_sanitizer.py`、`backend/tests/agents/test_table_placeholder_utils.py`

**无 COM 集成风格测试：**
- API：`backend/tests/api/test_generate_api.py`、`backend/tests/api/test_agent_run_api.py`、`backend/tests/api/test_tender_api.py`、`backend/tests/api/test_comment_supplement_api.py`、`backend/tests/api/test_template_candidates.py`
- Service：`backend/tests/services/test_document_service_initial_state.py`、`backend/tests/services/test_document_service_task_result.py`、`backend/tests/services/test_agent_run_service.py`、`backend/tests/services/test_document_service_llm_snapshot.py`
- Graph：`backend/tests/graphs/test_generation_mode_branching.py`、`backend/tests/graphs/test_gngk_tender_graph.py`、`backend/tests/graphs/test_comment_supplement_graph.py`
- Skill/Node：`backend/tests/skills/test_task_skill_runtime.py`、`backend/tests/nodes/test_rewrite_nodes.py`、`backend/tests/nodes/test_tender_aware_word_dispatch.py`
- Retrieval：`backend/tests/retrieval/test_comment_bad_case_runtime.py`、`backend/tests/retrieval/test_comment_hybrid_retrieval_script.py`
- LLM/stream util：`backend/tests/util/test_llm_stream_utils.py`

**E2E 测试：**
- `backend/tests/` 下未检测到浏览器 E2E。
- 完整 Word COM E2E 需要 Windows + Word/WPS COM，通过 `backend/scripts/diagnose_word.py` 或真实生成任务验证（见上文「Word COM 闭环验证门槛」）。

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

@pytest.mark.parametrize("node_name", UPLOADED_REWRITE_PROGRESS_NODES)
def test_wrap_node_with_progress_updates_uploaded_rewrite_nodes(monkeypatch, node_name: str):
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
- 任务状态、SSE、`TaskKind`、LLM 快照变更：运行 `backend/tests/api/test_agent_run_api.py`、`backend/tests/services/test_task_service_task_kind.py`、`backend/tests/services/test_sse_manager_agent_step.py`、`backend/tests/services/test_document_service_llm_snapshot.py`、`backend/tests/services/test_document_service_task_result.py`。
- Graph/type 路由变更：运行 `python -m pytest tests/graphs -v` 和 `backend/tests/services/test_document_service_initial_state.py`。
- Generate-only 字段、生成模式、批注开关、样式回填变更：运行 `backend/tests/models/test_generate_request_generation_style.py`、`backend/tests/services/test_document_service_initial_state.py`、`backend/tests/graphs/test_generation_mode_branching.py`。
- Rewrite / uploaded file rewrite 变更：运行 `backend/tests/api/test_agent_run_api.py`、`backend/tests/services/test_agent_run_service.py`、`backend/tests/agents/test_task_context_assistant_tools.py`、`backend/tests/nodes/test_rewrite_nodes.py`、`backend/tests/nodes/test_uploaded_rewrite_inline_style_context.py`、`backend/tests/progress/test_uploaded_rewrite_progress_tracking.py`。
- Content agent / 内容清洗 / 结构化表占位符入口契约变更：运行 `backend/tests/agents/test_content_sanitizer.py`、`backend/tests/agents/test_generation_content_agent.py`、`backend/tests/agents/test_table_placeholder_utils.py` 和 `backend/tests/helper/test_text_parsing_table_placeholder.py`，再运行 `backend/tests/nodes/test_tender_aware_word_dispatch.py` 覆盖 rewrite 写回分支。
- Word helper 变更：运行相关 `backend/tests/helper/`，再运行受影响的 `backend/tests/nodes/`。
- Word node/direct-replace 变更：运行聚焦的 `backend/tests/nodes/test_<node>.py`，路由变化时再运行 `backend/tests/graphs/`。
- Prompt 或 LLM stream 变更：运行 `backend/tests/prompts/`、`backend/tests/util/test_llm_stream_utils.py` 和调用方测试。
- 补充批注变更：运行 `backend/tests/api/test_comment_supplement_api.py`、`backend/tests/graphs/test_comment_supplement_graph.py`、`backend/tests/services/test_document_service_comment_supplement.py`、`backend/tests/nodes/test_comment_agent_writeback_node.py`。
- 招标数据 / `GET /api/tender` 变更：运行 `backend/tests/api/test_tender_api.py`；如改 `backend/util/common_util/fetch_tender_data.py` 或 `tender_number.py`，加跑对应 util 测试。
- 模板候选变更：运行 `backend/tests/api/test_template_candidates.py`；如改 `backend/util/common_util/template_candidates.py`，加跑对应 util 测试。
- Retrieval / bad case prompt 变更：运行 `backend/tests/retrieval/` 和 `backend/tests/prompts/test_comment_prompt_bad_case_context.py`。

## 跨层同步检查

以下变更属于跨层契约，必须**同步前后端模型 / 类型 / 客户端 / 测试**，不能只改后端：
- **API shape 变更**：`GenerateRequest` / `GenerateResponse` / `AgentRunStreamRequest`（含必填 `context_snapshot`）/ `TaskResponse` / `TenderResponse` 字段增删改、`extra="forbid"` 边界调整。
- **SSE / NDJSON 事件**：新增 `SSEEventType`、agent run 事件名、`AgentStepEventData` 阶段或字段、LLM 快照 `content_mode`/`is_complete` 语义。
- **task type / tender type**：`TaskKind`、`TaskStatus` 协议值，`FormType` 枚举值，`TenderData`/`TenderType` 字段（`ifzgcg`/`ifdzpt2`/`tender_lx`/`fund_lx`/`purchase_method`）。
- **Prompt / LLM provider**：`LLMModel` provider 新增、`generation_style` 路由值、`MODEL_CONFIGS` provider key。
- **word helper 跨层**：受保护字段契约、rewrite 默认锚点表（`REWRITE_DEFAULT_ANCHORS`）、结构化表占位符 `table_id` 字符集。

## 测试覆盖缺口

- 真实 `.doc/.docx` + Word COM 端到端覆盖依赖 Windows + Word/WPS COM（见「Word COM 闭环验证门槛」）。
- 未检测到针对 Qdrant/embedding 的持久外部服务集成测试；`backend/scripts/test_comment_hybrid_retrieval.py` 是诊断脚本，不属于主 pytest 套件。
- `backend/tests/` 下未检测到浏览器 E2E。
- Task/SSE/文件下载的完整跨前端流程需要前端或真实本地应用验证。

---

*后端测试分析：2026-06-29*
