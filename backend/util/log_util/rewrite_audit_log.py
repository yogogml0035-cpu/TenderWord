from __future__ import annotations

import json
import os
import re
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence


REWRITE_STAGE_SKILL_DIRECTORY_ROUTE = "skill_directory_route"
REWRITE_STAGE_ROUTE_OR_REPLY = REWRITE_STAGE_SKILL_DIRECTORY_ROUTE
REWRITE_STAGE_SKILL_PROMPT_RENDER = "skill_prompt_render"
REWRITE_STAGE_TARGET_SELECTION = "rewrite_target_selection"
REWRITE_STAGE_TEXT = "rewrite_text"

REWRITE_AUDIT_STAGES = frozenset(
    {
        REWRITE_STAGE_SKILL_DIRECTORY_ROUTE,
        REWRITE_STAGE_SKILL_PROMPT_RENDER,
        REWRITE_STAGE_TARGET_SELECTION,
        REWRITE_STAGE_TEXT,
    }
)


def _get_rewrite_audit_dir() -> Path:
    target = Path(__file__).resolve().parents[2] / "prompts_log" / "rewrite_log"
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


def create_rewrite_audit_log(conversation_id: str, *, now: float | None = None) -> str:
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now or time.time()))
    safe_conversation_id = _sanitize_filename_part(conversation_id)
    audit_dir = _get_rewrite_audit_dir()

    candidate = audit_dir / f"rewrite_{timestamp}_{safe_conversation_id}.json"
    if candidate.exists():
        candidate = audit_dir / (
            f"rewrite_{timestamp}_{safe_conversation_id}_{uuid.uuid4().hex[:6]}.json"
        )

    _atomic_write_json(candidate, {})
    return str(candidate)


def write_rewrite_audit_stage(
    log_path: str,
    stage: str,
    messages: Sequence[Mapping[str, Any]],
) -> None:
    normalized_path = str(log_path or "").strip()
    if not normalized_path:
        return
    if stage not in REWRITE_AUDIT_STAGES:
        raise ValueError(f"unsupported rewrite audit stage: {stage}")

    target = Path(normalized_path)
    payload = _load_existing_payload(target)
    payload[stage] = _normalize_messages(messages)
    _atomic_write_json(target, payload)


__all__ = [
    "REWRITE_STAGE_SKILL_DIRECTORY_ROUTE",
    "REWRITE_STAGE_SKILL_PROMPT_RENDER",
    "REWRITE_STAGE_ROUTE_OR_REPLY",
    "REWRITE_STAGE_TARGET_SELECTION",
    "REWRITE_STAGE_TEXT",
    "REWRITE_AUDIT_STAGES",
    "create_rewrite_audit_log",
    "write_rewrite_audit_stage",
]
