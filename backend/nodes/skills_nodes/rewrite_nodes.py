from __future__ import annotations

import asyncio
import pathlib
import re
import shutil
import time
import uuid
from typing import Any, Dict, List

from backend.nodes.common_word_nodes.generate_polished_text import generate_polished_text
from backend.services.conversation_service import RewriteMessage, get_conversation_service
from backend.states import RewriteGraphState
from backend.util.common_util import StreamCallbacks, stream_llm_completion
from backend.util.log_util.progress_log import progress_log


JUDGE_TARGET_SYSTEM_PROMPT = """
你是文档修改版本选择助手。
你的任务是根据会话历史和用户最新修改指令，从候选 assistant 版本中选出最应该被修改的一版。

规则：
1. 只能返回候选 assistant 版本的零基索引。
2. 只能输出一个纯数字，不要输出解释、标点、JSON 或额外文本。
3. 若用户没有明确指定历史版本，默认选择最符合语义的候选版本。
4. 若多版都可行，优先选择最新且最相关的一版。
""".strip()


def _get_model_provider(config: Dict[str, Any] | None) -> str:
    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    model_provider = configurable.get("model_provider", "deepseek")
    return str(model_provider or "deepseek")


def _build_assistant_candidates(
    rewrite_messages: List[RewriteMessage],
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    assistant_index = 0
    for message in rewrite_messages:
        if message.role != "assistant" or not isinstance(message.rewrite_state, dict):
            continue
        candidates.append(
            {
                "assistant_index": assistant_index,
                "content": message.content,
                "created_at": message.created_at,
                "rewrite_state": dict(message.rewrite_state),
            }
        )
        assistant_index += 1
    return candidates


def _build_judge_target_prompt(
    rewrite_messages: List[RewriteMessage],
    assistant_candidates: List[Dict[str, Any]],
    user_prompt: str,
) -> str:
    lines: List[str] = ["【会话历史】"]
    assistant_counter = 0
    for idx, message in enumerate(rewrite_messages):
        if message.role == "assistant" and isinstance(message.rewrite_state, dict):
            rewrite_state = message.rewrite_state
            lines.extend(
                [
                    f"{idx}. role=assistant candidate_index={assistant_counter}",
                    f"content={message.content}",
                    f"tender_type={rewrite_state.get('tender_type', '')}",
                    f"prepared_doc_path={rewrite_state.get('prepared_doc_path', '')}",
                    "polished_text:",
                    str(rewrite_state.get("polished_text", "")),
                    "---",
                ]
            )
            assistant_counter += 1
            continue

        lines.extend(
            [
                f"{idx}. role={message.role}",
                f"content={message.content}",
                "---",
            ]
        )

    candidate_list = ", ".join(str(item["assistant_index"]) for item in assistant_candidates)
    lines.extend(
        [
            "",
            "【用户最新指令】",
            user_prompt,
            "",
            f"可选 assistant candidate_index: {candidate_list}",
            "请只输出一个纯数字索引。",
        ]
    )
    return "\n".join(lines)


def _parse_selected_index(raw_output: str, candidate_count: int) -> int:
    normalized = str(raw_output or "").strip()
    if not re.fullmatch(r"\d+", normalized):
        raise ValueError(f"rewrite 目标版本选择结果非法: {normalized!r}")
    index = int(normalized)
    if index < 0 or index >= candidate_count:
        raise ValueError(f"rewrite 目标版本索引越界: {index}")
    return index


def _select_rewrite_target_index(user_prompt: str, rewrite_messages: List[RewriteMessage], config) -> int:
    assistant_candidates = _build_assistant_candidates(rewrite_messages)
    if not assistant_candidates:
        raise ValueError("当前会话没有可用的 rewrite 版本候选")

    judge_prompt = _build_judge_target_prompt(
        rewrite_messages=rewrite_messages,
        assistant_candidates=assistant_candidates,
        user_prompt=user_prompt,
    )
    model_provider = _get_model_provider(config)
    callbacks = StreamCallbacks()

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(
        stream_llm_completion(
            model_provider=model_provider,
            system_prompt=JUDGE_TARGET_SYSTEM_PROMPT,
            user_prompt=judge_prompt,
            callbacks=callbacks,
            extra_params_override={"temperature": 0.0},
            timeout_seconds=20,
            check_interval=3.0,
        )
    )
    selected_index = _parse_selected_index(result, len(assistant_candidates))
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


def resolve_rewrite_target(state: RewriteGraphState, config) -> RewriteGraphState:
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
    assistant_candidates = _build_assistant_candidates(rewrite_messages)
    target_candidate = assistant_candidates[selected_index]
    target_state = dict(target_candidate["rewrite_state"])

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

    return RewriteGraphState(**updates)


def rewrite_text(state: RewriteGraphState, config) -> RewriteGraphState:
    next_state = dict(state)
    next_state["rewrite_mode"] = True
    return generate_polished_text(RewriteGraphState(**next_state), config)
