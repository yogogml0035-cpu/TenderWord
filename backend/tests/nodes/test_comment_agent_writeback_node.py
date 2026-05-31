from __future__ import annotations

from types import SimpleNamespace

from backend.nodes.common_word_nodes import comment_agent as comment_agent_node
from backend.nodes.common_word_nodes.comment_agent import comment_agent_writeback
from backend.prompts.comment_prompt import render_comment_prompt
from backend.prompts.types import CommentPromptInput


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
            "polished_text": "正文",
            "polished_comments": [],
            "generated_comment_count": 0,
        },
        config={"configurable": {"task_id": "task-1", "task_kind": "generate"}},
    )

    assert result["comment_writeback_result"]["warning"] is False
    assert result["comment_writeback_result"]["generated"] == 0
    assert result["comment_writeback_result"]["failed"] == 0


def test_comment_agent_writeback_allows_agent_generation_without_candidates(monkeypatch) -> None:
    captured = {}

    monkeypatch.setattr(
        comment_agent_node,
        "create_word_application",
        lambda **_kwargs: (object(), False),
    )
    monkeypatch.setattr(
        comment_agent_node,
        "open_document_with_retry",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(comment_agent_node, "unprotect_document", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        comment_agent_node,
        "find_anchor_range",
        lambda *_args, **_kwargs: (object(), object()),
    )
    monkeypatch.setattr(
        comment_agent_node,
        "resolve_anchor_content_range",
        lambda **_kwargs: {"range_start": 0, "range_end": 20},
    )
    monkeypatch.setattr(
        comment_agent_node,
        "save_document_with_retry",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        comment_agent_node,
        "close_word_application",
        lambda **_kwargs: None,
    )

    def fake_run_comment_agent(**kwargs):
        captured.update(kwargs)
        expected_prompt = render_comment_prompt(
            CommentPromptInput(
                tender_type="xjcg",
                polished_text="投标人须提供原厂授权函。",
            )
        )
        assert kwargs["initial_comments"] == []
        assert kwargs["allow_comment_generation"] is True
        assert (
            kwargs["comment_generation_instruction"]
            == expected_prompt.system_prompt + "\n\n" + expected_prompt.user_prompt
        )
        return SimpleNamespace(
            validation=SimpleNamespace(passed=[object()], failed=[], skipped=[]),
            writeback_result={
                "total": 1,
                "attempted": 1,
                "added": 1,
                "failed": 0,
                "skipped": 0,
                "issues": [],
            },
            audit_log_path=None,
            final_proposed_comments=[
                {
                    "reference_text": "投标人须提供原厂授权函",
                    "comment_text": "建议提示：不得要求原厂授权函。",
                }
            ],
        )

    monkeypatch.setattr(comment_agent_node, "run_comment_agent", fake_run_comment_agent)

    result = comment_agent_writeback(
        {
            "generation_mode": "agent",
            "task_kind": "generate",
            "tender_type": "xjcg",
            "prepared_doc_path": "D:/UploadFiles/output.docx",
            "polished_text": "投标人须提供原厂授权函。",
            "polished_comments": [],
            "generated_comment_count": 0,
            "insertion_before_text": "第三章  采购需求",
            "insertion_after_text": "第四章  响应文件有关格式",
        },
        config={
            "configurable": {
                "task_id": "task-2",
                "task_kind": "generate",
                "generation_mode": "agent",
            }
        },
    )

    assert captured["allow_comment_generation"] is True
    assert result["comment_writeback_result"]["generated"] == 1
    assert result["comment_writeback_result"]["added"] == 1


def test_comment_supplement_without_candidates_lets_comment_agent_generate(monkeypatch) -> None:
    captured = {}

    monkeypatch.setattr(
        comment_agent_node,
        "create_word_application",
        lambda **_kwargs: (object(), False),
    )
    monkeypatch.setattr(
        comment_agent_node,
        "open_document_with_retry",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(comment_agent_node, "unprotect_document", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        comment_agent_node,
        "find_anchor_range",
        lambda *_args, **_kwargs: (object(), object()),
    )
    monkeypatch.setattr(
        comment_agent_node,
        "resolve_anchor_content_range",
        lambda **_kwargs: {"range_start": 0, "range_end": 20},
    )
    monkeypatch.setattr(
        comment_agent_node,
        "save_document_with_retry",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        comment_agent_node,
        "close_word_application",
        lambda **_kwargs: None,
    )

    def fake_run_comment_agent(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            validation=SimpleNamespace(passed=[object()], failed=[], skipped=[]),
            writeback_result={
                "total": 1,
                "attempted": 1,
                "added": 1,
                "failed": 0,
                "skipped": 0,
                "issues": [],
            },
            audit_log_path=None,
            final_proposed_comments=[
                {
                    "reference_text": "投标人须提供原厂授权函",
                    "comment_text": "建议提示：不得要求原厂授权函。",
                }
            ],
        )

    monkeypatch.setattr(comment_agent_node, "run_comment_agent", fake_run_comment_agent)

    result = comment_agent_writeback(
        {
            "task_kind": "comment_supplement",
            "tender_type": "xjcg",
            "prepared_doc_path": "D:/UploadFiles/output.docx",
            "polished_text": "投标人须提供原厂授权函。",
            "polished_comments": [],
            "generated_comment_count": 0,
            "insertion_before_text": "第三章  采购需求",
            "insertion_after_text": "第四章  响应文件有关格式",
        },
        config={
            "configurable": {
                "task_id": "task-1",
                "task_kind": "comment_supplement",
            }
        },
    )

    assert captured["initial_comments"] == []
    assert captured["allow_comment_generation"] is True
    expected_prompt = render_comment_prompt(
        CommentPromptInput(
            tender_type="xjcg",
            polished_text="投标人须提供原厂授权函。",
        )
    )
    assert (
        captured["comment_generation_instruction"]
        == expected_prompt.system_prompt + "\n\n" + expected_prompt.user_prompt
    )
    assert result["comment_writeback_result"]["generated"] == 1
    assert result["comment_writeback_result"]["added"] == 1
