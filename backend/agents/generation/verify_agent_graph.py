from __future__ import annotations

import asyncio

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph

from backend.agents.generation.json_utils import parse_audit_findings
from backend.agents.generation.types import GenerationAgentState
from backend.util.common_util import StreamCallbacks, stream_llm_completion


VERIFY_SYSTEM_PROMPT = (
    "你是招标文件采购需求审核智能体。只输出 JSON 数组，不要输出解释。"
    "数组每项必须包含 evidence 和 fix_hint。没有问题时输出 []。"
)


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    raise RuntimeError("verify_agent cannot run inside an active event loop")


def _verify_text(state: GenerationAgentState) -> GenerationAgentState:
    current_text = str(state.get("current_text") or state.get("draft_text") or "")
    user_prompt = (
        "请审核以下采购需求正文是否存在明显缺漏、矛盾或不符合技术参数的问题。\n\n"
        f"招标类型：{state.get('tender_type') or 'xjcg'}\n"
        f"项目资料：{state.get('project_info') or ''}\n"
        f"技术参数：{state.get('origin_tender_params') or ''}\n\n"
        f"待审核正文：\n{current_text}"
    )
    raw_content = _run_async(
        stream_llm_completion(
            model_provider=str(state.get("model_provider") or "deepseek"),
            system_prompt=VERIFY_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            callbacks=StreamCallbacks(),
            check_interval=3.0,
        )
    )
    findings = parse_audit_findings(str(raw_content))
    return {
        "messages": [AIMessage(content=str(raw_content))],
        "structured_response": [finding.model_dump() for finding in findings],
        "findings": [finding.model_dump() for finding in findings],
    }


def create_verify_agent_graph():
    builder = StateGraph(GenerationAgentState)
    builder.add_node("verify_text", _verify_text)
    builder.add_edge(START, "verify_text")
    builder.add_edge("verify_text", END)
    return builder.compile()


__all__ = ["VERIFY_SYSTEM_PROMPT", "create_verify_agent_graph"]
