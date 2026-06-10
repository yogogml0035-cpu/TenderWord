from __future__ import annotations

import re
import time
import uuid
from pathlib import Path


def _get_context_log_dir(anchor_file: str, folder_name: str) -> Path:
    target = Path(anchor_file).resolve().parents[2] / "context_log" / folder_name
    target.mkdir(parents=True, exist_ok=True)
    return target


def get_generate_context_log_dir(anchor_file: str) -> Path:
    return _get_context_log_dir(anchor_file, "generate_log")


def get_content_agent_context_log_dir(anchor_file: str) -> Path:
    return _get_context_log_dir(anchor_file, "content_agent_log")


def get_verify_agent_context_log_dir(anchor_file: str) -> Path:
    return _get_context_log_dir(anchor_file, "verify_log")


def _sanitize_filename_part(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "task"
    return re.sub(r'[<>:"/\\|?*\s]+', "_", text).strip("._") or "task"


def write_agent_context_log_artifact(
    target_dir: Path,
    *,
    prefix: str,
    task_id: str,
    phase: str,
    content: str,
    round_index: int | None = None,
    now: float | None = None,
) -> Path:
    safe_task_id = _sanitize_filename_part(task_id)
    safe_phase = _sanitize_filename_part(phase)
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now or time.time()))
    round_part = f"_round{round_index}" if round_index is not None else ""
    file_stem = f"{prefix}_{safe_task_id}_{timestamp}{round_part}_{safe_phase}"
    path = target_dir / f"{file_stem}.txt"
    if path.exists():
        suffix = uuid.uuid4().hex[:6]
        path = target_dir / f"{file_stem}_{suffix}.txt"
    path.write_text(str(content or ""), encoding="utf-8")
    return path


__all__ = [
    "get_generate_context_log_dir",
    "get_content_agent_context_log_dir",
    "get_verify_agent_context_log_dir",
    "write_agent_context_log_artifact",
]
