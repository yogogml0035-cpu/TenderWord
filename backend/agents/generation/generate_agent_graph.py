import asyncio
import time
from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from backend.agents.generation.types import GenerationAgentState
from backend.models import AgentStepEventData
from backend.prompts.generate_prompt import render_generate_prompt
from backend.prompts.types import GeneratePromptInput
from backend.util.log_util.progress_log import progress_log
from backend.util.common_util import StreamCallbacks, stream_llm_completion

GENERATE_AGENT_NODE = "content_generate_agent"
AGENT_STEP_STREAM_INTERVAL_SECONDS = 0.25


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


def _get_configurable(config: dict[str, Any] | None) -> dict[str, Any]:
    return config.get("configurable", {}) if isinstance(config, dict) else {}


def _get_generation_context(config: dict[str, Any] | None) -> dict[str, Any]:
    context = _get_configurable(config).get("generation_agent_context")
    return context if isinstance(context, dict) else {}


def _context_value(
    state: GenerationAgentState,
    config: dict[str, Any] | None,
    key: str,
    default: Any = "",
) -> Any:
    context = _get_generation_context(config)
    value = context.get(key)
    if value is not None:
        return value
    return state.get(key, default)


def _emit_agent_step_snapshot(
    config: dict[str, Any] | None,
    content: str,
) -> None:
    configurable = _get_configurable(config)
    task_id = str(configurable.get("task_id") or "").strip()
    if not task_id:
        return

    task_kind = str(configurable.get("task_kind") or "generate")
    callback = configurable.get("agent_step_callback")
    event_data = AgentStepEventData(
        task_id=task_id,
        task_kind=task_kind,
        step_type="draft",
        round=0,
        node=GENERATE_AGENT_NODE,
        content=content,
        is_complete=False,
    )
    if callable(callback):
        try:
            callback(event_data)
        except Exception as exc:
            progress_log.debug(f"警告: content_generate_agent 过程回调失败: {exc}")

    try:
        from backend.core.sse_manager import sse_manager

        if getattr(sse_manager, "_loop", None) is not None:
            sse_manager.send_agent_step_threadsafe(
                task_id=task_id,
                task_kind=task_kind,
                step_type=event_data.step_type,
                round=event_data.round,
                node=event_data.node,
                content=event_data.content,
                findings=[],
                is_complete=event_data.is_complete,
            )
    except Exception:
        pass


def _build_stream_callbacks(config: dict[str, Any] | None) -> StreamCallbacks:
    configurable = _get_configurable(config)
    stream_callback = configurable.get("llm_stream_callback")
    suppress_llm_stdout = bool(configurable.get("suppress_llm_stdout", False))
    last_agent_step_at = 0.0
    last_agent_step_content = ""

    def _log_chunk(text: str) -> None:
        if suppress_llm_stdout:
            return
        progress_log.debug(text)

    def _on_update(text: str) -> None:
        nonlocal last_agent_step_at, last_agent_step_content
        snapshot = str(text or "")
        if callable(stream_callback):
            try:
                stream_callback(snapshot)
            except Exception as exc:
                progress_log.debug(f"警告: content_generate_agent LLM 流式回调失败: {exc}")

        now = time.monotonic()
        if (
            snapshot
            and snapshot != last_agent_step_content
            and now - last_agent_step_at >= AGENT_STEP_STREAM_INTERVAL_SECONDS
        ):
            _emit_agent_step_snapshot(config, snapshot)
            last_agent_step_at = now
            last_agent_step_content = snapshot

    return StreamCallbacks(on_chunk=_log_chunk, on_update=_on_update)


def _generate_draft(
    state: GenerationAgentState,
    config: RunnableConfig | None = None,
) -> GenerationAgentState:
    rendered_prompt = render_generate_prompt(
        GeneratePromptInput(
            tender_type=str(_context_value(state, config, "tender_type", "xjcg") or "xjcg"),
            generation_style=str(
                _context_value(state, config, "generation_style", "template") or "template"
            ),
            project_info=str(_context_value(state, config, "project_info", "") or ""),
            tender_params=_context_value(state, config, "tender_params"),
            origin_tender_params=_context_value(state, config, "origin_tender_params"),
        )
    )
    content = _run_async(
        stream_llm_completion(
            model_provider=str(
                _context_value(state, config, "model_provider", "deepseek") or "deepseek"
            ),
            system_prompt=rendered_prompt.system_prompt,
            user_prompt=rendered_prompt.user_prompt,
            callbacks=_build_stream_callbacks(config),
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
