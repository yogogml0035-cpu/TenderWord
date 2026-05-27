from __future__ import annotations

from typing import Any, Callable

from backend.agents.generation import AgentStepPayload, run_host_agent_generation
from backend.models import AgentStepEventData
from backend.states.base_state import TenderGraphStateBase


def _get_configurable(config: dict[str, Any] | None) -> dict[str, Any]:
    return config.get("configurable", {}) if isinstance(config, dict) else {}


def _build_agent_step_data(
    payload: AgentStepPayload,
    *,
    task_id: str,
    task_kind: str,
) -> AgentStepEventData:
    return AgentStepEventData(
        task_id=task_id,
        task_kind=task_kind,
        step_type=payload.step_type,
        round=payload.round,
        node=payload.node,
        content=payload.content,
        findings=[finding.model_dump(mode="json") for finding in payload.findings],
        is_complete=payload.is_complete,
    )


def _make_agent_step_callback(
    state: TenderGraphStateBase,
    config: dict[str, Any] | None,
) -> Callable[[AgentStepPayload], None] | None:
    configurable = _get_configurable(config)
    task_id = str(configurable.get("task_id") or state.get("task_id") or "").strip()
    if not task_id:
        return None

    task_kind = str(configurable.get("task_kind") or state.get("task_kind") or "generate")
    callback = configurable.get("agent_step_callback")

    def emit(payload: AgentStepPayload) -> None:
        event_data = _build_agent_step_data(payload, task_id=task_id, task_kind=task_kind)
        if callable(callback):
            callback(event_data)
        try:
            from backend.core.sse_manager import sse_manager

            sse_manager.send_agent_step_threadsafe(
                task_id=task_id,
                task_kind=task_kind,
                step_type=event_data.step_type,
                round=event_data.round,
                node=event_data.node,
                content=event_data.content,
                findings=[finding.model_dump(mode="json") for finding in event_data.findings],
                is_complete=event_data.is_complete,
            )
        except Exception:
            pass

    return emit


def host_agent_generate(
    state: TenderGraphStateBase,
    config=None,
) -> TenderGraphStateBase:
    """Run the DeepAgents generation branch and expose the standard text contract."""
    result = run_host_agent_generation(
        state,
        config,
        step_callback=_make_agent_step_callback(state, config),
    )
    return TenderGraphStateBase(
        polished_text=result.polished_text,
        generate_polished_done=True,
    )


__all__ = ["host_agent_generate"]
