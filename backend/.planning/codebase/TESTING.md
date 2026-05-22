# Testing Patterns

**Analysis Date:** 2026-05-22

## Test Framework

**Runner:**
- `pytest` is the backend test runner. It is declared in `backend/requirements.txt` and used by backend validation guidance in `AGENTS.md`.
- `pytest-asyncio` is declared in `backend/requirements.txt` and used for async route/service tests such as `backend/tests/api/test_generate_api.py` and `backend/tests/api/test_tender_api.py`.
- No dedicated `pytest.ini`, `pyproject.toml`, or backend coverage config is detected; `backend/tests/conftest.py` supplies import-path setup for the current test suite.

**Assertion Library:**
- Use plain `assert`, `pytest.raises`, `pytest.mark.parametrize`, `monkeypatch`, `tmp_path`, and focused fake objects. Examples live in `backend/tests/config/test_tender_config_protected_fields.py`, `backend/tests/nodes/test_gngk_fw_zc_update_word.py`, and `backend/tests/helper/test_content_ops.py`.

**Run Commands:**
```bash
cd backend
python -m pytest tests -v              # Run all backend tests
python -m pytest tests/nodes -v        # Run a backend module scope
python -m pytest tests -v -k protected # Run a focused expression
python scripts/diagnose_word.py        # Manual Word COM diagnostic on Windows
```

**WSL backend validation:**
```bash
cd backend
source .venv-linux/bin/activate
TMPDIR=/tmp python3 -m pytest tests -v
```

The WSL virtualenv and temp-directory rules come from `AGENTS.md`; Windows + Word COM setup requirements come from `README.md`.

## Test File Organization

**Location:**
- Backend tests are centralized under `backend/tests/` and grouped by module scope.
- Current backend scopes include `backend/tests/api/`, `backend/tests/config/`, `backend/tests/graphs/`, `backend/tests/helper/`, `backend/tests/logging/`, `backend/tests/models/`, `backend/tests/nodes/`, `backend/tests/progress/`, `backend/tests/prompts/`, `backend/tests/services/`, `backend/tests/skills/`, and `backend/tests/util/`.
- Do not add business tests directly under `backend/tests/` root except `backend/tests/conftest.py` and `backend/tests/__init__.py`; this placement rule is explicit in `AGENTS.md`.

**Naming:**
- Use `test_*.py` for every backend test file, as required by `AGENTS.md` and demonstrated by `backend/tests/api/test_generate_api.py`, `backend/tests/graphs/test_gngk_tender_graph.py`, and `backend/tests/nodes/test_comment_writeback.py`.
- Use test function names that state the behavior and expected result, such as `test_get_generate_task_missing_task_returns_404()` in `backend/tests/api/test_generate_api.py` and `test_split_polished_text_into_blocks_rejects_missing_or_out_of_order_fields()` in `backend/tests/nodes/test_gngk_fw_zc_update_word.py`.

**Structure:**
```text
backend/tests/
├── api/        # FastAPI route behavior and API error contracts
├── config/     # tender_config and settings-derived contract tests
├── graphs/     # graph registry, workflow wiring, state propagation
├── helper/     # COM-free Word helper logic
├── logging/    # audit/progress log path and config propagation
├── models/     # Pydantic request/response model defaults and validation
├── nodes/      # common and type-specific node behavior with fake COM objects
├── progress/   # task progress tracking and graph wrapper behavior
├── prompts/    # prompt routing and output contract rendering
├── services/   # service state construction and task result payloads
├── skills/     # task skill declaration and workflow contracts
└── util/       # external request utilities and LLM stream utilities
```

## Test Structure

**Suite Organization:**
```python
from __future__ import annotations

import pytest

from backend.config.tender_config import get_protected_field_profile


@pytest.mark.parametrize(
    ("tender_type", "expected_key"),
    [
        ("xjcg", "common_two_field"),
        ("gngk_fw_zc", "gngk_three_field"),
    ],
)
def test_get_protected_field_profile_resolves_expected_profile(
    tender_type: str,
    expected_key: str,
) -> None:
    profile = get_protected_field_profile(tender_type)

    assert profile.key == expected_key
```

This is the pattern used by `backend/tests/config/test_tender_config_protected_fields.py`.

**Patterns:**
- Use direct unit invocation for route handlers when the behavior does not require an ASGI server, as in `backend/tests/api/test_generate_api.py`.
- Use `pytest.mark.asyncio` for async route tests, as in `backend/tests/api/test_generate_api.py` and `backend/tests/api/test_tender_api.py`.
- Use `pytest.mark.parametrize` for type matrices, graph registries, and protected-field profiles, as in `backend/tests/config/test_tender_config_protected_fields.py`, `backend/tests/graphs/test_gngk_tender_graph.py`, and `backend/tests/services/test_document_service_initial_state.py`.
- Use explicit fake classes for Word-like COM objects rather than importing Word or pywin32 in unit tests. Examples include `_FakeRange` and `_FakeDocument` in `backend/tests/nodes/test_comment_writeback.py`, `_FakeDoc` in `backend/tests/nodes/test_gngk_fw_zc_update_word.py`, and `_FakeFormatRange` in `backend/tests/helper/test_content_ops.py`.
- Use helper builders for repetitive Pydantic request setup, such as `build_request()` in `backend/tests/services/test_document_service_initial_state.py` and `_build_edit_request()` in `backend/tests/logging/test_task_audit_log_paths.py`.

## Mocking

**Framework:** `pytest` `monkeypatch` is the primary mocking tool; `unittest.mock.patch` and `MagicMock` are used when call assertions or context-managed patching are clearer.

**Patterns:**
```python
def test_stream_llm_completion_uses_configured_timeout_when_unspecified(monkeypatch):
    monkeypatch.setattr(llm_stream_utils.settings, "LLM_STREAM_TIMEOUT_SECONDS", 20)
    monkeypatch.setattr(llm_stream_utils, "ensure_llm_env", lambda _provider: None)
```

This style is used in `backend/tests/util/test_llm_stream_utils.py`.

```python
with patch("backend.nodes.common_word_nodes.comment_writeback.time.sleep") as mock_sleep:
    result = write_polished_comments(...)
```

This style is used for retry timing assertions in `backend/tests/nodes/test_comment_writeback.py`.

**What to Mock:**
- Mock LLM calls and environment checks, as in `backend/tests/util/test_llm_stream_utils.py` and `backend/tests/nodes/test_edit_audit_logging.py`.
- Mock Word COM lifecycle functions and document/range objects when testing node behavior, as in `backend/tests/nodes/test_update_word_inline_style_writeback.py`, `backend/tests/nodes/test_replace_content.py`, and `backend/tests/helper/test_content_ops.py`.
- Mock task queue and SSE side effects when testing progress wrappers, as in `backend/tests/progress/test_edit_progress_tracking.py`.
- Mock log directories with `tmp_path` for audit path tests, as in `backend/tests/logging/test_task_audit_log_paths.py`.
- Mock external HTTP responses in utility tests, as in `backend/tests/util/test_fetch_tender_data.py`.

**What NOT to Mock:**
- Do not mock pure parsing and contract helpers when the helper is the unit under test. Test real behavior in `backend/helper/word_helper/protected_fields.py`, `backend/helper/word_helper/content_ops.py`, and `backend/helper/word_helper/inline_style_ops.py` through `backend/tests/helper/` and `backend/tests/nodes/`.
- Do not mock graph registry wiring when asserting backend `form_type` to graph/node bindings. `backend/tests/graphs/test_gngk_tender_graph.py` calls `document_service._init_graph_registry()` and checks the real `GRAPH_REGISTRY`.
- Do not use real Word COM for normal unit tests. Word COM is a Windows integration boundary documented in `README.md` and constrained by `AGENTS.md`.

## Fixtures and Factories

**Test Data:**
```python
def build_request(
    *,
    origin_tender: str | None,
    template: str | None,
    form_type: FormType = FormType.GJGK_TENDER,
) -> GenerateRequest:
    ...
```

Use local builders like `build_request()` in `backend/tests/services/test_document_service_initial_state.py` when constructing full Pydantic models.

**Location:**
- Shared global test setup lives in `backend/tests/conftest.py`; currently it only adjusts import paths.
- Keep fixtures close to the tests that need them when they are scope-specific, as in `backend/tests/progress/test_edit_progress_tracking.py`.
- Keep fake COM classes in the test module that exercises that behavior, as in `backend/tests/nodes/test_comment_writeback.py`, `backend/tests/nodes/test_gngk_fw_zc_update_word.py`, and `backend/tests/helper/test_content_ops.py`.

## Coverage

**Requirements:** Not enforced by a visible backend coverage configuration. Root validation guidance in `AGENTS.md` requires `python -m pytest tests -v` for backend changes.

**View Coverage:**
```bash
# Not configured in this repository.
# Add a coverage tool only with explicit project agreement.
```

**Current coverage shape:**
- API error behavior is covered in `backend/tests/api/test_generate_api.py` and `backend/tests/api/test_tender_api.py`.
- Tender config and protected-field profiles are covered in `backend/tests/config/test_tender_config_protected_fields.py`.
- Graph wiring and state propagation are covered in `backend/tests/graphs/test_gngk_tender_graph.py` and `backend/tests/graphs/test_gjgk_tender_graph.py`.
- Word helper behavior is covered in `backend/tests/helper/test_content_ops.py`, `backend/tests/helper/test_inline_style_ops.py`, and `backend/tests/helper/test_paragraph_boundary_ops.py`.
- Node behavior is covered in `backend/tests/nodes/`, including comment writeback, update word, protected fields, replacement extraction, and skill dispatch.
- Service state construction and task payloads are covered in `backend/tests/services/`.
- Prompt and skill contracts are covered in `backend/tests/prompts/` and `backend/tests/skills/`.

## Test Types

**Unit Tests:**
- Prefer unit tests for COM-free helpers, prompt renderers, Pydantic model validation, task progress logic, and service state construction. Examples live in `backend/tests/helper/`, `backend/tests/prompts/`, `backend/tests/models/`, `backend/tests/progress/`, and `backend/tests/services/`.

**Integration Tests:**
- Use lightweight integration tests for graph registration, workflow wiring, and graph compilation with fake nodes. `backend/tests/graphs/test_gngk_tender_graph.py` compiles a test graph and asserts state propagation without Word COM.
- Use service-level tests for task result payloads and initial state construction without launching FastAPI or Word, as in `backend/tests/services/test_document_service_initial_state.py` and `backend/tests/services/test_document_service_task_result.py`.

**E2E Tests:**
- Backend-only E2E is not currently represented under `backend/tests/`.
- User-visible browser E2E belongs to frontend Playwright per `AGENTS.md`; backend changes that alter task creation, SSE, completion, failure, or download contracts should add backend tests plus frontend/API contract coverage where appropriate.
- Real Word COM verification is a Windows integration activity. Use `python scripts/diagnose_word.py` from `backend/scripts/diagnose_word.py` and document the environment when a change requires real Word validation.

## COM-Safe Testing Strategy

**Default strategy:**
- Keep unit tests COM-free by extracting logic into `backend/helper/word_helper/` and using fake Word objects in `backend/tests/helper/` and `backend/tests/nodes/`.
- Test protected-field parsing, blank-line preservation, markdown table conversion, paragraph boundary decisions, inline style matching, and writeback summaries without opening Word. Relevant implementation paths are `backend/helper/word_helper/protected_fields.py`, `backend/helper/word_helper/text_parsing.py`, `backend/helper/word_helper/content_ops.py`, `backend/helper/word_helper/paragraph_boundary_ops.py`, and `backend/helper/word_helper/inline_style_ops.py`.
- Patch or fake `create_word_application`, `open_document_with_retry`, and `close_word_application` when a node-level test needs to cross the Word lifecycle boundary, following `backend/tests/nodes/test_update_word_inline_style_writeback.py`.

**Windows-only checks:**
- Run real Word COM diagnostics only on Windows with Microsoft Word available, as stated in `README.md`.
- Use `backend/scripts/diagnose_word.py` for environment diagnostics before claiming a COM integration works.
- Keep Linux/WSL pytest focused on logic that does not require Word COM; WSL backend test setup is documented in `AGENTS.md`.

## Common Patterns

**Async Testing:**
```python
@pytest.mark.asyncio
async def test_get_generate_task_missing_task_returns_404():
    with pytest.raises(HTTPException) as exc_info:
        await get_generate_task("missing-task")

    assert exc_info.value.status_code == 404
```

Use this pattern for async API handlers, as in `backend/tests/api/test_generate_api.py`.

**Error Testing:**
```python
with pytest.raises(ValueError, match="缺少关键字段: 服务期限："):
    split_polished_text_into_blocks("服务地点：上海院区\n付款方式：按季度结算")
```

Use this pattern for fail-fast business contracts, as in `backend/tests/nodes/test_gngk_fw_zc_update_word.py` and `backend/tests/config/test_tender_config_protected_fields.py`.

**Graph Wiring Testing:**
```python
document_service._init_graph_registry()

assert document_service.GRAPH_REGISTRY["gngk_fw_zc_tender"] is GngkFwZcTenderGraph
assert GngkFwZcTenderGraph.NODE_UPDATE_WORD is gngk_fw_zc_update_word
```

Use this pattern when adding or changing backend `form_type` routing, as in `backend/tests/graphs/test_gngk_tender_graph.py`.

**Progress Testing:**
```python
wrapped = wrap_node_with_progress(lambda state, config=None: {"ok": True}, node_name)
result = wrapped({}, {"configurable": {"task_id": "task-edit-1"}})
```

Use this pattern for progress-node coverage, as in `backend/tests/progress/test_edit_progress_tracking.py`.

**LLM Stream Testing:**
```python
monkeypatch.setattr(llm_stream_utils, "ensure_llm_env", lambda _provider: None)
monkeypatch.setattr(llm_stream_utils, "_stream_openai_compatible", _fake_stream_openai_compatible)
```

Use this pattern for timeout/config behavior without real network calls, as in `backend/tests/util/test_llm_stream_utils.py`.

## Validation Commands By Change Type

**Any backend change:**
```bash
cd backend
python -m pytest tests -v
```

This is the minimum backend command required by `AGENTS.md`.

**Backend route or API contract change:**
```bash
cd backend
python -m pytest tests/api tests/models tests/services -v
```

Also check shared API contract implications named in `AGENTS.md`: `backend/api/`, `backend/models/`, `frontend/types/`, and `frontend/lib/api.ts`.

**Graph, state, node, or tender type routing change:**
```bash
cd backend
python -m pytest tests/graphs tests/services tests/nodes tests/config -v
```

Use this for changes in `backend/graphs/`, `backend/states/`, `backend/nodes/`, `backend/config/tender_config.py`, and `backend/services/document_service.py`.

**Word helper change:**
```bash
cd backend
python -m pytest tests/helper tests/nodes -v
```

Use this for changes in `backend/helper/word_helper/` and Word-node callers under `backend/nodes/`.

**Prompt, LLM, or skill runtime change:**
```bash
cd backend
python -m pytest tests/prompts tests/skills tests/util tests/nodes -v
```

Use this for changes in `backend/prompts/`, `backend/skills/`, `backend/services/user_routing_service.py`, `backend/services/chat_stream_service.py`, and `backend/util/common_util/llm_stream_utils.py`.

**Logging, progress, SSE, or task queue change:**
```bash
cd backend
python -m pytest tests/logging tests/progress tests/services tests/api -v
```

Use this for changes in `backend/util/log_util/`, `backend/core/sse_manager.py`, `backend/task/task_queue_manager.py`, `backend/graphs/base_graph.py`, and `backend/api/stream.py`.

---

*Testing analysis: 2026-05-22*
