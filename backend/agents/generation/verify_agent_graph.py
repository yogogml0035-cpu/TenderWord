from __future__ import annotations

import asyncio
import json

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph

from backend.agents.generation.json_utils import (
    build_audit_findings_fallback,
    coerce_audit_findings,
    parse_audit_findings,
)
from backend.agents.generation.types import (
    AuditFinding,
    GenerationAgentProtocolError,
    GenerationAgentState,
)
from backend.util.common_util import StreamCallbacks, stream_llm_completion


CHECK_INTERVAL = 3.0
VERIFY_JSON_REPAIR_RETRY_LIMIT = 1
VERIFY_JSON_REPAIR_TEMPERATURE = 0.1
VERIFY_SYSTEM_PROMPT = (
    "你是招标文件采购需求审核智能体。必须只输出严格合法的 JSON 数组，不要输出解释、Markdown 或代码块。"
    "数组每项必须是对象，并且必须包含两个非空字符串字段："
    "evidence（指出待审核正文中的具体问题或缺漏证据）和 "
    "fix_hint（说明最小必要修复方式）。"
    "没有问题时输出 []。示例："
    '[{"evidence":"正文缺少质保期限要求","fix_hint":"补充与技术参数一致的质保期限，保持其它内容不变"}]。'
)
VERIFY_JSON_REPAIR_SYSTEM_PROMPT = (
    "你是 JSON 修复助手。只把输入修复为严格合法的 JSON 数组。"
    "数组每项必须包含非空字符串 evidence 和 fix_hint。禁止新增审核问题，禁止解释。"
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


def _contract_error_needs_retry(error: BaseException) -> bool:
    message = str(error)
    return any(
        marker in message
        for marker in ("缺少 evidence", "必须是对象", "必须是 JSON 数组")
    )

def _render_json_repair_prompt(raw_content: str, error: BaseException) -> str:
    return (
        "请修复下面的审核智能体输出，使其成为严格合法的 JSON 数组。\n"
        "输出规则：\n"
        "1. 只输出 JSON 数组本身，不要解释，不要代码块。\n"
        "2. 每一项必须包含非空字符串字段 evidence 和 fix_hint。\n"
        "3. 不要新增原输出中没有表达的审核问题；只能补齐字段名、数组包裹、引号、逗号、转义和缺失字段。\n"
        "4. 如果某项只有 evidence，请根据 evidence 写最小修复建议；如果某项只有 fix_hint，"
        "请把该建议概括为 evidence，同时保留 fix_hint。\n"
        "5. 如果原输出表达“没有问题”，请输出 []。\n\n"
        f"解析错误：{error}\n\n"
        f"原始输出：\n{raw_content}"
    )

def _request_json_repair(
    raw_content: str,
    *,
    error: BaseException,
    model_provider: str,
) -> str:
    return str(
        _run_async(
            stream_llm_completion(
                model_provider=model_provider,
                system_prompt=VERIFY_JSON_REPAIR_SYSTEM_PROMPT,
                user_prompt=_render_json_repair_prompt(raw_content, error),
                callbacks=StreamCallbacks(),
                extra_params_override={"temperature": VERIFY_JSON_REPAIR_TEMPERATURE},
                check_interval=CHECK_INTERVAL,
            )
        )
    )

def _parse_or_repair_audit_findings(
    raw_content: str,
    *,
    model_provider: str,
) -> list[AuditFinding]:
    try:
        return parse_audit_findings(raw_content)
    except GenerationAgentProtocolError as first_error:
        last_error: BaseException = first_error

    if _contract_error_needs_retry(last_error):
        try:
            repaired_content = _request_json_repair(
                raw_content,
                error=last_error,
                model_provider=model_provider,
            )
            return coerce_audit_findings(repaired_content)
        except Exception as exc:
            last_error = exc

    try:
        return coerce_audit_findings(raw_content)
    except GenerationAgentProtocolError as exc:
        last_error = exc

    for _ in range(VERIFY_JSON_REPAIR_RETRY_LIMIT):
        try:
            repaired_content = _request_json_repair(
                raw_content,
                error=last_error,
                model_provider=model_provider,
            )
            return coerce_audit_findings(repaired_content)
        except Exception as exc:
            last_error = exc

    return build_audit_findings_fallback(last_error)

def _verify_text(state: GenerationAgentState) -> GenerationAgentState:
    current_text = str(state.get("current_text") or state.get("draft_text") or "")
    model_provider = str(state.get("model_provider") or "deepseek")
    user_prompt = (
        "请审核以下采购需求正文是否存在明显缺漏、矛盾或不符合技术参数的问题。\n\n"
        "输出必须是严格 JSON 数组：[] 或 "
        '[{"evidence":"...","fix_hint":"..."}]。'
        "不要输出解释、Markdown、代码块或其它字段。\n\n"
        f"技术参数：{state.get('origin_tender_params') or ''}\n\n"
        f"待审核正文：\n{current_text}"
    )
    raw_content = _run_async(
        stream_llm_completion(
            model_provider=model_provider,
            system_prompt=VERIFY_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            callbacks=StreamCallbacks(),
            check_interval=CHECK_INTERVAL,
        )
    )
    findings = _parse_or_repair_audit_findings(
        str(raw_content),
        model_provider=model_provider,
    )
    findings_payload = [finding.model_dump() for finding in findings]
    findings_json = json.dumps(findings_payload, ensure_ascii=False)
    return {
        "messages": [AIMessage(content=findings_json)],
        "structured_response": findings_payload,
        "findings": findings_payload,
    }


def create_verify_agent_graph():
    builder = StateGraph(GenerationAgentState)
    builder.add_node("verify_text", _verify_text)
    builder.add_edge(START, "verify_text")
    builder.add_edge("verify_text", END)
    return builder.compile()


__all__ = [
    "VERIFY_JSON_REPAIR_SYSTEM_PROMPT",
    "VERIFY_SYSTEM_PROMPT",
    "create_verify_agent_graph",
]
