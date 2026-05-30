from __future__ import annotations

import json

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
            "template_reference_text": "gngk fw cz origin params",
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

    def _comment_agent(state, config=None):
        calls.append("comment_agent")
        return {"comment_writeback_result": {"generated": 0, "added": 0}}

    monkeypatch.setattr(GngkFwCzTenderGraph, "NODE_PREPARE_TEMPLATE", _prepare_template)
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
    monkeypatch.setattr(GngkFwCzTenderGraph, "NODE_COMMENT_AGENT", _comment_agent)


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
    assert "generate_comments" not in calls
    assert "delete_tender_param" in calls
    assert "gngk_hw_zc_get_replacements" in calls
    assert "common_update_word" in calls
    assert calls[-2:] == ["common_update_word", "comment_agent"]
    assert result["polished_text"] == "gngk fw cz agent draft"
    assert result["generate_polished_done"] is True
    assert update_seen["polished_text"] == "gngk fw cz agent draft"
    assert update_seen["replacements"] == [
        ("inherited requirement", "gngk fw cz replacement")
    ]
    assert update_seen["replace_content_done"] is True
    assert calls.index("delete_tender_param") < calls.index("common_update_word")
    assert len(runner.payloads) == 1
    assert runner.configs[0]["configurable"]["generation_agent_context"]["tender_type"] == "gngk_fw_cz"
