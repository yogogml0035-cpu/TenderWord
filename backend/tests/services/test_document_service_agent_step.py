from __future__ import annotations

from backend.models.sse import AgentStepEventData, SSEEventType
from backend.services.document_service import SSECallback


def test_sse_callback_push_agent_step_keeps_json_payload_contract() -> None:
    callback = SSECallback("task-agent-1")

    callback.push_agent_step(
        AgentStepEventData(
            task_id="task-agent-1",
            task_kind="generate",
            step_type="audit",
            round=1,
            node="verify_agent",
            findings=[
                {
                    "evidence": "缺少交付周期",
                    "fix_hint": "补充交付时间",
                }
            ],
            is_complete=True,
        )
    )

    events = callback.get_events()

    assert len(events) == 1
    assert events[0].event is SSEEventType.AGENT_STEP
    assert events[0].data["task_kind"] == "generate"
    assert events[0].data["findings"] == [
        {
            "evidence": "缺少交付周期",
            "fix_hint": "补充交付时间",
        }
    ]
