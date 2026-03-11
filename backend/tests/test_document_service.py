import asyncio
import importlib
from unittest.mock import Mock

import pytest

import backend.services.document_service as document_service_module
import backend.util.log_util.execution_log as execution_log_module
from backend.models.generate import FormType, GenerateRequest, LLMModel
from backend.models.tender import TenderData
from backend.services.document_service import DocumentService, _LLMSnapshotRelay
from backend.task.task_queue_manager import TaskQueueManager


def test_llm_snapshot_relay_throttles_intermediate_snapshots_and_flushes_final_state():
    callback = Mock()
    sse_manager = Mock()
    relay = _LLMSnapshotRelay(
        task_id="task-1",
        model_provider="deepseek",
        callback=callback,
        sse_manager=sse_manager,
        min_interval_seconds=999.0,
    )

    relay.on_snapshot("你")
    relay.on_snapshot("你好")
    relay.flush("你好啊")

    assert callback.push_llm.call_count == 2
    callback.push_llm.assert_any_call(
        content="你",
        node="generate_polished_text",
        model="deepseek",
        is_complete=False,
    )
    callback.push_llm.assert_any_call(
        content="你好啊",
        node="generate_polished_text",
        model="deepseek",
        is_complete=True,
    )

    assert sse_manager.send_llm_output_threadsafe.call_count == 2


def test_llm_snapshot_relay_does_not_emit_duplicate_completed_snapshots():
    callback = Mock()
    sse_manager = Mock()
    relay = _LLMSnapshotRelay(
        task_id="task-1",
        model_provider="deepseek",
        callback=callback,
        sse_manager=sse_manager,
        min_interval_seconds=0.0,
    )

    relay.flush("最终内容")
    relay.flush("最终内容")

    callback.push_llm.assert_called_once_with(
        content="最终内容",
        node="generate_polished_text",
        model="deepseek",
        is_complete=True,
    )
    sse_manager.send_llm_output_threadsafe.assert_called_once_with(
        task_id="task-1",
        content="最终内容",
        node="generate_polished_text",
        model="deepseek",
        is_complete=True,
    )


def test_document_service_invoke_graph_async_fail_fast_error_propagates(monkeypatch):
    service = DocumentService()
    callback = Mock()

    async def _raise_fail_fast(*_args, **_kwargs):
        raise RuntimeError("未找到前置锚点: 第三章 采购需求")

    async def _invoke_with_fail_fast(*_args, **_kwargs):
        return await _raise_fail_fast()

    graphs_module = importlib.import_module("backend.graphs")
    monkeypatch.setattr(graphs_module, "invoke_with_timing_async", _invoke_with_fail_fast)

    with pytest.raises(RuntimeError, match="未找到前置锚点"):
        asyncio.run(
            service._invoke_graph_async(
                compiled_graph=Mock(),
                initial_state={},
                task_id="task-1",
                callback=callback,
                model_provider="deepseek",
            )
        )


def test_document_service_create_task_returns_queue_snapshot(monkeypatch):
    original_instance = TaskQueueManager._instance
    TaskQueueManager._instance = None
    queue = TaskQueueManager()

    class DummyExecutor:
        def submit(self, *_args, **_kwargs):
            return Mock()

    monkeypatch.setattr(document_service_module, "GRAPH_REGISTRY", {"xjcg_tender": Mock()})
    monkeypatch.setattr(document_service_module, "_executor", DummyExecutor())

    try:
        service = DocumentService()
        request = GenerateRequest(
            form_type=FormType.XJCG_TENDER,
            tender_data=TenderData(
                project_name="示例项目",
                project_number="ZBGG-2026-001",
                project_content="采购示例内容",
                buyer_name="示例单位",
            ),
            file_paths={"template": "D:/UploadFiles/template.docx", "params": []},
            model=LLMModel.DEEPSEEK,
        )

        response = service.create_task(request)

        assert response.success is True
        assert response.status == "queued"
        assert response.queue_position == 0
        assert response.waiting_count == 0
    finally:
        queue._cleanup_thread_stop.set()
        queue._cleanup_thread.join(timeout=1)
        TaskQueueManager._instance = original_instance


class _DummyGraph:
    def estimate_total_nodes(self, _state):
        return 3

    def compile(self):
        return Mock()


def test_document_service_run_graph_logs_single_generate_audit_on_success(monkeypatch):
    service = DocumentService()
    service._task_queue = Mock()
    callback = Mock()

    sse_module = importlib.import_module("backend.core.sse_manager")
    monkeypatch.setattr(sse_module, "sse_manager", Mock())

    mock_info = Mock()
    mock_error = Mock()
    monkeypatch.setattr(execution_log_module._execution_logger, "info", mock_info)
    monkeypatch.setattr(execution_log_module._execution_logger, "error", mock_error)

    async def _fake_invoke(*_args, stdout_writer=None, stderr_writer=None, **_kwargs):
        assert stdout_writer is not None
        assert stderr_writer is not None
        stdout_writer.write("[extract_tender_params] 噪音日志\n")
        stderr_writer.write("stderr noise\n")
        return (
            {
                "project_zbr_xbr": "徐旭东、任彧晟",
                "project_number": "253505",
                "project_name": "细胞电转仪",
                "prepared_doc_path": "D:/output.docx",
            },
            1.23,
        )

    monkeypatch.setattr(service, "_invoke_graph_async", _fake_invoke)

    service._run_graph(
        task_id="task-1",
        graph_class=_DummyGraph,
        initial_state={
            "project_zbr_xbr": "徐旭东、任彧晟",
            "project_number": "253505",
            "project_name": "细胞电转仪",
        },
        callback=callback,
        model_provider="deepseek",
        task_kind="generate",
    )

    mock_info.assert_called_once_with(
        "徐旭东、任彧晟-253505-细胞电转仪结束生成，当前进入update_word"
    )
    mock_error.assert_not_called()


def test_document_service_run_graph_does_not_log_audit_on_failure(monkeypatch):
    service = DocumentService()
    service._task_queue = Mock()
    callback = Mock()

    sse_module = importlib.import_module("backend.core.sse_manager")
    monkeypatch.setattr(sse_module, "sse_manager", Mock())

    mock_info = Mock()
    monkeypatch.setattr(execution_log_module._execution_logger, "info", mock_info)

    async def _fake_invoke(*_args, stdout_writer=None, stderr_writer=None, **_kwargs):
        assert stdout_writer is not None
        assert stderr_writer is not None
        stdout_writer.write("stdout noise\n")
        stderr_writer.write("stderr noise\n")
        raise RuntimeError("boom")

    monkeypatch.setattr(service, "_invoke_graph_async", _fake_invoke)

    service._run_graph(
        task_id="task-2",
        graph_class=_DummyGraph,
        initial_state={
            "project_zbr_xbr": "徐旭东、任彧晟",
            "project_number": "253505",
            "project_name": "细胞电转仪",
        },
        callback=callback,
        model_provider="deepseek",
        task_kind="generate",
    )

    mock_info.assert_not_called()


def test_document_service_run_graph_does_not_log_audit_for_rewrite(monkeypatch):
    service = DocumentService()
    service._task_queue = Mock()
    callback = Mock()

    sse_module = importlib.import_module("backend.core.sse_manager")
    monkeypatch.setattr(sse_module, "sse_manager", Mock())

    mock_info = Mock()
    monkeypatch.setattr(execution_log_module._execution_logger, "info", mock_info)

    async def _fake_invoke(*_args, stdout_writer=None, stderr_writer=None, **_kwargs):
        assert stdout_writer is not None
        assert stderr_writer is not None
        stdout_writer.write("rewrite stdout noise\n")
        return (
            {
                "project_zbr_xbr": "徐旭东、任彧晟",
                "project_number": "253505",
                "project_name": "细胞电转仪",
                "prepared_doc_path": "D:/rewrite.docx",
            },
            0.8,
        )

    monkeypatch.setattr(service, "_invoke_graph_async", _fake_invoke)

    service._run_graph(
        task_id="task-3",
        graph_class=_DummyGraph,
        initial_state={
            "project_zbr_xbr": "徐旭东、任彧晟",
            "project_number": "253505",
            "project_name": "细胞电转仪",
        },
        callback=callback,
        model_provider="deepseek",
        task_kind="rewrite",
    )

    mock_info.assert_not_called()
