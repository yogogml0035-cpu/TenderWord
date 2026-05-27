from __future__ import annotations

import json
import re
from typing import Any

from backend.agents.generation.types import (
    AuditFinding,
    GenerationAgentProtocolError,
    HostAgentFinalOutput,
)


def _strip_code_fence_wrappers(text: str) -> str:
    stripped = str(text or "").strip()
    match = re.fullmatch(
        r"```(?:json)?\s*(.*?)\s*```",
        stripped,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return stripped
    return match.group(1).strip()


def _extract_first_json_value(text: str, opener: str, closer: str) -> str | None:
    raw = str(text or "")
    start = raw.find(opener)
    if start < 0:
        return None

    in_string = False
    escape = False
    depth = 0
    value_start = -1

    for index in range(start, len(raw)):
        char = raw[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == opener:
            if depth == 0:
                value_start = index
            depth += 1
            continue
        if char == closer and depth > 0:
            depth -= 1
            if depth == 0 and value_start >= 0:
                return raw[value_start : index + 1].strip()

    return None


def _build_json_candidates(raw_content: str, opener: str, closer: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def _add(value: str | None) -> None:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        candidates.append(normalized)

    initial = str(raw_content or "").lstrip("\ufeff").strip()
    stripped = _strip_code_fence_wrappers(initial)
    _add(initial)
    _add(stripped)
    for base in tuple(candidates):
        _add(_extract_first_json_value(base, opener, closer))
    return candidates


def _load_json_value(raw_content: str, opener: str, closer: str) -> Any:
    last_error: Exception | None = None
    for candidate in _build_json_candidates(raw_content, opener, closer):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
    if last_error:
        raise GenerationAgentProtocolError(f"智能体输出不是合法 JSON: {last_error}") from last_error
    raise GenerationAgentProtocolError("智能体输出不包含 JSON")


def parse_audit_findings(raw_content: str) -> list[AuditFinding]:
    parsed = _load_json_value(raw_content, "[", "]")
    if not isinstance(parsed, list):
        raise GenerationAgentProtocolError(
            f"审核智能体输出必须是 JSON 数组，实际为 {type(parsed).__name__}"
        )
    findings: list[AuditFinding] = []
    for index, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise GenerationAgentProtocolError(f"审核意见第 {index + 1} 项必须是对象")
        try:
            findings.append(AuditFinding.model_validate(item))
        except ValueError as exc:
            raise GenerationAgentProtocolError(
                f"审核意见第 {index + 1} 项缺少 evidence 或 fix_hint"
            ) from exc
    return findings


def parse_host_agent_final_output(raw_content: str) -> HostAgentFinalOutput:
    parsed = _load_json_value(raw_content, "{", "}")
    if not isinstance(parsed, dict):
        raise GenerationAgentProtocolError(
            f"host_agent 最终输出必须是 JSON 对象，实际为 {type(parsed).__name__}"
        )
    try:
        return HostAgentFinalOutput.model_validate(parsed)
    except ValueError as exc:
        raise GenerationAgentProtocolError(
            "host_agent 最终输出必须包含非空 polished_text"
        ) from exc


__all__ = [
    "parse_audit_findings",
    "parse_host_agent_final_output",
]
