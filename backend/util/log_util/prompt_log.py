from __future__ import annotations

import re
import time
import uuid
from pathlib import Path


def _get_prompt_log_dir(anchor_file: str, folder_name: str) -> Path:
    target = Path(anchor_file).resolve().parents[2] / "prompts_log" / folder_name
    target.mkdir(parents=True, exist_ok=True)
    return target


def get_generate_prompt_log_dir(anchor_file: str) -> Path:
    return _get_prompt_log_dir(anchor_file, "generate_log")


def get_host_agent_log_dir(anchor_file: str) -> Path:
    return _get_prompt_log_dir(anchor_file, "host_log")


def get_verify_agent_log_dir(anchor_file: str) -> Path:
    return _get_prompt_log_dir(anchor_file, "verify_log")


def _sanitize_filename_part(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "task"
    return re.sub(r'[<>:"/\\|?*\s]+', "_", text).strip("._") or "task"


def write_edit_generate_log_artifacts(
    anchor_file: str,
    *,
    task_id: str,
    rendered_prompt: str,
    generated_content: str,
    now: float | None = None,
) -> tuple[Path, Path]:
    """
    为 edit 任务写入 generate_log 双文件（渲染提示词 + 生成文本）。

    文件名保持 edit 专属命名，不影响 generate/rewrite 现有文件命名。
    """

    target_dir = get_generate_prompt_log_dir(anchor_file)
    safe_task_id = _sanitize_filename_part(task_id)
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now or time.time()))
    file_stem = f"prompt_edit_{safe_task_id}_{timestamp}"

    prompt_path = target_dir / f"{file_stem}_edit_prompt.txt"
    content_path = target_dir / f"{file_stem}_edit_generated_content.txt"
    if prompt_path.exists() or content_path.exists():
        suffix = uuid.uuid4().hex[:6]
        prompt_path = target_dir / f"{file_stem}_{suffix}_edit_prompt.txt"
        content_path = target_dir / f"{file_stem}_{suffix}_edit_generated_content.txt"

    prompt_path.write_text(str(rendered_prompt or ""), encoding="utf-8")
    content_path.write_text(str(generated_content or ""), encoding="utf-8")
    return prompt_path, content_path


def write_agent_log_artifact(
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
    "get_generate_prompt_log_dir",
    "get_host_agent_log_dir",
    "get_verify_agent_log_dir",
    "write_agent_log_artifact",
    "write_edit_generate_log_artifacts",
]
