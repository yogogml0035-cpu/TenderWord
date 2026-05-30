from __future__ import annotations

from backend.models.sse import AgentStepEventData, DoneEventData, SSEEventType
from backend.services.document_service import SSECallback


def test_sse_callback_push_agent_step_keeps_json_payload_contract() -> None:
    callback = SSECallback("task-agent-1")

    callback.push_agent_step(
        AgentStepEventData(
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


def test_sse_callback_push_agent_step_preserves_comment_agent_payload() -> None:
    callback = SSECallback("task-comment-1")

    callback.push_agent_step(
        AgentStepEventData(
            task_id="task-comment-1",
            task_kind="comment_supplement",
            step_type="final",
            round=1,
            node="comment_agent",
            content="comment_agent 最终写入统计",
            is_complete=True,
            comment_agent={
                "phase": "final",
                "rounds": [],
                "highlights": [],
                "writeback": {
                    "attempted": 2,
                    "added": 1,
                    "failed": 0,
                    "skipped": 1,
                    "issues": [],
                },
            },
        )
    )

    events = callback.get_events()

    assert len(events) == 1
    assert events[0].event is SSEEventType.AGENT_STEP
    assert events[0].data["comment_agent"]["writeback"]["added"] == 1


def test_sse_callback_push_agent_step_preserves_content_agent_payload() -> None:
    callback = SSECallback("task-agent-1")

    callback.push_agent_step(
        AgentStepEventData(
            task_id="task-agent-1",
            task_kind="generate",
            step_type="draft",
            round=1,
            node="content_generate_agent",
            content="初稿正文",
            is_complete=False,
            content_agent={
                "phase": "draft",
                "summary": "初稿生成完成，约 4 字。",
                "rounds": [
                    {
                        "round": 1,
                        "phase": "draft",
                        "label": "初稿生成",
                        "summary": "初稿生成完成，约 4 字。",
                        "issue_count": 0,
                        "fix_count": 0,
                        "content": "初稿正文",
                        "findings": [],
                    }
                ],
                "highlights": [],
            },
        )
    )

    events = callback.get_events()

    assert len(events) == 1
    assert events[0].event is SSEEventType.AGENT_STEP
    assert events[0].data["content_agent"]["phase"] == "draft"
    assert events[0].data["content_agent"]["rounds"][0]["label"] == "初稿生成"


def test_sse_callback_push_done_keeps_comment_writeback_contract() -> None:
    callback = SSECallback("task-comment-1")
    comment_writeback = {
        "summary": "AI批注写入: 生成=2, 成功=1, 失败=1, 跳过=0",
        "generated": 2,
        "added": 1,
        "failed": 1,
        "skipped": 0,
        "warning": True,
    }

    callback.push_done(
        DoneEventData(
            task_id="task-comment-1",
            task_kind="generate",
            success=True,
            message="任务完成",
            output_file="D:/UploadFiles/output.docx",
            comment_writeback=comment_writeback,
        )
    )

    events = callback.get_events()

    assert len(events) == 1
    assert events[0].event is SSEEventType.DONE
    assert events[0].data["comment_writeback"] == comment_writeback
