from __future__ import annotations

from backend.models.sse import AgentStepEventData, SSEEventType


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
