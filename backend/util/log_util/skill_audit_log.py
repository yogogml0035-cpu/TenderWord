from __future__ import annotations

import json
import os
import re
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence


TASK_AUDIT_LOG_PATH_KEY = "task_audit_log_path"
LEGACY_REWRITE_AUDIT_LOG_PATH_KEY = "rewrite_log_path"

REWRITE_STAGE_SKILL_DIRECTORY_ROUTE = "skill_directory_route"
REWRITE_STAGE_ROUTE_OR_REPLY = REWRITE_STAGE_SKILL_DIRECTORY_ROUTE
REWRITE_STAGE_SKILL_PROMPT_RENDER = "skill_prompt_render"
TASK_AUDIT_STAGE_SKILL_PROMPT_RENDER = REWRITE_STAGE_SKILL_PROMPT_RENDER
REWRITE_STAGE_TARGET_SELECTION = "rewrite_target_selection"
REWRITE_STAGE_TEXT = "rewrite_text"

TASK_AUDIT_STAGES = frozenset(
    {
        REWRITE_STAGE_SKILL_DIRECTORY_ROUTE,
        REWRITE_STAGE_SKILL_PROMPT_RENDER,
        REWRITE_STAGE_TARGET_SELECTION,
        REWRITE_STAGE_TEXT,
    }
)
REWRITE_AUDIT_STAGES = TASK_AUDIT_STAGES


def _get_task_audit_dir(prefix: str = "rewrite") -> Path:
    safe_prefix = _sanitize_filename_part(prefix)
    subdir = "rewrite_log"
    target = Path(__file__).resolve().parents[2] / "context_log" / subdir
    target.mkdir(parents=True, exist_ok=True)
    return target


def _sanitize_filename_part(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "conversation"
    return re.sub(r'[<>:"/\\|?*\s]+', "_", text).strip("._") or "conversation"


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            dir=str(path.parent),
            prefix=f"{path.stem}_",
            suffix=".tmp",
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = handle.name
        os.replace(temp_path, path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def _load_existing_payload(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError, ValueError, TypeError):
        return {}

    return dict(data) if isinstance(data, dict) else {}


def _normalize_messages(messages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, Mapping):
            continue
        normalized.append({str(key): value for key, value in dict(message).items()})
    return normalized


def create_task_audit_log(
    audit_id: str,
    *,
    prefix: str,
    now: float | None = None,
) -> str:
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now or time.time()))
    safe_audit_id = _sanitize_filename_part(audit_id)
    safe_prefix = _sanitize_filename_part(prefix) or "task"
    audit_dir = _get_task_audit_dir(safe_prefix)

    candidate = audit_dir / f"{safe_prefix}_{timestamp}_{safe_audit_id}.json"
    if candidate.exists():
        candidate = audit_dir / (
            f"{safe_prefix}_{timestamp}_{safe_audit_id}_{uuid.uuid4().hex[:6]}.json"
        )

    _atomic_write_json(candidate, {})
    return str(candidate)


def create_rewrite_audit_log(conversation_id: str, *, now: float | None = None) -> str:
    return create_task_audit_log(conversation_id, prefix="rewrite", now=now)


def resolve_task_audit_log_path(config: Mapping[str, Any] | None) -> str:
    if not isinstance(config, Mapping):
        return ""

    configurable = config.get("configurable", config)
    if not isinstance(configurable, Mapping):
        return ""

    task_audit_log_path = str(configurable.get(TASK_AUDIT_LOG_PATH_KEY) or "").strip()
    legacy_rewrite_log_path = str(
        configurable.get(LEGACY_REWRITE_AUDIT_LOG_PATH_KEY) or ""
    ).strip()
    return task_audit_log_path or legacy_rewrite_log_path


def write_task_audit_stage(
    log_path: str,
    stage: str,
    messages: Sequence[Mapping[str, Any]],
) -> None:
    normalized_path = str(log_path or "").strip()
    if not normalized_path:
        return
    if stage not in TASK_AUDIT_STAGES:
        raise ValueError(f"unsupported task audit stage: {stage}")

    target = Path(normalized_path)
    payload = _load_existing_payload(target)
    payload[stage] = _normalize_messages(messages)
    _atomic_write_json(target, payload)


def write_rewrite_audit_stage(
    log_path: str,
    stage: str,
    messages: Sequence[Mapping[str, Any]],
) -> None:
    write_task_audit_stage(log_path, stage, messages)


__all__ = [
    "LEGACY_REWRITE_AUDIT_LOG_PATH_KEY",
    "REWRITE_AUDIT_STAGES",
    "REWRITE_STAGE_ROUTE_OR_REPLY",
    "REWRITE_STAGE_SKILL_DIRECTORY_ROUTE",
    "REWRITE_STAGE_SKILL_PROMPT_RENDER",
    "REWRITE_STAGE_TARGET_SELECTION",
    "REWRITE_STAGE_TEXT",
    "TASK_AUDIT_LOG_PATH_KEY",
    "TASK_AUDIT_STAGE_SKILL_PROMPT_RENDER",
    "TASK_AUDIT_STAGES",
    "create_rewrite_audit_log",
    "create_task_audit_log",
    "resolve_task_audit_log_path",
    "write_rewrite_audit_stage",
    "write_task_audit_stage",
]
