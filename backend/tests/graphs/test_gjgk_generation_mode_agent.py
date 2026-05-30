from __future__ import annotations

import json

from backend.agents.generation import set_generation_agent_runner
from backend.graphs.gjgk_tender_graph import GjgkTenderGraph
from backend.nodes.common_word_nodes import replace_content
from backend.nodes.gjgk_word_nodes import (
    gjgk_delete_tender_param,
    gjgk_get_replacements,
)
from backend.nodes.gjgk_word_nodes.gjgk_update_word import gjgk_update_word


class FakeGenerationAgentRunner:
    def __init__(self, outputs: list[dict]):
        self.outputs = outputs
        self.payloads: list[dict] = []
        self.configs: list[dict] = []

    def invoke(self, payload: dict, config: dict | None = None):
        raise AssertionError("agent mode should use workspace streaming")

    def stream(self, payload: dict, config: dict | None = None, **_kwargs):
        self.payloads.append(payload)
        self.configs.append(config or {})
        backend = config["configurable"]["content_agent_backend"]
        current_text = ""
        audit_round = 1
        for output in self.outputs:
            structured = output.get("structured_response")
            if isinstance(structured, dict) and "draft_text" in structured:
                current_text = structured["draft_text"]
                backend.write("/drafts/round-1.md", current_text)
                yield {"node": "content_generate_agent", "round": 1, "content": current_text, "is_complete": True}
            elif isinstance(structured, list):
                raw_audit = json.dumps(structured, ensure_ascii=False)
                backend.write(f"/audits/round-{audit_round}.json", raw_audit)
                yield {
                    "node": "content_verify_agent",
                    "round": audit_round,
                    "content": raw_audit,
                    "is_complete": True,
                }
                if structured == []:
                    backend.write("/final/polished_text.md", current_text)
                    yield {"node": "content_agent", "content": "final written", "is_complete": True}
                audit_round += 1


def _draft_output(text: str) -> dict:
    return {"structured_response": {"draft_text": text}}


def _audit_output(items: list[dict[str, str]]) -> dict:
    return {"structured_response": items}


def _stub_gjgk_nodes(
    monkeypatch,
    calls: list[str],
    update_seen: dict[str, object],
    post_update_seen: dict[str, object],
) -> None:
    def _prepare_template(state, config=None):
        calls.append("prepare_template")
        return {"prepared_doc_path": state.get("prepared_doc_path", "fake-template.docx")}

    def _extract_tender_params(state, config=None):
        calls.append("extract_tender_params")
        return {
            "tender_params": "gjgk extracted params",
            "origin_tender_params": "gjgk origin params",
        }

    def _gjgk_delete_tender_param(state, config=None):
        calls.append("gjgk_delete_tender_param")
        return {"start_page": 31, "end_page": 33}

    def _gjgk_get_replacements(state, config=None):
        calls.append("gjgk_get_replacements")
        return {"replacements": [("international requirement", "gjgk replacement")]}

    def _replace_content(state, config=None):
        calls.append("replace_content")
        post_update_seen["polished_text"] = state.get("polished_text")
        post_update_seen["prepared_doc_path"] = state.get("prepared_doc_path")
        post_update_seen["replacements"] = state.get("replacements")
        return {"replace_content_done": True}

    def _generate_polished_text(state, config=None):
        calls.append("generate_polished_text")
        return {"polished_text": "workflow gjgk text", "generate_polished_done": True}

    def _generate_comments(state, config=None):
        calls.append("generate_comments")
        return {"polished_comments": []}

    def _gjgk_update_word(state, config=None):
        calls.append("gjgk_update_word")
        update_seen["polished_text"] = state.get("polished_text")
        update_seen["replacements"] = state.get("replacements")
        update_seen["replace_content_done"] = state.get("replace_content_done")
        return {"prepared_doc_path": "D:/UploadFiles/gjgk-output.docx"}

    monkeypatch.setattr(GjgkTenderGraph, "NODE_PREPARE_TEMPLATE", _prepare_template)
    monkeypatch.setattr(GjgkTenderGraph, "NODE_GET_COMMENTS", lambda state, config=None: {})
    monkeypatch.setattr(GjgkTenderGraph, "NODE_COPY_COMMENTS", lambda state, config=None: {})
    monkeypatch.setattr(
        GjgkTenderGraph, "NODE_EXTRACT_TENDER_PARAMS", _extract_tender_params
    )
    monkeypatch.setattr(
        GjgkTenderGraph,
        "NODE_DELETE_TENDER_PARAM",
        _gjgk_delete_tender_param,
    )
    monkeypatch.setattr(GjgkTenderGraph, "NODE_GET_REPLACEMENTS", _gjgk_get_replacements)
    monkeypatch.setattr(GjgkTenderGraph, "NODE_REPLACE_CONTENT", _replace_content)
    monkeypatch.setattr(
        GjgkTenderGraph, "NODE_GENERATE_POLISHED_TEXT", _generate_polished_text
    )
    monkeypatch.setattr(GjgkTenderGraph, "NODE_GENERATE_COMMENTS", _generate_comments)
    monkeypatch.setattr(GjgkTenderGraph, "NODE_UPDATE_WORD", _gjgk_update_word)


def test_gjgk_agent_branch_produces_polished_text_for_gjgk_update_and_post_hook(
    monkeypatch,
) -> None:
    assert GjgkTenderGraph.NODE_DELETE_TENDER_PARAM is gjgk_delete_tender_param
    assert GjgkTenderGraph.NODE_GET_REPLACEMENTS is gjgk_get_replacements
    assert GjgkTenderGraph.NODE_UPDATE_WORD is gjgk_update_word
    assert GjgkTenderGraph.NODE_REPLACE_CONTENT is replace_content
    assert GjgkTenderGraph().get_post_update_steps()[0][0] == "replace_content"

    calls: list[str] = []
    update_seen: dict[str, object] = {}
    post_update_seen: dict[str, object] = {}
    runner = FakeGenerationAgentRunner(
        [
            _draft_output("gjgk agent draft"),
            _audit_output([]),
        ]
    )
    set_generation_agent_runner(runner)
    try:
        _stub_gjgk_nodes(monkeypatch, calls, update_seen, post_update_seen)
        result = GjgkTenderGraph().compile().invoke(
            {
                "generation_mode": "agent",
                "tender_type": "gjgk",
                "origin_tender_path": "",
                "prepared_doc_path": "D:/UploadFiles/gjgk-template.docx",
                "project_content": "gjgk project content",
                "insertion_before_text": "before",
                "insertion_after_text": "after",
            },
            config={"configurable": {"model_provider": "deepseek"}},
        )
    finally:
        set_generation_agent_runner(None)

    assert "generate_polished_text" not in calls
    assert "gjgk_delete_tender_param" in calls
    assert "gjgk_get_replacements" in calls
    assert "gjgk_update_word" in calls
    assert "replace_content" in calls
    assert calls[-2:] == ["gjgk_update_word", "replace_content"]
    assert result["polished_text"] == "gjgk agent draft"
    assert result["generate_polished_done"] is True
    assert result["replace_content_done"] is True
    assert update_seen["polished_text"] == "gjgk agent draft"
    assert update_seen["replacements"] == [
        ("international requirement", "gjgk replacement")
    ]
    assert update_seen["replace_content_done"] is None
    assert post_update_seen["polished_text"] == "gjgk agent draft"
    assert post_update_seen["prepared_doc_path"] == "D:/UploadFiles/gjgk-output.docx"
    assert post_update_seen["replacements"] == [
        ("international requirement", "gjgk replacement")
    ]
    assert calls.index("gjgk_delete_tender_param") < calls.index("gjgk_update_word")
    assert calls.index("gjgk_get_replacements") < calls.index("gjgk_update_word")
    assert calls.index("gjgk_update_word") < calls.index("replace_content")
    assert len(runner.payloads) == 1
    assert runner.configs[0]["configurable"]["generation_agent_context"]["tender_type"] == "gjgk"


def test_gjgk_workflow_branch_still_uses_old_generation_node_and_post_hook(
    monkeypatch,
) -> None:
    assert GjgkTenderGraph.NODE_DELETE_TENDER_PARAM is gjgk_delete_tender_param
    assert GjgkTenderGraph.NODE_GET_REPLACEMENTS is gjgk_get_replacements
    assert GjgkTenderGraph.NODE_UPDATE_WORD is gjgk_update_word
    assert GjgkTenderGraph.NODE_REPLACE_CONTENT is replace_content

    calls: list[str] = []
    update_seen: dict[str, object] = {}
    post_update_seen: dict[str, object] = {}

    def _content_should_not_run(state, config=None):
        raise AssertionError("content_agent should not run for workflow generation mode")

    _stub_gjgk_nodes(monkeypatch, calls, update_seen, post_update_seen)
    monkeypatch.setattr(
        GjgkTenderGraph,
        "NODE_CONTENT_AGENT_GENERATE",
        _content_should_not_run,
        raising=False,
    )

    result = GjgkTenderGraph().compile().invoke(
        {
            "generation_mode": "workflow",
            "tender_type": "gjgk",
            "origin_tender_path": "",
            "prepared_doc_path": "D:/UploadFiles/gjgk-template.docx",
            "project_content": "gjgk project content",
            "insertion_before_text": "before",
            "insertion_after_text": "after",
        }
    )

    assert "generate_polished_text" in calls
    assert "gjgk_delete_tender_param" in calls
    assert "gjgk_get_replacements" in calls
    assert "gjgk_update_word" in calls
    assert "replace_content" in calls
    assert calls[-2:] == ["gjgk_update_word", "replace_content"]
    assert result["polished_text"] == "workflow gjgk text"
    assert result["generate_polished_done"] is True
    assert result["replace_content_done"] is True
    assert update_seen["polished_text"] == "workflow gjgk text"
    assert update_seen["replacements"] == [
        ("international requirement", "gjgk replacement")
    ]
    assert update_seen["replace_content_done"] is None
    assert post_update_seen["polished_text"] == "workflow gjgk text"
    assert post_update_seen["prepared_doc_path"] == "D:/UploadFiles/gjgk-output.docx"
    assert post_update_seen["replacements"] == [
        ("international requirement", "gjgk replacement")
    ]
    assert calls.index("gjgk_delete_tender_param") < calls.index("gjgk_update_word")
    assert calls.index("gjgk_get_replacements") < calls.index("gjgk_update_word")
    assert calls.index("gjgk_update_word") < calls.index("replace_content")
