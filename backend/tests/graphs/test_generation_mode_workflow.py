from __future__ import annotations

from backend.graphs.base_graph import StandardTenderWorkflowGraph
from backend.states.base_state import TenderGraphStateBase


def test_workflow_generation_mode_executes_generate_polished_text_not_content() -> None:
    calls: list[str] = []

    def _identity_node(state, config=None):
        return {}

    def _extract_node(state, config=None):
        calls.append("extract_tender_params")
        return {"tender_params": "extracted params"}

    def _generate_node(state, config=None):
        calls.append("generate_polished_text")
        return {"polished_text": "workflow text", "generate_polished_done": True}

    def _content_node(state, config=None):
        calls.append("content")
        return {"polished_text": "agent text", "generate_polished_done": True}

    def _update_node(state, config=None):
        calls.append("update_word")
        return {"prepared_doc_path": "D:/UploadFiles/output.docx"}

    class _WorkflowGraph(StandardTenderWorkflowGraph):
        STATE_CLS = TenderGraphStateBase
        NODE_PREPARE_TEMPLATE = _identity_node
        NODE_GET_COMMENTS = _identity_node
        NODE_COPY_COMMENTS = _identity_node
        NODE_EXTRACT_TENDER_PARAMS = _extract_node
        NODE_DELETE_TENDER_PARAM = _identity_node
        NODE_GET_REPLACEMENTS = _identity_node
        NODE_REPLACE_CONTENT = _identity_node
        NODE_GENERATE_POLISHED_TEXT = _generate_node
        NODE_HOST_AGENT_GENERATE = _content_node
        NODE_GENERATE_COMMENTS = _identity_node
        NODE_UPDATE_WORD = _update_node

    result = _WorkflowGraph().compile().invoke(
        {
            "generation_mode": "workflow",
            "origin_tender_path": "",
            "prepared_doc_path": "D:/UploadFiles/template.docx",
            "insertion_before_text": "before",
            "insertion_after_text": "after",
        }
    )

    assert "generate_polished_text" in calls
    assert "content" not in calls
    assert calls[-1] == "update_word"
    assert result["polished_text"] == "workflow text"
    assert result["generate_polished_done"] is True
    assert result["prepared_doc_path"] == "D:/UploadFiles/output.docx"
