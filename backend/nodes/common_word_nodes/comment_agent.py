from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from backend.agents.comments import run_comment_agent
from backend.agents.generation import AgentStepPayload
from backend.config.tender_config import get_anchor_target_sizes
from backend.models import AgentStepEventData
from backend.nodes.common_word_nodes.comment_writeback import (
    CommentWritebackResult,
    build_comment_writeback_summary_payload,
)
from backend.prompts.comment_prompt import render_comment_prompt
from backend.prompts.types import CommentPromptInput
from backend.states.base_state import TenderGraphStateBase
from backend.util.log_util.progress_log import progress_log
from backend.util.word_util import (
    close_word_application,
    create_word_application,
    open_document_with_retry,
    save_document_with_retry,
    unprotect_document,
)
from backend.util.word_util.anchor_utils import (
    find_anchor_range,
    resolve_anchor_content_range,
)

NODE_NAME = "comment_agent"


def _get_configurable(config: dict[str, Any] | None) -> dict[str, Any]:
    return config.get("configurable", {}) if isinstance(config, dict) else {}


def _build_agent_step_data(
    payload: AgentStepPayload,
    *,
    task_id: str,
    task_kind: str,
) -> AgentStepEventData:
    return AgentStepEventData(
        task_id=task_id,
        task_kind=task_kind,
        step_type=payload.step_type,
        round=payload.round,
        node=payload.node,
        content=payload.content,
        findings=[finding.model_dump(mode="json") for finding in payload.findings],
        comment_agent=payload.comment_agent,
        is_complete=payload.is_complete,
    )


def _make_agent_step_callback(
    state: TenderGraphStateBase,
    config: dict[str, Any] | None,
) -> Callable[[AgentStepPayload], None] | None:
    configurable = _get_configurable(config)
    task_id = str(configurable.get("task_id") or state.get("task_id") or "").strip()
    if not task_id:
        return None

    task_kind = str(configurable.get("task_kind") or state.get("task_kind") or "generate")
    callback = configurable.get("agent_step_callback")

    def emit(payload: AgentStepPayload) -> None:
        event_data = _build_agent_step_data(payload, task_id=task_id, task_kind=task_kind)
        if callable(callback):
            callback(event_data)

    return emit


def _emit_comment_agent_final_warning(
    state: TenderGraphStateBase,
    config: dict[str, Any] | None,
    *,
    message: str,
    warning: bool = True,
) -> None:
    callback = _make_agent_step_callback(state, config)
    if callback is None:
        return
    content = (
        "comment_agent 已结束，批注写入降级为 warning。\n"
        f"原因：{message}"
        if warning
        else f"comment_agent 已结束。\n{message}"
    )
    callback(
        AgentStepPayload(
            step_type="final",
            round=1,
            node=NODE_NAME,
            content=content,
            comment_agent={
                "phase": "final",
                "rounds": [],
                "highlights": [],
                "writeback": {
                    "attempted": 0,
                    "added": 0,
                    "failed": 0,
                    "skipped": 0,
                    "issues": [],
                },
            },
            is_complete=True,
        )
    )


def _coerce_generated_count(state: TenderGraphStateBase, comments: list[Any]) -> int:
    try:
        value = int(state.get("generated_comment_count") or 0)
    except (TypeError, ValueError):
        value = 0
    return value if value > 0 else len(comments)


def _failure_writeback_result(
    *,
    generated_count: int,
    reason: str,
    error: str,
) -> CommentWritebackResult:
    return {
        "total": int(generated_count),
        "attempted": 0,
        "added": 0,
        "failed": int(generated_count),
        "skipped": 0,
        "issues": [
            {
                "index": index,
                "reason": reason,
                "reference_text": "",
                "comment_text": "",
                "error": error,
            }
            for index in range(1, int(generated_count) + 1)
        ],
    }


def _empty_writeback_result() -> CommentWritebackResult:
    return {
        "total": 0,
        "attempted": 0,
        "added": 0,
        "failed": 0,
        "skipped": 0,
        "issues": [],
    }


def _state_from_writeback(
    state: TenderGraphStateBase,
    *,
    generated_count: int,
    writeback_result: CommentWritebackResult,
    insertion_log_parts: list[str],
    audit_log_path: Path | None = None,
) -> TenderGraphStateBase:
    summary_payload = build_comment_writeback_summary_payload(
        generated_count=generated_count,
        writeback_result=writeback_result,
    )
    summary = str(summary_payload["summary"])
    if summary_payload["warning"]:
        progress_log.warning(summary)
    else:
        progress_log.info(summary)

    issues = writeback_result.get("issues", [])
    new_state = dict(state)
    previous_log = str(new_state.get("insertion_log") or "").strip()
    log_text = "; ".join(part for part in insertion_log_parts if part)
    if previous_log and log_text:
        new_state["insertion_log"] = f"{previous_log}; {log_text}"
    elif log_text:
        new_state["insertion_log"] = log_text
    new_state["comment_writeback_summary"] = summary
    new_state["comment_writeback_added"] = int(summary_payload["added"])
    new_state["comment_writeback_failed"] = int(summary_payload["failed"])
    new_state["comment_writeback_skipped"] = int(summary_payload["skipped"])
    new_state["comment_writeback_errors"] = [
        {
            "reference_text": issue.get("reference_text", ""),
            "reason": issue.get("reason", ""),
            "error": issue.get("error", ""),
        }
        for issue in issues
    ]
    new_state["comment_writeback_result"] = summary_payload
    if audit_log_path is not None:
        new_state["comment_agent_audit_log_path"] = str(audit_log_path)
    return TenderGraphStateBase(**new_state)


def comment_agent_writeback(
    state: TenderGraphStateBase,
    config=None,
) -> TenderGraphStateBase:
    """Run comment_agent after agent-mode body writeback without failing the task."""
    configurable = _get_configurable(config)
    task_kind = str(configurable.get("task_kind") or state.get("task_kind") or "generate")
    generation_mode = str(
        configurable.get("generation_mode") or state.get("generation_mode") or ""
    )
    comments = list(state.get("polished_comments") or [])
    generated_count = _coerce_generated_count(state, comments)
    log_parts = ["comment_agent 开始处理批注"]
    allow_comment_generation = (
        task_kind == "comment_supplement" or generation_mode == "agent"
    ) and not comments

    if not comments and not allow_comment_generation:
        log_parts.append("没有可写入的 AI 批注，跳过 comment_agent")
        _emit_comment_agent_final_warning(
            state,
            config,
            message="没有可写入的 AI 批注，已跳过。",
            warning=False,
        )
        return _state_from_writeback(
            state,
            generated_count=generated_count,
            writeback_result=_empty_writeback_result(),
            insertion_log_parts=log_parts,
        )

    prepared_doc_path = str(state.get("prepared_doc_path") or "").strip()
    before_text = str(state.get("insertion_before_text") or "").strip()
    after_text = str(state.get("insertion_after_text") or "").strip()
    if not prepared_doc_path or not before_text or not after_text:
        error = "缺少 prepared_doc_path 或插入锚点，comment_agent 批注写入已降级为 warning"
        log_parts.append(error)
        _emit_comment_agent_final_warning(state, config, message=error)
        return _state_from_writeback(
            state,
            generated_count=generated_count,
            writeback_result=_failure_writeback_result(
                generated_count=generated_count,
                reason="missing_comment_agent_anchor_context",
                error=error,
            ),
            insertion_log_parts=log_parts,
        )

    word = None
    doc = None
    com_initialized = False
    try:
        tender_type = str(state.get("tender_type") or "xjcg")
        before_size, after_size = get_anchor_target_sizes(tender_type)
        word, com_initialized = create_word_application(
            initial_delay=0.0,
            post_init_delay=1.0,
            use_existing=False,
            verify=False,
            node_name=NODE_NAME,
        )
        doc = open_document_with_retry(
            word_app=word,
            file_path=prepared_doc_path,
            read_only=False,
            node_name=NODE_NAME,
        )
        if unprotect_document(doc, node_name=NODE_NAME):
            log_parts.append("已取消文档保护")

        before_hit, after_hit = find_anchor_range(
            doc,
            before_text,
            after_text,
            before_size=before_size,
            after_size=after_size,
            prefer_before="last",
            prefer_after="first",
        )
        if not before_hit:
            raise ValueError(f"未找到前置锚点段落: {before_text}")
        if not after_hit:
            raise ValueError(f"未找到后置锚点段落: {after_text}")

        content_range = resolve_anchor_content_range(
            doc=doc,
            word_app=word,
            before_hit=before_hit,
            after_hit=after_hit,
            tender_type=tender_type,
            allow_empty=True,
        )
        bound_start = int(content_range["range_start"])
        bound_end = int(content_range["range_end"])
        log_parts.append(f"comment_agent 批注范围: {bound_start}-{bound_end}")

        comment_generation_instruction = None
        if allow_comment_generation:
            rendered_prompt = render_comment_prompt(
                CommentPromptInput(
                    tender_type=tender_type,
                    polished_text=str(state.get("polished_text") or ""),
                )
            )
            comment_generation_instruction = (
                rendered_prompt.system_prompt + "\n\n" + rendered_prompt.user_prompt
            )
            log_parts.append("comment_agent 将使用统一批注 prompt 自主生成批注候选")

        result = run_comment_agent(
            initial_comments=comments,
            polished_text=str(state.get("polished_text") or ""),
            doc=doc,
            bound_start=bound_start,
            bound_end=bound_end,
            model_provider=str(configurable.get("model_provider") or "deepseek"),
            task_id=str(configurable.get("task_id") or state.get("task_id") or "comment-agent"),
            config=config,
            step_callback=_make_agent_step_callback(state, config),
            allow_comment_generation=allow_comment_generation,
            comment_generation_instruction=comment_generation_instruction,
        )
        if allow_comment_generation:
            generated_count = max(
                generated_count,
                len(getattr(result.validation, "passed", []) or [])
                + len(getattr(result.validation, "failed", []) or [])
                + len(getattr(result.validation, "skipped", []) or []),
                len(result.final_proposed_comments or []),
            )
        try:
            save_document_with_retry(doc, node_name=NODE_NAME)
            log_parts.append("comment_agent 批注写入后已保存文档")
        except Exception as save_error:
            log_parts.append(f"comment_agent 保存文档失败，已降级为 warning: {save_error}")
            return _state_from_writeback(
                state,
                generated_count=generated_count,
                writeback_result=_failure_writeback_result(
                    generated_count=generated_count,
                    reason="comment_agent_save_failed",
                    error=str(save_error),
                ),
                insertion_log_parts=log_parts,
                audit_log_path=result.audit_log_path,
            )

        return _state_from_writeback(
            state,
            generated_count=generated_count,
            writeback_result=result.writeback_result,
            insertion_log_parts=log_parts,
            audit_log_path=result.audit_log_path,
        )
    except Exception as error:
        log_parts.append(f"comment_agent 批注写入失败，已降级为 warning: {error}")
        progress_log.exception("[comment_agent] 批注写入失败，任务继续完成")
        if not getattr(error, "_comment_agent_final_emitted", False):
            _emit_comment_agent_final_warning(state, config, message=str(error))
        return _state_from_writeback(
            state,
            generated_count=generated_count,
            writeback_result=_failure_writeback_result(
                generated_count=generated_count,
                reason="comment_agent_failed",
                error=str(error),
            ),
            insertion_log_parts=log_parts,
        )
    finally:
        close_word_application(
            word_app=word,
            doc=doc,
            com_initialized=com_initialized,
            wait_time=0.0,
            node_name=NODE_NAME,
        )


__all__ = ["comment_agent_writeback"]
