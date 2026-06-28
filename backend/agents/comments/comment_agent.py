from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol

from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool

from backend.agents.comments.tools import (
    CommentAgentToolContext,
    create_comment_agent_tools,
    normalize_comment_candidates,
    validate_comment_reference_candidates,
    write_validated_comment_candidates_to_word,
)
from backend.agents.comments.types import (
    COMMENT_AGENT_NODE,
    VALIDATE_COMMENT_REFERENCES_TOOL,
    WRITE_VALIDATED_COMMENTS_TOOL,
    CommentAgentAuditPayload,
    CommentAgentResult,
    CommentAgentToolSnapshot,
    CommentValidationResult,
)
from backend.agents.comments.workspace import write_comment_agent_audit_log
from backend.agents.generation.model_factory import create_generation_chat_model
from backend.agents.generation.types import AgentStepPayload
from backend.nodes.common_word_nodes.comment_writeback import CommentWritebackResult
from backend.util.log_util.progress_log import progress_log

COMMENT_AGENT_SYSTEM_PROMPT = """
你是批注锚点智能体 comment_agent，只负责提交批注候选的首版校验，不做多轮修复。

硬性规则：
1. 必须先调用 validate_comment_references，把当前 proposed_comments 作为工具参数提交；校验工具只能调用 1 次。
2. 同 index 的 comment_text 必须和初始 JSON 完全一致，不得改写、润色、删减或新增批注意见。
3. reference_text 必须精确来自 polished_text，连续、逐字、原标点一致，不得跨段拼接；不得改写正文或凭空新增批注。
4. 校验完成后最多调用 1 次 write_validated_comments_to_word 提交最终候选；该工具不直接写 Word，真正写入由运行时在 graph 节点线程执行。重复锚点由写回层确定性扩展，不需要你再修复。
5. 最终只输出简短中文结果摘要，不展示工具消息或排障细节。
""".strip()

COMMENT_AGENT_GENERATION_SYSTEM_PROMPT = """
你是批注生成智能体 comment_agent，负责生成批注候选首版，再校验锚点并提交写回，不做多轮修复。

硬性规则：
1. 先在内部基于 polished_text 和批注生成规则生成 proposed_comments，元素只能包含 reference_text 与 comment_text。
2. 严禁把 proposed_comments、JSON 数组、候选清单或推理过程写在普通回复正文里；候选只能作为工具参数提交。
3. 生成首版候选后，必须调用 validate_comment_references，把完整 proposed_comments 放入工具参数；校验工具只能调用 1 次。如果未发现任何候选，也必须用 proposed_comments=[] 调用该工具。
4. 同 index 的 comment_text 在校验后不得改写、润色、删减或新增；reference_text 必须精确来自 polished_text，连续、逐字、原标点一致。
5. 校验完成后必须调用 1 次 write_validated_comments_to_word，把最终 proposed_comments 作为工具参数提交；该工具不直接写 Word，真正写入由运行时在 graph 节点线程执行。重复锚点由写回层确定性扩展，不需要你再修复。
6. 工具提交完成后，最终只输出简短中文结果摘要，不展示工具消息、候选 JSON 或排障细节。
""".strip()

NO_VALID_GENERATED_COMMENTS_NOTICE = (
    "模型未通过工具提交有效批注候选，已跳过 Word 批注写入。"
)

class CommentAgentRunner(Protocol):
    def invoke(
        self,
        payload: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any] | str:
        ...

_fake_runner: CommentAgentRunner | None = None

def set_comment_agent_runner(runner: CommentAgentRunner | None) -> None:
    global _fake_runner
    _fake_runner = runner

def build_comment_agent_middleware() -> list[ToolCallLimitMiddleware]:
    return [
        ToolCallLimitMiddleware(
            tool_name=VALIDATE_COMMENT_REFERENCES_TOOL,
            run_limit=1,
            exit_behavior="error",
        ),
        ToolCallLimitMiddleware(
            tool_name=WRITE_VALIDATED_COMMENTS_TOOL,
            run_limit=1,
            exit_behavior="error",
        ),
    ]

def create_comment_agent_runner(
    model_provider: str,
    *,
    tools: list[BaseTool],
    allow_comment_generation: bool = False,
) -> CommentAgentRunner:
    return create_agent(
        model=create_generation_chat_model(model_provider),
        tools=tools,
        system_prompt=(
            COMMENT_AGENT_GENERATION_SYSTEM_PROMPT
            if allow_comment_generation
            else COMMENT_AGENT_SYSTEM_PROMPT
        ),
        middleware=build_comment_agent_middleware(),
        name=COMMENT_AGENT_NODE,
    )

def _message_text(message: Any) -> str:
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

def _is_ai_message(message: Any) -> bool:
    if isinstance(message, AIMessage):
        return True
    if isinstance(message, ToolMessage):
        return False
    return message.__class__.__name__ in {"AIMessage", "AIMessageChunk"}

def _iter_messages(value: Any) -> Iterable[Any]:
    if value is None:
        return
    if isinstance(value, BaseMessage):
        yield value
        return
    if isinstance(value, tuple) and value:
        yield from _iter_messages(value[0])
        return
    if isinstance(value, list):
        for item in value:
            yield from _iter_messages(item)
        return
    if isinstance(value, dict):
        if "messages" in value:
            yield from _iter_messages(value.get("messages"))
        for node_value in value.values():
            if isinstance(node_value, dict) and "messages" in node_value:
                yield from _iter_messages(node_value.get("messages"))

def _emit_ai_messages(
    value: Any,
    *,
    ai_messages: list[str],
) -> None:
    for message in _iter_messages(value):
        if not _is_ai_message(message):
            continue
        content = _message_text(message).strip()
        if not content:
            continue
        ai_messages.append(content)


STATUS_LABELS = {
    "passed": "通过",
    "failed": "需修复",
    "fixed": "已修复",
    "skipped": "已跳过",
}

REASON_LABELS = {
    "passed": "锚点已通过校验",
    "reference_text_non_unique_will_expand_on_writeback": "锚点在正文中出现多处，写回时将确定性扩展",
    "reference_text_not_found_in_polished_text": "当前锚点未在最终正文中精确匹配",
    "comment_text_changed": "批注意见被改写，已拒绝",
    "missing_candidate": "缺少对应批注候选",
    "missing_reference_text": "缺少当前锚点文本",
    "unexpected_candidate": "存在多余批注候选",
    "missing_initial_reference_or_comment_text": "原始锚点或批注意见为空，已跳过",
    "reference_text_not_found": "当前锚点未在 Word 写入范围内匹配",
    "reference_text_not_found_in_word_bound": "当前锚点未在 Word 写入范围内匹配",
    "reference_text_not_unique_in_word_bound": "当前锚点在 Word 写入范围内出现多处",
    "normalized_reference_not_unique": "规范化匹配在范围内命中多处，已跳过",
    "overlapping_comment_exists": "目标位置已有批注，已跳过",
    "comment_add_failed": "Word 批注写入失败",
    "missing_word_document": "缺少 Word 文档实例",
}

ROUND_LABELS = {
    1: "首版锚点校验",
    2: "第 2 轮锚点校验",
}


def _reason_label(reason: str) -> str:
    return REASON_LABELS.get(str(reason or ""), str(reason or "未知原因"))


def _status_label(status: str, *, fixed: bool = False) -> str:
    if fixed:
        return STATUS_LABELS["fixed"]
    return STATUS_LABELS.get(str(status or ""), str(status or ""))


def _issue_to_highlight(issue: Any, *, fixed: bool = False) -> dict[str, Any]:
    return {
        "index": int(getattr(issue, "index", 0) or 0),
        "status": _status_label(str(getattr(issue, "status", "")), fixed=fixed),
        "reason": _reason_label(str(getattr(issue, "reason", ""))),
        "original_reference_text": str(getattr(issue, "original_reference_text", "") or ""),
        "reference_text": str(getattr(issue, "reference_text", "") or ""),
        "candidate_fragments": [
            str(item)
            for item in (getattr(issue, "candidate_fragments", []) or [])
            if str(item)
        ],
    }


def _round_highlights(
    snapshot: CommentAgentToolSnapshot,
    previous_snapshot: CommentAgentToolSnapshot | None = None,
) -> list[dict[str, Any]]:
    previous_failed_indexes = {
        item.index
        for item in (previous_snapshot.validation.failed if previous_snapshot else [])
    }
    highlights = [
        _issue_to_highlight(issue)
        for issue in [*snapshot.validation.failed, *snapshot.validation.skipped]
    ]
    for issue in snapshot.validation.passed:
        if issue.index in previous_failed_indexes:
            highlights.append(_issue_to_highlight(issue, fixed=True))
    return highlights


def _snapshot_to_round(
    snapshot: CommentAgentToolSnapshot,
    previous_snapshot: CommentAgentToolSnapshot | None = None,
) -> dict[str, Any]:
    return {
        "round": snapshot.round,
        "label": ROUND_LABELS.get(snapshot.round, f"第 {snapshot.round} 轮锚点校验"),
        "passed": snapshot.validation.passed_count,
        "failed": snapshot.validation.failed_count,
        "skipped": snapshot.validation.skipped_count,
        "highlights": _round_highlights(snapshot, previous_snapshot),
    }


def _snapshots_to_rounds(snapshots: list[CommentAgentToolSnapshot] | None) -> list[dict[str, Any]]:
    rounds: list[dict[str, Any]] = []
    previous: CommentAgentToolSnapshot | None = None
    for snapshot in list(snapshots or [])[:2]:
        rounds.append(_snapshot_to_round(snapshot, previous))
        previous = snapshot
    return rounds


def _validation_to_round(validation: CommentValidationResult) -> dict[str, Any]:
    return {
        "round": 0,
        "label": "最终静默复校验",
        "passed": validation.passed_count,
        "failed": validation.failed_count,
        "skipped": validation.skipped_count,
        "highlights": [
            _issue_to_highlight(issue)
            for issue in [*validation.failed, *validation.skipped]
        ],
    }


def _writeback_to_structured(writeback_result: CommentWritebackResult) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    for item in list(writeback_result.get("issues") or []):
        if not isinstance(item, dict):
            continue
        issues.append(
            {
                "index": int(item.get("index") or 0),
                "status": "已跳过" if item.get("reason") == "overlapping_comment_exists" else "需修复",
                "reason": _reason_label(str(item.get("reason") or "")),
                "original_reference_text": "",
                "reference_text": str(item.get("reference_text") or ""),
                "candidate_fragments": [],
            }
        )
    return {
        "attempted": int(writeback_result.get("attempted") or 0),
        "added": int(writeback_result.get("added") or 0),
        "failed": int(writeback_result.get("failed") or 0),
        "skipped": int(writeback_result.get("skipped") or 0),
        "issues": issues,
    }


def _build_comment_agent_payload(
    *,
    phase: str,
    validation: CommentValidationResult | None = None,
    writeback_result: CommentWritebackResult | None = None,
    snapshots: list[CommentAgentToolSnapshot] | None = None,
    current_snapshot: CommentAgentToolSnapshot | None = None,
    notice: str | None = None,
) -> dict[str, Any]:
    visible_snapshots = list(snapshots or [])
    if current_snapshot is not None:
        visible_snapshots = [
            snapshot
            for snapshot in visible_snapshots
            if snapshot.round != current_snapshot.round
        ]
    rounds = _snapshots_to_rounds(visible_snapshots)
    current_round = None
    if current_snapshot is not None:
        previous = None
        for snapshot in list(snapshots or []):
            if snapshot.round >= current_snapshot.round:
                break
            previous = snapshot
        current_round = _snapshot_to_round(current_snapshot, previous)
        rounds = [*rounds, current_round][:2]

    payload: dict[str, Any] = {
        "phase": phase,
        "rounds": rounds,
        "highlights": current_round["highlights"] if current_round else [],
    }
    if notice:
        payload["notice"] = notice
    if validation is not None:
        payload["final_validation"] = _validation_to_round(validation)
    if writeback_result is not None:
        payload["writeback"] = _writeback_to_structured(writeback_result)
    return payload


def _format_issue_line(issue: Any, *, fixed: bool = False) -> str:
    fragments = getattr(issue, "candidate_fragments", []) or []
    fragment_text = ""
    if fragments:
        fragment_text = "；候选片段：" + " / ".join(str(item) for item in fragments)
    return (
        f"- #{issue.index} {_status_label(issue.status, fixed=fixed)}: "
        f"原始锚点「{issue.original_reference_text}」 -> "
        f"当前锚点「{issue.reference_text}」；原因：{_reason_label(issue.reason)}{fragment_text}"
    )


def _format_tool_snapshot(
    snapshot: CommentAgentToolSnapshot,
    previous_snapshot: CommentAgentToolSnapshot | None = None,
) -> str:
    validation = snapshot.validation
    lines = [
        ROUND_LABELS.get(snapshot.round, f"第 {snapshot.round} 轮锚点校验"),
        f"通过 {validation.passed_count} 条，失败 {validation.failed_count} 条，跳过 {validation.skipped_count} 条。",
    ]
    for issue in [*validation.failed, *validation.skipped]:
        lines.append(_format_issue_line(issue))
    previous_failed_indexes = {
        item.index
        for item in (previous_snapshot.validation.failed if previous_snapshot else [])
    }
    for issue in validation.passed:
        if issue.index in previous_failed_indexes:
            lines.append(_format_issue_line(issue, fixed=True))
    return "\n".join(lines)


def _format_final_snapshot(
    *,
    validation: CommentValidationResult,
    writeback_result: CommentWritebackResult,
    snapshots: list[CommentAgentToolSnapshot] | None = None,
    error: str | None = None,
) -> str:
    if error:
        detail = (
            "comment_agent 已结束，批注写入降级为 warning。\n"
            f"原因：{error}"
        )
        if snapshots:
            previous_snapshot: CommentAgentToolSnapshot | None = None
            blocks = []
            for item in snapshots[:2]:
                blocks.append(_format_tool_snapshot(item, previous_snapshot))
                previous_snapshot = item
            return "\n\n".join([*blocks, detail])
        return detail

    final_stats = (
        "comment_agent 最终写入统计\n"
        f"校验通过 {validation.passed_count} 条，失败 {validation.failed_count} 条，跳过 {validation.skipped_count} 条。\n"
        f"Word 写入尝试 {int(writeback_result.get('attempted') or 0)} 条，"
        f"成功 {int(writeback_result.get('added') or 0)} 条，"
        f"失败 {int(writeback_result.get('failed') or 0)} 条，"
        f"跳过 {int(writeback_result.get('skipped') or 0)} 条。"
    )
    if snapshots:
        previous_snapshot: CommentAgentToolSnapshot | None = None
        blocks = []
        for item in snapshots[:2]:
            blocks.append(_format_tool_snapshot(item, previous_snapshot))
            previous_snapshot = item
        return "\n\n".join([*blocks, final_stats])
    return final_stats


def _emit_tool_snapshots(
    *,
    context: CommentAgentToolContext,
    emitted_count: int,
    step_callback: Callable[[AgentStepPayload], None] | None,
) -> int:
    if step_callback is None:
        return len(context.tool_snapshots)

    visible_snapshots = context.tool_snapshots[:2]
    previous_snapshot = visible_snapshots[emitted_count - 1] if emitted_count > 0 else None
    for snapshot in visible_snapshots[emitted_count:]:
        step_callback(
            AgentStepPayload(
                step_type="tool_snapshot",
                round=1,
                node=COMMENT_AGENT_NODE,
                content=_format_tool_snapshot(snapshot, previous_snapshot),
                comment_agent=_build_comment_agent_payload(
                    phase="validation_round",
                    snapshots=visible_snapshots[: snapshot.round - 1],
                    current_snapshot=snapshot,
                ),
                is_complete=False,
            )
        )
        previous_snapshot = snapshot
    return len(visible_snapshots)


def _emit_final_snapshot(
    *,
    validation: CommentValidationResult,
    writeback_result: CommentWritebackResult,
    snapshots: list[CommentAgentToolSnapshot] | None = None,
    step_callback: Callable[[AgentStepPayload], None] | None,
    round_number: int,
    error: str | None = None,
) -> None:
    if step_callback is None:
        return
    step_callback(
        AgentStepPayload(
            step_type="final",
            round=1,
            node=COMMENT_AGENT_NODE,
            content=_format_final_snapshot(
                validation=validation,
                writeback_result=writeback_result,
                snapshots=snapshots,
                error=error,
            ),
            comment_agent=_build_comment_agent_payload(
                phase="final",
                validation=validation,
                writeback_result=writeback_result,
                snapshots=snapshots,
                notice=error,
            ),
            is_complete=True,
        )
    )

def _runner_supports_stream(runner: CommentAgentRunner) -> bool:
    return callable(getattr(runner, "stream", None))

def _stream_runner(
    runner: CommentAgentRunner,
    payload: dict[str, Any],
    config: dict[str, Any],
    *,
    context: CommentAgentToolContext,
    ai_messages: list[str],
    step_callback: Callable[[AgentStepPayload], None] | None,
) -> Any:
    final_chunk: Any = None
    emitted_snapshot_count = 0
    try:
        stream = runner.stream(  # type: ignore[attr-defined]
            payload,
            config,
            stream_mode=["messages", "updates"],
        )
    except TypeError:
        stream = runner.stream(payload, config)  # type: ignore[attr-defined]

    for chunk in stream:
        final_chunk = chunk
        if isinstance(chunk, tuple):
            if len(chunk) == 2:
                _emit_ai_messages(
                    chunk[1],
                    ai_messages=ai_messages,
                )
            elif len(chunk) == 3:
                _emit_ai_messages(
                    chunk[2],
                    ai_messages=ai_messages,
                )
            emitted_snapshot_count = _emit_tool_snapshots(
                context=context,
                emitted_count=emitted_snapshot_count,
                step_callback=step_callback,
            )
            continue
        _emit_ai_messages(
            chunk,
            ai_messages=ai_messages,
        )
        emitted_snapshot_count = _emit_tool_snapshots(
            context=context,
            emitted_count=emitted_snapshot_count,
            step_callback=step_callback,
        )
    _emit_tool_snapshots(
        context=context,
        emitted_count=emitted_snapshot_count,
        step_callback=step_callback,
    )
    return final_chunk

def _build_runner_config(
    config: dict[str, Any] | None,
    *,
    context: CommentAgentToolContext,
) -> dict[str, Any]:
    next_config = {**config} if isinstance(config, dict) else {}
    configurable = next_config.get("configurable", {})
    configurable = {**configurable} if isinstance(configurable, dict) else {}
    configurable["comment_agent_tool_context"] = context
    next_config["configurable"] = configurable
    return next_config

def _build_user_prompt(
    *,
    initial_comments: list[dict[str, str]],
    polished_text: str,
    allow_comment_generation: bool = False,
    comment_generation_instruction: str | None = None,
) -> str:
    if allow_comment_generation and not initial_comments:
        generation_instruction = str(comment_generation_instruction or "").strip()
        instruction_block = (
            f"【批注生成规则】\n{generation_instruction}\n\n"
            if generation_instruction
            else ""
        )
        return (
            "请直接接手批注生成任务：先生成批注候选 proposed_comments，"
            "但不要在普通回复正文中输出候选、JSON 或推理过程；"
            "必须把完整 proposed_comments 作为 validate_comment_references 的工具参数提交，"
            "再调用工具完成首版校验和最终候选提交。"
            "Word 写入由运行时完成，工具线程不会直接操作 Word；重复锚点由写回层确定性扩展，无需修复。\n\n"
            f"{instruction_block}"
            "【polished_text】\n"
            f"{polished_text}"
        )

    return (
        "请提交以下批注候选的首版校验，并用工具完成校验与最终候选提交。"
        "Word 写入由运行时完成，工具线程不会直接操作 Word；重复锚点由写回层确定性扩展，无需修复。\n\n"
        "【初始批注 JSON】\n"
        f"{json.dumps(initial_comments, ensure_ascii=False, indent=2)}\n\n"
        "【polished_text】\n"
        f"{polished_text}"
    )

def _default_writeback_result(validation: CommentValidationResult) -> CommentWritebackResult:
    return {
        "total": len(validation.passed),
        "attempted": 0,
        "added": 0,
        "failed": len(validation.failed),
        "skipped": len(validation.skipped),
        "issues": [
            {
                "index": issue.index,
                "reason": issue.reason,
                "reference_text": issue.reference_text,
                "comment_text": issue.comment_text,
            }
            for issue in [*validation.failed, *validation.skipped]
        ],
    }

def _build_audit_payload(
    *,
    task_id: str,
    notice: str | None = None,
    initial_comments: list[dict[str, str]],
    ai_messages: list[str],
    validation: CommentValidationResult,
    validation_results: list[dict[str, Any]],
    tool_snapshots: list[dict[str, Any]],
    final_proposed_comments: list[dict[str, str]],
    writeback_result: CommentWritebackResult,
) -> CommentAgentAuditPayload:
    payload: CommentAgentAuditPayload = {
        "task_id": task_id,
        "initial_comments": initial_comments,
        "ai_messages": ai_messages,
        "validation_results": validation_results,
        "tool_snapshots": tool_snapshots,
        "final_proposed_comments": final_proposed_comments,
        "final_passed": [item.model_dump(mode="json") for item in validation.passed],
        "final_failed": [item.model_dump(mode="json") for item in validation.failed],
        "final_skipped": [item.model_dump(mode="json") for item in validation.skipped],
        "writeback_result": writeback_result,
    }
    if notice:
        payload["notice"] = notice
    return payload

def run_comment_agent(
    *,
    initial_comments: list[dict[str, Any]],
    polished_text: str,
    doc: Any | None = None,
    bound_start: int = 0,
    bound_end: int | None = None,
    model_provider: str = "deepseek",
    task_id: str = "comment-agent",
    config: dict[str, Any] | None = None,
    runner: CommentAgentRunner | None = None,
    step_callback: Callable[[AgentStepPayload], None] | None = None,
    audit_log_path: str | Path | None = None,
    project_number: str | None = None,
    project_name: str | None = None,
    allow_comment_generation: bool = False,
    comment_generation_instruction: str | None = None,
) -> CommentAgentResult:
    normalized_initial = [
        item.model_dump(mode="json")
        for item in normalize_comment_candidates(initial_comments)
    ]
    context = CommentAgentToolContext(
        initial_comments=normalized_initial,
        polished_text=str(polished_text or ""),
        allow_comment_generation=allow_comment_generation and not normalized_initial,
    )
    tools = create_comment_agent_tools(context)
    selected_runner = runner or _fake_runner or create_comment_agent_runner(
        model_provider,
        tools=tools,
        allow_comment_generation=context.allow_comment_generation,
    )
    runner_config = _build_runner_config(config, context=context)
    payload = {
        "messages": [
            HumanMessage(
                content=_build_user_prompt(
                    initial_comments=normalized_initial,
                    polished_text=str(polished_text or ""),
                    allow_comment_generation=context.allow_comment_generation,
                    comment_generation_instruction=comment_generation_instruction,
                )
            )
        ]
    }
    ai_messages: list[str] = []

    progress_log.info(
        "[comment_agent] 开始批注锚点校验: task_id=%s, comments=%d",
        task_id,
        len(normalized_initial),
    )

    # initial_comments 已存在（非自主生成）时，模型不再做锚点修复：
    # 直接进入确定性校验和写回，避免无谓的二轮 LLM 调用。
    skip_runner = bool(normalized_initial) and not context.allow_comment_generation

    try:
        if skip_runner:
            deterministic_validation = validate_comment_reference_candidates(
                initial_comments=normalized_initial,
                proposed_comments=normalized_initial,
                polished_text=str(polished_text or ""),
            )
            context.validation_results.append(
                deterministic_validation.model_dump(mode="json")
            )
            context.tool_snapshots.append(
                CommentAgentToolSnapshot(
                    round=1,
                    proposed_comments=normalized_initial,
                    validation=deterministic_validation,
                )
            )
            _emit_tool_snapshots(
                context=context,
                emitted_count=0,
                step_callback=step_callback,
            )
        elif _runner_supports_stream(selected_runner):
            _stream_runner(
                selected_runner,
                payload,
                runner_config,
                context=context,
                ai_messages=ai_messages,
                step_callback=step_callback,
            )
        else:
            final_output = selected_runner.invoke(payload, runner_config)
            _emit_ai_messages(
                final_output,
                ai_messages=ai_messages,
            )
            _emit_tool_snapshots(
                context=context,
                emitted_count=0,
                step_callback=step_callback,
            )
    except Exception as error:
        if context.validation_results:
            validation = CommentValidationResult.model_validate(
                context.validation_results[-1]
            )
        else:
            validation = CommentValidationResult()
        writeback_result = _default_writeback_result(validation)
        audit_payload = _build_audit_payload(
            task_id=task_id,
            notice=f"comment_agent 运行异常：{error}",
            initial_comments=context.initial_comments or normalized_initial,
            ai_messages=ai_messages,
            validation=validation,
            validation_results=context.validation_results,
            tool_snapshots=[
                snapshot.model_dump(mode="json")
                for snapshot in context.tool_snapshots
            ],
            final_proposed_comments=context.final_proposed_comments,
            writeback_result=writeback_result,
        )
        write_comment_agent_audit_log(
            audit_payload,
            task_id=task_id,
            path=audit_log_path,
            project_number=project_number,
            project_name=project_name,
        )
        _emit_final_snapshot(
            validation=validation,
            writeback_result=writeback_result,
            snapshots=context.tool_snapshots,
            step_callback=step_callback,
            round_number=len(context.tool_snapshots) or 1,
            error=str(error),
        )
        try:
            setattr(error, "_comment_agent_final_emitted", True)
        except Exception:
            pass
        raise

    if (
        context.allow_comment_generation
        and not context.validation_results
        and not context.final_proposed_comments
        and not context.initial_comments
    ):
        validation = CommentValidationResult()
        writeback_result = _default_writeback_result(validation)
        audit_payload = _build_audit_payload(
            task_id=task_id,
            notice=NO_VALID_GENERATED_COMMENTS_NOTICE,
            initial_comments=[],
            ai_messages=ai_messages,
            validation=validation,
            validation_results=context.validation_results,
            tool_snapshots=[
                snapshot.model_dump(mode="json") for snapshot in context.tool_snapshots
            ],
            final_proposed_comments=[],
            writeback_result=writeback_result,
        )
        audit_path = write_comment_agent_audit_log(
            audit_payload,
            task_id=task_id,
            path=audit_log_path,
            project_number=project_number,
            project_name=project_name,
        )
        _emit_final_snapshot(
            validation=validation,
            writeback_result=writeback_result,
            snapshots=context.tool_snapshots,
            step_callback=step_callback,
            round_number=len(context.tool_snapshots) or 1,
            error=NO_VALID_GENERATED_COMMENTS_NOTICE,
        )
        progress_log.warning(
            "[comment_agent] 未生成有效批注候选: task_id=%s",
            task_id,
        )
        return CommentAgentResult(
            validation=validation,
            writeback_result=writeback_result,
            audit_log_path=audit_path,
            ai_messages=ai_messages,
            final_proposed_comments=[],
        )

    if context.validation_results:
        validation = CommentValidationResult.model_validate(context.validation_results[-1])
    else:
        validation = validate_comment_reference_candidates(
            initial_comments=normalized_initial,
            proposed_comments=normalized_initial,
            polished_text=str(polished_text or ""),
        )
        context.validation_results.append(validation.model_dump(mode="json"))
        context.tool_snapshots.append(
            CommentAgentToolSnapshot(
                round=1,
                proposed_comments=normalized_initial,
                validation=validation,
            )
        )
        _emit_tool_snapshots(
            context=context,
            emitted_count=0,
            step_callback=step_callback,
        )

    effective_initial_comments = context.initial_comments or normalized_initial
    final_proposed_comments = (
        context.final_proposed_comments
        or (context.tool_snapshots[-1].proposed_comments if context.tool_snapshots else [])
        or effective_initial_comments
    )
    try:
        validation, writeback_result = write_validated_comment_candidates_to_word(
            doc=doc,
            initial_comments=effective_initial_comments,
            proposed_comments=final_proposed_comments,
            polished_text=str(polished_text or ""),
            bound_start=int(bound_start),
            bound_end=bound_end,
            log_parts=context.log_parts,
        )
    except Exception as error:
        writeback_result = _default_writeback_result(validation)
        audit_payload = _build_audit_payload(
            task_id=task_id,
            notice=f"comment_agent 写回异常：{error}",
            initial_comments=effective_initial_comments,
            ai_messages=ai_messages,
            validation=validation,
            validation_results=context.validation_results,
            tool_snapshots=[
                snapshot.model_dump(mode="json")
                for snapshot in context.tool_snapshots
            ],
            final_proposed_comments=final_proposed_comments,
            writeback_result=writeback_result,
        )
        write_comment_agent_audit_log(
            audit_payload,
            task_id=task_id,
            path=audit_log_path,
            project_number=project_number,
            project_name=project_name,
        )
        _emit_final_snapshot(
            validation=validation,
            writeback_result=writeback_result,
            snapshots=context.tool_snapshots,
            step_callback=step_callback,
            round_number=len(context.tool_snapshots) or 1,
            error=str(error),
        )
        try:
            setattr(error, "_comment_agent_final_emitted", True)
        except Exception:
            pass
        raise

    audit_payload = _build_audit_payload(
        task_id=task_id,
        notice=None,
        initial_comments=effective_initial_comments,
        ai_messages=ai_messages,
        validation=validation,
        validation_results=context.validation_results,
        tool_snapshots=[
            snapshot.model_dump(mode="json") for snapshot in context.tool_snapshots
        ],
        final_proposed_comments=final_proposed_comments,
        writeback_result=writeback_result,
    )
    audit_path = write_comment_agent_audit_log(
        audit_payload,
        task_id=task_id,
        path=audit_log_path,
        project_number=project_number,
        project_name=project_name,
    )

    _emit_final_snapshot(
        validation=validation,
        writeback_result=writeback_result,
        snapshots=context.tool_snapshots,
        step_callback=step_callback,
        round_number=len(context.tool_snapshots) or 1,
    )

    progress_log.info(
        "[comment_agent] 批注锚点校验完成: task_id=%s, passed=%d, failed=%d, skipped=%d, added=%d",
        task_id,
        len(validation.passed),
        len(validation.failed),
        len(validation.skipped),
        int(writeback_result.get("added") or 0),
    )

    return CommentAgentResult(
        validation=validation,
        writeback_result=writeback_result,
        audit_log_path=audit_path,
        ai_messages=ai_messages,
        final_proposed_comments=final_proposed_comments,
    )

__all__ = [
    "COMMENT_AGENT_SYSTEM_PROMPT",
    "build_comment_agent_middleware",
    "create_comment_agent_runner",
    "run_comment_agent",
    "set_comment_agent_runner",
]
