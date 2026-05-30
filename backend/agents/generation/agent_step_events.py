from __future__ import annotations

from typing import Any

from backend.models import AgentStepEventData


def get_configurable(config: dict[str, Any] | None) -> dict[str, Any]:
    return config.get("configurable", {}) if isinstance(config, dict) else {}


def emit_agent_step_event(
    config: dict[str, Any] | None,
    *,
    node: str,
    content: str | None,
    round_index: int,
    is_complete: bool,
    step_type: str = "stream",
    findings: list[dict[str, str]] | None = None,
) -> None:
    configurable = get_configurable(config)
    task_id = str(configurable.get("task_id") or "").strip()
    if not task_id:
        return

    callback = configurable.get("agent_step_callback")
    if not callable(callback):
        return

    callback(
        AgentStepEventData(
            task_id=task_id,
            task_kind=str(configurable.get("task_kind") or "generate"),
            step_type=step_type,
            round=round_index,
            node=node,
            content=content,
            findings=findings or [],
            is_complete=is_complete,
        )
    )


__all__ = ["emit_agent_step_event", "get_configurable"]
