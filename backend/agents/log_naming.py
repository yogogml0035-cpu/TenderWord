from __future__ import annotations

import re
from typing import Any


def sanitize_agent_log_part(value: Any, *, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f\s]+', "_", text).strip("._")
    return sanitized or fallback


def build_agent_log_stem(
    task_id: Any,
    *,
    project_number: Any = None,
    project_name: Any = None,
    fallback: str,
) -> str:
    parts = [sanitize_agent_log_part(task_id, fallback=fallback)]
    for value in (project_number, project_name):
        text = str(value or "").strip()
        if not text:
            continue
        parts.append(sanitize_agent_log_part(text, fallback="project"))
    return "_".join(parts)


__all__ = [
    "build_agent_log_stem",
    "sanitize_agent_log_part",
]
