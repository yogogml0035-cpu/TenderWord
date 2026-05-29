from __future__ import annotations

import json

from backend.agents.generation import set_generation_agent_runner
from backend.graphs.xjcg_tender_graph import XjcgTenderGraph


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
                backend.write("/drafts/round-0.md", current_text)
                yield {"node": "content_generate_agent", "content": current_text, "is_complete": True}
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


def _stub_xjcg_nodes(monkeypatch, calls: list[str], update_seen: dict[str, object]) -> None:
    def _prepare_template(state, config=None):
        calls.append("prepare_template")
        return {"prepared_doc_path": state.get("prepared_doc_path", "fake-template.docx")}

    def _extract_tender_params(state, config=None):
        calls.append("extract_tender_params")
        return {"tender_params": "xjcg extracted params"}

    def _delete_tender_param(state, config=None):
        calls.append("delete_tender_param")
        return {"start_page": 1, "end_page": 1}

    def _get_replacements(state, config=None):
        calls.append("xjcg_get_replacements")
        return {"replacements": {"采购需求": "xjcg replacement"}}

    def _replace_content(state, config=None):
        calls.append("replace_content")
        return {"replace_content_done": True}

    def _generate_polished_text(state, config=None):
        calls.append("generate_polished_text")
        return {"polished_text": "workflow xjcg text", "generate_polished_done": True}

    def _generate_comments(state, config=None):
        calls.append("generate_comments")
        return {"polished_comments": []}

    def _update_word(state, config=None):
        calls.append("update_word")
        update_seen["polished_text"] = state.get("polished_text")
        update_seen["replace_content_done"] = state.get("replace_content_done")
        return {"prepared_doc_path": "D:/UploadFiles/xjcg-output.docx"}

    monkeypatch.setattr(XjcgTenderGraph, "NODE_PREPARE_TEMPLATE", _prepare_template)
    monkeypatch.setattr(XjcgTenderGraph, "NODE_GET_COMMENTS", lambda state, config=None: {})
    monkeypatch.setattr(XjcgTenderGraph, "NODE_COPY_COMMENTS", lambda state, config=None: {})
    monkeypatch.setattr(
        XjcgTenderGraph, "NODE_EXTRACT_TENDER_PARAMS", _extract_tender_params
    )
    monkeypatch.setattr(
        XjcgTenderGraph, "NODE_DELETE_TENDER_PARAM", _delete_tender_param
    )
    monkeypatch.setattr(XjcgTenderGraph, "NODE_GET_REPLACEMENTS", _get_replacements)
    monkeypatch.setattr(XjcgTenderGraph, "NODE_REPLACE_CONTENT", _replace_content)
    monkeypatch.setattr(
        XjcgTenderGraph, "NODE_GENERATE_POLISHED_TEXT", _generate_polished_text
    )
    monkeypatch.setattr(XjcgTenderGraph, "NODE_GENERATE_COMMENTS", _generate_comments)
    monkeypatch.setattr(XjcgTenderGraph, "NODE_UPDATE_WORD", _update_word)


def test_xjcg_agent_branch_produces_polished_text_for_common_update(
    monkeypatch,
) -> None:
    calls: list[str] = []
    update_seen: dict[str, object] = {}
    runner = FakeGenerationAgentRunner(
        [
            _draft_output("xjcg agent draft"),
            _audit_output([]),
        ]
    )
    set_generation_agent_runner(runner)
    try:
        _stub_xjcg_nodes(monkeypatch, calls, update_seen)
        result = XjcgTenderGraph().compile().invoke(
            {
                "generation_mode": "agent",
                "tender_type": "xjcg",
                "origin_tender_path": "",
                "prepared_doc_path": "D:/UploadFiles/xjcg-template.docx",
                "project_content": "xjcg project content",
                "insertion_before_text": "before",
                "insertion_after_text": "after",
            },
            config={"configurable": {"model_provider": "deepseek"}},
        )
    finally:
        set_generation_agent_runner(None)

    assert "generate_polished_text" not in calls
    assert "update_word" in calls
    assert calls[-1] == "update_word"
    assert result["polished_text"] == "xjcg agent draft"
    assert result["generate_polished_done"] is True
    assert update_seen["polished_text"] == "xjcg agent draft"
    assert update_seen["replace_content_done"] is True
    assert len(runner.payloads) == 1
    assert runner.configs[0]["configurable"]["generation_agent_context"]["tender_type"] == "xjcg"


def test_xjcg_workflow_branch_still_uses_old_generation_node(monkeypatch) -> None:
    calls: list[str] = []
    update_seen: dict[str, object] = {}

    def _content_should_not_run(state, config=None):
        raise AssertionError("content_agent should not run for workflow generation mode")

    _stub_xjcg_nodes(monkeypatch, calls, update_seen)
    monkeypatch.setattr(
        XjcgTenderGraph,
        "NODE_CONTENT_AGENT_GENERATE",
        _content_should_not_run,
        raising=False,
    )

    result = XjcgTenderGraph().compile().invoke(
        {
            "generation_mode": "workflow",
            "tender_type": "xjcg",
            "origin_tender_path": "",
            "prepared_doc_path": "D:/UploadFiles/xjcg-template.docx",
            "project_content": "xjcg project content",
            "insertion_before_text": "before",
            "insertion_after_text": "after",
        }
    )

    assert "generate_polished_text" in calls
    assert "update_word" in calls
    assert calls[-1] == "update_word"
    assert result["polished_text"] == "workflow xjcg text"
    assert result["generate_polished_done"] is True
    assert update_seen["polished_text"] == "workflow xjcg text"
    assert update_seen["replace_content_done"] is True
