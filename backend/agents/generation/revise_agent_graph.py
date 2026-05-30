import asyncio
import json
from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from backend.agents.generation.agent_step_events import emit_agent_step_event
from backend.agents.generation.types import GenerationAgentState
from backend.agents.generation.workspace import (
    audit_path,
    context_value,
    get_workspace_backend,
    infer_current_text_path,
    infer_next_revision_round,
    read_backend_text,
    revision_path,
    write_backend_text,
)
from backend.util.common_util import StreamCallbacks, stream_llm_completion
from backend.util.log_util.progress_log import progress_log


REVISE_AGENT_NODE = "content_revise_agent"
CHECK_INTERVAL = 3.0
REVISE_SYSTEM_PROMPT = """
你是招标文件采购需求修订智能体 content_revise_agent。

硬性规则：
1. 只根据 /audits/round-N.json 中的 evidence 与 fix_hint 修复对应位置。
2. 未被 audit 指定的位置必须逐字保留，不得润色、扩写、删减或重排。
3. 输出必须是修订后的完整采购需求正文，不要输出解释、Markdown 代码块或 JSON。
4. 如果 audit 为 []，直接返回“无需修订”，不得输出或重写当前正文。
""".strip()


def _emit_revise_agent_step_snapshot(
    config: dict[str, Any] | None,
    *,
    content: str,
    round_index: int,
    is_complete: bool,
) -> None:
    try:
        emit_agent_step_event(
            config,
            round_index=round_index,
            node=REVISE_AGENT_NODE,
            content=content,
            is_complete=is_complete,
        )
    except Exception as exc:
        progress_log.debug(f"警告: content_revise_agent 过程回调失败: {exc}")


def _build_stream_callbacks(
    config: dict[str, Any] | None,
    *,
    round_index: int,
) -> StreamCallbacks:
    def _on_update(text: str) -> None:
        snapshot = str(text or "")
        if not snapshot:
            return
        _emit_revise_agent_step_snapshot(
            config,
            content=snapshot,
            round_index=round_index,
            is_complete=False,
        )

    return StreamCallbacks(on_update=_on_update)


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    raise RuntimeError("revise_agent cannot run inside an active event loop")


def _render_revise_user_prompt(
    *,
    current_text: str,
    audit_json: str,
) -> str:
    return (
        "请按审核 JSON 对【当前正文】做最小必要修复。\n"
        "除 evidence/fix_hint 明确指定的位置外，其它内容必须逐字保留。\n\n"
        f"【审核 JSON】\n{audit_json}\n\n"
        f"【当前正文】\n{current_text}"
    )


def _revise_text(
    state: GenerationAgentState,
    config: RunnableConfig | None = None,
) -> GenerationAgentState:
    backend = get_workspace_backend(config)
    if backend:
        round_index = int(
            context_value(state, config, "revision_round", 0)
            or infer_next_revision_round(backend)
        )
        current_text_path = str(
            context_value(state, config, "current_text_path")
            or infer_current_text_path(backend)
        )
        current_text = read_backend_text(backend, current_text_path)
        raw_audit = read_backend_text(backend, audit_path(round_index))
    else:
        round_index = int(context_value(state, config, "revision_round", 1) or 1)
        current_text = str(context_value(state, config, "current_text", "") or "")
        raw_audit = json.dumps(
            context_value(state, config, "audit_findings", []) or [],
            ensure_ascii=False,
        )

    try:
        audit_items = json.loads(raw_audit)
    except json.JSONDecodeError:
        audit_items = [{"evidence": "审核 JSON 格式异常", "fix_hint": "保持当前正文不变"}]

    if audit_items == []:
        _emit_revise_agent_step_snapshot(
            config,
            content="无需修订",
            round_index=round_index,
            is_complete=True,
        )
        return {
            "messages": [AIMessage(content="无需修订")],
            "structured_response": {
                "status": "no_revision",
                "message": "无需修订",
            },
            "no_revision": True,
        }

    revised_text = str(
        _run_async(
            stream_llm_completion(
                model_provider=str(context_value(state, config, "model_provider", "deepseek") or "deepseek"),
                system_prompt=REVISE_SYSTEM_PROMPT,
                user_prompt=_render_revise_user_prompt(
                    current_text=current_text,
                    audit_json=raw_audit,
                ),
                callbacks=_build_stream_callbacks(config, round_index=round_index),
                check_interval=CHECK_INTERVAL,
            )
        )
    )

    if backend:
        write_backend_text(backend, revision_path(round_index), revised_text)
        _emit_revise_agent_step_snapshot(
            config,
            content=revised_text,
            round_index=round_index,
            is_complete=True,
        )

    return {
        "messages": [AIMessage(content=f"已修订正文并写入 {revision_path(round_index)}")],
        "structured_response": {"revision_path": revision_path(round_index)},
        "revision_path": revision_path(round_index),
        **({} if backend else {"polished_text": revised_text}),
    }


def create_revise_agent_graph():
    builder = StateGraph(GenerationAgentState)
    builder.add_node("revise_text", _revise_text)
    builder.add_edge(START, "revise_text")
    builder.add_edge("revise_text", END)
    return builder.compile()


__all__ = ["REVISE_SYSTEM_PROMPT", "create_revise_agent_graph"]
