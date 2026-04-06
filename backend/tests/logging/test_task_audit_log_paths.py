from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from backend.models.generate import EditTaskRequest, FormType, GenerateResponse, LLMModel
from backend.models.tender import TenderData
from backend.services.document_service import DocumentService, SSECallback
from backend.util.log_util.skill_audit_log import create_edit_audit_log


def _build_edit_request() -> EditTaskRequest:
    return EditTaskRequest(
        conversation_id="conv-edit-1",
        form_type=FormType.XJCG_TENDER,
        model=LLMModel.DEEPSEEK,
        edit_prompt="请把交付日期改为合同签订后30天",
        file_path="/tmp/source.docx",
        tender_lx=0,
        fund_source_lx=1,
        tender_data_snapshot=TenderData(
            project_name="项目A",
            project_number="NO-1",
            project_content="内容",
            buyer_name="采购人",
        ),
    )


def test_create_edit_audit_log_creates_prefixed_file(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.util.log_util.skill_audit_log._get_task_audit_dir",
        lambda: tmp_path,
    )

    log_path = create_edit_audit_log("conv-edit-1", now=0.0)

    assert Path(log_path).is_file()
    assert Path(log_path).parent == tmp_path
    assert Path(log_path).name.startswith("edit_")


def test_create_edit_task_passes_task_audit_log_path_to_submit(monkeypatch):
    request = _build_edit_request()
    service = DocumentService.__new__(DocumentService)
    captured: dict[str, object] = {}

    monkeypatch.setattr("backend.services.document_service.EDIT_SKILL_GRAPH_CLASS", object())
    monkeypatch.setattr(
        "backend.services.document_service.create_edit_audit_log",
        lambda audit_id: f"/tmp/{audit_id}-audit.json",
    )

    service._conversation_service = SimpleNamespace(
        get_latest_rewrite_state=lambda conversation_id: None
    )
    service._allocate_task_callback_pair = lambda: ("task-edit-1", SSECallback("task-edit-1"))
    service._build_edit_graph_initial_state = (
        lambda *, request, task_id: {
            "task_id": task_id,
            "user_session_id": request.conversation_id,
            "tender_type": "xjcg",
        }
    )

    def _fake_submit_graph_task(**kwargs):
        captured.update(kwargs)
        return GenerateResponse(
            success=True,
            task_id="task-edit-1",
            message="ok",
            task_kind="edit",
        )

    service._submit_graph_task = _fake_submit_graph_task

    response = asyncio.run(service.create_edit_task(request))

    assert response.success is True
    assert captured["task_audit_log_path"] == "/tmp/task-edit-1-audit.json"
    assert captured["task_user_prompt"] == request.edit_prompt
    assert captured["task_kind"] == "edit"


def test_invoke_graph_async_writes_task_and_legacy_audit_keys(monkeypatch):
    service = DocumentService.__new__(DocumentService)
    captured_configs: list[dict[str, object]] = []

    async def _fake_invoke_with_timing_async(
        compiled_graph,
        initial_state,
        verbose=True,
        config=None,
    ):
        captured_configs.append(config)
        return {"prepared_doc_path": "/tmp/output.docx"}, 0.01

    monkeypatch.setattr(
        "backend.graphs.invoke_with_timing_async",
        _fake_invoke_with_timing_async,
    )

    result, elapsed = asyncio.run(
        service._invoke_graph_async(
            compiled_graph=object(),
            initial_state={},
            task_id="task-edit-1",
            callback=SSECallback("task-edit-1"),
            model_provider="deepseek",
            llm_node_name="edit_text",
            task_audit_log_path="/tmp/task-audit.json",
            rewrite_log_path=None,
        )
    )

    assert result["prepared_doc_path"] == "/tmp/output.docx"
    assert elapsed == 0.01
    assert captured_configs
    configurable = captured_configs[0]["configurable"]
    assert configurable["task_audit_log_path"] == "/tmp/task-audit.json"
    assert configurable["rewrite_log_path"] == "/tmp/task-audit.json"


def test_invoke_graph_async_preserves_explicit_legacy_rewrite_log_path(monkeypatch):
    service = DocumentService.__new__(DocumentService)
    captured_configs: list[dict[str, object]] = []

    async def _fake_invoke_with_timing_async(
        compiled_graph,
        initial_state,
        verbose=True,
        config=None,
    ):
        captured_configs.append(config)
        return {}, 0.02

    monkeypatch.setattr(
        "backend.graphs.invoke_with_timing_async",
        _fake_invoke_with_timing_async,
    )

    asyncio.run(
        service._invoke_graph_async(
            compiled_graph=object(),
            initial_state={},
            task_id="task-rewrite-1",
            callback=SSECallback("task-rewrite-1"),
            model_provider="deepseek",
            llm_node_name="rewrite_text",
            task_audit_log_path="/tmp/task-audit.json",
            rewrite_log_path="/tmp/legacy-rewrite.json",
        )
    )

    configurable = captured_configs[0]["configurable"]
    assert configurable["task_audit_log_path"] == "/tmp/task-audit.json"
    assert configurable["rewrite_log_path"] == "/tmp/legacy-rewrite.json"
