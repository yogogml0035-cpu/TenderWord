from __future__ import annotations

from backend.models.sse import AgentStepEventData, DoneEventData, SSEEventType


def test_agent_step_event_data_contains_audit_findings_contract() -> None:
    event_data = AgentStepEventData(
        task_id="task-agent-1",
        task_kind="generate",
        step_type="audit",
        round=1,
        node="content_verify_agent",
        findings=[
            {
                "evidence": "缺少交付周期",
                "fix_hint": "补充合同签订后的交付时间",
            }
        ],
        is_complete=True,
    )

    payload = event_data.model_dump(mode="json")

    assert SSEEventType.AGENT_STEP.value == "agent_step"
    assert payload["task_id"] == "task-agent-1"
    assert payload["task_kind"] == "generate"
    assert payload["step_type"] == "audit"
    assert payload["round"] == 1
    assert payload["node"] == "content_verify_agent"
    assert payload["is_complete"] is True
    assert payload["timestamp"]
    assert payload["findings"] == [
        {
            "evidence": "缺少交付周期",
            "fix_hint": "补充合同签订后的交付时间",
        }
    ]


def test_agent_step_revision_event_can_carry_content_snapshot() -> None:
    event_data = AgentStepEventData(
        task_id="task-agent-1",
        task_kind="generate",
        step_type="revision",
        round=2,
        node="content_agent",
        content="修复后的采购需求正文",
        is_complete=True,
    )

    payload = event_data.model_dump(mode="json")

    assert payload["step_type"] == "revision"
    assert payload["content"] == "修复后的采购需求正文"
    assert payload["findings"] == []


def test_agent_step_round_is_one_based_contract() -> None:
    event_data = AgentStepEventData(
        task_id="task-agent-1",
        task_kind="generate",
        step_type="stream",
        round=1,
        node="content_generate_agent",
        content="初稿正文",
        is_complete=True,
    )

    payload = event_data.model_dump(mode="json")

    assert payload["round"] == 1

def test_agent_step_event_data_can_carry_structured_comment_agent_payload() -> None:
    event_data = AgentStepEventData(
        task_id="task-comment-1",
        task_kind="comment_supplement",
        step_type="final",
        round=1,
        node="comment_agent",
        content="comment_agent 最终写入统计",
        is_complete=True,
        comment_agent={
            "phase": "final",
            "rounds": [
                {
                    "round": 1,
                    "label": "第 1 轮锚点校验",
                    "passed": 0,
                    "failed": 1,
                    "skipped": 0,
                    "highlights": [
                        {
                            "index": 1,
                            "status": "需修复",
                            "reason": "当前锚点未在最终正文中精确匹配",
                            "original_reference_text": "★7.售后服务",
                            "reference_text": "★7.售后服务",
                            "candidate_fragments": ["7.售后服务"],
                        }
                    ],
                },
                {
                    "round": 2,
                    "label": "第 2 轮修复复核",
                    "passed": 1,
                    "failed": 0,
                    "skipped": 0,
                    "highlights": [
                        {
                            "index": 1,
                            "status": "已修复",
                            "reason": "锚点已通过校验",
                            "original_reference_text": "★7.售后服务",
                            "reference_text": "7.售后服务",
                            "candidate_fragments": [],
                        }
                    ],
                },
            ],
            "highlights": [],
            "final_validation": {
                "round": 0,
                "label": "最终静默复校验",
                "passed": 1,
                "failed": 0,
                "skipped": 0,
                "highlights": [],
            },
            "writeback": {
                "attempted": 1,
                "added": 1,
                "failed": 0,
                "skipped": 0,
                "issues": [],
            },
        },
    )

    payload = event_data.model_dump(mode="json")

    assert payload["comment_agent"]["rounds"][0]["label"] == "第 1 轮锚点校验"
    assert payload["comment_agent"]["rounds"][1]["highlights"][0]["status"] == "已修复"
    assert payload["comment_agent"]["writeback"]["added"] == 1

def test_done_event_data_contains_comment_writeback_contract() -> None:
    event_data = DoneEventData(
        task_id="task-comment-1",
        task_kind="comment_supplement",
        success=True,
        message="任务完成",
        comment_writeback={
            "summary": "AI批注写入: 生成=2, 成功=1, 失败=1, 跳过=0",
            "generated": 2,
            "added": 1,
            "failed": 1,
            "skipped": 0,
            "warning": True,
        },
    )

    payload = event_data.model_dump(mode="json")

    assert payload["task_kind"] == "comment_supplement"
    assert payload["comment_writeback"] == {
        "summary": "AI批注写入: 生成=2, 成功=1, 失败=1, 跳过=0",
        "generated": 2,
        "added": 1,
        "failed": 1,
        "skipped": 0,
        "warning": True,
    }
