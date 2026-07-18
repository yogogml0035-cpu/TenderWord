# 后端测试模式

**分析日期：** 2026-07-18

**范围：** `backend/tests/`、`backend/requirements.txt`、`backend/scripts/diagnose_word.py` 及与测试直接相关的实现。未读取 `backend/.env`。

**关键事实来源：**
- 配置与依赖：`backend/requirements.txt`、`backend/tests/conftest.py`
- 近期批注链路：`tests/agents/test_comment_agent.py`、`tests/nodes/test_annotate_corrections.py`、`tests/nodes/test_comment_writeback.py`、`tests/nodes/test_comment_agent_writeback_node.py`、`tests/graphs/test_comment_supplement_graph.py`、`tests/api/test_comment_supplement_api.py`
- API / model / service / graph / helper / retrieval / logging 全套 `tests/` 镜像目录

## 测试框架

**运行器：**
- `pytest>=8.3.0`、`pytest-asyncio>=0.24.0`（`backend/requirements.txt`）。
- **无** 后端 `pytest.ini` / `pyproject.toml` / `setup.cfg` / `tox.ini`；**无** 全局 `asyncio_mode`。
- 异步测试必须逐用例标注 `@pytest.mark.asyncio`（strict 显式标记，不自动发现 async）。
- **无** `pytest-cov` / `coverage` 依赖或阈值。
- 全仓唯一共享 conftest：`backend/tests/conftest.py`（仅 `sys.path`：项目根 + `backend/`）。

**断言：**
- pytest 原生 `assert`。
- 局部使用 `HTTPException`、`ValidationError` / `model_validate()`、`pytest.raises`、`pytest.mark.parametrize`、fake class。

## 如何运行

```bash
cd backend
python -m pytest tests -v
python -m pytest tests/api -v
python -m pytest tests/nodes/test_annotate_corrections.py tests/nodes/test_comment_writeback.py -v
python -m pytest tests/agents/test_comment_agent.py -v
python -m pytest tests/graphs tests/nodes -v
python -m pytest tests/prompts tests/util tests/retrieval -v
```

Windows 虚拟环境：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -v
.\.venv\Scripts\python.exe scripts\diagnose_word.py
```

WSL/Linux（无 COM；隔离临时目录）：

```bash
cd backend
TMPDIR=/tmp TMP=/tmp TEMP=/tmp .venv-linux/bin/python -m pytest tests -v
```

## 测试布局

**位置：** `backend/tests/<scope>/test_*.py`，不与源码 co-locate。

**规模（2026-07-18）：** 约 **87** 个 `test_*.py` 文件。

| 目录 | 约计 | 关注点 |
|------|------|--------|
| `agents/` | 7 | comment agent、content agent、sanitizer、table placeholder、task context assistant |
| `api/` | 5 | generate、agent run NDJSON、tender、comment_supplement、template_candidates |
| `config/` | 2 | settings/LangSmith、protected fields |
| `graphs/` | 11 | generation_mode 分支、各 form graph、comment_supplement graph |
| `helper/` | 7 | Word helper fake（style、cleanup、delete、table placeholder parse） |
| `logging/` | 1 | task audit log 路径 |
| `models/` | 3 | GenerateRequest、SSE agent_step |
| `nodes/` | 28 | rewrite、annotate_corrections、comment_writeback、update_word、dispatch |
| `progress/` | 1 | 上传 rewrite 进度节点 |
| `prompts/` | 3 | generate routing、comment prompt |
| `retrieval/` | 5 | bad case、embedding、qdrant、索引脚本 |
| `services/` | 8 | document/agent_run/task/SSE snapshot |
| `skills/` | 2 | task skill runtime / instructions |
| `util/` | 4 | LLM stream、fetch tender、table models、symbol tokens |

**命名：**
- 文件 `test_<主题>.py`。
- 函数 `test_<行为>_<期望>()`，例如 `test_annotate_corrections_normalizes_text_and_tables`、`test_write_polished_comments_retries_on_rpc_error`、`test_comment_agent_writeback_degrades_missing_word_context_to_warning`。

## 测试结构模式

**API（async + monkeypatch service）：**

```python
@pytest.mark.asyncio
async def test_create_comment_supplement_task_returns_created_response(monkeypatch) -> None:
    class FakeDocumentService:
        def create_comment_supplement_task(self, request):
            return GenerateResponse(...)  # 或等价响应模型

    monkeypatch.setattr(api_module, "get_document_service", lambda: FakeDocumentService())
    response = await api_module.create_comment_supplement_task(request)
    assert response.success is True
```

**Service / initial state：**

```python
service = object.__new__(DocumentService)
state = service._build_initial_state(request, task_id="task-1")
assert "generation_style" not in rewrite_state
```

**Graph 编译与分支：** 子类化真实 graph 基类，替换节点为轻量 callable，`.compile().invoke(state)` 断言调用顺序。

**Word helper / comment writeback（fake COM 对象）：** 内联 `_FakeDocument` / `_FakeRange` / `_FakeFind` / `_FakeCommentsCollection`，实现 `Range`、`Find.Execute`、`Comments.Add` 等最小表面，**不**启动 Word。

## Mock 策略

**常用工具：** `monkeypatch`、`unittest.mock.patch` / `MagicMock`、`tmp_path`、文件内 fake class、async generator。

**应 Mock：**
- LLM：`stream_llm_completion`、agent `create_agent` / runner、`_run_annotation_llm`。
- 外部 HTTP：`fetch_tender_data`、`fetch_template_file` / `requests.get`。
- SSE：`send_progress_threadsafe`、`send_llm_output_threadsafe`。
- Word 生命周期：`create_word_application`、`open_document_with_retry`、`save_document_with_retry`、`close_word_application`、`find_anchor_range` 等（见 `test_comment_agent_writeback_node.py` 的 `_patch_word_success`）。
- 审计/workspace 根目录：`COMMENT_AGENT_AUDIT_ROOT`、`get_generate_context_log_dir` → `tmp_path`。
- 进度套件：`autouse` 清空 `TaskQueueManager` 并 stub SSE（`tests/progress/`）。

**不应 Mock：**
- Pydantic 请求/响应 shape 与枚举默认值。
- Graph registry 类属性绑定。
- 下载路径 containment 与上传类型校验本身。
- Prompt 契约字符串、sanitizer、table placeholder 纯函数（确定性输入直接调用）。
- `MODEL_CONFIGS` 默认值（stream 测试只 mock client / heartbeat / settings 属性）。

## 夹具与工厂

- `conftest.py` **无** 业务 fixture；共享 setup 仅 import path。
- 多数 fake 与 `autouse` 清理写在测试文件内，避免隐藏依赖。
- 临时文件一律 `tmp_path`；勿写真实 `settings.UPLOAD_DIR`。
- 路径字符串可用 `D:/UploadFiles/...` 作契约，不要求文件真实存在（除非测存在性）。
- 本地 factory 示例：`build_request(...)`、`build_select_request(...)` 在各文件内定义。

## 近期真实模式：批注链路

### `annotate_corrections`（`tests/nodes/test_annotate_corrections.py`）

- monkeypatch `_write_correction_log_artifact` 与 `_run_annotation_llm`，测标识归一化（`△/*` → `▲/★`）、表格 cell 文本、更正批注文案「原技术参数为…现改为…」。
- 无 `tender_params` 时断言 **不** 调用 LLM。
- `_run_annotation_llm` 路径：mock `stream_llm_completion` 为 async fake，断言 `extra_params_override={"temperature": 0.1}`，并用 `tmp_path` 检查 prompt/raw_output 工件。
- Prompt 契约：系统提示中的事实门控、审核器「不确定时不要保留」、parser 拒绝错误锚点/非固定措辞。

### `comment_writeback`（`tests/nodes/test_comment_writeback.py`）

- 完整 fake Word 表面：`_FakeDocument` + `Comments.Add` 可配置重试失败 / 永久失败。
- `TestCommentWritebackRetryLogic`：`patch(...time.sleep)` 验证 RPC 重试次数与 `comment_add_failed` issue。
- `build_comment_writeback_summary_payload`：仅当 `generated>0` 且 `failed>0` 时 `warning=True`。
- 表格/markdown 行匹配等分组测试同文件后续 `TestCommentWritebackTableMatching`。

### `comment_agent`（`tests/agents/test_comment_agent.py`）

- 系统 prompt 契约：不捏造「无原始技术参数」的差异批注。
- fake `Find`/`Range`/`Comments` 验证 `validate_comment_reference_candidates` 与 `write_validated_comment_candidates_to_word`。
- runner 命名与 tool limit：`VALIDATE_COMMENT_REFERENCES_TOOL` / `WRITE_VALIDATED_COMMENTS_TOOL`。
- audit 路径命名含 project 元数据清洗（`tmp_path` + monkeypatch `COMMENT_AGENT_AUDIT_ROOT`）。

### `comment_agent_writeback` 节点（`tests/nodes/test_comment_agent_writeback_node.py`）

- `autouse` 关闭 bad case context、审计根指向 `tmp_path`。
- 缺锚点上下文 → `comment_writeback_result.warning` + `reason == "missing_comment_agent_anchor_context"` + `agent_step` final 事件。
- 空候选不 warning；成功路径用 `_patch_word_success` 替掉全部 COM 入口。

### Comment supplement API / graph

- API：`@pytest.mark.asyncio` + FakeDocumentService。
- Graph：`tests/graphs/test_comment_supplement_graph.py` 替换 prepare/agent/finalize 节点测边。

## 模型与边界测试

- Generate 默认/枚举：`tests/models/test_generate_request_generation_style.py`。
- `tender_params` 双形态：`test_generate_request_tender_params.py`。
- generate-only 字段不进 rewrite state：`test_document_service_initial_state.py`。
- SSE agent_step shape：`test_sse_agent_step.py`。
- Agent run NDJSON：`tests/api/test_agent_run_api.py`（`media_type`、`Cache-Control`、必填 `context_snapshot`）。
- Tender API：`ifzgcg` 透传、investment 字符串化、不支持采购方式的非阻断 warning。

## Prompt / LLM / Retrieval

- Prompt routing 真实 builder：`tests/prompts/test_generate_prompt_routing.py`。
- Comment prompt / bad case：`tests/prompts/test_comment_prompt_*.py`。
- Sanitizer / table placeholder：`tests/agents/test_content_sanitizer.py`、`test_table_placeholder_utils.py`、`tests/helper/test_text_parsing_table_placeholder.py`。
- LLM stream：`tests/util/test_llm_stream_utils.py`（超时、`ensure_llm_env` 只暴露配置键）。
- Retrieval：本地 Markdown + fake embedding/Qdrant + `tmp_path`；失败断言降级，不要求在线 Qdrant。

## Word COM 策略与闭环门槛

**默认套件 = no-COM：**
- 不依赖 `pytest.skip` / `importorskip` / `sys.platform` 条件跳过；通过 fake + monkeypatch 覆盖 COM 交互面。
- Graph/node 单元测试不启动真实 Word。

**完整 COM 闭环：**
- 必须在 Windows + 本机 Word/WPS + `pywin32`（requirements 中 `platform_system == "Windows"` 条件安装）。
- 诊断：`python scripts/diagnose_word.py`。
- WSL/Linux pytest **不能**证明 COM 或真实 `.doc/.docx` 写回正确。

## 覆盖率

- 未配置 coverage 阈值或插件。
- 若需覆盖率，先补项目约定与依赖，再使用带 `--cov` 的 pytest。

## 测试类型一览

**单元：** models、config、helper、prompts、sanitizer、placeholder、annotate parser。

**无 COM 集成风格：** api、services、graphs、skills/nodes rewrite、retrieval、LLM stream util、审计日志路径、comment agent / writeback / supplement。

**E2E：** `backend/tests/` 无浏览器 E2E；Word 闭环靠 Windows 诊断脚本与真实任务。

## 异步约定（再次强调）

```python
@pytest.mark.asyncio
async def test_service_streams_events(monkeypatch):
    events = []
    async for event in service.stream(request, payload):
        events.append(event)
    assert events[0].startswith('{"event"')
```

- 漏标 `@pytest.mark.asyncio` 会导致 async 测试不被正确执行或失败（无 auto mode）。
- 同步测试（绝大多数 node/helper）不要无故标 asyncio。

## 安全与夹具卫生

- 测试不得读取或打印真实 `.env` 密钥。
- Agent run / audit 相关断言验证 scrub 后摘要与白名单字段（`tests/agents/test_task_context_assistant_logging.py`）。
- 审计与 workspace 输出隔离到 `tmp_path`。

---

*后端测试模式分析：2026-07-18*
