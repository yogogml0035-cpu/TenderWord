from __future__ import annotations

import json

from backend.agents.generation import set_generation_agent_runner
from backend.graphs.gngk_hw_zc_tender_graph import GngkHwZcTenderGraph
from backend.nodes.common_word_nodes import update_word as common_update_word
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


def _stub_gngk_hw_zc_nodes(
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
            "tender_params": "gngk hw zc extracted params",
            "origin_tender_params": "gngk hw zc origin params",
        }

    def _delete_tender_param(state, config=None):
        calls.append("delete_tender_param")
        return {"start_page": 1, "end_page": 1}

    def _gngk_hw_zc_get_replacements(state, config=None):
        calls.append("gngk_hw_zc_get_replacements")
        return {"replacements": [("requirement", "gngk hw zc replacement")]}

    def _replace_content(state, config=None):
        calls.append("replace_content")
        return {"replace_content_done": True}

    def _generate_polished_text(state, config=None):
        calls.append("generate_polished_text")
        return {"polished_text": "workflow gngk hw zc text", "generate_polished_done": True}

    def _generate_comments(state, config=None):
        calls.append("generate_comments")
        return {"polished_comments": []}

    def _common_update_word(state, config=None):
        calls.append("common_update_word")
        update_seen["polished_text"] = state.get("polished_text")
        update_seen["replacements"] = state.get("replacements")
        update_seen["replace_content_done"] = state.get("replace_content_done")
        return {"prepared_doc_path": "D:/UploadFiles/gngk-hw-zc-output.docx"}

    monkeypatch.setattr(GngkHwZcTenderGraph, "NODE_PREPARE_TEMPLATE", _prepare_template)
    monkeypatch.setattr(GngkHwZcTenderGraph, "NODE_GET_COMMENTS", lambda state, config=None: {})
    monkeypatch.setattr(GngkHwZcTenderGraph, "NODE_COPY_COMMENTS", lambda state, config=None: {})
    monkeypatch.setattr(
        GngkHwZcTenderGraph, "NODE_EXTRACT_TENDER_PARAMS", _extract_tender_params
    )
    monkeypatch.setattr(
        GngkHwZcTenderGraph, "NODE_DELETE_TENDER_PARAM", _delete_tender_param
    )
    monkeypatch.setattr(
        GngkHwZcTenderGraph, "NODE_GET_REPLACEMENTS", _gngk_hw_zc_get_replacements
    )
    monkeypatch.setattr(GngkHwZcTenderGraph, "NODE_REPLACE_CONTENT", _replace_content)
    monkeypatch.setattr(
        GngkHwZcTenderGraph, "NODE_GENERATE_POLISHED_TEXT", _generate_polished_text
    )
    monkeypatch.setattr(GngkHwZcTenderGraph, "NODE_GENERATE_COMMENTS", _generate_comments)
    monkeypatch.setattr(GngkHwZcTenderGraph, "NODE_UPDATE_WORD", _common_update_word)


def test_gngk_hw_zc_agent_branch_produces_polished_text_for_common_update(
    monkeypatch,
) -> None:
    assert GngkHwZcTenderGraph.NODE_GET_REPLACEMENTS is gngk_hw_zc_get_replacements
    assert GngkHwZcTenderGraph.NODE_UPDATE_WORD is common_update_word

    calls: list[str] = []
    update_seen: dict[str, object] = {}
    runner = FakeGenerationAgentRunner(
        [
            _draft_output("gngk hw zc agent draft"),
            _audit_output([]),
        ]
    )
    set_generation_agent_runner(runner)
    try:
        _stub_gngk_hw_zc_nodes(monkeypatch, calls, update_seen)
        result = GngkHwZcTenderGraph().compile().invoke(
            {
                "generation_mode": "agent",
                "tender_type": "gngk_hw_zc",
                "origin_tender_path": "",
                "prepared_doc_path": "D:/UploadFiles/gngk-hw-zc-template.docx",
                "project_content": "gngk hw zc project content",
                "insertion_before_text": "before",
                "insertion_after_text": "after",
            },
            config={"configurable": {"model_provider": "deepseek"}},
        )
    finally:
        set_generation_agent_runner(None)

    assert "generate_polished_text" not in calls
    assert "gngk_hw_zc_get_replacements" in calls
    assert "common_update_word" in calls
    assert calls[-1] == "common_update_word"
    assert result["polished_text"] == "gngk hw zc agent draft"
    assert result["generate_polished_done"] is True
    assert update_seen["polished_text"] == "gngk hw zc agent draft"
    assert update_seen["replacements"] == [("requirement", "gngk hw zc replacement")]
    assert update_seen["replace_content_done"] is True
    assert len(runner.payloads) == 1
    assert runner.configs[0]["configurable"]["generation_agent_context"]["tender_type"] == "gngk_hw_zc"


def test_gngk_hw_zc_workflow_branch_still_uses_old_generation_node(
    monkeypatch,
) -> None:
    assert GngkHwZcTenderGraph.NODE_GET_REPLACEMENTS is gngk_hw_zc_get_replacements
    assert GngkHwZcTenderGraph.NODE_UPDATE_WORD is common_update_word

    calls: list[str] = []
    update_seen: dict[str, object] = {}

    def _content_should_not_run(state, config=None):
        raise AssertionError("content_agent should not run for workflow generation mode")

    _stub_gngk_hw_zc_nodes(monkeypatch, calls, update_seen)
    monkeypatch.setattr(
        GngkHwZcTenderGraph,
        "NODE_CONTENT_AGENT_GENERATE",
        _content_should_not_run,
        raising=False,
    )

    result = GngkHwZcTenderGraph().compile().invoke(
        {
            "generation_mode": "workflow",
            "tender_type": "gngk_hw_zc",
            "origin_tender_path": "",
            "prepared_doc_path": "D:/UploadFiles/gngk-hw-zc-template.docx",
            "project_content": "gngk hw zc project content",
            "insertion_before_text": "before",
            "insertion_after_text": "after",
        }
    )

    assert "generate_polished_text" in calls
    assert "gngk_hw_zc_get_replacements" in calls
    assert "common_update_word" in calls
    assert calls[-1] == "common_update_word"
    assert result["polished_text"] == "workflow gngk hw zc text"
    assert result["generate_polished_done"] is True
    assert update_seen["polished_text"] == "workflow gngk hw zc text"
    assert update_seen["replacements"] == [("requirement", "gngk hw zc replacement")]
    assert update_seen["replace_content_done"] is True
