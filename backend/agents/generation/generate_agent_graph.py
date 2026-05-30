import asyncio
import time
from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from backend.agents.generation.agent_step_events import (
    emit_agent_step_event,
    get_configurable,
)
from backend.agents.generation.types import GenerationAgentState
from backend.agents.generation.workspace import (
    DRAFT_PATH,
    context_value,
    get_workspace_backend,
    read_generation_context,
    write_backend_text,
)
from backend.prompts.generate_prompt import render_generate_prompt
from backend.prompts.types import GeneratePromptInput
from backend.util.log_util.progress_log import progress_log
from backend.util.common_util import StreamCallbacks, stream_llm_completion

GENERATE_AGENT_NODE = "content_generate_agent"
AGENT_STEP_STREAM_INTERVAL_SECONDS = 0.25
GENERATE_AGENT_ROUND = 1


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


def _get_generation_context(config: dict[str, Any] | None) -> dict[str, Any]:
    context = get_configurable(config).get("generation_agent_context")
    return context if isinstance(context, dict) else {}


def _context_value(
    state: GenerationAgentState,
    config: dict[str, Any] | None,
    key: str,
    default: Any = "",
) -> Any:
    return context_value(state, config, key, default)


def _emit_agent_step_snapshot(
    config: dict[str, Any] | None,
    content: str,
) -> None:
    try:
        emit_agent_step_event(
            config,
            round_index=GENERATE_AGENT_ROUND,
            node=GENERATE_AGENT_NODE,
            content=content,
            is_complete=False,
        )
    except Exception as exc:
        progress_log.debug(f"警告: content_generate_agent 过程回调失败: {exc}")


def _emit_agent_step_complete(
    config: dict[str, Any] | None,
    content: str,
) -> None:
    try:
        emit_agent_step_event(
            config,
            round_index=GENERATE_AGENT_ROUND,
            node=GENERATE_AGENT_NODE,
            content=content,
            is_complete=True,
        )
    except Exception as exc:
        progress_log.debug(f"警告: content_generate_agent 完成回调失败: {exc}")


def _build_stream_callbacks(config: dict[str, Any] | None) -> StreamCallbacks:
    configurable = get_configurable(config)
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


def _text_length(value: Any) -> int:
    return len(str(value or ""))


def _generate_draft(
    state: GenerationAgentState,
    config: RunnableConfig | None = None,
) -> GenerationAgentState:
    backend = get_workspace_backend(config)
    file_context: dict[str, Any] = read_generation_context(backend) if backend else {}
    merged_state: GenerationAgentState = {**file_context, **state}
    tender_type = str(_context_value(merged_state, config, "tender_type", "xjcg") or "xjcg")
    generation_style = str(
        _context_value(merged_state, config, "generation_style", "template") or "template"
    )
    project_info = str(_context_value(merged_state, config, "project_info", "") or "")
    tender_params = _context_value(merged_state, config, "tender_params")
    origin_tender_params = _context_value(merged_state, config, "origin_tender_params")
    log_summary = (
        "[content_generate_agent] prompt 输入摘要: tender_type=%s, generation_style=%s, "
        "project_info_chars=%d, origin_tender_params_chars=%d, tender_params_chars=%d"
    )
    log_args = (
        tender_type,
        generation_style,
        _text_length(project_info),
        _text_length(origin_tender_params),
        _text_length(tender_params),
    )
    all_inputs_empty = (
        _text_length(project_info) == 0
        and _text_length(origin_tender_params) == 0
        and _text_length(tender_params) == 0
    )
    if all_inputs_empty:
        progress_log.warning(log_summary, *log_args)
    else:
        progress_log.debug(log_summary, *log_args)
    rendered_prompt = render_generate_prompt(
        GeneratePromptInput(
            tender_type=tender_type,
            generation_style=generation_style,
            project_info=project_info,
            tender_params=tender_params,
            origin_tender_params=origin_tender_params,
        )
    )
    content = _run_async(
        stream_llm_completion(
            model_provider=str(
                _context_value(merged_state, config, "model_provider", "deepseek") or "deepseek"
            ),
            system_prompt=rendered_prompt.system_prompt,
            user_prompt=rendered_prompt.user_prompt,
            callbacks=_build_stream_callbacks(config),
            check_interval=3.0,
        )
    )
    if backend:
        write_backend_text(backend, DRAFT_PATH, str(content))
        _emit_agent_step_snapshot(config, str(content))
        _emit_agent_step_complete(config, str(content))
        structured_response = {"draft_path": DRAFT_PATH}
    else:
        structured_response = {"draft_text": str(content)}
    return {
        "messages": [AIMessage(content=f"已生成初稿并写入 {DRAFT_PATH}")],
        "structured_response": structured_response,
        **({"draft_path": DRAFT_PATH} if backend else {"draft_text": str(content)}),
    }


def create_generate_agent_graph():
    builder = StateGraph(GenerationAgentState)
    builder.add_node("generate_draft", _generate_draft)
    builder.add_edge(START, "generate_draft")
    builder.add_edge("generate_draft", END)
    return builder.compile()


__all__ = ["create_generate_agent_graph"]
