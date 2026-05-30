from __future__ import annotations

from backend.nodes.common_word_nodes.comment_agent import comment_agent_writeback


def test_comment_agent_writeback_degrades_missing_word_context_to_warning() -> None:
    events = []
    result = comment_agent_writeback(
        {
            "generation_mode": "agent",
            "polished_text": "正文锚点",
            "polished_comments": [
                {
                    "reference_text": "正文锚点",
                    "comment_text": "补充审查意见",
                }
            ],
            "generated_comment_count": 1,
        },
        config={
            "configurable": {
                "task_id": "task-1",
                "task_kind": "generate",
                "agent_step_callback": events.append,
            }
        },
    )

    assert result["comment_writeback_result"]["warning"] is True
    assert result["comment_writeback_result"]["generated"] == 1
    assert result["comment_writeback_result"]["failed"] == 1
    assert result["comment_writeback_added"] == 0
    assert result["comment_writeback_failed"] == 1
    assert result["comment_writeback_errors"][0]["reason"] == "missing_comment_agent_anchor_context"
    assert events[-1].node == "comment_agent"
    assert events[-1].step_type == "final"
    assert events[-1].is_complete is True


def test_comment_agent_writeback_skips_empty_candidates_without_warning() -> None:
    result = comment_agent_writeback(
        {
            "generation_mode": "agent",
            "polished_text": "正文",
            "polished_comments": [],
            "generated_comment_count": 0,
        },
        config={"configurable": {"task_id": "task-1", "task_kind": "generate"}},
    )

    assert result["comment_writeback_result"]["warning"] is False
    assert result["comment_writeback_result"]["generated"] == 0
    assert result["comment_writeback_result"]["failed"] == 0
