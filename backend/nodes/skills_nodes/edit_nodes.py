from __future__ import annotations

import asyncio
import pathlib
import shutil
import time
import uuid
from typing import Any, Dict

from backend.config.tender_config import get_anchor_target_sizes
from backend.helper.word_helper.inline_style_ops import (
    build_inline_style_extraction_logs,
    extract_inline_style_fragments,
)
from backend.nodes.common_word_nodes.comment_extraction import (
    result_to_polished_comments,
)
from backend.prompts.skill_prompt import render_task_skill_prompt
from backend.prompts.types import TaskSkillPromptInput, TaskSkillPromptSection
from backend.skills import get_skill_registry
from backend.states import TaskSkillGraphState
from backend.util.common_util import StreamCallbacks, stream_llm_completion
from backend.util.log_util.progress_log import progress_log
from backend.util.log_util.prompt_log import write_edit_generate_log_artifacts
from backend.util.log_util.skill_audit_log import (
    EDIT_STAGE_TEXT_REQUEST,
    resolve_task_audit_log_path,
    TASK_AUDIT_STAGE_SKILL_PROMPT_RENDER,
    write_task_audit_stage,
)
from backend.util.word_util import (
    WordDocumentInspector,
    close_word_application,
    create_word_application,
    extract_content_with_tables,
    open_document_with_retry,
    unprotect_document,
)
from backend.util.word_util.anchor_utils import find_anchor_range, resolve_anchor_content_range

NODE_NAME_RESOLVE = "resolve_edit_target"
NODE_NAME_EXTRACT = "extract_edit_context"


def _get_model_provider(config: Dict[str, Any] | None) -> str:
    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    return str(configurable.get("model_provider") or "deepseek")


def _build_edit_output_path(source_path: pathlib.Path) -> pathlib.Path:
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    suffix = source_path.suffix or ".docx"
    candidate = source_path.with_name(f"{source_path.stem}_edit_{timestamp}{suffix}")
    if candidate.exists():
        candidate = source_path.with_name(
            f"{source_path.stem}_edit_{timestamp}_{uuid.uuid4().hex[:4]}{suffix}"
        )
    return candidate


def resolve_edit_target(state: TaskSkillGraphState, config) -> TaskSkillGraphState:
    source_path_value = str(state.get("source_document_path") or "").strip()
    if not source_path_value:
        raise ValueError("source_document_path 不能为空")

    source_path = pathlib.Path(source_path_value).expanduser()
    if not source_path.is_file():
        raise FileNotFoundError(f"edit 目标文档不存在: {source_path}")

    edit_output_path = _build_edit_output_path(source_path.resolve())
    edit_output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source_path), str(edit_output_path))

    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    cleanup_holder = configurable.get("rewrite_cleanup_holder")
    if isinstance(cleanup_holder, dict):
        cleanup_holder["path"] = str(edit_output_path)

    progress_log.info(
        "[%s] 已创建 edit 工作副本: %s",
        NODE_NAME_RESOLVE,
        edit_output_path,
    )

    updates: Dict[str, Any] = {
        "source_document_path": str(source_path.resolve()),
        "prepared_doc_path": str(edit_output_path),
        "verbose_style_progress_logs": True,
        "suppress_comment_progress_logs": True,
    }
    return TaskSkillGraphState(**updates)


def extract_edit_context(state: TaskSkillGraphState, config) -> TaskSkillGraphState:
    del config
    document_path = str(state.get("prepared_doc_path") or "").strip()
    if not document_path:
        raise ValueError("extract_edit_context 需要 prepared_doc_path")

    before_text = state.get("insertion_before_text")
    after_text = state.get("insertion_after_text")
    if not before_text or not after_text:
        raise ValueError("extract_edit_context 需要 insertion_before_text 和 insertion_after_text")

    file_path = pathlib.Path(document_path).expanduser()
    if not file_path.is_file():
        raise FileNotFoundError(f"extract_edit_context 文档不存在: {file_path}")

    tender_type = str(state.get("tender_type") or "xjcg")
    verbose_style_progress_logs = bool(state.get("verbose_style_progress_logs"))
    before_size, after_size = get_anchor_target_sizes(tender_type)

    word_app = None
    doc = None
    com_initialized = False
    try:
        word_app, com_initialized = create_word_application(
            initial_delay=0.5,
            post_init_delay=0.5,
            use_existing=False,
            verify=True,
            node_name=NODE_NAME_EXTRACT,
        )
        doc = open_document_with_retry(
            word_app=word_app,
            file_path=str(file_path),
            read_only=True,
            node_name=NODE_NAME_EXTRACT,
        )
        unprotect_document(doc, node_name=NODE_NAME_EXTRACT)

        before_hit, after_hit = find_anchor_range(
            doc=doc,
            before_text=str(before_text),
            after_text=str(after_text),
            before_size=before_size,
            after_size=after_size,
            prefer_before="last",
            prefer_after="first",
        )
        if not before_hit:
            raise ValueError(f"未找到前置锚点: {before_text}")
        if not after_hit:
            raise ValueError(f"未找到后置锚点: {after_text}")

        content_range = resolve_anchor_content_range(
            doc=doc,
            word_app=word_app,
            before_hit=before_hit,
            after_hit=after_hit,
            tender_type=tender_type,
        )
        range_start = int(content_range["range_start"])
        range_end = int(content_range["range_end"])
        start_page = int(content_range["start_page"])
        end_page = int(content_range["end_page"])

        extracted_content = extract_content_with_tables(doc.Range(range_start, range_end))
        inspector = WordDocumentInspector(
            word_app=word_app,
            doc=doc,
            node_name=NODE_NAME_EXTRACT,
        )
        result = inspector.analyze_document(
            range_start=range_start,
            range_end=range_end,
        )
        polished_comments = result_to_polished_comments(result)
        inline_style_fragments = extract_inline_style_fragments(
            doc=doc,
            bound_start=range_start,
            bound_end=range_end,
        )

        progress_log.info(
            "[%s] 已提取编辑正文、批注和样式: comments=%d, styles=%d, pages=%d-%d",
            NODE_NAME_EXTRACT,
            len(polished_comments),
            len(inline_style_fragments),
            start_page,
            end_page,
        )
        if verbose_style_progress_logs:
            for message in build_inline_style_extraction_logs(
                inline_style_fragments,
                step_label="样式提取",
            ):
                progress_log.info("[%s] %s", NODE_NAME_EXTRACT, message)
        return TaskSkillGraphState(
            source_section_text=extracted_content,
            polished_comments=polished_comments,
            inline_style_fragments=inline_style_fragments,
            start_page=start_page,
            end_page=end_page,
            verbose_style_progress_logs=verbose_style_progress_logs,
            suppress_comment_progress_logs=bool(state.get("suppress_comment_progress_logs")),
        )
    finally:
        close_word_application(
            word_app=word_app,
            doc=doc,
            com_initialized=com_initialized,
            wait_time=1.0,
            node_name=NODE_NAME_EXTRACT,
        )


def edit_text(state: TaskSkillGraphState, config) -> TaskSkillGraphState:
    skill = get_skill_registry().get_definition("edit")
    edit_user_prompt = str(state.get("edit_user_prompt") or "").strip()
    if not edit_user_prompt:
        raise ValueError("edit_user_prompt 不能为空")

    rendered_prompt = render_task_skill_prompt(
        TaskSkillPromptInput(
            skill_id=skill.name,
            instruction=skill.instruction,
            sections=(
                TaskSkillPromptSection(
                    title="当前锚点区正文",
                    content=str(state.get("source_section_text") or ""),
                ),
                TaskSkillPromptSection(
                    title="用户修改指令",
                    content=edit_user_prompt,
                ),
            ),
        )
    )

    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    stream_callback = configurable.get("llm_stream_callback")
    complete_callback = configurable.get("llm_stream_complete_callback")
    suppress_llm_stdout = bool(configurable.get("suppress_llm_stdout", False))
    task_audit_log_path = resolve_task_audit_log_path(config)

    if task_audit_log_path:
        write_task_audit_stage(
            task_audit_log_path,
            TASK_AUDIT_STAGE_SKILL_PROMPT_RENDER,
            [
                {"role": "system", "content": rendered_prompt.system_prompt},
                {"role": "user", "content": rendered_prompt.user_prompt},
            ],
        )

    def _push_stream_update(text: str) -> None:
        if callable(stream_callback) and text is not None:
            stream_callback(str(text))

    def _log_chunk(text: str) -> None:
        if not suppress_llm_stdout:
            progress_log.debug(text)

    def _capture_request_messages(messages: list[dict[str, Any]]) -> None:
        if not task_audit_log_path:
            return
        write_task_audit_stage(
            task_audit_log_path,
            EDIT_STAGE_TEXT_REQUEST,
            messages,
        )

    callbacks = StreamCallbacks(
        on_chunk=_log_chunk,
        on_update=_push_stream_update,
        on_request_messages=_capture_request_messages,
    )

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    content = loop.run_until_complete(
        stream_llm_completion(
            model_provider=_get_model_provider(config),
            system_prompt=rendered_prompt.system_prompt,
            user_prompt=rendered_prompt.user_prompt,
            callbacks=callbacks,
            check_interval=3.0,
        )
    )

    if callable(complete_callback):
        complete_callback(str(content))

    task_id = str(configurable.get("task_id") or state.get("task_id") or "").strip()
    if not task_id:
        task_id = f"edit_{uuid.uuid4().hex[:8]}"
    try:
        write_edit_generate_log_artifacts(
            __file__,
            task_id=task_id,
            rendered_prompt=(
                f"{rendered_prompt.system_prompt}\n{rendered_prompt.user_prompt}"
            ),
            generated_content=str(content),
        )
    except Exception as e:
        progress_log.debug(f"警告: 保存 edit generate_log 产物失败: {e}")

    return TaskSkillGraphState(
        polished_text=str(content),
        generate_polished_done=True,
    )
