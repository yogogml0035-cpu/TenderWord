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
        "name": "generate_agent",
        "description": "Generate the first draft procurement requirement text.",
        "runnable": create_generate_agent_graph(),
    }
    verify_agent: CompiledSubAgent = {
        "name": "verify_agent",
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
            "你是采购需求生成 host_agent。必须调用 generate_agent 生成初稿，"
            "调用 verify_agent 审核，并按审核意见修复。最终只输出结构化 JSON，"
            "至少包含 polished_text。"
        ),
        subagents=[subagents.generate_agent, subagents.verify_agent],
        response_format=HostAgentFinalOutput,
        name=HOST_AGENT_NODE,
    )


def _extract_text_from_runner_output(output: dict[str, Any] | str) -> str:
    if isinstance(output, str):
        return output
    structured = output.get("structured_response")
    if structured is not None:
        if isinstance(structured, HostAgentFinalOutput):
            return structured.model_dump_json(ensure_ascii=False)
        if hasattr(structured, "model_dump_json"):
            return structured.model_dump_json()
        return json.dumps(structured, ensure_ascii=False)
    messages = output.get("messages")
    if isinstance(messages, list):
        for message in reversed(messages):
            content = getattr(message, "content", None)
            if content is None and isinstance(message, dict):
                content = message.get("content")
            if str(content or "").strip():
                return str(content)
    return ""


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


def _invoke_host_runner(
    runner: GenerationAgentRunner,
    payload: dict[str, Any],
) -> HostAgentFinalOutput:
    try:
        output = runner.invoke(payload)
    except Exception as exc:
        if _is_tool_call_unsupported(exc):
            raise GenerationAgentToolCallUnsupportedError(
                "当前模型或 DeepAgents runner 不支持工具调用，无法使用智能体生成"
            ) from exc
        raise
    return parse_host_agent_final_output(_extract_text_from_runner_output(output))


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
    output = _invoke_host_runner(
        selected_runner,
        _build_generation_payload(state, model_provider),
    )
    _emit_step(
        step_callback,
        AgentStepPayload(
            step_type="revision",
            round=int(output.revision_rounds),
            node=HOST_AGENT_NODE,
            content=output.polished_text,
            findings=output.audit_findings,
            is_complete=True,
        ),
    )
    return output


def parse_verify_agent_output(raw_content: str) -> list[AuditFinding]:
    return parse_audit_findings(raw_content)


__all__ = [
    "HOST_AGENT_NODE",
    "MAX_REVISION_ROUNDS",
    "GenerationSubAgents",
    "build_generation_subagents",
    "create_host_agent_runner",
    "parse_verify_agent_output",
    "run_host_agent_generation",
    "set_generation_agent_runner",
]
