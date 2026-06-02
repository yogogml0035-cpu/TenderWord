from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_DEFAULT_AGENT_RUN_LOG_DIR = _BACKEND_DIR / "logs"
_FILENAME_SAFE_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
_BEARER_PATTERN = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+")
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r'(?i)(?:"?(?:authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|'
    r'password|passwd|secret)"?\s*[:=]\s*)(?:"[^"]*"|\'[^\']*\'|[^\s,;]+)'
)
_UNIX_PATH_PATTERN = re.compile(
    r"(?:(?:/mnt|/home|/Users|/private|/var|/tmp|/etc)/[^\s\"']+)"
)
_WINDOWS_PATH_PATTERN = re.compile(r"(?:[A-Za-z]:\\[^\s\"']+)")
_DOTENV_PATTERN = re.compile(r"(?i)\.env\b")
_TRACEBACK_PATTERN = re.compile(r"(?i)traceback \(most recent call last\):")


def _sanitize_filename_part(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return "agent-run"
    return _FILENAME_SAFE_PATTERN.sub("-", normalized).strip("._-") or "agent-run"


def scrub_sensitive_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    if _TRACEBACK_PATTERN.search(text):
        return "[REDACTED_STACK]"

    if "\n" in text:
        first_line = text.splitlines()[0].strip()
        if _TRACEBACK_PATTERN.search(first_line):
            return "[REDACTED_STACK]"
        text = first_line

    text = _BEARER_PATTERN.sub("[REDACTED_SECRET]", text)
    text = _SECRET_ASSIGNMENT_PATTERN.sub("[REDACTED_SECRET]", text)
    text = _WINDOWS_PATH_PATTERN.sub("[REDACTED_PATH]", text)
    text = _UNIX_PATH_PATTERN.sub("[REDACTED_PATH]", text)
    text = _DOTENV_PATTERN.sub("[REDACTED_PATH]", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class AgentRunAuditLogger:
    def __init__(self, logs_dir: str | Path | None = None) -> None:
        self._logs_dir = Path(logs_dir or _DEFAULT_AGENT_RUN_LOG_DIR).resolve()
        self._logs_dir.mkdir(parents=True, exist_ok=True)

    @property
    def logs_dir(self) -> Path:
        return self._logs_dir

    def log_path_for_run(self, run_id: str) -> Path:
        safe_run_id = _sanitize_filename_part(run_id)
        return self._logs_dir / f"agent-run-{safe_run_id}.jsonl"

    def append_event(
        self,
        *,
        event_name: str,
        conversation_id: str,
        selected_skills: Sequence[Any],
        payload: Any,
    ) -> Path:
        run_id = str(getattr(payload, "run_id", "") or "").strip()
        if not run_id:
            raise ValueError("run_id 不能为空")

        path = self.log_path_for_run(run_id)
        entry = self._build_entry(
            event_name=event_name,
            conversation_id=conversation_id,
            selected_skills=selected_skills,
            payload=payload,
        )
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return path

    def read_conversation_summaries(
        self,
        conversation_id: str,
        *,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        normalized_conversation_id = str(conversation_id or "").strip()
        if not normalized_conversation_id:
            return []

        summaries: list[dict[str, Any]] = []
        for log_path in sorted(
            self._logs_dir.glob("agent-run-*.jsonl"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        ):
            summary = self._summarize_log_file(log_path, normalized_conversation_id)
            if summary is None:
                continue
            summaries.append(summary)
            if len(summaries) >= max(1, limit):
                break
        return summaries

    def _build_entry(
        self,
        *,
        event_name: str,
        conversation_id: str,
        selected_skills: Sequence[Any],
        payload: Any,
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event_name,
            "run_id": str(getattr(payload, "run_id", "") or "").strip(),
            "conversation_id": str(conversation_id or "").strip(),
            "selected_skills": [self._skill_value(item) for item in selected_skills],
        }

        if event_name == "run_started":
            entry["runtime"] = self._scalar_value(getattr(payload, "runtime", ""))
        elif event_name == "thinking_stage":
            entry.update(
                {
                    "stage": self._scalar_value(getattr(payload, "stage", "")),
                    "label": self._scalar_value(getattr(payload, "label", "")),
                    "status": self._scalar_value(getattr(payload, "status", "")),
                    "summary": self._thinking_summary(payload),
                    "guard_result": self._scalar_value(getattr(payload, "guard_result", "")),
                    "tool_name": self._scalar_value(getattr(payload, "tool_name", "")),
                    "selected_skill": self._skill_value(
                        getattr(payload, "selected_skill", None)
                    ),
                }
            )
        elif event_name == "tool_call":
            entry.update(
                {
                    "tool_name": self._scalar_value(getattr(payload, "tool_name", "")),
                    "status": self._scalar_value(getattr(payload, "status", "")),
                    "summary": scrub_sensitive_text(getattr(payload, "summary", "")),
                    "task_kind": self._scalar_value(getattr(payload, "task_kind", "")),
                }
            )
        elif event_name == "task_accepted":
            entry.update(
                {
                    "task_id": self._scalar_value(getattr(payload, "task_id", "")),
                    "task_kind": self._scalar_value(getattr(payload, "task_kind", "")),
                    "status": self._scalar_value(getattr(payload, "status", "")),
                    "queue_position": getattr(payload, "queue_position", None),
                    "waiting_count": getattr(payload, "waiting_count", None),
                }
            )
        elif event_name == "needs_input":
            entry.update(
                {
                    "summary": scrub_sensitive_text(getattr(payload, "message", "")),
                    "missing_requirements": [
                        scrub_sensitive_text(item)
                        for item in getattr(payload, "missing_requirements", []) or []
                    ],
                    "selected_skill": self._skill_value(
                        getattr(payload, "selected_skill", None)
                    ),
                }
            )
        elif event_name == "done":
            entry.update(
                {
                    "summary": scrub_sensitive_text(getattr(payload, "message", "")),
                    "task_id": self._scalar_value(getattr(payload, "task_id", "")),
                    "selected_skill": self._skill_value(
                        getattr(payload, "selected_skill", None)
                    ),
                }
            )
        elif event_name == "error":
            entry.update(
                {
                    "code": self._scalar_value(getattr(payload, "code", "")),
                    "summary": scrub_sensitive_text(getattr(payload, "message", "")),
                }
            )

        return {key: value for key, value in entry.items() if value not in ("", None, [], {})}

    def _summarize_log_file(
        self,
        log_path: Path,
        conversation_id: str,
    ) -> dict[str, Any] | None:
        try:
            lines = log_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return None

        if not lines:
            return None

        summary: dict[str, Any] | None = None
        for raw_line in lines:
            try:
                entry = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if str(entry.get("conversation_id") or "").strip() != conversation_id:
                continue

            if summary is None:
                summary = {
                    "run_id": str(entry.get("run_id") or "").strip(),
                    "selected_skills": list(entry.get("selected_skills") or []),
                    "latest_event": str(entry.get("event") or "").strip(),
                    "updated_at": str(entry.get("timestamp") or "").strip(),
                    "guard_results": [],
                    "tool_names": [],
                    "stage_summaries": [],
                    "task_id": None,
                    "task_kind": None,
                }

            summary["latest_event"] = str(entry.get("event") or "").strip()
            summary["updated_at"] = str(entry.get("timestamp") or "").strip()
            if entry.get("guard_result"):
                summary["guard_results"].append(str(entry["guard_result"]))
            if entry.get("tool_name"):
                summary["tool_names"].append(str(entry["tool_name"]))
            if entry.get("summary"):
                summary["stage_summaries"].append(
                    {
                        "event": str(entry.get("event") or "").strip(),
                        "summary": scrub_sensitive_text(entry["summary"]),
                    }
                )
            if entry.get("task_id"):
                summary["task_id"] = scrub_sensitive_text(entry["task_id"])
            if entry.get("task_kind"):
                summary["task_kind"] = scrub_sensitive_text(entry["task_kind"])

        if summary is None:
            return None

        summary["guard_results"] = summary["guard_results"][-3:]
        summary["tool_names"] = summary["tool_names"][-3:]
        summary["stage_summaries"] = summary["stage_summaries"][-4:]
        return summary

    def _thinking_summary(self, payload: Any) -> str:
        stage = str(getattr(payload, "stage", "") or "").strip()
        if stage == "understand":
            selected_skill = self._skill_value(getattr(payload, "selected_skill", None))
            if selected_skill == "rewrite":
                return "已识别为 rewrite 请求。"
            if selected_skill == "edit":
                return "已识别为 edit 请求。"
            return "已接收用户消息并等待能力确认。"
        return scrub_sensitive_text(getattr(payload, "summary", ""))

    def _skill_value(self, value: Any) -> str:
        if value is None:
            return ""
        return self._scalar_value(value)

    def _scalar_value(self, value: Any) -> str:
        return scrub_sensitive_text(getattr(value, "value", value))


__all__ = [
    "AgentRunAuditLogger",
    "scrub_sensitive_text",
]
