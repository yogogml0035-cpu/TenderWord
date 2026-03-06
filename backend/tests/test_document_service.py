from unittest.mock import Mock

from backend.services.document_service import _LLMSnapshotRelay


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
