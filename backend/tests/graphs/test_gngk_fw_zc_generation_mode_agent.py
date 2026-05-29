from __future__ import annotations

from backend.agents.generation import set_generation_agent_runner
from backend.graphs.gngk_fw_zc_tender_graph import GngkFwZcTenderGraph
from backend.nodes.gngk_word_nodes import (
    gngk_fw_zc_delete_tender_param,
    gngk_fw_zc_get_replacements,
    gngk_fw_zc_update_word,
)


class FakeGenerationAgentRunner:
    def __init__(self, outputs: list[dict]):
        self.outputs = outputs
        self.payloads: list[dict] = []

    def invoke(self, payload: dict):
        index = len(self.payloads)
        if index >= len(self.outputs):
            raise AssertionError(f"unexpected runner invocation {index + 1}")
        self.payloads.append(payload)
        return self.outputs[index]


def _draft_output(text: str) -> dict:
    return {"structured_response": {"draft_text": text}}


def _audit_output(items: list[dict[str, str]]) -> dict:
    return {"structured_response": items}


def _stub_gngk_fw_zc_nodes(
    monkeypatch,
    calls: list[str],
    update_seen: dict[str, object],
) -> None:
    def _prepare_template(state, config=None):
        calls.append("prepare_template")
        return {"prepared_doc_path": state.get("prepared_doc_path", "fake-template.docx")}

    def _extract_tender_params(state, config=None):
        calls.append("extract_tender_params")
        return {
            "tender_params": "gngk fw zc extracted params",
            "origin_tender_params": "gngk fw zc origin params",
        }

    def _gngk_fw_zc_delete_tender_param(state, config=None):
        calls.append("gngk_fw_zc_delete_tender_param")
        return {"start_page": 21, "end_page": 24}

    def _gngk_fw_zc_get_replacements(state, config=None):
        calls.append("gngk_fw_zc_get_replacements")
        return {"replacements": [("service requirement", "gngk fw zc replacement")]}

    def _replace_content(state, config=None):
        calls.append("replace_content")
        return {"replace_content_done": True}

    def _generate_polished_text(state, config=None):
        calls.append("generate_polished_text")
        return {"polished_text": "workflow gngk fw zc text", "generate_polished_done": True}

    def _generate_comments(state, config=None):
        calls.append("generate_comments")
        return {"polished_comments": []}

    def _gngk_fw_zc_update_word(state, config=None):
        calls.append("gngk_fw_zc_update_word")
        update_seen["polished_text"] = state.get("polished_text")
        update_seen["replacements"] = state.get("replacements")
        update_seen["replace_content_done"] = state.get("replace_content_done")
        return {"prepared_doc_path": "D:/UploadFiles/gngk-fw-zc-output.docx"}

    monkeypatch.setattr(GngkFwZcTenderGraph, "NODE_PREPARE_TEMPLATE", _prepare_template)
    monkeypatch.setattr(GngkFwZcTenderGraph, "NODE_GET_COMMENTS", lambda state, config=None: {})
    monkeypatch.setattr(GngkFwZcTenderGraph, "NODE_COPY_COMMENTS", lambda state, config=None: {})
    monkeypatch.setattr(
        GngkFwZcTenderGraph, "NODE_EXTRACT_TENDER_PARAMS", _extract_tender_params
    )
    monkeypatch.setattr(
        GngkFwZcTenderGraph,
        "NODE_DELETE_TENDER_PARAM",
        _gngk_fw_zc_delete_tender_param,
    )
    monkeypatch.setattr(
        GngkFwZcTenderGraph, "NODE_GET_REPLACEMENTS", _gngk_fw_zc_get_replacements
    )
    monkeypatch.setattr(GngkFwZcTenderGraph, "NODE_REPLACE_CONTENT", _replace_content)
    monkeypatch.setattr(
        GngkFwZcTenderGraph, "NODE_GENERATE_POLISHED_TEXT", _generate_polished_text
    )
    monkeypatch.setattr(GngkFwZcTenderGraph, "NODE_GENERATE_COMMENTS", _generate_comments)
    monkeypatch.setattr(GngkFwZcTenderGraph, "NODE_UPDATE_WORD", _gngk_fw_zc_update_word)


def test_gngk_fw_zc_agent_branch_produces_polished_text_for_service_update(
    monkeypatch,
) -> None:
    assert GngkFwZcTenderGraph.NODE_DELETE_TENDER_PARAM is gngk_fw_zc_delete_tender_param
    assert GngkFwZcTenderGraph.NODE_GET_REPLACEMENTS is gngk_fw_zc_get_replacements
    assert GngkFwZcTenderGraph.NODE_UPDATE_WORD is gngk_fw_zc_update_word

    calls: list[str] = []
    update_seen: dict[str, object] = {}
    runner = FakeGenerationAgentRunner(
        [
            _draft_output("gngk fw zc agent draft"),
            _audit_output([]),
        ]
    )
    set_generation_agent_runner(runner)
    try:
        _stub_gngk_fw_zc_nodes(monkeypatch, calls, update_seen)
        result = GngkFwZcTenderGraph().compile().invoke(
            {
                "generation_mode": "agent",
                "tender_type": "gngk_fw_zc",
                "origin_tender_path": "",
                "prepared_doc_path": "D:/UploadFiles/gngk-fw-zc-template.docx",
                "project_content": "gngk fw zc project content",
                "insertion_before_text": "before",
                "insertion_after_text": "after",
            },
            config={"configurable": {"model_provider": "deepseek"}},
        )
    finally:
        set_generation_agent_runner(None)

    assert "generate_polished_text" not in calls
    assert "gngk_fw_zc_delete_tender_param" in calls
    assert "gngk_fw_zc_get_replacements" in calls
    assert "gngk_fw_zc_update_word" in calls
    assert calls[-1] == "gngk_fw_zc_update_word"
    assert result["polished_text"] == "gngk fw zc agent draft"
    assert result["generate_polished_done"] is True
    assert update_seen["polished_text"] == "gngk fw zc agent draft"
    assert update_seen["replacements"] == [
        ("service requirement", "gngk fw zc replacement")
    ]
    assert update_seen["replace_content_done"] is True
    assert calls.index("gngk_fw_zc_delete_tender_param") < calls.index(
        "gngk_fw_zc_update_word"
    )
    assert [payload["agent_phase"] for payload in runner.payloads] == [
        "generate",
        "verify",
    ]
    assert runner.payloads[0]["tender_type"] == "gngk_fw_zc"


def test_gngk_fw_zc_workflow_branch_still_uses_old_generation_node(
    monkeypatch,
) -> None:
    assert GngkFwZcTenderGraph.NODE_DELETE_TENDER_PARAM is gngk_fw_zc_delete_tender_param
    assert GngkFwZcTenderGraph.NODE_GET_REPLACEMENTS is gngk_fw_zc_get_replacements
    assert GngkFwZcTenderGraph.NODE_UPDATE_WORD is gngk_fw_zc_update_word

    calls: list[str] = []
    update_seen: dict[str, object] = {}

    def _content_should_not_run(state, config=None):
        raise AssertionError("content_agent should not run for workflow generation mode")

    _stub_gngk_fw_zc_nodes(monkeypatch, calls, update_seen)
    monkeypatch.setattr(
        GngkFwZcTenderGraph,
        "NODE_CONTENT_AGENT_GENERATE",
        _content_should_not_run,
        raising=False,
    )

    result = GngkFwZcTenderGraph().compile().invoke(
        {
            "generation_mode": "workflow",
            "tender_type": "gngk_fw_zc",
            "origin_tender_path": "",
            "prepared_doc_path": "D:/UploadFiles/gngk-fw-zc-template.docx",
            "project_content": "gngk fw zc project content",
            "insertion_before_text": "before",
            "insertion_after_text": "after",
        }
    )

    assert "generate_polished_text" in calls
    assert "gngk_fw_zc_delete_tender_param" in calls
    assert "gngk_fw_zc_get_replacements" in calls
    assert "gngk_fw_zc_update_word" in calls
    assert calls[-1] == "gngk_fw_zc_update_word"
    assert result["polished_text"] == "workflow gngk fw zc text"
    assert result["generate_polished_done"] is True
    assert update_seen["polished_text"] == "workflow gngk fw zc text"
    assert update_seen["replacements"] == [
        ("service requirement", "gngk fw zc replacement")
    ]
    assert update_seen["replace_content_done"] is True
    assert calls.index("gngk_fw_zc_delete_tender_param") < calls.index(
        "gngk_fw_zc_update_word"
    )
