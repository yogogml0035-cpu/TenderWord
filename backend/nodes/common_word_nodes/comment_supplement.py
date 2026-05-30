from __future__ import annotations

import asyncio
import pathlib
import shutil
import time
import uuid
from typing import Any

from backend.nodes.common_word_nodes.generate_comments import (
    _parse_comment_output,
    _sanitize_filename,
    _write_text_if_possible,
)
from backend.prompts.comment_no_reference_prompt import (
    render_comment_no_reference_prompt,
)
from backend.prompts.types import CommentNoReferencePromptInput
from backend.states import TenderGraphStateBase
from backend.util.common_util import (
    LLMTimeoutError,
    StreamCallbacks,
    stream_llm_completion,
)
from backend.util.log_util.progress_log import progress_log
from backend.util.log_util.prompt_log import get_generate_prompt_log_dir

CHECK_INTERVAL = 3.0
NO_REFERENCE_COMMENT_TEMPERATURE = 0.7

NODE_PREPARE = "prepare_comment_supplement"
NODE_GENERATE = "generate_comments"
NODE_FINALIZE = "finalize_comment_supplement"

def _get_configurable(config: dict[str, Any] | None) -> dict[str, Any]:
    return config.get("configurable", {}) if isinstance(config, dict) else {}

def _build_comment_supplement_output_path(source_path: pathlib.Path, task_id: str) -> pathlib.Path:
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    suffix = source_path.suffix or ".docx"
    task_part = _sanitize_filename(str(task_id or "").strip()) or uuid.uuid4().hex[:8]
    candidate = source_path.with_name(
        f"{source_path.stem}_comment_supplement_{task_part}_{timestamp}{suffix}"
    )
    if candidate.exists():
        candidate = source_path.with_name(
            f"{source_path.stem}_comment_supplement_{task_part}_{timestamp}_{uuid.uuid4().hex[:4]}{suffix}"
        )
    return candidate

def prepare_comment_supplement(
    state: TenderGraphStateBase,
    config=None,
) -> TenderGraphStateBase:
    """Copy the current generated file to a new comment-supplement work file."""
    source_path_value = str(
        state.get("comment_supplement_source_file")
        or state.get("source_prepared_doc_path")
        or state.get("prepared_doc_path")
        or ""
    ).strip()
    if not source_path_value:
        raise ValueError("comment_supplement 需要当前源文档路径")

    source_path = pathlib.Path(source_path_value).expanduser()
    if not source_path.is_file():
        raise FileNotFoundError(f"comment_supplement 源文档不存在: {source_path}")

    configurable = _get_configurable(config)
    task_id = str(configurable.get("task_id") or state.get("task_id") or "").strip()
    output_path = _build_comment_supplement_output_path(source_path.resolve(), task_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source_path), str(output_path))

    cleanup_holder = configurable.get("rewrite_cleanup_holder")
    if isinstance(cleanup_holder, dict):
        cleanup_holder["path"] = str(output_path)

    progress_log.info("[%s] 已创建补充批注工作副本: %s", NODE_PREPARE, output_path)

    updates = dict(state)
    updates.update(
        {
            "comment_supplement_source_file": str(source_path.resolve()),
            "source_prepared_doc_path": str(source_path.resolve()),
            "comment_supplement_temp_output_path": str(output_path),
            "origin_tender_path": str(output_path),
            "clean_draft_path": str(output_path),
            "prepared_doc_path": str(output_path),
        }
    )
    return TenderGraphStateBase(**updates)

def _build_prompt_log_paths(state: TenderGraphStateBase) -> tuple[Any, Any, Any]:
    try:
        prompts_log_dir = get_generate_prompt_log_dir(__file__)
        project_number = str(state.get("project_number", "") or "").strip()
        project_name = str(state.get("project_name", "") or "").strip()
        filename_parts = [
            _sanitize_filename(part) for part in (project_number, project_name) if part
        ]
        timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
        prompt_base = "-".join(filename_parts + ["补充批注"]) if filename_parts else "补充批注"
        return (
            prompts_log_dir / f"prompt_{prompt_base}_no_reference_comments_prompt_{timestamp}.txt",
            prompts_log_dir / f"prompt_{prompt_base}_no_reference_comments_raw_output_{timestamp}.txt",
            prompts_log_dir / f"prompt_{prompt_base}_no_reference_comments_json_{timestamp}.txt",
        )
    except Exception as error:
        progress_log.warning("[%s] 准备补充批注 prompt 日志路径失败: %s", NODE_GENERATE, error)
        return None, None, None

def generate_comment_supplement_comments(
    state: TenderGraphStateBase,
    config=None,
) -> TenderGraphStateBase:
    """Generate no-reference comment candidates from latest rewrite_state.polished_text."""
    polished_text = str(state.get("polished_text") or "").strip()
    if not polished_text:
        progress_log.warning("[%s] 缺少 polished_text，跳过补充批注生成", NODE_GENERATE)
        return TenderGraphStateBase(polished_comments=[], generated_comment_count=0)

    tender_type = str(state.get("tender_type") or "xjcg").strip() or "xjcg"
    rendered_prompt = render_comment_no_reference_prompt(
        CommentNoReferencePromptInput(
            tender_type=tender_type,
            polished_text=polished_text,
        )
    )

    prompt_file, raw_output_file, parsed_output_file = _build_prompt_log_paths(state)
    try:
        _write_text_if_possible(
            prompt_file,
            rendered_prompt.system_prompt + "\n" + rendered_prompt.user_prompt,
        )
    except Exception as error:
        progress_log.warning("[%s] 保存补充批注 prompt 失败: %s", NODE_GENERATE, error)

    configurable = _get_configurable(config)
    model_provider = str(configurable.get("model_provider") or "deepseek")
    suppress_llm_stdout = bool(configurable.get("suppress_llm_stdout", False))

    def _log_chunk(text: str) -> None:
        if suppress_llm_stdout:
            return
        progress_log.debug(text, end="", flush=True)

    callbacks = StreamCallbacks(on_chunk=_log_chunk, on_update=lambda _text: None)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        content = loop.run_until_complete(
            stream_llm_completion(
                model_provider=model_provider,
                system_prompt=rendered_prompt.system_prompt,
                user_prompt=rendered_prompt.user_prompt,
                callbacks=callbacks,
                extra_params_override={"temperature": NO_REFERENCE_COMMENT_TEMPERATURE},
                check_interval=CHECK_INTERVAL,
            )
        )
    except LLMTimeoutError as error:
        progress_log.error("[%s] 补充批注 LLM 超时: %s", NODE_GENERATE, error)
        return TenderGraphStateBase(polished_comments=[], generated_comment_count=0)
    except Exception as error:
        progress_log.exception("[%s] 补充批注生成失败: %s", NODE_GENERATE, error)
        return TenderGraphStateBase(polished_comments=[], generated_comment_count=0)

    try:
        _write_text_if_possible(raw_output_file, content)
    except Exception as error:
        progress_log.warning("[%s] 保存补充批注原始输出失败: %s", NODE_GENERATE, error)

    comments: list[dict[str, str]] = []
    try:
        comments = _parse_comment_output(content)
    except Exception as error:
        progress_log.warning("[%s] 补充批注 JSON 解析失败，降级为空数组: %s", NODE_GENERATE, error)

    try:
        import json

        _write_text_if_possible(
            parsed_output_file,
            json.dumps(comments, ensure_ascii=False, indent=2),
        )
    except Exception as error:
        progress_log.warning("[%s] 保存补充批注 JSON 输出失败: %s", NODE_GENERATE, error)

    progress_log.info("[%s] 生成补充批注候选 %s 条", NODE_GENERATE, len(comments))
    return TenderGraphStateBase(
        polished_comments=comments,
        generated_comment_count=len(comments),
        comments_summary=f"补充批注候选 {len(comments)} 条",
    )

def finalize_comment_supplement(
    state: TenderGraphStateBase,
    config=None,
) -> TenderGraphStateBase:
    del config
    prepared_doc_path = str(state.get("prepared_doc_path") or "").strip()
    if not prepared_doc_path:
        raise ValueError("comment_supplement 完成时缺少 prepared_doc_path")
    return TenderGraphStateBase(
        prepared_doc_path=prepared_doc_path,
        comment_supplement_completed=True,
    )

__all__ = [
    "finalize_comment_supplement",
    "generate_comment_supplement_comments",
    "prepare_comment_supplement",
]
