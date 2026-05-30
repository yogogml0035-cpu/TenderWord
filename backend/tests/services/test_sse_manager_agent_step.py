from __future__ import annotations

import asyncio
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
        node="content_verify_agent",
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
    assert event.data["node"] == "content_verify_agent"
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
        node="content_agent",
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

@pytest.mark.asyncio
async def test_send_agent_step_replays_structured_comment_agent_payload() -> None:
    manager = SSEManager(heartbeat_interval=1)
    comment_agent = {
        "phase": "final",
        "rounds": [],
        "highlights": [],
        "writeback": {
            "attempted": 8,
            "added": 7,
            "failed": 0,
            "skipped": 1,
            "issues": [
                {
                    "index": 8,
                    "status": "已跳过",
                    "reason": "目标位置已有批注，已跳过",
                    "original_reference_text": "",
                    "reference_text": "售后服务",
                    "candidate_fragments": [],
                }
            ],
        },
    }

    await manager.send_agent_step(
        task_id="task-comment-1",
        task_kind="comment_supplement",
        step_type="final",
        round=1,
        node="comment_agent",
        content="comment_agent 最终写入统计",
        comment_agent=comment_agent,
        is_complete=True,
    )

    missed_events = await manager.get_missed_events("task-comment-1", 0)

    assert missed_events[0].event is SSEEventType.AGENT_STEP
    assert missed_events[0].data["comment_agent"]["writeback"]["added"] == 7
    assert missed_events[0].data["comment_agent"]["writeback"]["issues"][0]["reason"] == "目标位置已有批注，已跳过"

@pytest.mark.asyncio
async def test_send_agent_step_replays_structured_content_agent_payload() -> None:
    manager = SSEManager(heartbeat_interval=1)
    content_agent = {
        "phase": "audit",
        "summary": "第 1 轮审核发现 1 个问题。",
        "rounds": [
            {
                "round": 1,
                "phase": "audit",
                "label": "第 1 轮审核发现",
                "summary": "第 1 轮审核发现 1 个问题。",
                "issue_count": 1,
                "fix_count": 0,
                "content": '[{"evidence":"缺少交付地点","fix_hint":"补充交付地点"}]',
                "findings": [
                    {
                        "evidence": "缺少交付地点",
                        "fix_hint": "补充交付地点",
                    }
                ],
            }
        ],
        "highlights": [
            {
                "evidence": "缺少交付地点",
                "fix_hint": "补充交付地点",
            }
        ],
    }

    await manager.send_agent_step(
        task_id="task-agent-1",
        task_kind="generate",
        step_type="stream",
        round=1,
        node="content_verify_agent",
        content='[{"evidence":"缺少交付地点","fix_hint":"补充交付地点"}]',
        content_agent=content_agent,
        is_complete=False,
    )

    missed_events = await manager.get_missed_events("task-agent-1", 0)

    assert missed_events[0].event is SSEEventType.AGENT_STEP
    assert missed_events[0].data["content_agent"]["summary"] == "第 1 轮审核发现 1 个问题。"
    assert missed_events[0].data["content_agent"]["rounds"][0]["issue_count"] == 1

@pytest.mark.asyncio
async def test_send_done_buffers_comment_writeback_contract() -> None:
    manager = SSEManager(heartbeat_interval=1)
    comment_writeback = {
        "summary": "AI批注写入: 生成=2, 成功=1, 失败=1, 跳过=0",
        "generated": 2,
        "added": 1,
        "failed": 1,
        "skipped": 0,
        "warning": True,
    }

    event_id = await manager.send_done(
        task_id="task-comment-1",
        task_kind="comment_supplement",
        success=True,
        message="任务完成",
        comment_writeback=comment_writeback,
    )

    missed_events = await manager.get_missed_events("task-comment-1", 0)

    assert event_id == 1
    assert len(missed_events) == 1
    event = missed_events[0]
    assert event.event is SSEEventType.DONE
    assert event.data["task_kind"] == "comment_supplement"
    assert event.data["comment_writeback"] == comment_writeback

@pytest.mark.asyncio
async def test_send_done_threadsafe_passes_comment_writeback_contract() -> None:
    manager = SSEManager(heartbeat_interval=1)
    manager.bind_loop(asyncio.get_running_loop())
    comment_writeback = {
        "summary": "AI批注写入: 生成=0, 成功=0, 失败=0, 跳过=0",
        "generated": 0,
        "added": 0,
        "failed": 0,
        "skipped": 0,
        "warning": False,
    }

    manager.send_done_threadsafe(
        task_id="task-comment-threadsafe-1",
        task_kind="comment_supplement",
        success=True,
        message="任务完成",
        comment_writeback=comment_writeback,
    )
    await asyncio.sleep(0)

    missed_events = await manager.get_missed_events("task-comment-threadsafe-1", 0)

    assert len(missed_events) == 1
    event = missed_events[0]
    assert event.event is SSEEventType.DONE
    assert event.data["task_kind"] == "comment_supplement"
    assert event.data["comment_writeback"] == comment_writeback
