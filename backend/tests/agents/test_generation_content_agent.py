from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from deepagents import CompiledSubAgent

from backend.agents.generation import (
    CONTENT_AGENT_SYSTEM_PROMPT,
    GenerationAgentProtocolError,
    build_generation_subagents,
    parse_verify_agent_output,
    run_content_agent_generation,
    set_generation_agent_runner,
)
from backend.agents.generation import content_agents as content_agent_module
from backend.agents.generation import revise_agent_graph as revise_agent_graph_module
from backend.agents.generation import verify_agent_graph as verify_agent_graph_module
from backend.agents.generation.types import AgentStepPayload, AuditFinding
from backend.agents.generation.workspace import (
    FINAL_POLISHED_TEXT_PATH,
    audit_path,
    create_workspace_backend,
    create_workspace_dir,
    ensure_round_within_protocol,
    infer_next_audit_round,
    infer_next_revision_round,
    validate_round_protocol,
    write_generation_context,
)
from backend.agents.log_naming import build_agent_log_stem


@pytest.fixture(autouse=True)
def _redirect_content_agent_workspace(tmp_path, monkeypatch) -> Path:
    workspace_root = tmp_path / "content_agent_workspace"

    def fake_create_workspace_dir(
        task_id: str,
        *,
        project_number: str | None = None,
        project_name: str | None = None,
        now: float | None = None,
    ) -> Path:
        stem = build_agent_log_stem(
            task_id,
            project_number=project_number,
            project_name=project_name,
            fallback="content-agent",
        )
        workspace_dir = workspace_root / f"{stem}_20260529-153000"
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
            if "draft" in output:
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
                    final_path = (
                        Path(config["configurable"]["content_agent_workspace_dir"])
                        / "final"
                        / "polished_text.md"
                    )
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


_TABLE_PARAM_FIXTURE = (
    "技术参数：\n"
    "| 序号 | 参数 |\n"
    "| --- | --- |\n"
    "[[TABLE:TP1_1]]\n"
)


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
    assert "/inputs/generation_context.md" in subagents.content_generate_agent["description"]
    assert "/audits/round-N.json" in subagents.content_verify_agent["description"]
    assert "/revisions/round-N.md" in subagents.content_revise_agent["description"]


def test_content_prompts_use_workspace_file_protocol() -> None:
    subagents = build_generation_subagents()

    assert "TodoList" in CONTENT_AGENT_SYSTEM_PROMPT
    assert "content_generate_agent" in CONTENT_AGENT_SYSTEM_PROMPT
    assert "content_verify_agent" in CONTENT_AGENT_SYSTEM_PROMPT
    assert "content_revise_agent" in CONTENT_AGENT_SYSTEM_PROMPT
    assert "/final/polished_text.md" in CONTENT_AGENT_SYSTEM_PROMPT
    assert "投标阶段打分内容必须删除" in CONTENT_AGENT_SYSTEM_PROMPT
    assert "Generate the first draft" not in subagents.content_generate_agent["description"]
    assert "Audit procurement requirement" not in subagents.content_verify_agent["description"]


def test_content_verify_agent_repairs_missing_fields_with_retry(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    async def fake_stream_llm_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return '[{"evidence":"缺少质保期限"}]'
        return '[{"evidence":"缺少质保期限","fix_hint":"补充质保期限，保持其它内容不变"}]'

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    graph = verify_agent_graph_module.create_verify_agent_graph()
    result = graph.invoke(
        {
            "current_text": "采购需求正文",
            "template_reference_text": "参考内容旧质保期限：3年",
            "tender_params": "质保期限：5年",
            "model_provider": "deepseek",
        }
    )

    expected = [
        {"evidence": "缺少质保期限", "fix_hint": "补充质保期限，保持其它内容不变"}
    ]
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
                    "generation_style": "param",
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
    assert "【生成风格】" in user_prompt
    assert "config project info" in user_prompt
    assert "config origin params" in user_prompt
    assert "config tender params" in user_prompt
    assert "config draft text" in user_prompt
    assert "结构化表占位符硬契约" in user_prompt
    assert "严格合法的 JSON 数组" in system_prompt
    assert "Few-shots" in system_prompt


def test_content_verify_agent_drops_noop_findings(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    async def fake_stream_llm_completion(**kwargs):
        calls.append(kwargs)
        return '[{"evidence":"两者一致，无问题","fix_hint":"无需修改"}]'

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = verify_agent_graph_module.create_verify_agent_graph().invoke(
        {"current_text": "采购需求正文", "model_provider": "deepseek"}
    )

    assert len(calls) == 1
    assert result["structured_response"] == []
    assert json.loads(result["messages"][-1].content) == []


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


def test_content_verify_agent_output_is_coerced_to_json_schema() -> None:
    findings = parse_verify_agent_output(
        '[{"evidence": "missing warranty", "fix_hint": "add warranty"}]'
    )

    assert findings[0].evidence == "missing warranty"
    assert findings[0].fix_hint == "add warranty"

    single_object = parse_verify_agent_output('{"evidence":"bad"}')
    assert single_object[0].evidence == "bad"
    assert "最小必要修复" in single_object[0].fix_hint

    missing_evidence = parse_verify_agent_output('[{"fix_hint":"add"}]')
    assert "未提供 evidence" in missing_evidence[0].evidence
    assert missing_evidence[0].fix_hint == "add"

    fallback = parse_verify_agent_output("not json")
    assert "审核智能体输出格式异常" in fallback[0].evidence


def test_content_verify_agent_streams_raw_json_snapshots(monkeypatch) -> None:
    agent_steps: list[object] = []

    async def fake_stream_llm_completion(**kwargs):
        kwargs["callbacks"].on_update('[{"evidence":"partial')
        kwargs["callbacks"].on_update(
            '[{"evidence":"缺少质保期限","fix_hint":"补充质保期限"}]'
        )
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
        '[{"evidence":"partial',
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
    assert [event.content for event in agent_steps] == ["修订中", "修订后的正文"]
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
            "project_number": "XJ-001",
            "project_name": "测试 项目",
            "project_content": "project",
            "tender_params": "params",
            "template_reference_text": "origin",
        },
        {"configurable": {"model_provider": "deepseek", "task_id": "task-agent-42"}},
        runner=runner,
        step_callback=events.append,
    )

    workspace_dir = result.workspace_dir
    assert workspace_dir == (
        _redirect_content_agent_workspace
        / "task-agent-42_XJ-001_测试_项目_20260529-153000"
    )
    assert (workspace_dir / "drafts" / "round-1.md").read_text(encoding="utf-8") == "draft text"
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
    assert events[-1].step_type == "final"
    assert events[-1].content_agent["final_result"]["content"] == "final text"


def test_content_agent_tracker_preserves_completed_audit_after_late_empty_update() -> None:
    tracker = content_agent_module.ContentAgentProcessTracker()
    finding = {"evidence": "缺少 ★ 指标", "fix_hint": "补充 ★ 符号"}

    tracker.build_step(
        AgentStepPayload(
            step_type="stream",
            round=1,
            node="content_verify_agent",
            content=json.dumps([finding], ensure_ascii=False),
            is_complete=True,
        )
    )
    tracker.build_step(
        AgentStepPayload(
            step_type="stream",
            round=1,
            node="content_revise_agent",
            content="已补充 ★ 符号",
            is_complete=True,
        )
    )
    late_update = tracker.build_step(
        AgentStepPayload(
            step_type="stream",
            round=1,
            node="content_verify_agent",
            content="",
            is_complete=False,
        )
    )

    assert late_update is not None
    audit_round = late_update.rounds[0]
    revision_round = late_update.rounds[1]
    assert audit_round.phase == "audit"
    assert audit_round.issue_count == 1
    assert audit_round.findings[0].evidence == "缺少 ★ 指标"
    assert revision_round.phase == "revision"
    assert revision_round.fix_count == 1
    assert revision_round.findings[0].evidence == "缺少 ★ 指标"


def test_content_runner_fails_when_final_file_missing() -> None:
    runner = FakeRunner([{"draft": "draft text"}, {"audit": [], "round": 1}])

    with pytest.raises(GenerationAgentProtocolError, match="/final/polished_text.md"):
        run_content_agent_generation({}, runner=runner)


def test_content_runner_fails_when_final_file_empty() -> None:
    runner = FakeRunner([{"final": "non-empty", "raw_physical": "   "}])

    with pytest.raises(GenerationAgentProtocolError, match="为空"):
        run_content_agent_generation({}, runner=runner)


def test_content_runner_no_longer_restores_table_placeholder_in_final_text(
    _redirect_content_agent_workspace,
) -> None:
    """`[[TABLE:id]]` 是内部写回入口，最终正文不再自动补回占位符；
    写回层根据结构化表模型决定恢复或丢弃，缺失占位符不视为错误。"""
    runner = FakeRunner(
        [
            {"draft": "draft text"},
            {"audit": [], "round": 1},
            {"final": "技术参数：\n| 序号 | 参数 |\n| 1 | A |\n"},
        ]
    )

    result = run_content_agent_generation(
        {
            "generation_style": "param",
            "project_content": "project",
            "tender_params": _TABLE_PARAM_FIXTURE,
            "template_reference_text": "origin",
        },
        {
            "configurable": {
                "model_provider": "deepseek",
                "task_id": "task-final-no-restore-table",
            }
        },
        runner=runner,
    )

    # 占位符不再被自动补回；final 正文保持模型输出，缺失占位符不报错。
    assert "[[TABLE:TP1_1]]" not in result.polished_text
    assert "技术参数" in result.polished_text
    assert result.audit_findings == []


def test_content_runner_rechecks_final_text_when_last_audit_has_findings(monkeypatch) -> None:
    runner = FakeRunner(
        [
            {"draft": "draft"},
            {"audit": [{"evidence": "old issue", "fix_hint": "fix old issue"}], "round": 1},
            {"revision": "revision 1", "round": 1},
            {"audit": [{"evidence": "still old", "fix_hint": "replace old"}], "round": 2},
            {"revision": "revision 2", "round": 2},
            {"audit": [{"evidence": "still old", "fix_hint": "replace old"}], "round": 3},
            {"revision": "fixed final", "round": 3},
            {"final": "fixed final"},
        ]
    )
    calls = []

    def fake_verify_final_text_findings(*, final_text, generation_context, model_provider):
        calls.append((final_text, generation_context, model_provider))
        return []

    monkeypatch.setattr(
        content_agent_module,
        "verify_final_text_findings",
        fake_verify_final_text_findings,
    )

    result = run_content_agent_generation(
        {
            "generation_style": "param",
            "project_content": "project",
            "tender_params": "params",
            "template_reference_text": "origin",
        },
        {"configurable": {"model_provider": "deepseek", "task_id": "task-final-clean"}},
        runner=runner,
    )

    assert result.polished_text == "fixed final"
    assert result.audit_findings == []
    assert calls[0][0] == "fixed final"
    assert calls[0][1]["tender_params"] == "params"
    assert calls[0][2] == "deepseek"


def test_content_runner_returns_warning_findings_when_final_recheck_still_has_findings(
    monkeypatch,
) -> None:
    runner = FakeRunner(
        [
            {"draft": "draft"},
            {"audit": [{"evidence": "extra", "fix_hint": "remove extra"}], "round": 3},
            {"revision": "bad final", "round": 3},
            {"final": "bad final"},
        ]
    )
    warnings: list[str] = []

    monkeypatch.setattr(
        content_agent_module,
        "verify_final_text_findings",
        lambda **_kwargs: [
            AuditFinding(evidence="正文仍有多余内容", fix_hint="删除多余内容")
        ],
    )
    monkeypatch.setattr(
        content_agent_module.progress_log,
        "warning",
        lambda message, *args: warnings.append(str(message) % args if args else str(message)),
    )

    result = run_content_agent_generation(
        {
            "generation_style": "param",
            "project_content": "project",
            "tender_params": "params",
            "template_reference_text": "origin",
        },
        {"configurable": {"model_provider": "deepseek", "task_id": "task-final-bad"}},
        runner=runner,
    )

    assert result.polished_text == "bad final"
    assert result.audit_findings == [
        AuditFinding(evidence="正文仍有多余内容", fix_hint="删除多余内容")
    ]
    assert any("最终复核未通过" in message for message in warnings)


def test_content_runner_accepts_invoke_only_test_runner() -> None:
    def write_final(backend):
        backend.write(FINAL_POLISHED_TEXT_PATH, "invoke final")

    runner = InvokeOnlyFakeRunner(write_final)

    result = run_content_agent_generation({}, runner=runner)

    assert result.polished_text == "invoke final"
    assert len(runner.payloads) == 1


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


def test_content_verify_agent_no_longer_flags_missing_table_placeholder(
    monkeypatch,
) -> None:
    """`[[TABLE:id]]` 占位符是内部写回入口，缺失它不再产生 finding；
    审核环节不再要求模型补回或原样保留占位符。"""
    async def fake_stream_llm_completion(**_kwargs):
        return "[]"

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = verify_agent_graph_module.create_verify_agent_graph().invoke(
        {
            "current_text": (
                "技术参数：\n"
                "| 序号 | 参数 |\n"
                "| --- | --- |\n"
                "| 1 | A |\n"
            ),
            "tender_params": _TABLE_PARAM_FIXTURE,
            "model_provider": "deepseek",
        }
    )

    findings = result["structured_response"]
    assert findings == []


def test_content_verify_agent_keeps_empty_when_all_table_placeholders_present(
    monkeypatch,
) -> None:
    async def fake_stream_llm_completion(**_kwargs):
        return "[]"

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = verify_agent_graph_module.create_verify_agent_graph().invoke(
        {
            "current_text": "技术参数：\n[[TABLE:TP1_1]]\n",
            "tender_params": _TABLE_PARAM_FIXTURE,
            "model_provider": "deepseek",
        }
    )

    assert result["structured_response"] == []


def test_content_verify_agent_no_longer_reports_missing_table_placeholder(monkeypatch) -> None:
    """缺失占位符不再单独报 finding；多个占位符缺失也不产生任何占位符相关 finding。"""
    async def fake_stream_llm_completion(**_kwargs):
        return "[]"

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = verify_agent_graph_module.create_verify_agent_graph().invoke(
        {
            "current_text": "技术参数：\n[[TABLE:TP1_1]]\n",
            "tender_params": "技术参数：\n[[TABLE:TP1_1]]\n[[TABLE:TP1_2]]\n",
            "model_provider": "deepseek",
        }
    )

    findings = result["structured_response"]
    assert findings == []


def test_content_verify_agent_does_not_append_placeholder_finding_to_llm_findings(
    monkeypatch,
) -> None:
    """占位符缺失不再追加 finding；LLM 自身的审核结果原样保留，不被占位符检查覆盖。"""
    async def fake_stream_llm_completion(**_kwargs):
        return '[{"evidence":"缺少 ★ 指标","fix_hint":"补充 ★ 符号"}]'

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = verify_agent_graph_module.create_verify_agent_graph().invoke(
        {
            "current_text": (
                "技术参数：\n"
                "| 序号 | 参数 |\n"
                "| --- | --- |\n"
                "| 1 | A |\n"
            ),
            "tender_params": _TABLE_PARAM_FIXTURE,
            "model_provider": "deepseek",
        }
    )

    findings = result["structured_response"]
    assert len(findings) == 1
    assert findings[0]["evidence"] == "缺少 ★ 指标"
    # 不再追加占位符相关 finding。
    assert not any("[[TABLE:" in f["evidence"] for f in findings)


def test_content_verify_agent_prompt_states_table_placeholder_is_internal_entry(
    monkeypatch,
) -> None:
    """审核提示词把 `[[TABLE:id]]` 描述为内部写回入口，且明确不要求补回占位符。"""
    calls: list[dict[str, object]] = []

    async def fake_stream_llm_completion(**kwargs):
        calls.append(kwargs)
        return "[]"

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    verify_agent_graph_module.create_verify_agent_graph().invoke(
        {
            "current_text": "正文\n[[TABLE:TP1_1]]",
            "tender_params": "[[TABLE:TP1_1]]",
            "model_provider": "deepseek",
        }
    )

    user_prompt = str(calls[0]["user_prompt"])
    assert "结构化表占位符硬契约" in user_prompt
    assert "内部写回入口" in user_prompt
    assert "不应作为可见行" in user_prompt
    assert "不要**为缺失" in user_prompt


def test_verify_final_text_findings_no_longer_reports_missing_placeholder(
    monkeypatch,
) -> None:
    """最终复核不再叠加占位符缺失检查；即使 LLM 返回 [] 且正文缺占位符，也不报 finding。"""
    async def fake_stream_llm_completion(**_kwargs):
        return "[]"

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    findings = verify_agent_graph_module.verify_final_text_findings(
        final_text=(
            "技术参数：\n"
            "| 序号 | 参数 |\n"
            "| --- | --- |\n"
            "| 1 | A |\n"
        ),
        generation_context={
            "generation_style": "template",
            "tender_params": _TABLE_PARAM_FIXTURE,
        },
        model_provider="deepseek",
    )

    assert findings == []


def test_content_runner_final_recheck_allows_missing_placeholder_when_section_removed(
    monkeypatch,
    _redirect_content_agent_workspace,
) -> None:
    runner = FakeRunner(
        [
            {"draft": "draft"},
            {"audit": [{"evidence": "多余内容", "fix_hint": "删除多余内容"}], "round": 3},
            {"revision": "附件三：保洁耗材\n序号 / 名称 / 费用\n正文 多余内容\n", "round": 3},
            {"final": "附件三：保洁耗材\n序号 / 名称 / 费用\n正文 多余内容\n"},
        ]
    )

    monkeypatch.setattr(
        content_agent_module,
        "verify_final_text_findings",
        lambda **_kwargs: [
            AuditFinding(evidence="正文仍有多余内容", fix_hint="删除多余内容")
        ],
    )

    result = run_content_agent_generation(
        {
            "generation_style": "param",
            "project_content": "project",
            "tender_params": _TABLE_PARAM_FIXTURE,
            "template_reference_text": "origin",
        },
        {
            "configurable": {
                "model_provider": "deepseek",
                "task_id": "task-final-union",
            }
        },
        runner=runner,
    )

    assert result.polished_text.startswith("附件三：保洁耗材")
    assert result.audit_findings == [
        AuditFinding(evidence="正文仍有多余内容", fix_hint="删除多余内容")
    ]


def test_infer_next_audit_round_raises_when_all_rounds_present(tmp_path) -> None:
    workspace_dir = create_workspace_dir("task-infer-audit")
    backend = create_workspace_backend(workspace_dir)
    for round_index in range(1, 4):
        backend.write(audit_path(round_index), "[]")

    # 第 3 轮审核产物已存在，第 4 轮写入路径不得产生。
    with pytest.raises(GenerationAgentProtocolError, match="协议轮次已用尽"):
        infer_next_audit_round(backend)


def test_infer_next_revision_round_raises_when_all_rounds_present(tmp_path) -> None:
    workspace_dir = create_workspace_dir("task-infer-revision")
    backend = create_workspace_backend(workspace_dir)
    for round_index in range(1, 4):
        backend.write(f"/revisions/round-{round_index}.md", f"revision {round_index}")

    with pytest.raises(GenerationAgentProtocolError, match="协议轮次已用尽"):
        infer_next_revision_round(backend)


def test_ensure_round_within_protocol_accepts_valid_rounds() -> None:
    assert ensure_round_within_protocol(1) == 1
    assert ensure_round_within_protocol(3) == 3


def test_ensure_round_within_protocol_rejects_out_of_range_rounds() -> None:
    with pytest.raises(GenerationAgentProtocolError, match="协议轮次已用尽"):
        ensure_round_within_protocol(4, artifact_type="审核")
    with pytest.raises(GenerationAgentProtocolError, match="协议轮次已用尽"):
        ensure_round_within_protocol(0)
    with pytest.raises(GenerationAgentProtocolError, match="协议轮次已用尽"):
        ensure_round_within_protocol(-1)


def test_verify_agent_graph_raises_and_skips_round4_when_three_rounds_exist(
    monkeypatch,
    _redirect_content_agent_workspace,
) -> None:
    workspace_dir = create_workspace_dir("task-verify-round4")
    backend = create_workspace_backend(workspace_dir)
    write_generation_context(
        backend,
        {
            "generation_style": "template",
            "current_text": "采购需求正文",
            "model_provider": "deepseek",
        },
    )
    for round_index in range(1, 4):
        backend.write(audit_path(round_index), "[]")
        backend.write(f"/revisions/round-{round_index}.md", f"revision {round_index}")

    async def fake_stream_llm_completion(**_kwargs):
        pytest.fail("协议轮次用尽时不应再调用审核 LLM")

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    with pytest.raises(GenerationAgentProtocolError, match="协议轮次已用尽"):
        verify_agent_graph_module.create_verify_agent_graph().invoke(
            {
                "current_text": "采购需求正文",
                "model_provider": "deepseek",
            },
            {
                "configurable": {
                    "content_agent_backend": backend,
                }
            },
        )

    # 第 4 轮审核产物不得被写出。
    assert backend.read(audit_path(4)).file_data is None


def test_revise_agent_graph_raises_and_skips_round4_when_three_rounds_exist(
    monkeypatch,
    _redirect_content_agent_workspace,
) -> None:
    workspace_dir = create_workspace_dir("task-revise-round4")
    backend = create_workspace_backend(workspace_dir)
    for round_index in range(1, 4):
        backend.write(audit_path(round_index), "[]")
        backend.write(f"/revisions/round-{round_index}.md", f"revision {round_index}")

    async def fake_stream_llm_completion(**_kwargs):
        pytest.fail("协议轮次用尽时不应再调用修订 LLM")

    monkeypatch.setattr(
        revise_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    with pytest.raises(GenerationAgentProtocolError, match="协议轮次已用尽"):
        revise_agent_graph_module.create_revise_agent_graph().invoke(
            {
                "current_text": "采购需求正文",
                "audit_findings": [{"evidence": "问题", "fix_hint": "修复"}],
                "revision_round": 4,
                "model_provider": "deepseek",
            },
            {
                "configurable": {
                    "content_agent_backend": backend,
                    "generation_agent_context": {
                        "current_text": "采购需求正文",
                        "audit_findings": [{"evidence": "问题", "fix_hint": "修复"}],
                        "revision_round": 4,
                        "model_provider": "deepseek",
                    },
                }
            },
        )

    # 第 4 轮修订产物不得被写出。
    assert backend.read("/revisions/round-4.md").file_data is None


def test_content_runner_delivers_final_after_three_rounds_with_remaining_findings(
    monkeypatch,
    _redirect_content_agent_workspace,
) -> None:
    runner = FakeRunner(
        [
            {"draft": "draft"},
            {"audit": [{"evidence": "issue 1", "fix_hint": "fix 1"}], "round": 1},
            {"revision": "revision 1", "round": 1},
            {"audit": [{"evidence": "issue 2", "fix_hint": "fix 2"}], "round": 2},
            {"revision": "revision 2", "round": 2},
            {"audit": [{"evidence": "issue 3", "fix_hint": "fix 3"}], "round": 3},
            {"revision": "final revised", "round": 3},
            {"final": "final revised"},
        ]
    )

    monkeypatch.setattr(
        content_agent_module,
        "verify_final_text_findings",
        lambda **_kwargs: [AuditFinding(evidence="issue 3", fix_hint="fix 3")],
    )

    result = run_content_agent_generation(
        {
            "generation_style": "param",
            "project_content": "project",
            "tender_params": "params",
            "template_reference_text": "origin",
        },
        {"configurable": {"model_provider": "deepseek", "task_id": "task-three-rounds"}},
        runner=runner,
    )

    # 第 3 轮后固定停止返修，交付最终正文。
    assert result.polished_text == "final revised"
    assert result.revision_rounds == 3
    # 剩余问题暴露在最终 payload，便于卡片最终完成区逐条展示 warning。
    assert result.audit_findings == [
        AuditFinding(evidence="issue 3", fix_hint="fix 3"),
    ]
    workspace_dir = result.workspace_dir
    # 第 4 轮产物不得出现。
    assert not (workspace_dir / "audits" / "round-4.json").exists()
    assert not (workspace_dir / "revisions" / "round-4.md").exists()


def test_content_runner_tolerates_historical_round4_artifact(
    monkeypatch,
    _redirect_content_agent_workspace,
) -> None:
    class Round4LeavingRunner:
        def __init__(self):
            self.payloads: list[dict] = []
            self.configs: list[dict | None] = []

        def invoke(self, payload, config=None):  # type: ignore[no-untyped-def]
            raise AssertionError("workspace runner should stream, not invoke")

        def stream(self, payload, config=None, **_kwargs):  # type: ignore[no-untyped-def]
            self.payloads.append(payload)
            self.configs.append(config)
            backend = config["configurable"]["content_agent_backend"]
            # 正常写完初稿并通过第 1 轮审核，写 final。
            backend.write("/drafts/round-1.md", "draft")
            yield {"node": "content_generate_agent", "round": 1, "content": "draft", "is_complete": True}
            backend.write(audit_path(1), "[]")
            yield {"node": "content_verify_agent", "round": 1, "content": "[]", "is_complete": True}
            backend.write(FINAL_POLISHED_TEXT_PATH, "final text")
            yield {"node": "content_agent", "content": "final written", "is_complete": True}
            # 模拟历史/异常 runner 在写 final 后仍留下越界 round-4 产物。
            backend.write("/audits/round-4.json", "[]")

    runner = Round4LeavingRunner()

    result = run_content_agent_generation(
        {
            "generation_style": "param",
            "project_content": "project",
            "tender_params": "params",
            "template_reference_text": "origin",
        },
        {"configurable": {"model_provider": "deepseek", "task_id": "task-tolerate-round4"}},
        runner=runner,
    )

    # 越界产物存在但不作为 fatal，也不参与交付/统计。
    workspace_dir = result.workspace_dir
    assert (workspace_dir / "audits" / "round-4.json").exists()
    assert result.polished_text == "final text"
    assert result.audit_findings == []
    # revision_rounds 只统计协议内合法轮次，不含 round-4。
    assert result.revision_rounds == 0


def test_content_runner_falls_back_to_final_when_runner_requests_round4(
    monkeypatch,
    _redirect_content_agent_workspace,
) -> None:
    class Round4RequestingRunner:
        def __init__(self):
            self.payloads: list[dict] = []
            self.configs: list[dict | None] = []

        def invoke(self, payload, config=None):  # type: ignore[no-untyped-def]
            raise AssertionError("workspace runner should stream, not invoke")

        def stream(self, payload, config=None, **_kwargs):  # type: ignore[no-untyped-def]
            self.payloads.append(payload)
            self.configs.append(config)
            backend = config["configurable"]["content_agent_backend"]
            # 正常走完 3 轮并写 final。
            backend.write("/drafts/round-1.md", "draft")
            yield {"node": "content_generate_agent", "round": 1, "content": "draft", "is_complete": True}
            backend.write(audit_path(1), "[]")
            backend.write(audit_path(2), "[]")
            backend.write(audit_path(3), "[]")
            backend.write("/revisions/round-2.md", "revision 2")
            yield {"node": "content_agent", "content": "final written", "is_complete": True}
            backend.write(FINAL_POLISHED_TEXT_PATH, "final text")
            # final 写完后，runner 仍尝试越界发起第 4 轮审核；
            # 这会触发 verify graph 的轮次校验并抛“协议轮次已用尽”错误。
            raise GenerationAgentProtocolError("协议轮次已用尽：已存在 3 轮审核产物")

    runner = Round4RequestingRunner()

    result = run_content_agent_generation(
        {
            "generation_style": "param",
            "project_content": "project",
            "tender_params": "params",
            "template_reference_text": "origin",
        },
        {"configurable": {"model_provider": "deepseek", "task_id": "task-round4-request"}},
        runner=runner,
    )

    # final 已写入，越界审核请求不整单失败，按最终正文兜底交付。
    assert result.polished_text == "final text"
    # revision_rounds 只统计协议内合法轮次（round-2），不含 round-4。
    assert result.revision_rounds == 2


def test_content_runner_fails_when_round4_requested_and_final_missing(
    _redirect_content_agent_workspace,
) -> None:
    class Round4RequestingRunner:
        def invoke(self, payload, config=None):  # type: ignore[no-untyped-def]
            raise AssertionError("workspace runner should stream, not invoke")

        def stream(self, payload, config=None, **_kwargs):  # type: ignore[no-untyped-def]
            backend = config["configurable"]["content_agent_backend"]
            backend.write(audit_path(1), "[]")
            backend.write(audit_path(2), "[]")
            backend.write(audit_path(3), "[]")
            # 越界请求且未写 final：属真正的协议违规，应向上抛错。
            raise GenerationAgentProtocolError("协议轮次已用尽：已存在 3 轮审核产物")

    runner = Round4RequestingRunner()

    with pytest.raises(GenerationAgentProtocolError, match="协议轮次已用尽"):
        run_content_agent_generation(
            {
                "generation_style": "param",
                "project_content": "project",
                "tender_params": "params",
                "template_reference_text": "origin",
            },
            {"configurable": {"model_provider": "deepseek", "task_id": "task-round4-no-final"}},
            runner=runner,
        )


# ---------------------------------------------------------------------------
# 受保护基础字段防删除护栏 (protected_field_guard)
# ---------------------------------------------------------------------------

_XJCG_PAYMENT_TEMPLATE = (
    "一、项目概述\n"
    "1、设备名称及数量：球管/壹个\n"
    "2、交付日期：合同签订后两个月内交货\n"
    "3、付款方式：设备安装验收合格后的三个月内付清全款。\n"
)


def _verify_findings(monkeypatch, *, llm_output, current_text, tender_type="xjcg", template=None):
    async def fake_stream_llm_completion(**_kwargs):
        return llm_output

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )
    result = verify_agent_graph_module.create_verify_agent_graph().invoke(
        {
            "current_text": current_text,
            "tender_type": tender_type,
            "template_reference_text": template or "",
            "model_provider": "deepseek",
        }
    )
    return result["structured_response"]


def test_verify_drops_delete_payment_finding_before_writing_audit(monkeypatch) -> None:
    """LLM 返回“删除付款方式”的 finding 时，最终写入 audit JSON 前被过滤。"""
    findings = _verify_findings(
        monkeypatch,
        llm_output=(
            '[{"evidence":"付款方式无新材料支撑的旧事实","fix_hint":"'
            '删除付款方式字段行，保持其它内容不变"}]'
        ),
        current_text=(
            "一、项目概述\n"
            "2、交付日期：合同签订后两个月内交货\n"
            "3、付款方式：设备安装验收合格后的三个月内付清全款。\n"
        ),
        template=_XJCG_PAYMENT_TEMPLATE,
    )
    # “删除付款方式”的 finding 被丢弃；正文里付款方式/交付日期都存在，不补回。
    assert findings == []


def test_verify_appends_backfill_when_payment_missing(monkeypatch) -> None:
    """当前正文缺少 `付款方式：` 且参考模板有该字段时，追加补回 finding。"""
    findings = _verify_findings(
        monkeypatch,
        llm_output="[]",
        current_text=(
            "一、项目概述\n"
            "2、交付日期：合同签订后两个月内交货\n"
        ),
        template=_XJCG_PAYMENT_TEMPLATE,
    )
    # LLM 返回 []，但正文缺付款方式；guard 追加一条“补回付款方式”的 finding。
    assert len(findings) == 1
    assert "付款方式" in findings[0]["evidence"]
    assert "设备安装验收合格后的三个月内付清全款" in findings[0]["fix_hint"]


def test_verify_no_delete_finding_when_text_keeps_payment_and_material_lacks_it(
    monkeypatch,
) -> None:
    """当前正文已有 `付款方式：` 且新材料未提供付款方式时，不产生删除 finding。"""
    findings = _verify_findings(
        monkeypatch,
        llm_output="[]",
        current_text=(
            "一、项目概述\n"
            "2、交付日期：合同签订后两个月内交货\n"
            "3、付款方式：设备安装验收合格后的三个月内付清全款。\n"
        ),
        template=_XJCG_PAYMENT_TEMPLATE,
    )
    assert findings == []


def test_verify_inherits_template_field_per_package_for_multi_package(monkeypatch) -> None:
    """多包场景按包序号继承参考模板字段；参考缺对应包时复用第一个可用字段。"""
    multi_pkg_template = (
        "第1包：显微镜\n"
        "1、交付日期：合同签订后30天内交货\n"
        "2、付款方式：设备验收合格后30天内付清全款。\n"
        "第2包：离心机\n"
        "1、交付日期：合同签订后60天内交货\n"
        "2、付款方式：设备验收合格后60天内付清全款。\n"
    )
    from backend.agents.generation.protected_field_guard import (
        sanitize_protected_field_findings,
    )

    # 包2 缺付款方式：应从包2继承“设备验收合格后60天内付清全款”。
    findings = sanitize_protected_field_findings(
        findings=[],
        tender_type="xjcg",
        current_text="第2包：离心机\n1、交付日期：合同签订后60天内交货\n",
        template_reference_text=multi_pkg_template,
        package_index=2,
    )
    assert len(findings) == 1
    assert "付款方式" in findings[0].evidence
    assert "设备验收合格后60天内付清全款" in findings[0].fix_hint

    # 参考只有 2 个包，请求包 3 时回退到第一个可用字段行。
    findings_pkg3 = sanitize_protected_field_findings(
        findings=[],
        tender_type="xjcg",
        current_text="交付日期：合同签订后30天内交货\n",
        template_reference_text=multi_pkg_template,
        package_index=3,
    )
    # 包3 缺付款方式，回退到第一个可用付款方式行（包1）。
    payment_findings = [f for f in findings_pkg3 if "付款方式" in f.evidence]
    assert len(payment_findings) == 1
    assert "设备验收合格后30天内付清全款" in payment_findings[0].fix_hint


def test_verify_guard_skips_direct_replace_tender_type(monkeypatch) -> None:
    """`gngk_hw_cz` 这类 direct_replace 类型不进入 protected-field guard。"""
    from backend.agents.generation.protected_field_guard import (
        sanitize_protected_field_findings,
    )

    raw_finding = AuditFinding(
        evidence="付款方式无新材料支撑",
        fix_hint="删除付款方式字段行",
    )
    findings = sanitize_protected_field_findings(
        findings=[raw_finding],
        tender_type="gngk_hw_cz",
        current_text="",
        template_reference_text=_XJCG_PAYMENT_TEMPLATE,
    )
    # direct_replace 类型原样返回，不过滤、不补回。
    assert findings == [raw_finding]


def test_verify_guard_filters_delete_verb_variants() -> None:
    """删除/移除/去掉/删去 + 受保护字段名都被识别为删除建议并过滤。"""
    from backend.agents.generation.protected_field_guard import (
        sanitize_protected_field_findings,
    )

    current_text = (
        "2、交付日期：合同签订后两个月内交货\n"
        "3、付款方式：设备安装验收合格后的三个月内付清全款。\n"
    )
    for verb in ("删除", "移除", "去掉", "删去"):
        finding = AuditFinding(
            evidence=f"付款方式是旧事实",
            fix_hint=f"{verb}付款方式字段行",
        )
        findings = sanitize_protected_field_findings(
            findings=[finding],
            tender_type="xjcg",
            current_text=current_text,
            template_reference_text=_XJCG_PAYMENT_TEMPLATE,
        )
        # 正文里付款方式/交付日期都存在，删除 finding 被丢弃且不补回。
        assert findings == [], f"verb={verb} should be filtered"


def test_revise_ignores_delete_protected_field_audit_item(monkeypatch) -> None:
    """revise 阶段即使 audit JSON 要求删除受保护字段，guard 也会过滤掉该项。"""
    captured_audits: list[str] = []

    async def fake_stream_llm_completion(**kwargs):
        captured_audits.append(str(kwargs.get("user_prompt", "")))
        return "修订后的正文（保留付款方式）"

    monkeypatch.setattr(
        revise_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = revise_agent_graph_module.create_revise_agent_graph().invoke(
        {
            "current_text": (
                "2、交付日期：合同签订后两个月内交货\n"
                "3、付款方式：设备安装验收合格后的三个月内付清全款。\n"
            ),
            "tender_type": "xjcg",
            "template_reference_text": _XJCG_PAYMENT_TEMPLATE,
            "audit_findings": [
                {
                    "evidence": "付款方式无新材料支撑",
                    "fix_hint": "删除付款方式字段行",
                }
            ],
            "revision_round": 1,
            "model_provider": "deepseek",
        }
    )

    # 删除付款方式的 finding 被 guard 过滤；剩余 audit 为空时跳过修订。
    assert result["structured_response"] == {
        "status": "no_revision",
        "message": "无需修订",
    }
    assert result["no_revision"] is True
    # 删除付款方式的 audit item 不应进入 LLM。
    assert not captured_audits


def test_revise_keeps_real_audit_after_protected_field_filter(monkeypatch) -> None:
    """revise 阶段保留非删除类 audit item，只过滤删除受保护字段的 item。"""
    captured_audits: list[str] = []

    async def fake_stream_llm_completion(**kwargs):
        captured_audits.append(str(kwargs.get("user_prompt", "")))
        return "修订后的正文"

    monkeypatch.setattr(
        revise_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = revise_agent_graph_module.create_revise_agent_graph().invoke(
        {
            "current_text": (
                "2、交付日期：合同签订后两个月内交货\n"
                "3、付款方式：设备安装验收合格后的三个月内付清全款。\n"
                "技术参数缺少 ★ 符号。\n"
            ),
            "tender_type": "xjcg",
            "template_reference_text": _XJCG_PAYMENT_TEMPLATE,
            "audit_findings": [
                {
                    "evidence": "技术参数缺少 ★ 符号",
                    "fix_hint": "补充 ★ 符号",
                },
                {
                    "evidence": "付款方式无新材料支撑",
                    "fix_hint": "删除付款方式字段行",
                },
            ],
            "revision_round": 1,
            "model_provider": "deepseek",
        }
    )

    # 只过滤删除付款方式的 item；★ 符号 finding 保留，触发修订。
    assert "revision_path" in result["structured_response"]
    assert result["polished_text"] == "修订后的正文"
    # 传给 LLM 的 audit JSON 只保留 ★ 符号 finding。
    assert "补充 ★ 符号" in captured_audits[0]
    assert "删除付款方式" not in captured_audits[0]


def test_verify_final_text_findings_appends_backfill_for_missing_payment(monkeypatch) -> None:
    """最终复核也应用受保护字段护栏：缺付款方式时追加补回 finding。"""
    async def fake_stream_llm_completion(**_kwargs):
        return "[]"

    monkeypatch.setattr(
        verify_agent_graph_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    findings = verify_agent_graph_module.verify_final_text_findings(
        final_text="2、交付日期：合同签订后两个月内交货\n",
        generation_context={
            "generation_style": "template",
            "tender_type": "xjcg",
            "template_reference_text": _XJCG_PAYMENT_TEMPLATE,
        },
        model_provider="deepseek",
    )
    assert len(findings) == 1
    assert "付款方式" in findings[0].evidence