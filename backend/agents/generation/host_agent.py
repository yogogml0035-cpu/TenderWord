from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from deepagents import CompiledSubAgent, create_deep_agent

from backend.agents.generation.generate_agent_graph import create_generate_agent_graph
from backend.agents.generation.json_utils import (
    coerce_audit_findings,
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
from backend.util.log_util.progress_log import progress_log
from backend.util.log_util.prompt_log import (
    get_host_agent_log_dir,
    get_verify_agent_log_dir,
    write_agent_log_artifact,
)


MAX_REVISION_ROUNDS = 3
HOST_AGENT_NODE = "host_agent"
GENERATE_AGENT_NODE = "generate_agent"
VERIFY_AGENT_NODE = "verify_agent"
HOST_AGENT_SYSTEM_PROMPT = (
    "你是采购需求生成主智能体（host_agent）。系统会通过 agent_phase 字段指定当前阶段。"
    "当 agent_phase=generate 时，必须调用 generate_agent，并且只输出包含 draft_text "
    "字段的 JSON 对象；当 agent_phase=verify 时，必须调用 verify_agent，并且只输出 "
    "JSON 数组；当 agent_phase=revise 时，必须根据 audit_findings 修复 current_text，"
    "并且逐项读取 JSON 字段 evidence 和 fix_hint：只修复 evidence 指向且 fix_hint 要求的内容，"
    "不得新增、删除、润色或改写其它无关内容；如果 evidence 表示审核输出格式异常，"
    "或 fix_hint 要求保持原文不变，必须原样返回 current_text。"
    "revise 只输出包含 polished_text 字段的 JSON 对象。不要自动回退到非工具调用模式。"
)


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
        "description": "生成采购需求初稿。",
        "runnable": create_generate_agent_graph(),
    }
    verify_agent: CompiledSubAgent = {
        "name": VERIFY_AGENT_NODE,
        "description": "审核采购需求正文，并返回 JSON 数组；数组元素必须包含 evidence 和 fix_hint 字段。",
        "runnable": create_verify_agent_graph(),
    }
    return GenerationSubAgents(generate_agent=generate_agent, verify_agent=verify_agent)


def create_host_agent_runner(model_provider: str) -> GenerationAgentRunner:
    subagents = build_generation_subagents()
    return create_deep_agent(
        model=create_generation_chat_model(model_provider),
        tools=[],
        system_prompt=HOST_AGENT_SYSTEM_PROMPT,
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
    return coerce_audit_findings(
        _extract_text_from_runner_output(output),
        fallback_on_error=True,
    )


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


def _get_task_id(state: TenderGraphStateBase, configurable: dict[str, Any]) -> str:
    return str(
        configurable.get("task_id") or state.get("task_id") or "host-agent"
    ).strip()


def _write_host_artifact(
    *,
    task_id: str,
    phase: str,
    content: str,
    round_index: int | None = None,
) -> None:
    try:
        write_agent_log_artifact(
            get_host_agent_log_dir(__file__),
            prefix="host",
            task_id=task_id,
            phase=phase,
            round_index=round_index,
            content=content,
        )
    except Exception as exc:
        progress_log.debug(f"警告: 保存 host_agent 日志失败: {exc}")


def _write_verify_artifact(
    *,
    task_id: str,
    current_text: str,
    findings: list[AuditFinding],
    round_index: int,
) -> None:
    try:
        payload = {
            "round": round_index,
            "current_text": current_text,
            "findings": [finding.model_dump(mode="json") for finding in findings],
        }
        write_agent_log_artifact(
            get_verify_agent_log_dir(__file__),
            prefix="verify",
            task_id=task_id,
            phase="audit_findings",
            round_index=round_index,
            content=json.dumps(payload, ensure_ascii=False, indent=2),
        )
    except Exception as exc:
        progress_log.debug(f"警告: 保存 verify_agent 日志失败: {exc}")


def run_host_agent_generation(
    state: TenderGraphStateBase,
    config: dict[str, Any] | None = None,
    *,
    runner: GenerationAgentRunner | None = None,
    step_callback: Callable[[AgentStepPayload], None] | None = None,
) -> HostAgentFinalOutput:
    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    model_provider = str(configurable.get("model_provider") or "deepseek")
    task_id = _get_task_id(state, configurable)
    selected_runner = runner or _fake_runner or create_host_agent_runner(model_provider)
    base_payload = _build_generation_payload(state, model_provider)

    progress_log.info(
        "[host_agent] 开始智能体生成: task_id=%s, tender_type=%s, model=%s",
        task_id,
        base_payload["tender_type"],
        model_provider,
    )
    draft_text = _parse_draft_output(
        _invoke_runner(
            selected_runner,
            _build_phase_payload(base_payload, "generate"),
        )
    )
    _write_host_artifact(
        task_id=task_id,
        phase="draft",
        round_index=0,
        content=draft_text,
    )
    progress_log.info(
        "[host_agent] 初稿生成完成: task_id=%s, chars=%d",
        task_id,
        len(draft_text),
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
        _write_verify_artifact(
            task_id=task_id,
            current_text=current_text,
            findings=findings,
            round_index=revision_rounds,
        )
        progress_log.info(
            "[host_agent] 第 %d 轮审核完成: task_id=%s, findings=%d",
            revision_rounds,
            task_id,
            len(findings),
        )
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
            _write_host_artifact(
                task_id=task_id,
                phase="final",
                round_index=revision_rounds,
                content=current_text,
            )
            progress_log.info(
                "[host_agent] 审核无问题，智能体生成完成: task_id=%s, revision_rounds=%d",
                task_id,
                revision_rounds,
            )
            return HostAgentFinalOutput(
                polished_text=current_text,
                audit_findings=[],
                revision_rounds=revision_rounds,
            )

        revision_rounds += 1
        progress_log.info(
            "[host_agent] 开始第 %d 轮修复: task_id=%s, findings=%d",
            revision_rounds,
            task_id,
            len(findings),
        )
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
        _write_host_artifact(
            task_id=task_id,
            phase="revision",
            round_index=revision_rounds,
            content=current_text,
        )
        progress_log.info(
            "[host_agent] 第 %d 轮修复完成: task_id=%s, chars=%d",
            revision_rounds,
            task_id,
            len(current_text),
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
            _write_host_artifact(
                task_id=task_id,
                phase="final",
                round_index=revision_rounds,
                content=current_text,
            )
            progress_log.info(
                "[host_agent] 达到最大修复轮次后放行: task_id=%s, revision_rounds=%d, remaining_findings=%d",
                task_id,
                revision_rounds,
                len(last_findings),
            )
            return HostAgentFinalOutput(
                polished_text=current_text,
                audit_findings=last_findings,
                revision_rounds=revision_rounds,
            )


def parse_verify_agent_output(raw_content: str) -> list[AuditFinding]:
    return coerce_audit_findings(raw_content, fallback_on_error=True)


__all__ = [
    "GENERATE_AGENT_NODE",
    "HOST_AGENT_NODE",
    "HOST_AGENT_SYSTEM_PROMPT",
    "MAX_REVISION_ROUNDS",
    "VERIFY_AGENT_NODE",
    "GenerationSubAgents",
    "build_generation_subagents",
    "create_host_agent_runner",
    "parse_verify_agent_output",
    "run_host_agent_generation",
    "set_generation_agent_runner",
]
