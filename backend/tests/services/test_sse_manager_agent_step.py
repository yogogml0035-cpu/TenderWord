from __future__ import annotations

import json

import pytest

from backend.core.sse_manager import SSEManager
from backend.models.sse import SSEEventType


@pytest.mark.asyncio
async def test_send_agent_step_buffers_event_for_replay() -> None:
    manager = SSEManager(heartbeat_interval=1)

    event_id = await manager.send_agent_step(
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

    missed_events = await manager.get_missed_events("task-agent-1", 0)

    assert event_id == 1
    assert len(missed_events) == 1
    event = missed_events[0]
    assert event.event is SSEEventType.AGENT_STEP
    assert event.data["task_id"] == "task-agent-1"
    assert event.data["task_kind"] == "generate"
    assert event.data["step_type"] == "audit"
    assert event.data["round"] == 1
    assert event.data["node"] == "verify_agent"
    assert event.data["is_complete"] is True
    assert event.data["timestamp"]
    assert event.data["findings"] == [
        {
            "evidence": "缺少交付周期",
            "fix_hint": "补充交付时间",
        }
    ]


@pytest.mark.asyncio
async def test_event_stream_replays_agent_step_then_done_terminal() -> None:
    manager = SSEManager(heartbeat_interval=1)
    await manager.send_agent_step(
        task_id="task-agent-1",
        task_kind="generate",
        step_type="revision",
        round=1,
        node="host_agent",
        content="修复后的正文",
        is_complete=True,
    )
    await manager.send_done(
        task_id="task-agent-1",
        task_kind="generate",
        success=True,
        message="任务完成",
    )

    stream = manager.event_stream("task-agent-1", "client-1", last_event_id=0)
    events = []
    async for raw_event in stream:
        if raw_event.startswith("id:"):
            events.append(raw_event)

    assert [event.splitlines()[1] for event in events] == [
        "event: agent_step",
        "event: done",
    ]
    agent_payload = json.loads(events[0].split("data: ", 1)[1].strip())
    assert agent_payload["step_type"] == "revision"
    assert agent_payload["content"] == "修复后的正文"
