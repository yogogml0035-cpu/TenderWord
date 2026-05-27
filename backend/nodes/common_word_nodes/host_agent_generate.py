from __future__ import annotations

from backend.agents.generation import run_host_agent_generation
from backend.states.base_state import TenderGraphStateBase


def host_agent_generate(
    state: TenderGraphStateBase,
    config=None,
) -> TenderGraphStateBase:
    """Run the DeepAgents generation branch and expose the standard text contract."""
    result = run_host_agent_generation(state, config)
    return TenderGraphStateBase(
        polished_text=result.polished_text,
        generate_polished_done=True,
    )


__all__ = ["host_agent_generate"]
