import asyncio
import importlib
from unittest.mock import Mock

import pytest

from backend.services.document_service import DocumentService, _LLMSnapshotRelay


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
