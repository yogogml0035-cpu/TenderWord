from __future__ import annotations

from pathlib import Path

from backend.graphs.comment_supplement_graph import CommentSupplementGraph
from backend.nodes.common_word_nodes import comment_supplement as comment_supplement_nodes
from backend.nodes.common_word_nodes.comment_supplement import (
    generate_comment_supplement_comments,
    prepare_comment_supplement,
)
from backend.states import TenderGraphStateBase

def test_comment_supplement_graph_runs_prepare_generate_agent_finalize() -> None:
    calls: list[str] = []
    seen: dict[str, object] = {}

    def _prepare(state, config=None):
        calls.append("prepare_comment_supplement")
        return {
            "prepared_doc_path": "copy.docx",
            "polished_text": state.get("polished_text"),
        }

    def _generate(state, config=None):
        calls.append("generate_comments")
        assert state.get("prepared_doc_path") == "copy.docx"
        return {
            "polished_comments": [
                {
                    "reference_text": "原厂授权函",
                    "comment_text": "建议提示：不得要求原厂授权函。",
                }
            ],
            "generated_comment_count": 1,
        }

    def _agent(state, config=None):
        calls.append("comment_agent")
        seen["comments"] = state.get("polished_comments")
        return {
            "comment_writeback_result": {
                "summary": "AI批注写入: 生成=1, 成功=1, 失败=0, 跳过=0",
                "generated": 1,
                "added": 1,
                "failed": 0,
                "skipped": 0,
                "warning": False,
            }
        }

    def _finalize(state, config=None):
        calls.append("finalize_comment_supplement")
        return {"comment_supplement_completed": True}

    class _Graph(CommentSupplementGraph):
        NODE_PREPARE_COMMENT_SUPPLEMENT = _prepare
        NODE_GENERATE_COMMENTS = _generate
        NODE_COMMENT_AGENT = _agent
        NODE_FINALIZE_COMMENT_SUPPLEMENT = _finalize

    result = _Graph().compile().invoke(
        {
            "task_id": "task-1",
            "conversation_id": "conv-1",
            "polished_text": "投标人须提供原厂授权函。",
        }
    )

    assert calls == [
        "prepare_comment_supplement",
        "generate_comments",
        "comment_agent",
        "finalize_comment_supplement",
    ]
    assert seen["comments"] == [
        {
            "reference_text": "原厂授权函",
            "comment_text": "建议提示：不得要求原厂授权函。",
        }
    ]
    assert result["prepared_doc_path"] == "copy.docx"
    assert result["comment_supplement_completed"] is True

def test_comment_supplement_graph_estimates_four_nodes() -> None:
    assert CommentSupplementGraph().estimate_total_nodes({}) == 4

def test_prepare_comment_supplement_copies_current_file(tmp_path: Path) -> None:
    source = tmp_path / "generated.docx"
    source.write_bytes(b"docx")

    result = prepare_comment_supplement(
        TenderGraphStateBase(
            task_id="task-abc",
            comment_supplement_source_file=str(source),
            prepared_doc_path=str(source),
        ),
        config={"configurable": {"task_id": "task-abc", "rewrite_cleanup_holder": {}}},
    )

    output_path = Path(result["prepared_doc_path"])
    assert output_path != source
    assert output_path.read_bytes() == b"docx"
    assert output_path.name.startswith("generated_comment_supplement_task-abc_")

def test_generate_comment_supplement_comments_uses_no_reference_prompt(monkeypatch) -> None:
    captured: dict[str, str] = {}

    async def fake_stream_llm_completion(**kwargs):
        captured["system_prompt"] = kwargs["system_prompt"]
        captured["user_prompt"] = kwargs["user_prompt"]
        return '[{"reference_text":"原厂授权函","comment_text":"建议提示：不得要求原厂授权函。"}]'

    monkeypatch.setattr(
        comment_supplement_nodes,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = generate_comment_supplement_comments(
        TenderGraphStateBase(
            tender_type="xjcg",
            polished_text="投标人须提供原厂授权函。",
        ),
        config={"configurable": {"model_provider": "deepseek", "suppress_llm_stdout": True}},
    )

    assert "三维审查要求" in captured["system_prompt"]
    assert "投标人须提供原厂授权函。" in captured["user_prompt"]
    assert result["generated_comment_count"] == 1
    assert result["polished_comments"] == [
        {
            "reference_text": "原厂授权函",
            "comment_text": "建议提示：不得要求原厂授权函。",
        }
    ]
