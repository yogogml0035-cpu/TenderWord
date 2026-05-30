from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Mapping

COMMENT_AGENT_AUDIT_ROOT = (
    Path(__file__).resolve().parents[2] / "prompts_log" / "comment_agent_audit"
)

def sanitize_audit_part(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z_.-]+", "_", str(value or "").strip())
    return normalized.strip("._") or "comment-agent"

def create_comment_agent_audit_path(
    task_id: str,
    *,
    now: float | None = None,
) -> Path:
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now or time.time()))
    COMMENT_AGENT_AUDIT_ROOT.mkdir(parents=True, exist_ok=True)
    return COMMENT_AGENT_AUDIT_ROOT / f"{sanitize_audit_part(task_id)}_{timestamp}.json"

def write_comment_agent_audit_log(
    audit_payload: Mapping[str, Any],
    *,
    task_id: str,
    path: str | Path | None = None,
    now: float | None = None,
) -> Path:
    audit_path = Path(path) if path else create_comment_agent_audit_path(task_id, now=now)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(dict(audit_payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return audit_path

__all__ = [
    "COMMENT_AGENT_AUDIT_ROOT",
    "create_comment_agent_audit_path",
    "sanitize_audit_part",
    "write_comment_agent_audit_log",
]
