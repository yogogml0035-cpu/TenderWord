import asyncio
import importlib
from unittest.mock import Mock

import pytest

import backend.services.document_service as document_service_module
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
