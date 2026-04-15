from __future__ import annotations

import re
import time
import uuid
from pathlib import Path


def get_generate_prompt_log_dir(anchor_file: str) -> Path:
    target = Path(anchor_file).resolve().parents[2] / "prompts_log" / "generate_log"
    target.mkdir(parents=True, exist_ok=True)
    return target


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


__all__ = [
    "get_generate_prompt_log_dir",
    "write_edit_generate_log_artifacts",
]
