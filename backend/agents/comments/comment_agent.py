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
)
from backend.agents.comments.types import (
    COMMENT_AGENT_NODE,
    VALIDATE_COMMENT_REFERENCES_TOOL,
    WRITE_VALIDATED_COMMENTS_TOOL,
    CommentAgentAuditPayload,
    CommentAgentResult,
    CommentValidationResult,
)
from backend.agents.comments.workspace import write_comment_agent_audit_log
from backend.agents.generation.model_factory import create_generation_chat_model
from backend.agents.generation.types import AgentStepPayload
from backend.nodes.common_word_nodes.comment_writeback import CommentWritebackResult
from backend.util.log_util.progress_log import progress_log

COMMENT_AGENT_SYSTEM_PROMPT = """
你是批注锚点修复智能体 comment_agent，只负责校验和修复批注候选的 reference_text。

硬性规则：
1. 必须先调用 validate_comment_references，输入 proposed_comments。
2. 你最多可以根据校验反馈修复 reference_text 并再次调用校验工具；校验工具最多 3 次。
3. 同 index 的 comment_text 必须和初始 JSON 完全一致，不得改写、润色、删减或新增批注意见。
4. 只能修改 reference_text，使它精确来自 polished_text；不得改写正文、不得凭空新增批注。
5. 完成校验后最多调用 1 次 write_validated_comments_to_word。
6. 最终只输出简短中文结果摘要，不展示工具消息或排障细节。
""".strip()

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
            run_limit=3,
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
) -> CommentAgentRunner:
    return create_agent(
        model=create_generation_chat_model(model_provider),
        tools=tools,
        system_prompt=COMMENT_AGENT_SYSTEM_PROMPT,
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
    step_callback: Callable[[AgentStepPayload], None] | None,
) -> None:
    for message in _iter_messages(value):
        if not _is_ai_message(message):
            continue
        content = _message_text(message).strip()
        if not content:
            continue
        ai_messages.append(content)
        if step_callback is not None:
            step_callback(
                AgentStepPayload(
                    step_type="stream",
                    round=1,
                    node=COMMENT_AGENT_NODE,
                    content=content,
                    is_complete=False,
                )
            )

def _runner_supports_stream(runner: CommentAgentRunner) -> bool:
    return callable(getattr(runner, "stream", None))

def _stream_runner(
    runner: CommentAgentRunner,
    payload: dict[str, Any],
    config: dict[str, Any],
    *,
    ai_messages: list[str],
    step_callback: Callable[[AgentStepPayload], None] | None,
) -> Any:
    final_chunk: Any = None
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
                    step_callback=step_callback,
                )
            elif len(chunk) == 3:
                _emit_ai_messages(
                    chunk[2],
                    ai_messages=ai_messages,
                    step_callback=step_callback,
                )
            continue
        _emit_ai_messages(
            chunk,
            ai_messages=ai_messages,
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
) -> str:
    return (
        "请修复以下批注候选的 reference_text，并用工具完成校验与写入。\n\n"
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
    initial_comments: list[dict[str, str]],
    ai_messages: list[str],
    validation: CommentValidationResult,
    validation_results: list[dict[str, Any]],
    writeback_result: CommentWritebackResult,
) -> CommentAgentAuditPayload:
    return {
        "task_id": task_id,
        "initial_comments": initial_comments,
        "ai_messages": ai_messages,
        "validation_results": validation_results,
        "final_passed": [item.model_dump(mode="json") for item in validation.passed],
        "final_failed": [item.model_dump(mode="json") for item in validation.failed],
        "final_skipped": [item.model_dump(mode="json") for item in validation.skipped],
        "writeback_result": writeback_result,
    }

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
) -> CommentAgentResult:
    normalized_initial = [
        item.model_dump(mode="json")
        for item in normalize_comment_candidates(initial_comments)
    ]
    context = CommentAgentToolContext(
        initial_comments=normalized_initial,
        polished_text=str(polished_text or ""),
        doc=doc,
        bound_start=int(bound_start),
        bound_end=bound_end,
    )
    tools = create_comment_agent_tools(context)
    selected_runner = runner or _fake_runner or create_comment_agent_runner(
        model_provider,
        tools=tools,
    )
    runner_config = _build_runner_config(config, context=context)
    payload = {
        "messages": [
            HumanMessage(
                content=_build_user_prompt(
                    initial_comments=normalized_initial,
                    polished_text=str(polished_text or ""),
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

    if _runner_supports_stream(selected_runner):
        _stream_runner(
            selected_runner,
            payload,
            runner_config,
            ai_messages=ai_messages,
            step_callback=step_callback,
        )
    else:
        final_output = selected_runner.invoke(payload, runner_config)
        _emit_ai_messages(
            final_output,
            ai_messages=ai_messages,
            step_callback=step_callback,
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

    writeback_result = context.writeback_result or _default_writeback_result(validation)
    audit_payload = _build_audit_payload(
        task_id=task_id,
        initial_comments=normalized_initial,
        ai_messages=ai_messages,
        validation=validation,
        validation_results=context.validation_results,
        writeback_result=writeback_result,
    )
    audit_path = write_comment_agent_audit_log(
        audit_payload,
        task_id=task_id,
        path=audit_log_path,
    )

    if step_callback is not None:
        step_callback(
            AgentStepPayload(
                step_type="stream",
                round=1,
                node=COMMENT_AGENT_NODE,
                content=None,
                is_complete=True,
            )
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
    )

__all__ = [
    "COMMENT_AGENT_SYSTEM_PROMPT",
    "build_comment_agent_middleware",
    "create_comment_agent_runner",
    "run_comment_agent",
    "set_comment_agent_runner",
]
