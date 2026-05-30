from __future__ import annotations

from backend.graphs.base_graph import StandardTenderWorkflowGraph
from backend.states.base_state import TenderGraphStateBase


def _identity_node(state, config=None):
    return {}


def _build_graph(calls: list[str]) -> StandardTenderWorkflowGraph:
    def _extract_node(state, config=None):
        calls.append("extract_tender_params")
        return {"tender_params": "extracted params"}

    def _word_node(state, config=None):
        calls.append("word_operation")
        return {}

    def _generate_node(state, config=None):
        calls.append("generate_polished_text")
        return {"polished_text": "workflow text", "generate_polished_done": True}

    def _content_node(state, config=None):
        calls.append("content_agent")
        return {"polished_text": "agent text", "generate_polished_done": True}

    def _comments_node(state, config=None):
        calls.append("generate_comments")
        return {"polished_comments": []}

    def _update_node(state, config=None):
        calls.append("update_word")
        if state.get("generation_mode") == "agent":
            assert state.get("suppress_ai_comment_writeback") is True
        else:
            assert state.get("suppress_ai_comment_writeback") is False
        return {"prepared_doc_path": "D:/UploadFiles/output.docx"}

    def _comment_agent_node(state, config=None):
        calls.append("comment_agent")
        return {
            "comment_writeback_result": {
                "summary": "AI 批注写入：生成 0 条，成功 0 条，失败 0 条，跳过 0 条",
                "generated": 0,
                "added": 0,
                "failed": 0,
                "skipped": 0,
                "warning": False,
            }
        }

    class _GenerationModeGraph(StandardTenderWorkflowGraph):
        STATE_CLS = TenderGraphStateBase
        NODE_PREPARE_TEMPLATE = _identity_node
        NODE_GET_COMMENTS = _identity_node
        NODE_COPY_COMMENTS = _identity_node
        NODE_EXTRACT_TENDER_PARAMS = _extract_node
        NODE_DELETE_TENDER_PARAM = _word_node
        NODE_GET_REPLACEMENTS = _word_node
        NODE_REPLACE_CONTENT = _word_node
        NODE_GENERATE_POLISHED_TEXT = _generate_node
        NODE_CONTENT_AGENT_GENERATE = _content_node
        NODE_GENERATE_COMMENTS = _comments_node
        NODE_UPDATE_WORD = _update_node
        NODE_COMMENT_AGENT = _comment_agent_node

    return _GenerationModeGraph()


def _run_graph(generation_mode: str) -> tuple[dict, list[str]]:
    calls: list[str] = []
    result = _build_graph(calls).compile().invoke(
        {
            "generation_mode": generation_mode,
            "origin_tender_path": "",
            "prepared_doc_path": "D:/UploadFiles/template.docx",
            "insertion_before_text": "before",
            "insertion_after_text": "after",
        }
    )
    return result, calls


def test_workflow_branch_uses_generate_polished_text_and_skips_content() -> None:
    result, calls = _run_graph("workflow")

    assert "generate_polished_text" in calls
    assert "content_agent" not in calls
    assert "comment_agent" not in calls
    assert "word_operation" in calls
    assert calls[-1] == "update_word"
    assert result["polished_text"] == "workflow text"
    assert result["generate_polished_done"] is True


def test_agent_branch_uses_content_and_skips_generate_polished_text() -> None:
    result, calls = _run_graph("agent")

    assert "content_agent" in calls
    assert "generate_polished_text" not in calls
    assert "word_operation" in calls
    assert calls[-2:] == ["update_word", "comment_agent"]
    assert result["polished_text"] == "agent text"
    assert result["generate_polished_done"] is True


def test_generation_branches_continue_to_comments_when_origin_tender_exists() -> None:
    calls: list[str] = []
    result = _build_graph(calls).compile().invoke(
        {
            "generation_mode": "agent",
            "origin_tender_path": "D:/UploadFiles/review.docx",
            "prepared_doc_path": "D:/UploadFiles/template.docx",
            "insertion_before_text": "before",
            "insertion_after_text": "after",
        }
    )

    assert "content_agent" in calls
    assert "generate_comments" in calls
    assert calls[-2:] == ["update_word", "comment_agent"]
    assert result["polished_text"] == "agent text"


def test_estimate_total_nodes_uses_selected_generation_branch() -> None:
    graph = _build_graph([])

    assert graph.estimate_total_nodes({"generation_mode": "workflow"}) == 7
    assert graph.estimate_total_nodes({"generation_mode": "agent"}) == 8
