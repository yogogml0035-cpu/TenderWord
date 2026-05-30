from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from deepagents import CompiledSubAgent

from backend.agents.generation import (
    CONTENT_AGENT_SYSTEM_PROMPT,
    GenerationAgentProtocolError,
    GenerationAgentToolCallUnsupportedError,
    build_generation_subagents,
    parse_verify_agent_output,
    run_content_agent_generation,
    set_generation_agent_runner,
)
from backend.agents.generation import content_agents as content_agent_module
from backend.agents.generation import revise_agent_graph as revise_agent_graph_module
from backend.agents.generation import verify_agent_graph as verify_agent_graph_module
from backend.agents.generation.model_factory import create_generation_chat_model
from backend.agents.generation.workspace import (
    FINAL_POLISHED_TEXT_PATH,
    GENERATION_CONTEXT_PATH,
    read_backend_text,
)
from backend.prompts.types import GeneratePromptInput, RenderedPrompt


@pytest.fixture(autouse=True)
def _redirect_content_agent_workspace(tmp_path, monkeypatch) -> Path:
    workspace_root = tmp_path / "content_agent_workspace"
    def fake_create_workspace_dir(task_id: str) -> Path:
        workspace_dir = workspace_root / f"{task_id}_20260529-153000"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        return workspace_dir

    monkeypatch.setattr(
        "backend.agents.generation.workspace.CONTENT_AGENT_WORKSPACE_ROOT",
        workspace_root,
    )
    monkeypatch.setattr(
        content_agent_module,
        "create_workspace_dir",
        fake_create_workspace_dir,
    )
    return workspace_root


class FakeRunner:
    def __init__(self, outputs):
        self.outputs = outputs if isinstance(outputs, list) else [outputs]
        self.payloads: list[dict] = []
        self.configs: list[dict | None] = []

    def invoke(self, payload: dict, config: dict | None = None):
        raise AssertionError("workspace runner should stream, not invoke")

    def stream(self, payload: dict, config: dict | None = None, **_kwargs):
        self.payloads.append(payload)
        self.configs.append(config)
        backend = config["configurable"]["content_agent_backend"]
        for output in self.outputs:
            if "main" in output:
                yield {
                    "node": "content_agent",
                    "content": output["main"],
                    "is_complete": bool(output.get("is_complete", False)),
                }
            elif "draft" in output:
                backend.write("/drafts/round-1.md", output["draft"])
                yield {
                    "node": "content_generate_agent",
                    "round": 1,
                    "content": output["draft"],
                    "is_complete": True,
                }
            elif "audit" in output:
                round_index = output.get("round", 1)
                content = json.dumps(output["audit"], ensure_ascii=False)
                backend.write(f"/audits/round-{round_index}.json", content)
                yield {
                    "node": "content_verify_agent",
                    "round": round_index,
                    "content": content,
                    "is_complete": True,
                }
            elif "revision" in output:
                round_index = output.get("round", 1)
                backend.write(f"/revisions/round-{round_index}.md", output["revision"])
                yield {
                    "node": "content_revise_agent",
                    "round": round_index,
                    "content": output["revision"],
                    "is_complete": True,
                }
            elif "final" in output:
                backend.write(FINAL_POLISHED_TEXT_PATH, output["final"])
                if output.get("raw_physical") is not None:
                    final_path = Path(
                        config["configurable"]["content_agent_workspace_dir"]
                    ) / "final" / "polished_text.md"
                    final_path.parent.mkdir(parents=True, exist_ok=True)
                    final_path.write_text(output["raw_physical"], encoding="utf-8")
                yield {
                    "node": "content_agent",
                    "content": "final written",
                    "is_complete": True,
                }


class InvokeOnlyFakeRunner:
    def __init__(self, callback):
        self.payloads: list[dict] = []
        self.configs: list[dict | None] = []
        self.callback = callback

    def invoke(self, payload: dict, config: dict | None = None):
        self.payloads.append(payload)
        self.configs.append(config)
        self.callback(config["configurable"]["content_agent_backend"])
        return {"messages": []}


class ToolCallUnsupportedRunner:
    def invoke(self, payload: dict, config: dict | None = None):
        raise RuntimeError("model does not support tools or tool calls")


def _read_generation_context_from_runner(runner: FakeRunner) -> dict:
    backend = runner.configs[0]["configurable"]["content_agent_backend"]
    markdown = read_backend_text(backend, GENERATION_CONTEXT_PATH)
    match = re.search(r"```json\s*(.*?)\s*```", markdown, re.DOTALL)
    assert match is not None
    return json.loads(match.group(1))


def test_build_generation_subagents_wraps_compiled_state_graphs() -> None:
    subagents = build_generation_subagents()

    assert isinstance(subagents.content_generate_agent, dict)
    assert isinstance(subagents.content_verify_agent, dict)
    assert isinstance(subagents.content_revise_agent, dict)
    assert subagents.content_generate_agent["name"] == "content_generate_agent"
    assert subagents.content_verify_agent["name"] == "content_verify_agent"
    assert subagents.content_revise_agent["name"] == "content_revise_agent"
    assert set(subagents.content_generate_agent) == set(CompiledSubAgent.__annotations__)
    assert set(subagents.content_verify_agent) == set(CompiledSubAgent.__annotations__)
    assert set(subagents.content_revise_agent) == set(CompiledSubAgent.__annotations__)
    assert hasattr(subagents.content_generate_agent["runnable"], "invoke")
    assert hasattr(subagents.content_verify_agent["runnable"], "invoke")
    assert hasattr(subagents.content_revise_agent["runnable"], "invoke")
    assert "/inputs/generation_context.md" in subagents.content_generate_agent["description"]
    assert "/audits/round-N.json" in subagents.content_verify_agent["description"]
    assert "/revisions/round-N.md" in subagents.content_revise_agent["description"]


def test_content_prompts_use_workspace_file_protocol() -> None:
    subagents = build_generation_subagents()

    assert "采购需求生成主智能体" in CONTENT_AGENT_SYSTEM_PROMPT
    assert "TodoList" in CONTENT_AGENT_SYSTEM_PROMPT
    assert "content_generate_agent" in CONTENT_AGENT_SYSTEM_PROMPT
    assert "content_verify_agent" in CONTENT_AGENT_SYSTEM_PROMPT
    assert "content_revise_agent" in CONTENT_AGENT_SYSTEM_PROMPT
    assert "/final/polished_text.md" in CONTENT_AGENT_SYSTEM_PROMPT
    assert "只有 content_agent 可以写" in CONTENT_AGENT_SYSTEM_PROMPT
    assert "最多 3 轮" in CONTENT_AGENT_SYSTEM_PROMPT
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
            "template_reference_text": "new params",
            "model_provider": "qwen",
            "messages": [],
        }
    )

    assert captured_prompt["data"] == GeneratePromptInput(
        tender_type="gngk",
        generation_style="param",
        project_info="project info",
        tender_params="template params",
        template_reference_text="new params",
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
                    "template_reference_text": "config origin params",
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
        template_reference_text="config origin params",
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
            "template_reference_text": "参考内容旧质保期限：1年",
            "tender_params": "质保期限：3年",
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
                    "project_info": "config project info",
                    "template_reference_text": "config origin params",
                    "tender_params": "config tender params",
                    "model_provider": "qwen",
                }
            }
        },
    )

    assert result["structured_response"] == []
    assert calls[0]["model_provider"] == "qwen"
    user_prompt = str(calls[0]["user_prompt"])
    system_prompt = str(calls[0]["system_prompt"])
    assert "【项目基础信息】\nconfig project info" in user_prompt
    assert "【参考内容（只作模板，不作事实真源）】\nconfig origin params" in user_prompt
    assert "【技术参数（原材料，事实真源）】\nconfig tender params" in user_prompt
    assert "【待审核正文】\nconfig draft text" in user_prompt
    assert "参考内容】只作章节/编号/表格/语气模板" in user_prompt
    assert "★、▲ 指标" in user_prompt
    assert "多个包件/标段/采购包/独立设备组" in user_prompt
    assert "只能输出严格合法的 JSON 数组本身" in system_prompt
    assert "Few-shots" in system_prompt
    assert "禁止输出“第 1 轮审核”" in system_prompt
    assert "不要用技术参数中的设备标题覆盖项目基础信息" in system_prompt


def test_content_verify_agent_flags_placeholder_current_text_without_llm(monkeypatch) -> None:
    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        lambda **_kwargs: pytest.fail("placeholder current_text should not call LLM"),
    )

    result = verify_agent_graph_module.create_verify_agent_graph().invoke(
        {"current_text": "<完整采购需求正文>", "model_provider": "deepseek"}
    )

    finding = result["structured_response"][0]
    assert "占位符" in finding["evidence"]
    assert "不是实际采购需求正文" in finding["evidence"]
    assert "不得输出尖括号占位符" in finding["fix_hint"]
    assert json.loads(result["messages"][-1].content) == result["structured_response"]


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


def test_content_verify_agent_streams_raw_json_snapshots(monkeypatch) -> None:
    agent_steps: list[object] = []

    async def fake_stream_llm_completion(**kwargs):
        kwargs["callbacks"].on_update('[{"evidence":"缺')
        kwargs["callbacks"].on_update('[{"evidence":"缺少质保期限","fix_hint":"补充质保期限"}]')
        return '[{"evidence":"缺少质保期限","fix_hint":"补充质保期限"}]'

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = verify_agent_graph_module.create_verify_agent_graph().invoke(
        {
            "current_text": "采购需求正文",
            "model_provider": "deepseek",
        },
        {
            "configurable": {
                "task_id": "task-agent-verify-stream",
                "agent_step_callback": agent_steps.append,
            }
        },
    )

    assert result["structured_response"] == [
        {"evidence": "缺少质保期限", "fix_hint": "补充质保期限"}
    ]
    assert [event.content for event in agent_steps] == [
        '[{"evidence":"缺',
        '[{"evidence":"缺少质保期限","fix_hint":"补充质保期限"}]',
    ]
    assert all(event.node == "content_verify_agent" for event in agent_steps)
    assert all(event.step_type == "stream" for event in agent_steps)
    assert all(event.is_complete is False for event in agent_steps)


def test_content_revise_agent_streams_revision_snapshots(monkeypatch) -> None:
    agent_steps: list[object] = []

    async def fake_stream_llm_completion(**kwargs):
        kwargs["callbacks"].on_update("修订中")
        kwargs["callbacks"].on_update("修订后的正文")
        return "修订后的正文"

    monkeypatch.setattr(
        revise_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = revise_agent_graph_module.create_revise_agent_graph().invoke(
        {
            "current_text": "原正文",
            "audit_findings": [{"evidence": "缺少字段", "fix_hint": "补充字段"}],
            "revision_round": 1,
            "model_provider": "deepseek",
        },
        {
            "configurable": {
                "task_id": "task-agent-revise-stream",
                "agent_step_callback": agent_steps.append,
            }
        },
    )

    assert result["structured_response"] == {"revision_path": "/revisions/round-1.md"}
    assert result["polished_text"] == "修订后的正文"
    assert [event.content for event in agent_steps] == [
        "修订中",
        "修订后的正文",
    ]
    assert all(event.node == "content_revise_agent" for event in agent_steps)
    assert all(event.step_type == "stream" for event in agent_steps)
    assert all(event.is_complete is False for event in agent_steps)


def test_content_revise_agent_skips_empty_audit_without_rewriting(monkeypatch) -> None:
    agent_steps: list[object] = []

    async def fake_stream_llm_completion(**_kwargs):
        pytest.fail("empty audit should not call revision LLM")

    monkeypatch.setattr(
        revise_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = revise_agent_graph_module.create_revise_agent_graph().invoke(
        {
            "current_text": "原正文不应被重新输出",
            "audit_findings": [],
            "revision_round": 1,
            "model_provider": "deepseek",
        },
        {
            "configurable": {
                "task_id": "task-agent-revise-empty-audit",
                "agent_step_callback": agent_steps.append,
            }
        },
    )

    assert result["structured_response"] == {
        "status": "no_revision",
        "message": "无需修订",
    }
    assert result["no_revision"] is True
    assert "polished_text" not in result
    assert "revision_path" not in result
    assert [event.content for event in agent_steps] == ["无需修订"]
    assert all(event.node == "content_revise_agent" for event in agent_steps)
    assert all(event.is_complete is True for event in agent_steps)


def test_content_runner_creates_workspace_and_reads_final_file(
    _redirect_content_agent_workspace,
) -> None:
    runner = FakeRunner(
        [
            {"main": "计划：生成、审核、验收"},
            {"draft": "draft text"},
            {"audit": [{"evidence": "missing warranty", "fix_hint": "add it"}], "round": 1},
            {"revision": "revised text", "round": 1},
            {"audit": [], "round": 2},
            {"final": "final text"},
        ]
    )
    events = []

    result = run_content_agent_generation(
        {
            "tender_type": "xjcg",
            "generation_style": "template",
            "project_content": "project",
            "tender_params": "params",
            "template_reference_text": "origin",
        },
        {"configurable": {"model_provider": "deepseek", "task_id": "task-agent-42"}},
        runner=runner,
        step_callback=events.append,
    )

    workspace_dir = result.workspace_dir
    assert workspace_dir == _redirect_content_agent_workspace / "task-agent-42_20260529-153000"
    assert (workspace_dir / "inputs" / "generation_context.md").exists()
    assert (workspace_dir / "drafts" / "round-1.md").read_text(encoding="utf-8") == "draft text"
    assert (workspace_dir / "audits" / "round-1.json").exists()
    assert (workspace_dir / "revisions" / "round-1.md").read_text(encoding="utf-8") == "revised text"
    assert (workspace_dir / "final" / "polished_text.md").read_text(encoding="utf-8") == "final text"
    assert result.polished_text == "final text"
    assert result.audit_findings == []
    assert result.revision_rounds == 1
    assert [event.node for event in events] == [
        "content_generate_agent",
        "content_verify_agent",
        "content_revise_agent",
        "content_verify_agent",
        "content_agent",
    ]
    assert [event.round for event in events] == [1, 1, 1, 2, 2]
    assert [event.step_type for event in events] == [
        "stream",
        "stream",
        "stream",
        "stream",
        "final",
    ]
    assert [event.content_agent["phase"] for event in events] == [
        "draft",
        "audit",
        "revision",
        "audit",
        "final",
    ]
    assert [event.content_agent["summary"] for event in events] == [
        "初稿生成完成，约 10 字。",
        "第 1 轮审核发现 1 个问题。",
        "第 1 轮修复完成，已处理 1 个问题。",
        "第 2 轮修复复核通过。",
        "最终完成，修复 1 轮，最终正文约 10 字。",
    ]
    assert events[2].content_agent["rounds"][2]["fix_count"] == 1
    assert events[-1].content_agent["final_result"]["content"] == "final text"


def test_content_runner_writes_complete_generation_context() -> None:
    runner = FakeRunner([{"draft": "draft text"}, {"audit": [], "round": 1}, {"final": "draft text"}])

    result = run_content_agent_generation(
        {
            "tender_type": "gngk_hw_zc",
            "generation_style": "param",
            "project_content": "project",
            "tender_params": {"name": "params"},
            "template_reference_text": "origin",
        },
        {"configurable": {"model_provider": "qwen", "task_id": "task-agent-context"}},
        runner=runner,
    )

    context = _read_generation_context_from_runner(runner)
    assert context == {
        "task_id": "task-agent-context",
        "tender_type": "gngk_hw_zc",
        "generation_style": "param",
        "project_info": "project",
        "template_reference_text": "origin",
        "tender_params": {"name": "params"},
        "model_provider": "qwen",
    }
    assert result.polished_text == "draft text"
    assert result.workspace_dir.name == "task-agent-context_20260529-153000"
    assert runner.payloads[0]["messages"][0]["content"].startswith("请按文件协议自主完成采购需求生成")
    assert runner.configs[0]["configurable"]["generation_agent_context"] == context


def test_content_runner_fails_when_final_file_missing() -> None:
    runner = FakeRunner([{"draft": "draft text"}, {"audit": [], "round": 1}])

    with pytest.raises(GenerationAgentProtocolError, match="/final/polished_text.md"):
        run_content_agent_generation({}, runner=runner)


def test_content_runner_fails_when_final_file_empty() -> None:
    runner = FakeRunner([{"final": "non-empty", "raw_physical": "   "}])

    with pytest.raises(GenerationAgentProtocolError, match="为空"):
        run_content_agent_generation({}, runner=runner)


def test_content_runner_fails_when_final_file_is_placeholder() -> None:
    runner = FakeRunner([{"final": "<完整采购需求正文>"}])

    with pytest.raises(GenerationAgentProtocolError, match="占位符"):
        run_content_agent_generation({}, runner=runner)


def test_content_runner_rejects_round_four_artifacts() -> None:
    runner = FakeRunner(
        [
            {"draft": "draft"},
            {"audit": [{"evidence": "e4", "fix_hint": "f4"}], "round": 4},
            {"final": "final"},
        ]
    )

    with pytest.raises(GenerationAgentProtocolError, match="超出协议轮次"):
        run_content_agent_generation({}, runner=runner)


def test_content_runner_accepts_invoke_only_test_runner() -> None:
    def write_final(backend):
        backend.write(FINAL_POLISHED_TEXT_PATH, "invoke final")

    runner = InvokeOnlyFakeRunner(write_final)

    result = run_content_agent_generation({}, runner=runner)

    assert result.polished_text == "invoke final"
    assert len(runner.payloads) == 1


def test_content_rejects_tool_call_unsupported_errors() -> None:
    with pytest.raises(GenerationAgentToolCallUnsupportedError, match="不支持工具调用"):
        run_content_agent_generation({}, runner=ToolCallUnsupportedRunner())


def test_fake_runner_injection_point(monkeypatch) -> None:
    set_generation_agent_runner(FakeRunner([{"final": "injected text"}]))
    monkeypatch.setattr(
        content_agent_module,
        "create_content_agent_runner",
        lambda _model_provider, backend=None: pytest.fail("real runner should not be created"),
    )
    try:
        result = run_content_agent_generation({})
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
