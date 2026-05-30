from __future__ import annotations

from pathlib import Path

from backend.graphs.comment_supplement_graph import CommentSupplementGraph
from backend.nodes.common_word_nodes.comment_supplement import (
    prepare_comment_supplement,
)
from backend.states import TenderGraphStateBase

def test_comment_supplement_graph_runs_prepare_agent_finalize() -> None:
    calls: list[str] = []
    seen: dict[str, object] = {}

    def _prepare(state, config=None):
        calls.append("prepare_comment_supplement")
        return {
            "prepared_doc_path": "copy.docx",
            "polished_text": state.get("polished_text"),
        }

    def _agent(state, config=None):
        calls.append("comment_agent")
        seen["prepared_doc_path"] = state.get("prepared_doc_path")
        seen["polished_text"] = state.get("polished_text")
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
        "comment_agent",
        "finalize_comment_supplement",
    ]
    assert seen["prepared_doc_path"] == "copy.docx"
    assert seen["polished_text"] == "投标人须提供原厂授权函。"
    assert result["prepared_doc_path"] == "copy.docx"
    assert result["comment_supplement_completed"] is True

def test_comment_supplement_graph_estimates_three_nodes() -> None:
    assert CommentSupplementGraph().estimate_total_nodes({}) == 3

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
