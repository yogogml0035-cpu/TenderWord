import asyncio
import importlib
from unittest.mock import Mock

import pytest

import backend.services.document_service as document_service_module
import backend.util.log_util.execution_log as execution_log_module
from backend.models.generate import FormType, GenerateRequest, GenerateResponse, LLMModel
from backend.models.tender import TenderData
from backend.services.conversation_service import ConversationService
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


def test_document_service_create_rewrite_task_forwards_rewrite_log_path(monkeypatch):
    service = DocumentService()
    captured: dict[str, object] = {}

    class ConversationStub:
        def has_rewrite_history(self, _conversation_id: str) -> bool:
            return True

        def get_latest_rewrite_state(self, _conversation_id: str):
            return {
                "prepared_doc_path": "D:/existing.docx",
                "polished_text": "原文",
                "source_origin_tender_path": "D:/origin.docx",
            }

    def _fake_submit_graph_task(**kwargs):
        captured.update(kwargs)
        return GenerateResponse(success=True, task_id="task-9", task_kind="rewrite")

    service._conversation_service = ConversationStub()
    monkeypatch.setattr(document_service_module, "REWRITE_SKILL_GRAPH_CLASS", _DummyGraph)
    monkeypatch.setattr(service, "_submit_graph_task", _fake_submit_graph_task)

    response = asyncio.run(
        service.create_rewrite_task(
            conversation_id="conv-9",
            user_prompt="请把第三章写正式",
            model_provider="deepseek",
            rewrite_log_path="D:/logs/rewrite.json",
        )
    )

    assert response.success is True
    assert captured["rewrite_log_path"] == "D:/logs/rewrite.json"
    assert captured["task_kind"] == "rewrite"
    assert captured["conversation_id"] == "conv-9"
    assert captured["rewrite_user_prompt"] == "请把第三章写正式"
    assert captured["initial_state"]["skill_id"] == "rewrite"
    assert captured["initial_state"]["source_origin_tender_path"] == "D:/origin.docx"


def test_document_service_invoke_graph_async_includes_rewrite_log_path_in_config(monkeypatch):
    service = DocumentService()
    callback = Mock()
    captured_config: dict[str, object] = {}

    async def _fake_invoke_with_timing_async(
        _compiled_graph,
        _initial_state,
        *,
        verbose,
        config,
    ):
        assert verbose is True
        captured_config.update(config)
        return {"polished_text": "改写结果"}, 0.25

    graphs_module = importlib.import_module("backend.graphs")
    monkeypatch.setattr(graphs_module, "invoke_with_timing_async", _fake_invoke_with_timing_async)

    asyncio.run(
        service._invoke_graph_async(
            compiled_graph=Mock(),
            initial_state={},
            task_id="task-10",
            callback=callback,
            model_provider="deepseek",
            llm_node_name="rewrite_text",
            rewrite_log_path="D:/logs/rewrite.json",
        )
    )

    assert captured_config["configurable"]["rewrite_log_path"] == "D:/logs/rewrite.json"


def test_build_rewrite_state_snapshot_persists_tender_params():
    service = DocumentService()

    snapshot = service._build_rewrite_state_snapshot(
        result_state={
            "prepared_doc_path": "D:/rewrite.docx",
            "polished_text": "改写结果",
            "tender_params": "完整技术参数",
        },
        initial_state={
            "tender_type": "xjcg",
            "insertion_before_text": "第三章  采购需求",
            "insertion_after_text": "第四章  响应文件有关格式",
        },
    )

    assert snapshot["tender_params"] == "完整技术参数"
    assert snapshot["polished_text"] == "改写结果"


def test_build_rewrite_state_snapshot_persists_uploaded_origin_path():
    service = DocumentService()

    snapshot = service._build_rewrite_state_snapshot(
        result_state={},
        initial_state={
            "tender_type": "xjcg",
            "prepared_doc_path": "D:/rewrite.docx",
            "source_origin_tender_path": "D:/origin.docx",
        },
    )

    assert snapshot["source_origin_tender_path"] == "D:/origin.docx"


def test_rewrite_snapshot_keeps_tender_params_across_generate_and_rewrite_success():
    conversation_service = ConversationService()

    conversation_service.seed_generate_success(
        "conv-1",
        {
            "prepared_doc_path": "D:/origin.docx",
            "polished_text": "首版正文",
            "tender_params": "首版技术参数",
            "tender_type": "xjcg",
        },
    )
    first_snapshot = conversation_service.get_latest_rewrite_state("conv-1")
    assert first_snapshot is not None
    assert first_snapshot["tender_params"] == "首版技术参数"

    conversation_service.append_rewrite_success(
        "conv-1",
        user_prompt="请修改",
        rewrite_state={
            "prepared_doc_path": "D:/rewrite.docx",
            "polished_text": "二版正文",
            "tender_params": first_snapshot["tender_params"],
            "tender_type": "xjcg",
        },
    )

    latest_snapshot = conversation_service.get_latest_rewrite_state("conv-1")
    assert latest_snapshot is not None
    assert latest_snapshot["tender_params"] == "首版技术参数"
    assert latest_snapshot["polished_text"] == "二版正文"


def test_rewrite_snapshot_keeps_uploaded_origin_path_across_generate_and_rewrite_success():
    conversation_service = ConversationService()

    conversation_service.seed_generate_success(
        "conv-2",
        {
            "prepared_doc_path": "D:/origin.docx",
            "polished_text": "首版正文",
            "source_origin_tender_path": "D:/origin-review.docx",
            "tender_type": "xjcg",
        },
    )
    first_snapshot = conversation_service.get_latest_rewrite_state("conv-2")
    assert first_snapshot is not None
    assert first_snapshot["source_origin_tender_path"] == "D:/origin-review.docx"

    conversation_service.append_rewrite_success(
        "conv-2",
        user_prompt="请修改",
        rewrite_state={
            "prepared_doc_path": "D:/rewrite.docx",
            "polished_text": "二版正文",
            "source_origin_tender_path": first_snapshot["source_origin_tender_path"],
            "tender_type": "xjcg",
        },
    )

    latest_snapshot = conversation_service.get_latest_rewrite_state("conv-2")
    assert latest_snapshot is not None
    assert latest_snapshot["source_origin_tender_path"] == "D:/origin-review.docx"
