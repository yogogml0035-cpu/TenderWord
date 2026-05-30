from __future__ import annotations

import inspect
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol

from deepagents import CompiledSubAgent, create_deep_agent
from deepagents.backends.protocol import BackendProtocol

from backend.agents.generation.generate_agent_graph import create_generate_agent_graph
from backend.agents.generation.json_utils import (
    coerce_audit_findings,
    is_contract_placeholder_text,
)
from backend.agents.generation.model_factory import create_generation_chat_model
from backend.agents.generation.revise_agent_graph import create_revise_agent_graph
from backend.agents.generation.types import (
    AgentStepPayload,
    AuditFinding,
    ContentAgentFinalOutput,
    GenerationAgentProtocolError,
    GenerationAgentToolCallUnsupportedError,
)
from backend.agents.generation.verify_agent_graph import create_verify_agent_graph
from backend.agents.generation.workspace import (
    DRAFT_PATH,
    FINAL_POLISHED_TEXT_PATH,
    GENERATION_CONTEXT_PATH,
    MAX_REVISION_ROUNDS,
    audit_path,
    create_workspace_backend,
    create_workspace_dir,
    infer_next_audit_round,
    infer_next_revision_round,
    read_backend_text,
    read_backend_text_optional,
    validate_round_protocol,
    write_generation_context,
)
from backend.states import TenderGraphStateBase
from backend.util.log_util.progress_log import progress_log


CONTENT_AGENT_NODE = "content_agent"
GENERATE_AGENT_NODE = "content_generate_agent"
VERIFY_AGENT_NODE = "content_verify_agent"
REVISE_AGENT_NODE = "content_revise_agent"

CONTENT_AGENT_SYSTEM_PROMPT = f"""
你是采购需求生成主智能体（content_agent），负责自主调度初次生成流程。

你必须使用 TodoList 维护计划，并通过 task 工具调用这些子智能体：
- content_generate_agent：读取 {GENERATION_CONTEXT_PATH}，写 {DRAFT_PATH}。
- content_verify_agent：读取上下文和当前正文文件，写 /audits/round-N.json。
- content_revise_agent：读取当前正文和 /audits/round-N.json，只修复审核指定位置，写 /revisions/round-N.md。

硬性协议：
1. 所有输入、草稿、审核、修订和最终正文都只通过文件系统路径交接，不要把完整正文塞进 task 描述。
2. 先调用 content_generate_agent 生成初稿，再调用 content_verify_agent 审核；审核最多 3 轮，路径只能是 /audits/round-1.json 到 /audits/round-3.json。
3. 如果审核 JSON 是 []，不要调用 content_revise_agent，直接把当前正文完整写入 {FINAL_POLISHED_TEXT_PATH}。
4. 如果审核 JSON 非空，调用 content_revise_agent 写 /revisions/round-N.md，然后继续下一轮审核；修订路径只能是 /revisions/round-1.md 到 /revisions/round-3.md。
5. 只有 content_agent 可以写 {FINAL_POLISHED_TEXT_PATH}；子智能体不得写 final。
6. 第 3 轮修订后必须停止返修，并把当前修订正文写入 {FINAL_POLISHED_TEXT_PATH}。
7. 最终回复只输出简短验收说明，不要重复最终正文，不要展示隐藏 reasoning。
8. 不得要求用户补充信息，不得自动回退 workflow。
""".strip()


class GenerationAgentRunner(Protocol):
    def invoke(
        self,
        payload: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any] | str:
        ...


@dataclass(frozen=True)
class GenerationSubAgents:
    content_generate_agent: CompiledSubAgent
    content_verify_agent: CompiledSubAgent
    content_revise_agent: CompiledSubAgent


_fake_runner: GenerationAgentRunner | None = None


def set_generation_agent_runner(runner: GenerationAgentRunner | None) -> None:
    global _fake_runner
    _fake_runner = runner


def build_generation_subagents() -> GenerationSubAgents:
    content_generate_agent: CompiledSubAgent = {
        "name": GENERATE_AGENT_NODE,
        "description": f"读取 {GENERATION_CONTEXT_PATH} 并生成采购需求初稿，写入 {DRAFT_PATH}。",
        "runnable": create_generate_agent_graph(),
    }
    content_verify_agent: CompiledSubAgent = {
        "name": VERIFY_AGENT_NODE,
        "description": "读取上下文和当前正文文件，按审核规则输出原始 JSON 数组并写入 /audits/round-N.json。",
        "runnable": create_verify_agent_graph(),
    }
    content_revise_agent: CompiledSubAgent = {
        "name": REVISE_AGENT_NODE,
        "description": "读取当前正文与 /audits/round-N.json，只修复审核指定位置并写入 /revisions/round-N.md。",
        "runnable": create_revise_agent_graph(),
    }
    return GenerationSubAgents(
        content_generate_agent=content_generate_agent,
        content_verify_agent=content_verify_agent,
        content_revise_agent=content_revise_agent,
    )


def create_content_agent_runner(
    model_provider: str,
    backend: BackendProtocol | None = None,
) -> GenerationAgentRunner:
    subagents = build_generation_subagents()
    return create_deep_agent(
        model=create_generation_chat_model(model_provider),
        tools=[],
        system_prompt=CONTENT_AGENT_SYSTEM_PROMPT,
        subagents=[
            subagents.content_generate_agent,
            subagents.content_verify_agent,
            subagents.content_revise_agent,
        ],
        backend=backend,
        name=CONTENT_AGENT_NODE,
    )


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


def _runner_accepts_config(runner: GenerationAgentRunner) -> bool:
    try:
        signature = inspect.signature(runner.invoke)
    except (TypeError, ValueError):
        return True

    parameters = list(signature.parameters.values())
    if any(parameter.kind == inspect.Parameter.VAR_POSITIONAL for parameter in parameters):
        return True
    if "config" in signature.parameters:
        return True
    positional_count = sum(
        parameter.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        for parameter in parameters
    )
    return positional_count >= 2


def _invoke_runner(
    runner: GenerationAgentRunner,
    payload: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any] | str:
    try:
        if _runner_accepts_config(runner):
            return runner.invoke(payload, config)
        return runner.invoke(payload)
    except Exception as exc:
        if _is_tool_call_unsupported(exc):
            raise GenerationAgentToolCallUnsupportedError(
                "当前模型或 DeepAgents runner 不支持工具调用，无法使用智能体生成"
            ) from exc
        raise


def _runner_supports_stream(runner: GenerationAgentRunner) -> bool:
    return callable(getattr(runner, "stream", None))


def _stream_runner(
    runner: GenerationAgentRunner,
    payload: dict[str, Any],
    config: dict[str, Any],
) -> Iterable[Any]:
    try:
        return runner.stream(  # type: ignore[attr-defined]
            payload,
            config,
            stream_mode=["messages", "updates", "tasks"],
            subgraphs=True,
        )
    except TypeError:
        return runner.stream(payload, config)  # type: ignore[attr-defined]
    except Exception as exc:
        if _is_tool_call_unsupported(exc):
            raise GenerationAgentToolCallUnsupportedError(
                "当前模型或 DeepAgents runner 不支持工具调用，无法使用智能体生成"
            ) from exc
        raise


def _build_generation_payload(
    state: TenderGraphStateBase,
    model_provider: str,
    task_id: str,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "tender_type": str(state.get("tender_type") or "xjcg"),
        "generation_style": str(state.get("generation_style") or "template"),
        "project_info": str(state.get("project_content") or ""),
        "origin_tender_params": state.get("origin_tender_params"),
        "tender_params": state.get("tender_params"),
        "model_provider": model_provider,
    }


def _build_runner_config(
    config: dict[str, Any] | None,
    *,
    payload: dict[str, Any],
    backend: BackendProtocol,
    workspace_dir: Path,
    step_callback: Callable[[AgentStepPayload], None] | None,
) -> dict[str, Any]:
    next_config = {**config} if isinstance(config, dict) else {}
    existing_configurable = next_config.get("configurable", {})
    configurable = (
        {**existing_configurable} if isinstance(existing_configurable, dict) else {}
    )
    configurable["generation_agent_context"] = dict(payload)
    configurable["content_agent_backend"] = backend
    configurable["content_agent_workspace_dir"] = str(workspace_dir)
    configurable["agent_step_callback"] = _build_agent_step_bridge(step_callback)
    next_config["configurable"] = configurable
    return next_config


def _get_task_id(state: TenderGraphStateBase, configurable: dict[str, Any]) -> str:
    return str(
        configurable.get("task_id") or state.get("task_id") or "content-agent"
    ).strip()


def _text_length(value: Any) -> int:
    return len(str(value or ""))


def _log_generation_input_summary(
    *,
    task_id: str,
    generation_style: str,
    payload: dict[str, Any],
) -> None:
    project_info_chars = _text_length(payload.get("project_info"))
    origin_chars = _text_length(payload.get("origin_tender_params"))
    tender_chars = _text_length(payload.get("tender_params"))
    message = (
        "[content_agent] 生成上下文摘要: task_id=%s, generation_style=%s, "
        "project_info_chars=%d, origin_tender_params_chars=%d, tender_params_chars=%d"
    )
    args = (
        task_id,
        generation_style,
        project_info_chars,
        origin_chars,
        tender_chars,
    )
    if project_info_chars == 0 and origin_chars == 0 and tender_chars == 0:
        progress_log.warning(message, *args)
        return
    progress_log.debug(message, *args)


def _build_main_agent_user_prompt() -> str:
    return f"""
请按文件协议自主完成采购需求生成。

固定路径：
- 输入上下文：{GENERATION_CONTEXT_PATH}
- 初稿：{DRAFT_PATH}
- 审核：/audits/round-1.json 至 /audits/round-3.json
- 修订：/revisions/round-1.md 至 /revisions/round-3.md
- 最终正文：{FINAL_POLISHED_TEXT_PATH}

执行要求：
1. 先用 TodoList 写出 generate、verify、revise/final 的计划。
2. 调用 content_generate_agent 生成初稿。
3. 第 N 轮审核时调用 content_verify_agent，让它读取当前正文文件并写 /audits/round-N.json。
4. 如果审核 JSON 为 []，由你读取当前正文并写入 {FINAL_POLISHED_TEXT_PATH}。
5. 如果审核 JSON 非空且 N <= 3，调用 content_revise_agent 写 /revisions/round-N.md；然后继续下一轮审核。
6. 第 3 轮修订后直接把 /revisions/round-3.md 写入 {FINAL_POLISHED_TEXT_PATH}。
7. 最终只回复简短验收说明，不重复正文。
""".strip()


def _emit_step(
    callback: Callable[[AgentStepPayload], None] | None,
    payload: AgentStepPayload,
) -> None:
    if callback is None:
        return
    callback(payload)


def _agent_step_payload_from_event(event: Any) -> AgentStepPayload | None:
    if isinstance(event, AgentStepPayload):
        return event
    if event is None:
        return None
    if hasattr(event, "model_dump"):
        data = event.model_dump(mode="json")
    elif isinstance(event, dict):
        data = event
    else:
        return None
    return AgentStepPayload(
        step_type=str(data.get("step_type") or "stream"),
        round=int(data.get("round") or 1),
        node=str(data.get("node") or CONTENT_AGENT_NODE),
        content=data.get("content"),
        findings=coerce_audit_findings(
            json.dumps(data.get("findings") or [], ensure_ascii=False),
            fallback_on_error=True,
        )
        if data.get("findings")
        else [],
        is_complete=bool(data.get("is_complete")),
    )


def _build_agent_step_bridge(
    callback: Callable[[AgentStepPayload], None] | None,
) -> Callable[[Any], None] | None:
    if callback is None:
        return None

    def emit(event: Any) -> None:
        payload = _agent_step_payload_from_event(event)
        if payload is not None and payload.node != CONTENT_AGENT_NODE:
            _emit_step(callback, payload)

    return emit


def _infer_round_from_text(value: Any) -> int | None:
    match = re.search(r"round-(\d+)", str(value or ""))
    if not match:
        return None
    return int(match.group(1))


def _infer_round_from_workspace(
    *,
    node: str,
    backend: BackendProtocol | None,
) -> int:
    if node == GENERATE_AGENT_NODE:
        return 1
    if backend is not None and node == VERIFY_AGENT_NODE:
        return infer_next_audit_round(backend)
    if backend is not None and node == REVISE_AGENT_NODE:
        return infer_next_revision_round(backend)
    return 1


def _message_text(message: Any) -> str:
    if message is None:
        return ""
    if hasattr(message, "text"):
        try:
            return str(message.text or "")
        except Exception:
            pass
    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
        return "".join(parts)
    return str(content or "")


def _normalize_stream_chunk(chunk: Any) -> tuple[tuple[str, ...], str, Any] | None:
    if isinstance(chunk, tuple):
        if len(chunk) == 3 and isinstance(chunk[0], tuple) and isinstance(chunk[1], str):
            return chunk
        if len(chunk) == 2 and isinstance(chunk[0], str):
            return (), chunk[0], chunk[1]
    return None


def _emit_task_start_if_needed(
    *,
    data: Any,
    backend: BackendProtocol | None,
    step_callback: Callable[[AgentStepPayload], None] | None,
) -> None:
    if not isinstance(data, dict) or data.get("name") != "tools" or "result" in data:
        return
    for tool_call in _iter_task_tool_calls(data):
        tool_name = str(tool_call.get("name") or "").strip()
        if tool_name != "task":
            continue
        args = tool_call.get("args") or tool_call.get("input") or {}
        subagent_type = str(args.get("subagent_type") or "").strip()
        if subagent_type not in {GENERATE_AGENT_NODE, VERIFY_AGENT_NODE, REVISE_AGENT_NODE}:
            continue
        description = str(args.get("description") or "")
        _emit_step(
            step_callback,
            AgentStepPayload(
                step_type="stream",
                round=_infer_round_from_text(description)
                or _infer_round_from_workspace(node=subagent_type, backend=backend),
                node=subagent_type,
                content="",
                is_complete=False,
            ),
        )


def _iter_task_tool_calls(data: dict[str, Any]) -> Iterable[dict[str, Any]]:
    direct_tool_calls = data.get("tool_calls")
    if isinstance(direct_tool_calls, list):
        for tool_call in direct_tool_calls:
            if isinstance(tool_call, dict):
                yield tool_call

    input_value = data.get("input")
    if isinstance(input_value, list):
        for item in input_value:
            if isinstance(item, dict):
                yield item
        return

    if not isinstance(input_value, dict):
        return

    input_tool_calls = input_value.get("tool_calls")
    if isinstance(input_tool_calls, list):
        for tool_call in input_tool_calls:
            if isinstance(tool_call, dict):
                yield tool_call

    messages = input_value.get("messages")
    if not isinstance(messages, list):
        return
    for message in messages:
        message_tool_calls = getattr(message, "tool_calls", None)
        if message_tool_calls is None and isinstance(message, dict):
            message_tool_calls = message.get("tool_calls")
        if not isinstance(message_tool_calls, list):
            continue
        for tool_call in message_tool_calls:
            if isinstance(tool_call, dict):
                yield tool_call


def _emit_main_message_if_needed(
    *,
    namespace: tuple[str, ...],
    data: Any,
    step_callback: Callable[[AgentStepPayload], None] | None,
) -> None:
    return


def _relay_runner_stream(
    runner: GenerationAgentRunner,
    payload: dict[str, Any],
    config: dict[str, Any],
    step_callback: Callable[[AgentStepPayload], None] | None,
) -> None:
    if not _runner_supports_stream(runner):
        _invoke_runner(runner, payload, config)
        return

    try:
        for chunk in _stream_runner(runner, payload, config):
            if isinstance(chunk, AgentStepPayload):
                _emit_step(step_callback, chunk)
                continue
            if isinstance(chunk, dict) and {"node", "content"}.issubset(chunk):
                node = str(chunk.get("node") or CONTENT_AGENT_NODE)
                if node == CONTENT_AGENT_NODE:
                    continue
                _emit_step(
                    step_callback,
                    AgentStepPayload(
                        step_type=str(chunk.get("step_type") or "stream"),
                        round=int(chunk.get("round") or 1),
                        node=node,
                        content=str(chunk.get("content") or ""),
                        findings=coerce_audit_findings(
                            json.dumps(chunk.get("findings") or [], ensure_ascii=False),
                            fallback_on_error=True,
                        ) if chunk.get("findings") else [],
                        is_complete=bool(chunk.get("is_complete")),
                    ),
                )
                continue

            normalized = _normalize_stream_chunk(chunk)
            if normalized is None:
                continue
            namespace, mode, data = normalized
            if mode == "tasks":
                backend = config.get("configurable", {}).get("content_agent_backend")
                _emit_task_start_if_needed(
                    data=data,
                    backend=backend if isinstance(backend, BackendProtocol) else None,
                    step_callback=step_callback,
                )
            elif mode == "messages":
                _emit_main_message_if_needed(
                    namespace=namespace,
                    data=data,
                    step_callback=step_callback,
                )
    except Exception as exc:
        if _is_tool_call_unsupported(exc):
            raise GenerationAgentToolCallUnsupportedError(
                "当前模型或 DeepAgents runner 不支持工具调用，无法使用智能体生成"
            ) from exc
        raise


def _validate_final_text(final_text: str) -> str:
    normalized = str(final_text or "").strip()
    if (
        not normalized
        or normalized == "System reminder: File exists but has empty contents"
    ):
        raise GenerationAgentProtocolError(f"{FINAL_POLISHED_TEXT_PATH} 为空")
    if is_contract_placeholder_text(normalized):
        raise GenerationAgentProtocolError(f"{FINAL_POLISHED_TEXT_PATH} 是占位符，不是实际正文")
    return normalized


def _read_optional_audit_findings(backend: BackendProtocol) -> tuple[list[AuditFinding], int]:
    last_findings: list[AuditFinding] = []
    last_round = 0
    for round_index in range(1, MAX_REVISION_ROUNDS + 1):
        try:
            raw = read_backend_text(backend, audit_path(round_index))
        except GenerationAgentProtocolError:
            continue
        last_round = round_index
        last_findings = coerce_audit_findings(raw, fallback_on_error=True)
    return last_findings, last_round


def _count_revision_rounds(workspace_dir: Path) -> int:
    rounds = []
    revisions_dir = workspace_dir / "revisions"
    if not revisions_dir.exists():
        return 0
    for path in revisions_dir.iterdir():
        match = re.fullmatch(r"round-(\d+)\.md", path.name)
        if match:
            rounds.append(int(match.group(1)))
    return max(rounds, default=0)


def run_content_agent_generation(
    state: TenderGraphStateBase,
    config: dict[str, Any] | None = None,
    *,
    runner: GenerationAgentRunner | None = None,
    step_callback: Callable[[AgentStepPayload], None] | None = None,
) -> ContentAgentFinalOutput:
    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    model_provider = str(configurable.get("model_provider") or "deepseek")
    task_id = _get_task_id(state, configurable)
    workspace_dir = create_workspace_dir(task_id)
    backend = create_workspace_backend(workspace_dir)
    base_payload = _build_generation_payload(state, model_provider, task_id)
    runner_config = _build_runner_config(
        config,
        payload=base_payload,
        backend=backend,
        workspace_dir=workspace_dir,
        step_callback=step_callback,
    )
    selected_runner = runner or _fake_runner or create_content_agent_runner(
        model_provider,
        backend=backend,
    )

    write_generation_context(backend, base_payload)

    progress_log.info(
        "[content_agent] 开始智能体生成: task_id=%s, tender_type=%s, model=%s, workspace=%s",
        task_id,
        base_payload["tender_type"],
        model_provider,
        workspace_dir,
    )
    _log_generation_input_summary(
        task_id=task_id,
        generation_style=str(base_payload.get("generation_style") or "template"),
        payload=base_payload,
    )

    _relay_runner_stream(
        selected_runner,
        {"messages": [{"role": "user", "content": _build_main_agent_user_prompt()}]},
        runner_config,
        step_callback,
    )

    validate_round_protocol(workspace_dir)
    raw_final_text = read_backend_text_optional(backend, FINAL_POLISHED_TEXT_PATH)
    if raw_final_text is None:
        raw_final_text = read_backend_text(backend, FINAL_POLISHED_TEXT_PATH)
    final_text = _validate_final_text(raw_final_text)
    findings, last_audit_round = _read_optional_audit_findings(backend)
    revision_rounds = _count_revision_rounds(workspace_dir)

    _emit_step(
        step_callback,
        AgentStepPayload(
            step_type="final",
            round=max(1, last_audit_round, revision_rounds),
            node=CONTENT_AGENT_NODE,
            content="智能体生成完成，最终正文已通过文件协议写入 final。",
            is_complete=True,
        ),
    )
    progress_log.info(
        "[content_agent] 智能体生成完成: task_id=%s, revision_rounds=%d, final_chars=%d, workspace=%s",
        task_id,
        revision_rounds,
        len(final_text),
        workspace_dir,
    )
    return ContentAgentFinalOutput(
        polished_text=final_text,
        audit_findings=findings,
        revision_rounds=revision_rounds,
        workspace_dir=workspace_dir,
    )


def parse_verify_agent_output(raw_content: str) -> list[AuditFinding]:
    return coerce_audit_findings(raw_content, fallback_on_error=True)


__all__ = [
    "GENERATE_AGENT_NODE",
    "CONTENT_AGENT_NODE",
    "CONTENT_AGENT_SYSTEM_PROMPT",
    "MAX_REVISION_ROUNDS",
    "REVISE_AGENT_NODE",
    "VERIFY_AGENT_NODE",
    "GenerationSubAgents",
    "build_generation_subagents",
    "create_content_agent_runner",
    "parse_verify_agent_output",
    "run_content_agent_generation",
    "set_generation_agent_runner",
]
