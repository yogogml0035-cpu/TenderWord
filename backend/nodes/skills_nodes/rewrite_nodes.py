from __future__ import annotations

import asyncio
import pathlib
import shutil
import time
import uuid
from typing import Any, Dict, List

from backend.nodes.common_word_nodes.generate_polished_text import generate_polished_text
from backend.prompts.routing_prompt import (
    build_rewrite_target_selection_bundle,
    parse_rewrite_target_selection,
)
from backend.prompts.types import (
    RewriteHistoryMessage as PromptRewriteHistoryMessage,
    RewriteStateSnapshot,
    RewriteTargetSelectionPromptInput,
)
from backend.services.conversation_service import RewriteMessage, get_conversation_service
from backend.states import TaskSkillGraphState
from backend.util.common_util import StreamCallbacks, stream_llm_completion
from backend.util.log_util.progress_log import progress_log
from backend.util.log_util.rewrite_audit_log import (
    REWRITE_STAGE_TARGET_SELECTION,
    write_rewrite_audit_stage,
)


def _get_model_provider(config: Dict[str, Any] | None) -> str:
    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    model_provider = configurable.get("model_provider", "deepseek")
    return str(model_provider or "deepseek")


def _build_prompt_history_messages(
    rewrite_messages: List[RewriteMessage],
) -> List[PromptRewriteHistoryMessage]:
    prompt_messages: List[PromptRewriteHistoryMessage] = []
    for message in rewrite_messages:
        prompt_messages.append(
            PromptRewriteHistoryMessage(
                role=message.role,
                content=message.content,
                rewrite_state=RewriteStateSnapshot.from_mapping(message.rewrite_state),
                created_at=message.created_at,
            )
        )
    return prompt_messages


def _list_assistant_messages(rewrite_messages: List[RewriteMessage]) -> List[RewriteMessage]:
    return [
        message
        for message in rewrite_messages
        if message.role == "assistant" and isinstance(message.rewrite_state, dict)
    ]


def _get_rewrite_log_path(config: Dict[str, Any] | None) -> str:
    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    return str(configurable.get("rewrite_log_path") or "").strip()


def _select_rewrite_target_index(user_prompt: str, rewrite_messages: List[RewriteMessage], config) -> int:
    rendered_bundle = build_rewrite_target_selection_bundle(
        RewriteTargetSelectionPromptInput(
            messages=_build_prompt_history_messages(rewrite_messages),
            user_prompt=user_prompt,
        )
    )
    if not rendered_bundle.assistant_candidates:
        raise ValueError("当前会话没有可用的 rewrite 版本候选")

    model_provider = _get_model_provider(config)
    rewrite_log_path = _get_rewrite_log_path(config)

    def _capture_request_messages(messages: list[dict[str, Any]]) -> None:
        if not rewrite_log_path:
            return
        write_rewrite_audit_stage(
            rewrite_log_path,
            REWRITE_STAGE_TARGET_SELECTION,
            messages,
        )

    callbacks = StreamCallbacks(on_request_messages=_capture_request_messages)

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(
        stream_llm_completion(
            model_provider=model_provider,
            system_prompt=rendered_bundle.rendered_prompt.system_prompt,
            user_prompt=rendered_bundle.rendered_prompt.user_prompt,
            callbacks=callbacks,
            extra_params_override={"temperature": 0.0},
            timeout_seconds=20,
            check_interval=3.0,
        )
    )
    selected_index = parse_rewrite_target_selection(
        result, len(rendered_bundle.assistant_candidates)
    )
    progress_log.info(
        "[resolve_rewrite_target] 已选择 assistant candidate_index=%s",
        selected_index,
    )
    return selected_index


def _build_rewrite_output_path(source_path: pathlib.Path) -> pathlib.Path:
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    suffix = source_path.suffix or ".docx"
    candidate = source_path.with_name(f"{source_path.stem}_rewrite_{timestamp}{suffix}")
    if candidate.exists():
        candidate = source_path.with_name(
            f"{source_path.stem}_rewrite_{timestamp}_{uuid.uuid4().hex[:4]}{suffix}"
        )
    return candidate


def resolve_rewrite_target(state: TaskSkillGraphState, config) -> TaskSkillGraphState:
    conversation_id = str(state.get("conversation_id") or "").strip()
    rewrite_user_prompt = str(state.get("rewrite_user_prompt") or "").strip()
    if not conversation_id:
        raise ValueError("conversation_id 不能为空")
    if not rewrite_user_prompt:
        raise ValueError("rewrite_user_prompt 不能为空")

    conversation_service = get_conversation_service()
    rewrite_messages = conversation_service.list_rewrite_messages(conversation_id)
    if not rewrite_messages:
        raise ValueError("当前会话没有可用的 rewrite 历史")

    selected_index = _select_rewrite_target_index(rewrite_user_prompt, rewrite_messages, config)
    assistant_messages = _list_assistant_messages(rewrite_messages)
    target_state = dict(assistant_messages[selected_index].rewrite_state or {})

    source_prepared_doc_path = pathlib.Path(
        str(target_state.get("prepared_doc_path") or "")
    ).expanduser()
    if not source_prepared_doc_path.is_file():
        raise FileNotFoundError(f"rewrite 目标文档不存在: {source_prepared_doc_path}")

    rewrite_output_path = _build_rewrite_output_path(source_prepared_doc_path.resolve())
    rewrite_output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source_prepared_doc_path), str(rewrite_output_path))

    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    cleanup_holder = configurable.get("rewrite_cleanup_holder")
    if isinstance(cleanup_holder, dict):
        cleanup_holder["path"] = str(rewrite_output_path)

    updates: Dict[str, Any] = {
        "conversation_id": conversation_id,
        "rewrite_user_prompt": rewrite_user_prompt,
        "rewrite_target_index": selected_index,
        "rewrite_base_text": str(target_state.get("polished_text") or ""),
        "origin_tender_path": str(rewrite_output_path),
        "prepared_doc_path": str(rewrite_output_path),
        "rewrite_temp_output_path": str(rewrite_output_path),
        "source_prepared_doc_path": str(source_prepared_doc_path.resolve()),
        "clean_draft_path": str(rewrite_output_path),
        "rewrite_mode": True,
    }

    for key, value in target_state.items():
        if key in {"prepared_doc_path", "polished_text"}:
            continue
        if isinstance(value, str):
            updates[key] = value

    return TaskSkillGraphState(**updates)


def rewrite_text(state: TaskSkillGraphState, config) -> TaskSkillGraphState:
    next_state = dict(state)
    next_state["rewrite_mode"] = True
    return generate_polished_text(TaskSkillGraphState(**next_state), config)
