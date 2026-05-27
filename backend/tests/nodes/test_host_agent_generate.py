from __future__ import annotations

import importlib

from backend.agents.generation import HostAgentFinalOutput


def test_host_agent_generate_returns_standard_polished_text_contract(monkeypatch) -> None:
    captured: dict[str, object] = {}
    node_module = importlib.import_module(
        "backend.nodes.common_word_nodes.host_agent_generate"
    )

    def fake_run_host_agent_generation(state, config=None):
        captured["state"] = state
        captured["config"] = config
        return HostAgentFinalOutput(polished_text="agent final text")

    monkeypatch.setattr(
        node_module,
        "run_host_agent_generation",
        fake_run_host_agent_generation,
    )

    state = {"generation_mode": "agent", "tender_type": "xjcg"}
    config = {"configurable": {"model_provider": "deepseek"}}

    result = node_module.host_agent_generate(state, config)

    assert captured == {"state": state, "config": config}
    assert result["polished_text"] == "agent final text"
    assert result["generate_polished_done"] is True
