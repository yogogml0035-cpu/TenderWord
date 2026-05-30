from __future__ import annotations

import importlib

from backend.agents.generation import ContentAgentFinalOutput


def test_content_generate_returns_standard_polished_text_contract(monkeypatch) -> None:
    captured: dict[str, object] = {}
    node_module = importlib.import_module(
        "backend.nodes.common_word_nodes.content_agent_generate"
    )

    def fake_run_content_agent_generation(state, config=None, *, step_callback=None):
        captured["state"] = state
        captured["config"] = config
        captured["step_callback"] = step_callback
        return ContentAgentFinalOutput(polished_text="agent final text")

    monkeypatch.setattr(
        node_module,
        "run_content_agent_generation",
        fake_run_content_agent_generation,
    )

    state = {"generation_mode": "agent", "tender_type": "xjcg"}
    config = {"configurable": {"model_provider": "deepseek"}}

    result = node_module.content_agent_generate(state, config)

    assert captured["state"] is state
    assert captured["config"] is config
    assert captured["step_callback"] is None
    assert result["polished_text"] == "agent final text"
    assert result["generate_polished_done"] is True
