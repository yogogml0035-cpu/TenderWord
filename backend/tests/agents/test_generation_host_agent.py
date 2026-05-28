from __future__ import annotations

import json

import pytest
from deepagents import CompiledSubAgent

from backend.agents.generation import (
    GenerationAgentProtocolError,
    GenerationAgentToolCallUnsupportedError,
    HOST_AGENT_SYSTEM_PROMPT,
    build_generation_subagents,
    parse_verify_agent_output,
    run_host_agent_generation,
    set_generation_agent_runner,
)
from backend.agents.generation import content_agents as host_agent_module
from backend.agents.generation import verify_agent_graph as verify_agent_graph_module
from backend.agents.generation.model_factory import create_generation_chat_model
from backend.prompts.types import GeneratePromptInput, RenderedPrompt


@pytest.fixture(autouse=True)
def _redirect_agent_log_dirs(tmp_path, monkeypatch):
    host_dir = tmp_path / "host_log"
    verify_dir = tmp_path / "verify_log"
    host_dir.mkdir()
    verify_dir.mkdir()
    monkeypatch.setattr(
        host_agent_module,
        "get_host_agent_log_dir",
        lambda _anchor: host_dir,
    )
    monkeypatch.setattr(
        host_agent_module,
        "get_verify_agent_log_dir",
        lambda _anchor: verify_dir,
    )
    return host_dir, verify_dir


class FakeRunner:
    def __init__(self, outputs):
        self.outputs = outputs if isinstance(outputs, list) else [outputs]
        self.payloads: list[dict] = []
        self.configs: list[dict | None] = []

    def invoke(self, payload: dict, config: dict | None = None):
        index = len(self.payloads)
        if index >= len(self.outputs):
            raise AssertionError(f"unexpected runner invocation {index + 1}")
        self.payloads.append(payload)
        self.configs.append(config)
        return self.outputs[index]


class ToolCallUnsupportedRunner:
    def invoke(self, payload: dict):
        raise RuntimeError("model does not support tools or tool calls")


def _draft_output(text: str) -> dict:
    return {"structured_response": {"draft_text": text}}


def _deepagent_subagent_draft_output(text: str) -> dict:
    return {
        "draft_text": text,
        "messages": [
            {
                "content": (
                    "content_generate_agent 返回的结果显示，已生成初稿。"
                    f"请参考：{text}"
                )
            }
        ],
    }


def _deepagent_tool_message_draft_output(text: str) -> dict:
    return {
        "messages": [
            {"content": json.dumps({"draft_text": text}, ensure_ascii=False)},
            {
                "content": (
                    "content_generate_agent 返回的结果显示，已生成初稿。"
                    "请参考工具返回内容。"
                )
            },
        ],
    }


def _audit_output(items: list[dict[str, str]]) -> dict:
    return {"structured_response": items}


def _deepagent_subagent_audit_output(items: list[dict[str, str]]) -> dict:
    return {
        "findings": items,
        "messages": [{"content": "content_verify_agent 返回了结构化审核意见。"}],
    }


def _deepagent_tool_message_audit_output(items: list[dict[str, str]]) -> dict:
    return {
        "messages": [
            {"content": json.dumps(items, ensure_ascii=False)},
            {"content": "content_verify_agent 返回了结构化审核意见。"},
        ],
    }


def _revision_output(text: str) -> dict:
    return {"structured_response": {"polished_text": text}}


def _deepagent_subagent_revision_output(text: str) -> dict:
    return {
        "polished_text": text,
        "messages": [{"content": "content 已根据审核意见完成修复。"}],
    }


def test_build_generation_subagents_wraps_compiled_state_graphs() -> None:
    subagents = build_generation_subagents()

    assert isinstance(subagents.content_generate_agent, dict)
    assert isinstance(subagents.content_verify_agent, dict)
    assert subagents.content_generate_agent["name"] == "content_generate_agent"
    assert subagents.content_verify_agent["name"] == "content_verify_agent"
    assert set(subagents.content_generate_agent) == set(CompiledSubAgent.__annotations__)
    assert set(subagents.content_verify_agent) == set(CompiledSubAgent.__annotations__)
    assert hasattr(subagents.content_generate_agent["runnable"], "invoke")
    assert hasattr(subagents.content_verify_agent["runnable"], "invoke")
    assert subagents.content_generate_agent["description"] == "生成采购需求初稿。"
    assert "审核采购需求正文" in subagents.content_verify_agent["description"]


def test_content_prompts_use_chinese_natural_language() -> None:
    subagents = build_generation_subagents()

    assert "采购需求生成主智能体" in HOST_AGENT_SYSTEM_PROMPT
    assert "evidence 和 fix_hint" in HOST_AGENT_SYSTEM_PROMPT
    assert "不得新增、删除、润色" in HOST_AGENT_SYSTEM_PROMPT
    assert "Generate the first draft" not in subagents.content_generate_agent["description"]
    assert "Audit procurement requirement" not in subagents.content_verify_agent["description"]


def test_content_generate_agent_reuses_generate_prompt_and_model_config(monkeypatch) -> None:
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

    graph = build_generation_subagents().content_generate_agent["runnable"]
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


def test_content_generate_agent_reads_parent_context_from_config(monkeypatch) -> None:
    captured_prompt: dict[str, GeneratePromptInput] = {}

    def fake_render_generate_prompt(data: GeneratePromptInput) -> RenderedPrompt:
        captured_prompt["data"] = data
        return RenderedPrompt(system_prompt="system", user_prompt="user")

    async def fake_stream_llm_completion(**kwargs):
        return "draft text"

    monkeypatch.setattr(
        "backend.agents.generation.generate_agent_graph.render_generate_prompt",
        fake_render_generate_prompt,
    )
    monkeypatch.setattr(
        "backend.agents.generation.generate_agent_graph.stream_llm_completion",
        fake_stream_llm_completion,
    )

    graph = build_generation_subagents().content_generate_agent["runnable"]
    result = graph.invoke(
        {"messages": []},
        {
            "configurable": {
                "generation_agent_context": {
                    "tender_type": "gngk_hw_zc",
                    "generation_style": "param",
                    "project_info": "config project",
                    "tender_params": "config tender params",
                    "origin_tender_params": "config origin params",
                    "model_provider": "doubao",
                }
            }
        },
    )

    assert captured_prompt["data"] == GeneratePromptInput(
        tender_type="gngk_hw_zc",
        generation_style="param",
        project_info="config project",
        tender_params="config tender params",
        origin_tender_params="config origin params",
    )
    assert result["structured_response"] == {"draft_text": "draft text"}


def test_content_generate_agent_streams_snapshots_to_existing_callback(monkeypatch) -> None:
    snapshots: list[str] = []
    agent_steps: list[object] = []

    def fake_render_generate_prompt(data: GeneratePromptInput) -> RenderedPrompt:
        return RenderedPrompt(system_prompt="system", user_prompt="user")

    async def fake_stream_llm_completion(**kwargs):
        kwargs["callbacks"].on_update("部分")
        kwargs["callbacks"].on_update("部分正文")
        return "部分正文"

    monkeypatch.setattr(
        "backend.agents.generation.generate_agent_graph.render_generate_prompt",
        fake_render_generate_prompt,
    )
    monkeypatch.setattr(
        "backend.agents.generation.generate_agent_graph.stream_llm_completion",
        fake_stream_llm_completion,
    )
    monkeypatch.setattr(
        "backend.agents.generation.generate_agent_graph.AGENT_STEP_STREAM_INTERVAL_SECONDS",
        0,
    )

    graph = build_generation_subagents().content_generate_agent["runnable"]
    result = graph.invoke(
        {"messages": []},
        {
            "configurable": {
                "task_id": "task-agent-stream",
                "task_kind": "generate",
                "llm_stream_callback": snapshots.append,
                "agent_step_callback": agent_steps.append,
            }
        },
    )

    assert snapshots == ["部分", "部分正文"]
    assert [event.content for event in agent_steps] == ["部分", "部分正文"]
    assert all(event.is_complete is False for event in agent_steps)
    assert all(event.node == "content_generate_agent" for event in agent_steps)
    assert result["structured_response"] == {"draft_text": "部分正文"}

def test_content_verify_agent_repairs_missing_fields_with_retry(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    async def fake_stream_llm_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return '[{"evidence": "缺少质保期限"}]'
        return '[{"evidence": "缺少质保期限", "fix_hint": "补充质保期限，保持其它内容不变"}]'

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    graph = verify_agent_graph_module.create_verify_agent_graph()
    result = graph.invoke(
        {
            "current_text": "采购需求正文",
            "origin_tender_params": "质保期限：3年",
            "model_provider": "deepseek",
        }
    )

    expected = [{"evidence": "缺少质保期限", "fix_hint": "补充质保期限，保持其它内容不变"}]
    assert len(calls) == 2
    assert calls[1]["extra_params_override"] == {"temperature": 0.1}
    assert "严格合法的 JSON 数组" in str(calls[1]["user_prompt"])
    assert result["structured_response"] == expected
    assert json.loads(result["messages"][-1].content) == expected


def test_content_verify_agent_reads_current_text_from_config(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    async def fake_stream_llm_completion(**kwargs):
        calls.append(kwargs)
        return "[]"

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = verify_agent_graph_module.create_verify_agent_graph().invoke(
        {"messages": []},
        {
            "configurable": {
                "generation_agent_context": {
                    "current_text": "config draft text",
                    "origin_tender_params": "config origin params",
                    "model_provider": "qwen",
                }
            }
        },
    )

    assert result["structured_response"] == []
    assert calls[0]["model_provider"] == "qwen"
    assert "config origin params" in str(calls[0]["user_prompt"])
    assert "config draft text" in str(calls[0]["user_prompt"])


def test_content_verify_agent_repairs_common_json_issues_without_retry(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    async def fake_stream_llm_completion(**kwargs):
        calls.append(kwargs)
        return (
            "```json\n"
            + r'[{"evidence": "路径 C:\Temp", "fix_hint": "补充路径说明",}]'
            + "\n```"
        )

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = verify_agent_graph_module.create_verify_agent_graph().invoke(
        {"current_text": "采购需求正文", "model_provider": "deepseek"}
    )

    assert len(calls) == 1
    assert result["structured_response"] == [
        {"evidence": r"路径 C:\Temp", "fix_hint": "补充路径说明"}
    ]

def test_content_verify_agent_falls_back_to_valid_json_after_repair_failure(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    async def fake_stream_llm_completion(**kwargs):
        calls.append(kwargs)
        return "not json"

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = verify_agent_graph_module.create_verify_agent_graph().invoke(
        {"current_text": "采购需求正文", "model_provider": "deepseek"}
    )

    assert len(calls) == 2
    fallback = result["structured_response"][0]
    assert "审核智能体输出格式异常" in fallback["evidence"]
    assert "保持 current_text 原文不变" in fallback["fix_hint"]
    assert json.loads(result["messages"][-1].content) == result["structured_response"]

def test_content_verify_agent_output_is_coerced_to_json_schema() -> None:
    findings = parse_verify_agent_output(
        '[{"evidence": "missing warranty", "fix_hint": "add warranty"}]'
    )

    assert findings[0].evidence == "missing warranty"
    assert findings[0].fix_hint == "add warranty"

    single_object = parse_verify_agent_output('{"evidence": "bad"}')
    assert single_object[0].evidence == "bad"
    assert "最小必要修复" in single_object[0].fix_hint

    missing_evidence = parse_verify_agent_output('[{"fix_hint": "add"}]')
    assert "未提供 evidence" in missing_evidence[0].evidence
    assert missing_evidence[0].fix_hint == "add"

    fallback = parse_verify_agent_output("not json")
    assert "审核智能体输出格式异常" in fallback[0].evidence


def test_content_accepts_structured_json_with_non_empty_polished_text() -> None:
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


def test_content_passes_generation_context_to_deepagents_subgraphs() -> None:
    runner = FakeRunner([_draft_output("draft text"), _audit_output([])])

    result = run_host_agent_generation(
        {
            "tender_type": "gngk_hw_zc",
            "generation_style": "param",
            "project_content": "project",
            "tender_params": "params",
            "origin_tender_params": "origin",
        },
        {"configurable": {"model_provider": "qwen", "task_id": "task-agent-context"}},
        runner=runner,
    )

    assert result.polished_text == "draft text"
    generate_context = runner.configs[0]["configurable"]["generation_agent_context"]
    verify_context = runner.configs[1]["configurable"]["generation_agent_context"]
    assert generate_context == {
        "tender_type": "gngk_hw_zc",
        "generation_style": "param",
        "project_info": "project",
        "tender_params": "params",
        "origin_tender_params": "origin",
        "model_provider": "qwen",
    }
    assert verify_context == {
        **generate_context,
        "current_text": "draft text",
    }
    assert runner.configs[0]["configurable"]["task_id"] == "task-agent-context"


def test_content_prefers_subagent_state_over_host_summary_text() -> None:
    runner = FakeRunner(
        [
            _deepagent_subagent_draft_output("真正的 content_generate_agent 初稿正文"),
            _deepagent_subagent_audit_output(
                [{"evidence": "缺少验收标准", "fix_hint": "补充验收标准"}]
            ),
            _deepagent_subagent_revision_output("content 修改后的正文"),
            _deepagent_subagent_audit_output([]),
        ]
    )
    events = []

    result = run_host_agent_generation({}, runner=runner, step_callback=events.append)

    assert result.polished_text == "content 修改后的正文"
    assert events[0].node == "content_generate_agent"
    assert events[0].content == "真正的 content_generate_agent 初稿正文"
    assert events[1].node == "content_verify_agent"
    assert events[1].findings[0].evidence == "缺少验收标准"
    assert events[2].node == "content"
    assert events[2].content == "content 修改后的正文"
    assert "真正的 content_generate_agent 初稿正文" in runner.payloads[1]["current_text"]


def test_content_reads_draft_and_audit_from_deepagent_tool_messages() -> None:
    runner = FakeRunner(
        [
            _deepagent_tool_message_draft_output("ToolMessage 中的 content_generate_agent 初稿"),
            _deepagent_tool_message_audit_output(
                [{"evidence": "缺少付款方式", "fix_hint": "补充付款方式"}]
            ),
            _revision_output("content 根据意见修改后的正文"),
            _deepagent_tool_message_audit_output([]),
        ]
    )
    events = []

    result = run_host_agent_generation({}, runner=runner, step_callback=events.append)

    assert result.polished_text == "content 根据意见修改后的正文"
    assert events[0].node == "content_generate_agent"
    assert events[0].content == "ToolMessage 中的 content_generate_agent 初稿"
    assert events[1].node == "content_verify_agent"
    assert events[1].findings[0].evidence == "缺少付款方式"
    assert runner.payloads[1]["current_text"] == "ToolMessage 中的 content_generate_agent 初稿"


def test_content_rejects_plain_generate_summary_as_draft() -> None:
    runner = FakeRunner(
        [
            {
                "messages": [
                    {
                        "content": (
                            "content_generate_agent 返回的结果显示，由于没有提供项目基础信息，"
                            "无法生成具体的采购需求内容。请提供上述信息，我将重新调用 content_generate_agent。"
                        )
                    }
                ]
            }
        ]
    )

    with pytest.raises(GenerationAgentProtocolError, match="draft_text"):
        run_host_agent_generation({}, runner=runner)


def test_content_preserves_current_text_when_verify_json_fallback_requests_it() -> None:
    runner = FakeRunner(
        [
            _draft_output("draft text"),
            "not json",
            _audit_output([]),
        ]
    )
    events = []

    result = run_host_agent_generation({}, runner=runner, step_callback=events.append)

    assert result.polished_text == "draft text"
    assert [payload["agent_phase"] for payload in runner.payloads] == [
        "generate",
        "verify",
        "verify",
    ]
    assert [event.step_type for event in events] == ["draft", "audit", "revision", "audit"]
    assert events[2].node == "content"
    assert events[2].content == "draft text"


def test_content_writes_host_verify_logs_and_progress(
    monkeypatch,
    _redirect_agent_log_dirs,
) -> None:
    host_dir, verify_dir = _redirect_agent_log_dirs
    progress_messages: list[str] = []
    runner = FakeRunner(
        [
            _draft_output("draft text"),
            _audit_output([{"evidence": "missing warranty", "fix_hint": "add it"}]),
            _revision_output("final text"),
            _audit_output([]),
        ]
    )
    monkeypatch.setattr(
        host_agent_module.progress_log,
        "info",
        lambda message, *args: progress_messages.append(
            message % args if args else str(message)
        ),
    )

    result = run_host_agent_generation(
        {"task_id": "task-agent-42", "tender_type": "xjcg"},
        {"configurable": {"model_provider": "deepseek"}},
        runner=runner,
    )

    host_files = sorted(host_dir.glob("content_task-agent-42_*.txt"))
    verify_files = sorted(verify_dir.glob("verify_task-agent-42_*.txt"))

    assert result.polished_text == "final text"
    assert len(host_files) == 3
    assert any(path.name.endswith("_round0_draft.txt") for path in host_files)
    assert any(path.name.endswith("_round1_revision.txt") for path in host_files)
    assert any(path.name.endswith("_round1_final.txt") for path in host_files)
    host_content = "\n".join(path.read_text(encoding="utf-8") for path in host_files)
    assert "draft text" in host_content
    assert "final text" in host_content
    assert len(verify_files) == 2

    first_verify = json.loads(
        next(path for path in verify_files if "_round0_" in path.name).read_text(
            encoding="utf-8"
        )
    )
    assert first_verify["current_text"] == "draft text"
    assert first_verify["findings"] == [
        {"evidence": "missing warranty", "fix_hint": "add it"}
    ]
    assert any("开始智能体生成" in message for message in progress_messages)
    assert any("第 0 轮审核完成" in message for message in progress_messages)
    assert any("开始第 1 轮修复" in message for message in progress_messages)
    assert any("第 1 轮修复完成" in message for message in progress_messages)
    assert any("审核无问题，智能体生成完成" in message for message in progress_messages)


def test_content_coerces_invalid_audit_json_to_fallback_finding() -> None:
    runner = FakeRunner(
        [
            _draft_output("draft text"),
            "not json",
            _audit_output([]),
        ]
    )

    result = run_host_agent_generation({}, runner=runner)

    assert result.polished_text == "draft text"
    assert [payload["agent_phase"] for payload in runner.payloads] == [
        "generate",
        "verify",
        "verify",
    ]
    assert runner.payloads[2]["current_text"] == "draft text"


def test_content_releases_after_third_revision_with_findings() -> None:
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


def test_content_rejects_plain_text_final_output() -> None:
    runner = FakeRunner(
        [
            _draft_output("draft text"),
            _audit_output([{"evidence": "missing", "fix_hint": "fix"}]),
            "plain final text",
        ]
    )

    with pytest.raises(GenerationAgentProtocolError, match="JSON"):
        run_host_agent_generation({}, runner=runner)


def test_content_rejects_tool_call_unsupported_errors() -> None:
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
