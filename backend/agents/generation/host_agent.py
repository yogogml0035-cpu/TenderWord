from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from deepagents import CompiledSubAgent, create_deep_agent

from backend.agents.generation.generate_agent_graph import create_generate_agent_graph
from backend.agents.generation.json_utils import (
    parse_audit_findings,
    parse_host_agent_final_output,
)
from backend.agents.generation.model_factory import create_generation_chat_model
from backend.agents.generation.types import (
    AgentStepPayload,
    AuditFinding,
    GenerationAgentProtocolError,
    GenerationAgentToolCallUnsupportedError,
    HostAgentFinalOutput,
)
from backend.agents.generation.verify_agent_graph import create_verify_agent_graph
from backend.states import TenderGraphStateBase


MAX_REVISION_ROUNDS = 3
HOST_AGENT_NODE = "host_agent"
GENERATE_AGENT_NODE = "generate_agent"
VERIFY_AGENT_NODE = "verify_agent"


class GenerationAgentRunner(Protocol):
    def invoke(self, payload: dict[str, Any]) -> dict[str, Any] | str:
        ...


@dataclass(frozen=True)
class GenerationSubAgents:
    generate_agent: CompiledSubAgent
    verify_agent: CompiledSubAgent


_fake_runner: GenerationAgentRunner | None = None


def set_generation_agent_runner(runner: GenerationAgentRunner | None) -> None:
    global _fake_runner
    _fake_runner = runner


def build_generation_subagents() -> GenerationSubAgents:
    generate_agent: CompiledSubAgent = {
        "name": GENERATE_AGENT_NODE,
        "description": "Generate the first draft procurement requirement text.",
        "runnable": create_generate_agent_graph(),
    }
    verify_agent: CompiledSubAgent = {
        "name": VERIFY_AGENT_NODE,
        "description": (
            "Audit procurement requirement text and return a JSON array of "
            "objects with evidence and fix_hint."
        ),
        "runnable": create_verify_agent_graph(),
    }
    return GenerationSubAgents(generate_agent=generate_agent, verify_agent=verify_agent)


def create_host_agent_runner(model_provider: str) -> GenerationAgentRunner:
    subagents = build_generation_subagents()
    return create_deep_agent(
        model=create_generation_chat_model(model_provider),
        tools=[],
        system_prompt=(
            "你是采购需求生成 host_agent。系统会用 agent_phase 指定当前阶段。"
            "agent_phase=generate 时必须调用 generate_agent 并只输出 "
            "{\"draft_text\":\"...\"}；agent_phase=verify 时必须调用 "
            "verify_agent 并只输出 JSON 数组；agent_phase=revise 时按 "
            "audit_findings 修复 current_text，并只输出 "
            "{\"polished_text\":\"...\"}。不要自动回退到非工具调用模式。"
        ),
        subagents=[subagents.generate_agent, subagents.verify_agent],
        name=HOST_AGENT_NODE,
    )


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _extract_structured_response(output: dict[str, Any] | str) -> Any:
    if not isinstance(output, dict):
        return None
    return output.get("structured_response")


def _extract_message_text(output: dict[str, Any] | str) -> str:
    if not isinstance(output, dict):
        return str(output or "")
    messages = output.get("messages")
    if isinstance(messages, list):
        for message in reversed(messages):
            content = getattr(message, "content", None)
            if content is None and isinstance(message, dict):
                content = message.get("content")
            if str(content or "").strip():
                return str(content)
    return ""


def _extract_text_from_runner_output(output: dict[str, Any] | str) -> str:
    if isinstance(output, str):
        return output
    structured = _extract_structured_response(output)
    if structured is not None:
        if isinstance(structured, HostAgentFinalOutput):
            return structured.model_dump_json(ensure_ascii=False)
        if hasattr(structured, "model_dump_json"):
            return structured.model_dump_json()
        return json.dumps(_jsonable(structured), ensure_ascii=False)
    return _extract_message_text(output)


def _is_tool_call_unsupported(error: BaseException) -> bool:
    message = str(error).lower()
    markers = (
        "tool call",
        "tool_call",
        "tool calls",
        "tool_calls",
        "function call",
        "function_call",
        "does not support tools",
        "not support tools",
    )
    return any(marker in message for marker in markers)


def _invoke_runner(
    runner: GenerationAgentRunner,
    payload: dict[str, Any],
) -> dict[str, Any] | str:
    try:
        return runner.invoke(payload)
    except Exception as exc:
        if _is_tool_call_unsupported(exc):
            raise GenerationAgentToolCallUnsupportedError(
                "当前模型或 DeepAgents runner 不支持工具调用，无法使用智能体生成"
            ) from exc
        raise


def _coerce_draft_text(value: Any) -> str | None:
    if isinstance(value, dict):
        return value.get("draft_text") or value.get("polished_text")
    if isinstance(value, HostAgentFinalOutput):
        return value.polished_text
    if hasattr(value, "draft_text"):
        return getattr(value, "draft_text")
    return None


def _parse_draft_output(output: dict[str, Any] | str) -> str:
    draft_text = _coerce_draft_text(_extract_structured_response(output))
    if draft_text is None:
        raw_text = _extract_message_text(output)
        try:
            draft_text = _coerce_draft_text(json.loads(raw_text))
        except json.JSONDecodeError:
            draft_text = raw_text
    normalized = str(draft_text or "").strip()
    if not normalized:
        raise GenerationAgentProtocolError("generate_agent 必须返回非空初稿正文")
    return normalized


def _parse_verify_output(output: dict[str, Any] | str) -> list[AuditFinding]:
    return parse_audit_findings(_extract_text_from_runner_output(output))


def _parse_revision_output(output: dict[str, Any] | str) -> str:
    final_output = parse_host_agent_final_output(_extract_text_from_runner_output(output))
    return final_output.polished_text


def _emit_step(
    callback: Callable[[AgentStepPayload], None] | None,
    payload: AgentStepPayload,
) -> None:
    if callback is None:
        return
    callback(payload)


def _build_generation_payload(
    state: TenderGraphStateBase,
    model_provider: str,
) -> dict[str, Any]:
    return {
        "tender_type": str(state.get("tender_type") or "xjcg"),
        "generation_style": str(state.get("generation_style") or "template"),
        "project_info": str(state.get("project_content") or ""),
        "tender_params": state.get("tender_params"),
        "origin_tender_params": state.get("origin_tender_params"),
        "model_provider": model_provider,
    }


def _build_phase_payload(
    base_payload: dict[str, Any],
    phase: str,
    *,
    current_text: str = "",
    findings: list[AuditFinding] | None = None,
    revision_round: int = 0,
) -> dict[str, Any]:
    audit_findings = [finding.model_dump() for finding in findings or []]
    phase_payload = {
        **base_payload,
        "agent_phase": phase,
        "current_text": current_text,
        "audit_findings": audit_findings,
        "revision_round": revision_round,
    }
    if phase == "generate":
        instruction = "调用 generate_agent 生成采购需求初稿，并只输出 JSON 对象 draft_text。"
    elif phase == "verify":
        instruction = "调用 verify_agent 审核 current_text，并只输出 JSON 数组。"
    else:
        instruction = (
            "根据 audit_findings 修复 current_text，并只输出 JSON 对象 polished_text。"
        )
    phase_payload["messages"] = [{"role": "user", "content": instruction}]
    return phase_payload


def run_host_agent_generation(
    state: TenderGraphStateBase,
    config: dict[str, Any] | None = None,
    *,
    runner: GenerationAgentRunner | None = None,
    step_callback: Callable[[AgentStepPayload], None] | None = None,
) -> HostAgentFinalOutput:
    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    model_provider = str(configurable.get("model_provider") or "deepseek")
    selected_runner = runner or _fake_runner or create_host_agent_runner(model_provider)
    base_payload = _build_generation_payload(state, model_provider)

    draft_text = _parse_draft_output(
        _invoke_runner(
            selected_runner,
            _build_phase_payload(base_payload, "generate"),
        )
    )
    _emit_step(
        step_callback,
        AgentStepPayload(
            step_type="draft",
            round=0,
            node=GENERATE_AGENT_NODE,
            content=draft_text,
            is_complete=True,
        ),
    )

    current_text = draft_text
    revision_rounds = 0
    last_findings: list[AuditFinding] = []

    while True:
        findings = _parse_verify_output(
            _invoke_runner(
                selected_runner,
                _build_phase_payload(
                    base_payload,
                    "verify",
                    current_text=current_text,
                    revision_round=revision_rounds,
                ),
            )
        )
        last_findings = findings
        _emit_step(
            step_callback,
            AgentStepPayload(
                step_type="audit",
                round=revision_rounds,
                node=VERIFY_AGENT_NODE,
                findings=findings,
                is_complete=True,
            ),
        )
        if not findings:
            return HostAgentFinalOutput(
                polished_text=current_text,
                audit_findings=[],
                revision_rounds=revision_rounds,
            )

        revision_rounds += 1
        current_text = _parse_revision_output(
            _invoke_runner(
                selected_runner,
                _build_phase_payload(
                    base_payload,
                    "revise",
                    current_text=current_text,
                    findings=findings,
                    revision_round=revision_rounds,
                ),
            )
        )
        _emit_step(
            step_callback,
            AgentStepPayload(
                step_type="revision",
                round=revision_rounds,
                node=HOST_AGENT_NODE,
                content=current_text,
                findings=findings,
                is_complete=True,
            ),
        )
        if revision_rounds >= MAX_REVISION_ROUNDS:
            return HostAgentFinalOutput(
                polished_text=current_text,
                audit_findings=last_findings,
                revision_rounds=revision_rounds,
            )


def parse_verify_agent_output(raw_content: str) -> list[AuditFinding]:
    return parse_audit_findings(raw_content)


__all__ = [
    "GENERATE_AGENT_NODE",
    "HOST_AGENT_NODE",
    "MAX_REVISION_ROUNDS",
    "VERIFY_AGENT_NODE",
    "GenerationSubAgents",
    "build_generation_subagents",
    "create_host_agent_runner",
    "parse_verify_agent_output",
    "run_host_agent_generation",
    "set_generation_agent_runner",
]
