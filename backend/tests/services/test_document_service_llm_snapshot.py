from __future__ import annotations

from backend.models.sse import SSEEventType
from backend.services.document_service import (
    TASK_KIND_TO_LLM_NODE,
    SSECallback,
    _LLMSnapshotRelay,
)


class _FakeSSEManager:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def send_llm_output_threadsafe(self, **kwargs) -> None:
        self.events.append(kwargs)


def test_generate_workflow_llm_relay_keeps_snapshot_node_contract() -> None:
    callback = SSECallback("task-1")
    sse_manager = _FakeSSEManager()
    relay = _LLMSnapshotRelay(
        task_id="task-1",
        model_provider="deepseek",
        callback=callback,
        sse_manager=sse_manager,
        node=TASK_KIND_TO_LLM_NODE["generate"],
        min_interval_seconds=0,
    )

    relay.on_snapshot("draft snapshot")
    relay.flush("final snapshot")

    events = callback.get_events()
    assert [event.event for event in events] == [SSEEventType.LLM, SSEEventType.LLM]
    assert events[0].data == {
        "content": "draft snapshot",
        "content_mode": "snapshot",
        "node": "generate_polished_text",
        "model": "deepseek",
        "is_complete": False,
        "task_id": "task-1",
        "timestamp": events[0].data["timestamp"],
    }
    assert events[1].data["content"] == "final snapshot"
    assert events[1].data["content_mode"] == "snapshot"
    assert events[1].data["node"] == "generate_polished_text"
    assert events[1].data["is_complete"] is True
    assert sse_manager.events == [
        {
            "task_id": "task-1",
            "content": "draft snapshot",
            "node": "generate_polished_text",
            "model": "deepseek",
            "is_complete": False,
        },
        {
            "task_id": "task-1",
            "content": "final snapshot",
            "node": "generate_polished_text",
            "model": "deepseek",
            "is_complete": True,
        },
    ]
