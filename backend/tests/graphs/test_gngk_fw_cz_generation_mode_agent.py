from __future__ import annotations

from backend.agents.generation import set_generation_agent_runner
from backend.graphs.gngk_fw_cz_tender_graph import GngkFwCzTenderGraph
from backend.graphs.gngk_hw_zc_tender_graph import GngkHwZcTenderGraph
from backend.nodes.common_word_nodes import (
    delete_tender_param,
    update_word as common_update_word,
)
from backend.nodes.gngk_word_nodes import gngk_hw_zc_get_replacements


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


def _stub_gngk_fw_cz_nodes(
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
            "tender_params": "gngk fw cz extracted params",
            "origin_tender_params": "gngk fw cz origin params",
        }

    def _delete_tender_param(state, config=None):
        calls.append("delete_tender_param")
        return {"start_page": 31, "end_page": 33}

    def _gngk_hw_zc_get_replacements(state, config=None):
        calls.append("gngk_hw_zc_get_replacements")
        return {"replacements": [("inherited requirement", "gngk fw cz replacement")]}

    def _replace_content(state, config=None):
        calls.append("replace_content")
        return {"replace_content_done": True}

    def _generate_polished_text(state, config=None):
        calls.append("generate_polished_text")
        return {"polished_text": "workflow gngk fw cz text", "generate_polished_done": True}

    def _generate_comments(state, config=None):
        calls.append("generate_comments")
        return {"polished_comments": []}

    def _common_update_word(state, config=None):
        calls.append("common_update_word")
        update_seen["polished_text"] = state.get("polished_text")
        update_seen["replacements"] = state.get("replacements")
        update_seen["replace_content_done"] = state.get("replace_content_done")
        return {"prepared_doc_path": "D:/UploadFiles/gngk-fw-cz-output.docx"}

    monkeypatch.setattr(GngkFwCzTenderGraph, "NODE_PREPARE_TEMPLATE", _prepare_template)
    monkeypatch.setattr(GngkFwCzTenderGraph, "NODE_GET_COMMENTS", lambda state, config=None: {})
    monkeypatch.setattr(GngkFwCzTenderGraph, "NODE_COPY_COMMENTS", lambda state, config=None: {})
    monkeypatch.setattr(
        GngkFwCzTenderGraph, "NODE_EXTRACT_TENDER_PARAMS", _extract_tender_params
    )
    monkeypatch.setattr(
        GngkFwCzTenderGraph, "NODE_DELETE_TENDER_PARAM", _delete_tender_param
    )
    monkeypatch.setattr(
        GngkFwCzTenderGraph, "NODE_GET_REPLACEMENTS", _gngk_hw_zc_get_replacements
    )
    monkeypatch.setattr(GngkFwCzTenderGraph, "NODE_REPLACE_CONTENT", _replace_content)
    monkeypatch.setattr(
        GngkFwCzTenderGraph, "NODE_GENERATE_POLISHED_TEXT", _generate_polished_text
    )
    monkeypatch.setattr(GngkFwCzTenderGraph, "NODE_GENERATE_COMMENTS", _generate_comments)
    monkeypatch.setattr(GngkFwCzTenderGraph, "NODE_UPDATE_WORD", _common_update_word)


def test_gngk_fw_cz_agent_branch_smoke_preserves_inherited_chain(monkeypatch) -> None:
    assert issubclass(GngkFwCzTenderGraph, GngkHwZcTenderGraph)
    assert GngkFwCzTenderGraph.NODE_DELETE_TENDER_PARAM is delete_tender_param
    assert GngkFwCzTenderGraph.NODE_GET_REPLACEMENTS is gngk_hw_zc_get_replacements
    assert GngkFwCzTenderGraph.NODE_UPDATE_WORD is common_update_word

    calls: list[str] = []
    update_seen: dict[str, object] = {}
    runner = FakeGenerationAgentRunner(
        [
            _draft_output("gngk fw cz agent draft"),
            _audit_output([]),
        ]
    )
    set_generation_agent_runner(runner)
    try:
        _stub_gngk_fw_cz_nodes(monkeypatch, calls, update_seen)
        result = GngkFwCzTenderGraph().compile().invoke(
            {
                "generation_mode": "agent",
                "tender_type": "gngk_fw_cz",
                "origin_tender_path": "",
                "prepared_doc_path": "D:/UploadFiles/gngk-fw-cz-template.docx",
                "project_content": "gngk fw cz project content",
                "insertion_before_text": "before",
                "insertion_after_text": "after",
            },
            config={"configurable": {"model_provider": "deepseek"}},
        )
    finally:
        set_generation_agent_runner(None)

    assert "generate_polished_text" not in calls
    assert "delete_tender_param" in calls
    assert "gngk_hw_zc_get_replacements" in calls
    assert "common_update_word" in calls
    assert calls[-1] == "common_update_word"
    assert result["polished_text"] == "gngk fw cz agent draft"
    assert result["generate_polished_done"] is True
    assert update_seen["polished_text"] == "gngk fw cz agent draft"
    assert update_seen["replacements"] == [
        ("inherited requirement", "gngk fw cz replacement")
    ]
    assert update_seen["replace_content_done"] is True
    assert calls.index("delete_tender_param") < calls.index("common_update_word")
    assert [payload["agent_phase"] for payload in runner.payloads] == [
        "generate",
        "verify",
    ]
    assert runner.payloads[0]["tender_type"] == "gngk_fw_cz"
