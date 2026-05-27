from __future__ import annotations

import asyncio

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph

from backend.agents.generation.types import GenerationAgentState
from backend.prompts.generate_prompt import render_generate_prompt
from backend.prompts.types import GeneratePromptInput
from backend.util.common_util import StreamCallbacks, stream_llm_completion


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    raise RuntimeError("generate_agent cannot run inside an active event loop")


def _generate_draft(state: GenerationAgentState) -> GenerationAgentState:
    rendered_prompt = render_generate_prompt(
        GeneratePromptInput(
            tender_type=str(state.get("tender_type") or "xjcg"),
            generation_style=str(state.get("generation_style") or "template"),
            project_info=str(state.get("project_info") or ""),
            tender_params=state.get("tender_params"),
            origin_tender_params=state.get("origin_tender_params"),
        )
    )
    content = _run_async(
        stream_llm_completion(
            model_provider=str(state.get("model_provider") or "deepseek"),
            system_prompt=rendered_prompt.system_prompt,
            user_prompt=rendered_prompt.user_prompt,
            callbacks=StreamCallbacks(),
            check_interval=3.0,
        )
    )
    return {
        "messages": [AIMessage(content=str(content))],
        "structured_response": {"draft_text": str(content)},
        "draft_text": str(content),
    }


def create_generate_agent_graph():
    builder = StateGraph(GenerationAgentState)
    builder.add_node("generate_draft", _generate_draft)
    builder.add_edge(START, "generate_draft")
    builder.add_edge("generate_draft", END)
    return builder.compile()


__all__ = ["create_generate_agent_graph"]
