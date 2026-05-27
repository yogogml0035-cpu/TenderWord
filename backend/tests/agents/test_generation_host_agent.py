from __future__ import annotations

import pytest
from deepagents import CompiledSubAgent

from backend.agents.generation import (
    GenerationAgentProtocolError,
    GenerationAgentToolCallUnsupportedError,
    build_generation_subagents,
    parse_verify_agent_output,
    run_host_agent_generation,
    set_generation_agent_runner,
)
from backend.agents.generation import host_agent as host_agent_module
from backend.agents.generation.model_factory import create_generation_chat_model
from backend.prompts.types import GeneratePromptInput, RenderedPrompt


class FakeRunner:
    def __init__(self, outputs):
        self.outputs = outputs if isinstance(outputs, list) else [outputs]
        self.payloads: list[dict] = []

    def invoke(self, payload: dict):
        index = len(self.payloads)
        if index >= len(self.outputs):
            raise AssertionError(f"unexpected runner invocation {index + 1}")
        self.payloads.append(payload)
        return self.outputs[index]


class ToolCallUnsupportedRunner:
    def invoke(self, payload: dict):
        raise RuntimeError("model does not support tools or tool calls")


def _draft_output(text: str) -> dict:
    return {"structured_response": {"draft_text": text}}


def _audit_output(items: list[dict[str, str]]) -> dict:
    return {"structured_response": items}


def _revision_output(text: str) -> dict:
    return {"structured_response": {"polished_text": text}}


def test_build_generation_subagents_wraps_compiled_state_graphs() -> None:
    subagents = build_generation_subagents()

    assert isinstance(subagents.generate_agent, dict)
    assert isinstance(subagents.verify_agent, dict)
    assert subagents.generate_agent["name"] == "generate_agent"
    assert subagents.verify_agent["name"] == "verify_agent"
    assert set(subagents.generate_agent) == set(CompiledSubAgent.__annotations__)
    assert set(subagents.verify_agent) == set(CompiledSubAgent.__annotations__)
    assert hasattr(subagents.generate_agent["runnable"], "invoke")
    assert hasattr(subagents.verify_agent["runnable"], "invoke")


def test_generate_agent_reuses_generate_prompt_and_model_config(monkeypatch) -> None:
    captured_prompt: dict[str, GeneratePromptInput] = {}
    captured_stream: dict[str, object] = {}

    def fake_render_generate_prompt(data: GeneratePromptInput) -> RenderedPrompt:
        captured_prompt["data"] = data
        return RenderedPrompt(system_prompt="system", user_prompt="user")

    async def fake_stream_llm_completion(**kwargs):
        captured_stream.update(kwargs)
        return "draft text"

    monkeypatch.setattr(
        "backend.agents.generation.generate_agent_graph.render_generate_prompt",
        fake_render_generate_prompt,
    )
    monkeypatch.setattr(
        "backend.agents.generation.generate_agent_graph.stream_llm_completion",
        fake_stream_llm_completion,
    )

    graph = build_generation_subagents().generate_agent["runnable"]
    result = graph.invoke(
        {
            "tender_type": "gngk",
            "generation_style": "param",
            "project_info": "project info",
            "tender_params": "template params",
            "origin_tender_params": "new params",
            "model_provider": "qwen",
            "messages": [],
        }
    )

    assert captured_prompt["data"] == GeneratePromptInput(
        tender_type="gngk",
        generation_style="param",
        project_info="project info",
        tender_params="template params",
        origin_tender_params="new params",
    )
    assert captured_stream["model_provider"] == "qwen"
    assert captured_stream["system_prompt"] == "system"
    assert captured_stream["user_prompt"] == "user"
    assert result["structured_response"] == {"draft_text": "draft text"}


def test_verify_agent_output_must_be_json_array_with_evidence_and_fix_hint() -> None:
    findings = parse_verify_agent_output(
        '[{"evidence": "missing warranty", "fix_hint": "add warranty"}]'
    )

    assert findings[0].evidence == "missing warranty"
    assert findings[0].fix_hint == "add warranty"

    with pytest.raises(GenerationAgentProtocolError, match="JSON 数组"):
        parse_verify_agent_output('{"evidence": "bad"}')
    with pytest.raises(GenerationAgentProtocolError, match="evidence"):
        parse_verify_agent_output('[{"fix_hint": "add"}]')


def test_host_agent_accepts_structured_json_with_non_empty_polished_text() -> None:
    runner = FakeRunner(
        [
            _draft_output("draft text"),
            _audit_output([{"evidence": "missing warranty", "fix_hint": "add it"}]),
            _revision_output("final text"),
            _audit_output([]),
        ]
    )
    events = []

    result = run_host_agent_generation(
        {
            "tender_type": "xjcg",
            "generation_style": "template",
            "project_content": "project",
            "tender_params": "params",
            "origin_tender_params": "origin",
        },
        {"configurable": {"model_provider": "deepseek"}},
        runner=runner,
        step_callback=events.append,
    )

    assert result.polished_text == "final text"
    assert result.audit_findings == []
    assert result.revision_rounds == 1
    assert [payload["agent_phase"] for payload in runner.payloads] == [
        "generate",
        "verify",
        "revise",
        "verify",
    ]
    assert runner.payloads[0]["project_info"] == "project"
    assert runner.payloads[1]["current_text"] == "draft text"
    assert runner.payloads[2]["audit_findings"] == [
        {"evidence": "missing warranty", "fix_hint": "add it"}
    ]
    assert runner.payloads[3]["current_text"] == "final text"
    assert [event.step_type for event in events] == [
        "draft",
        "audit",
        "revision",
        "audit",
    ]
    assert [event.round for event in events] == [0, 0, 1, 1]
    assert events[2].content == "final text"
    assert events[2].is_complete is True


def test_host_agent_rejects_invalid_audit_json() -> None:
    runner = FakeRunner([_draft_output("draft text"), "not json"])

    with pytest.raises(GenerationAgentProtocolError, match="JSON"):
        run_host_agent_generation({}, runner=runner)


def test_host_agent_releases_after_third_revision_with_findings() -> None:
    runner = FakeRunner(
        [
            _draft_output("draft"),
            _audit_output([{"evidence": "e1", "fix_hint": "f1"}]),
            _revision_output("revision 1"),
            _audit_output([{"evidence": "e2", "fix_hint": "f2"}]),
            _revision_output("revision 2"),
            _audit_output([{"evidence": "e3", "fix_hint": "f3"}]),
            _revision_output("revision 3"),
        ]
    )
    events = []

    result = run_host_agent_generation(
        {},
        runner=runner,
        step_callback=events.append,
    )

    assert result.polished_text == "revision 3"
    assert result.revision_rounds == 3
    assert result.audit_findings[0].evidence == "e3"
    assert [payload["agent_phase"] for payload in runner.payloads] == [
        "generate",
        "verify",
        "revise",
        "verify",
        "revise",
        "verify",
        "revise",
    ]
    assert [event.step_type for event in events] == [
        "draft",
        "audit",
        "revision",
        "audit",
        "revision",
        "audit",
        "revision",
    ]
    assert events[-1].round == 3


def test_host_agent_rejects_plain_text_final_output() -> None:
    runner = FakeRunner(
        [
            _draft_output("draft text"),
            _audit_output([{"evidence": "missing", "fix_hint": "fix"}]),
            "plain final text",
        ]
    )

    with pytest.raises(GenerationAgentProtocolError, match="JSON"):
        run_host_agent_generation({}, runner=runner)


def test_host_agent_rejects_tool_call_unsupported_errors() -> None:
    with pytest.raises(GenerationAgentToolCallUnsupportedError, match="不支持工具调用"):
        run_host_agent_generation({}, runner=ToolCallUnsupportedRunner())


def test_fake_runner_injection_point(monkeypatch) -> None:
    set_generation_agent_runner(
        FakeRunner([_draft_output("injected text"), _audit_output([])])
    )
    monkeypatch.setattr(
        host_agent_module,
        "create_host_agent_runner",
        lambda _model_provider: pytest.fail("real runner should not be created"),
    )
    try:
        result = run_host_agent_generation({})
    finally:
        set_generation_agent_runner(None)

    assert result.polished_text == "injected text"


def test_model_factory_reuses_existing_llm_config(monkeypatch) -> None:
    class FakeSettings:
        def get_llm_config(self, provider: str):
            assert provider == "qwen"
            return {
                "base_url": "https://example.test/v1",
                "api_key": "test-key",
                "model": "qwen-test",
            }

    monkeypatch.setattr(
        "backend.agents.generation.model_factory.ensure_llm_env",
        lambda _provider: None,
    )
    monkeypatch.setattr(
        "backend.agents.generation.model_factory.settings",
        FakeSettings(),
    )
    monkeypatch.setattr(
        "backend.agents.generation.model_factory.get_llm_timeout_seconds",
        lambda: 37,
    )

    model = create_generation_chat_model("qwen")

    assert model.model_name == "qwen-test"
    assert model.openai_api_base == "https://example.test/v1"
    assert model.request_timeout == 37
    assert model.max_retries == 0
    assert model.max_tokens == 32768
    assert model.temperature == 0.1
    assert model.extra_body == {"enable_thinking": False}
