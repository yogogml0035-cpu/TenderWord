from __future__ import annotations

from backend.graphs.base_graph import StandardTenderWorkflowGraph
from backend.states.base_state import TenderGraphStateBase


def _identity_node(state, config=None):
    return {}


def _build_graph(
    calls: list[str],
    bad_case_retrieval_calls: list[str] | None = None,
) -> StandardTenderWorkflowGraph:
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
        if bad_case_retrieval_calls is not None:
            bad_case_retrieval_calls.append("workflow")
        return {"polished_comments": []}

    def _update_node(state, config=None):
        calls.append("update_word")
        if state.get("generation_mode") == "agent" or state.get("comment_generation_mode") == "off":
            assert state.get("suppress_ai_comment_writeback") is True
        else:
            assert state.get("suppress_ai_comment_writeback") is False
        return {"prepared_doc_path": "D:/UploadFiles/output.docx"}

    def _comment_agent_node(state, config=None):
        calls.append("comment_agent")
        if bad_case_retrieval_calls is not None:
            bad_case_retrieval_calls.append("agent")
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


def _run_graph(
    generation_mode: str,
    *,
    comment_generation_mode: str = "on",
    bad_case_retrieval_calls: list[str] | None = None,
) -> tuple[dict, list[str]]:
    calls: list[str] = []
    result = _build_graph(calls, bad_case_retrieval_calls).compile().invoke(
        {
            "generation_mode": generation_mode,
            "comment_generation_mode": comment_generation_mode,
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
    assert "generate_comments" in calls
    assert "comment_agent" not in calls
    assert "word_operation" in calls
    assert calls[-1] == "update_word"
    assert calls.index("generate_polished_text") < calls.index("generate_comments")
    assert calls.index("generate_comments") < calls.index("update_word")
    assert result["polished_text"] == "workflow text"
    assert result["generate_polished_done"] is True


def test_agent_branch_uses_content_and_skips_generate_polished_text() -> None:
    result, calls = _run_graph("agent")

    assert "content_agent" in calls
    assert "generate_polished_text" not in calls
    assert "generate_comments" not in calls
    assert "word_operation" in calls
    assert calls[-2:] == ["update_word", "comment_agent"]
    assert result["polished_text"] == "agent text"
    assert result["generate_polished_done"] is True


def test_workflow_branch_skips_generate_comments_when_comment_generation_is_off() -> None:
    result, calls = _run_graph("workflow", comment_generation_mode="off")

    assert "generate_polished_text" in calls
    assert "content_agent" not in calls
    assert "generate_comments" not in calls
    assert "comment_agent" not in calls
    assert "word_operation" in calls
    assert calls[-1] == "update_word"
    assert result["polished_text"] == "workflow text"
    assert result["polished_comments"] == []
    assert result["generated_comment_count"] == 0


def test_agent_branch_skips_comment_agent_when_comment_generation_is_off() -> None:
    result, calls = _run_graph("agent", comment_generation_mode="off")

    assert "content_agent" in calls
    assert "generate_polished_text" not in calls
    assert "generate_comments" not in calls
    assert "comment_agent" not in calls
    assert "word_operation" in calls
    assert calls[-1] == "update_word"
    assert result["polished_text"] == "agent text"
    assert result["polished_comments"] == []
    assert result["generated_comment_count"] == 0


def test_workflow_off_branch_does_not_trigger_bad_case_retrieval() -> None:
    bad_case_retrieval_calls: list[str] = []

    _result, calls = _run_graph(
        "workflow",
        comment_generation_mode="off",
        bad_case_retrieval_calls=bad_case_retrieval_calls,
    )

    assert "generate_comments" not in calls
    assert bad_case_retrieval_calls == []


def test_agent_off_branch_does_not_trigger_bad_case_retrieval() -> None:
    bad_case_retrieval_calls: list[str] = []

    _result, calls = _run_graph(
        "agent",
        comment_generation_mode="off",
        bad_case_retrieval_calls=bad_case_retrieval_calls,
    )

    assert "comment_agent" not in calls
    assert bad_case_retrieval_calls == []


def test_agent_branch_uses_comment_agent_regardless_of_source_document_path() -> None:
    calls: list[str] = []
    result = _build_graph(calls).compile().invoke(
        {
            "generation_mode": "agent",
            "source_document_path": "D:/UploadFiles/review.docx",
            "prepared_doc_path": "D:/UploadFiles/template.docx",
            "insertion_before_text": "before",
            "insertion_after_text": "after",
        }
    )

    assert "content_agent" in calls
    assert "generate_comments" not in calls
    assert calls[-2:] == ["update_word", "comment_agent"]
    assert result["polished_text"] == "agent text"


def test_standard_graph_registers_current_comment_topology_only() -> None:
    graph_nodes = set(_build_graph([]).compile().get_graph().nodes)
    removed_nodes = {
        "".join(("get", "_comments")),
        "".join(("copy", "_comments")),
        "comments_ready",
    }

    assert graph_nodes.isdisjoint(removed_nodes)
    assert "generate_comments" in graph_nodes
    assert "comment_agent" in graph_nodes


def test_estimate_total_nodes_uses_selected_generation_branch() -> None:
    graph = _build_graph([])

    assert graph.estimate_total_nodes({"generation_mode": "workflow"}) == 8
    assert graph.estimate_total_nodes({"generation_mode": "agent"}) == 8
    assert (
        graph.estimate_total_nodes(
            {"generation_mode": "workflow", "comment_generation_mode": "off"}
        )
        == 7
    )
    assert (
        graph.estimate_total_nodes(
            {"generation_mode": "agent", "comment_generation_mode": "off"}
        )
        == 7
    )
    assert (
        graph.estimate_total_nodes(
            {
                "generation_mode": "workflow",
                "source_document_path": "D:/UploadFiles/review.docx",
            }
        )
        == 8
    )
