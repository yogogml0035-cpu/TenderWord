from __future__ import annotations

import pathlib
import shutil
import time
import uuid
from typing import Any

from backend.nodes.common_word_nodes.generate_comments import _sanitize_filename
from backend.states import TenderGraphStateBase
from backend.util.log_util.progress_log import progress_log

NODE_PREPARE = "prepare_comment_supplement"
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
    "prepare_comment_supplement",
]
