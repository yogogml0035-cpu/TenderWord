from __future__ import annotations

import ast
import json
import re
from typing import Any

from backend.agents.generation.types import (
    AuditFinding,
    GenerationAgentProtocolError,
    ContentAgentFinalOutput,
)

AUDIT_JSON_FALLBACK_EVIDENCE = (
    "审核智能体输出格式异常，未能解析为完整 evidence/fix_hint JSON。"
)
AUDIT_JSON_FALLBACK_FIX_HINT = (
    "保持 current_text 原文不变；不要新增、删除或润色内容，等待下一轮审核重新生成结构化意见。"
)
AUDIT_FINDING_DEFAULT_FIX_HINT = (
    "根据 evidence 定位问题并作最小必要修复，保持其它内容不变。"
)
CONTRACT_PLACEHOLDER_PATTERN = re.compile(
    r"^[<＜]\s*(?:修复后|修复后的|最终)?\s*(?:完整|完整的)?\s*"
    r"(?:采购需求|需求)?\s*(?:正文|内容|draft_text|polished_text)\s*[>＞]$",
    re.IGNORECASE,
)
AUDIT_NOOP_TRANSLATION = str.maketrans(
    "",
    "",
    " \t\r\n，。！？、；：,.!?;:\"'“”‘’（）()[]【】<>《》·",
)
AUDIT_NOOP_EVIDENCE_MARKERS = (
    "无问题",
    "没有问题",
    "未发现问题",
    "不存在问题",
    "没有差异",
    "不存在差异",
    "无需修改",
    "无需修订",
    "无需调整",
    "无需处理",
    "保持不变",
    "保持原文不变",
    "保持内容不变",
    "不作修改",
    "无需变更",
    "不需要修改",
    "不需修改",
)
AUDIT_NOOP_FIX_HINT_MARKERS = (
    "无需修改",
    "无须修改",
    "不需修改",
    "不需要修改",
    "无需修订",
    "无须修订",
    "不需修订",
    "不需要修订",
    "无需调整",
    "无须调整",
    "不需调整",
    "不需要调整",
    "无需处理",
    "无须处理",
    "不需处理",
    "不需要处理",
    "保持不变",
    "保持原文不变",
    "保持内容不变",
    "不作修改",
    "无需变更",
    "无须变更",
    "不需变更",
    "不需要变更",
)
AUDIT_NOOP_FIX_HINT_EXACT = {"无"}


def is_contract_placeholder_text(value: Any) -> bool:
    text = str(value or "").strip()
    if not text or "\n" in text:
        return False
    return bool(CONTRACT_PLACEHOLDER_PATTERN.fullmatch(text))


def _normalize_audit_noop_text(value: Any) -> str:
    return str(value or "").strip().translate(AUDIT_NOOP_TRANSLATION)


def _is_noop_audit_finding(finding: AuditFinding) -> bool:
    evidence = _normalize_audit_noop_text(finding.evidence)
    fix_hint = _normalize_audit_noop_text(finding.fix_hint)
    if not evidence or not fix_hint:
        return False
    if fix_hint in AUDIT_NOOP_FIX_HINT_EXACT:
        return True
    return any(marker in evidence for marker in AUDIT_NOOP_EVIDENCE_MARKERS) and any(
        marker in fix_hint for marker in AUDIT_NOOP_FIX_HINT_MARKERS
    )


def filter_noop_audit_findings(findings: list[AuditFinding]) -> list[AuditFinding]:
    return [
        finding
        for finding in findings
        if not _is_noop_audit_finding(finding)
    ]


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

def _escape_invalid_json_backslashes(text: str) -> str:
    valid_escapes = {'"', "\\", "/", "b", "f", "n", "r", "t"}
    raw = str(text or "")
    chars: list[str] = []
    in_string = False
    index = 0

    while index < len(raw):
        char = raw[index]
        if not in_string:
            chars.append(char)
            if char == '"':
                in_string = True
            index += 1
            continue

        if char == "\\":
            next_char = raw[index + 1] if index + 1 < len(raw) else ""
            if next_char in valid_escapes:
                chars.append("\\")
                chars.append(next_char)
                index += 2
                continue
            if next_char == "u" and index + 5 < len(raw):
                unicode_candidate = raw[index + 2 : index + 6]
                if re.fullmatch(r"[0-9a-fA-F]{4}", unicode_candidate):
                    chars.append(raw[index : index + 6])
                    index += 6
                    continue
            chars.append("\\\\")
            index += 1
            continue

        chars.append(char)
        if char == '"':
            in_string = False
        index += 1

    return "".join(chars)

def _repair_common_json_issues(text: str) -> str:
    repaired = _strip_code_fence_wrappers(str(text or "").lstrip("\ufeff"))
    if repaired.lower().startswith("json\n"):
        repaired = repaired[5:].strip()
    repaired = _escape_invalid_json_backslashes(repaired)
    repaired = re.sub(r",(\s*[\]}])", r"\1", repaired)
    return repaired.strip()

def _looks_like_python_literal(candidate: str) -> bool:
    return bool(re.search(r"(^|[{\[,]\s*)'|:\s*'|\b(True|False|None)\b", candidate))


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

def _load_relaxed_json_value(raw_content: str, opener: str, closer: str) -> Any:
    last_error: Exception | None = None
    candidates = list(_build_json_candidates(raw_content, opener, closer))
    for candidate in tuple(candidates):
        repaired = _repair_common_json_issues(candidate)
        if repaired and repaired not in candidates:
            candidates.append(repaired)

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
        if not _looks_like_python_literal(candidate):
            continue
        try:
            return ast.literal_eval(candidate)
        except (SyntaxError, ValueError) as exc:
            last_error = exc
    if last_error:
        raise GenerationAgentProtocolError(f"智能体输出不是合法 JSON: {last_error}") from last_error
    raise GenerationAgentProtocolError("智能体输出不包含 JSON")

def _load_relaxed_audit_value(raw_content: str) -> Any:
    last_error: Exception | None = None
    for opener, closer in (("[", "]"), ("{", "}")):
        try:
            return _load_relaxed_json_value(raw_content, opener, closer)
        except GenerationAgentProtocolError as exc:
            last_error = exc
    raise GenerationAgentProtocolError("智能体输出不包含可修复的审核 JSON") from last_error

def _first_text(item: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = item.get(key)
        normalized = str(value or "").strip()
        if normalized:
            return normalized
    return ""

def _coerce_audit_finding(item: Any, index: int) -> AuditFinding:
    if isinstance(item, AuditFinding):
        return item

    if isinstance(item, dict):
        evidence = _first_text(
            item,
            (
                "evidence",
                "证据",
                "问题证据",
                "issue",
                "problem",
                "reason",
                "description",
                "text",
                "content",
            ),
        )
        fix_hint = _first_text(
            item,
            (
                "fix_hint",
                "修复建议",
                "建议",
                "suggestion",
                "recommendation",
                "fix",
                "action",
                "solution",
            ),
        )
        if evidence and fix_hint:
            return AuditFinding(evidence=evidence, fix_hint=fix_hint)
        if evidence:
            return AuditFinding(
                evidence=evidence,
                fix_hint=AUDIT_FINDING_DEFAULT_FIX_HINT,
            )
        if fix_hint:
            return AuditFinding(
                evidence=f"审核意见第 {index + 1} 项未提供 evidence；修复建议为：{fix_hint}",
                fix_hint=fix_hint,
            )
        compact = json.dumps(item, ensure_ascii=False, default=str)[:300]
        return AuditFinding(
            evidence=f"审核意见第 {index + 1} 项缺少 evidence/fix_hint：{compact}",
            fix_hint=AUDIT_FINDING_DEFAULT_FIX_HINT,
        )

    text = str(item or "").strip()
    if text:
        return AuditFinding(
            evidence=text,
            fix_hint=AUDIT_FINDING_DEFAULT_FIX_HINT,
        )
    return AuditFinding(
        evidence=f"审核意见第 {index + 1} 项为空，无法解析具体问题。",
        fix_hint=AUDIT_JSON_FALLBACK_FIX_HINT,
    )

def _normalize_audit_findings_value(parsed: Any) -> list[AuditFinding]:
    if isinstance(parsed, dict):
        for key in ("findings", "audit_findings", "issues", "items", "result", "data"):
            value = parsed.get(key)
            if isinstance(value, list):
                return [
                    _coerce_audit_finding(item, index)
                    for index, item in enumerate(value)
                ]
        parsed = [parsed]

    if not isinstance(parsed, list):
        raise GenerationAgentProtocolError(
            f"审核智能体输出必须是 JSON 数组，实际为 {type(parsed).__name__}"
        )
    return [_coerce_audit_finding(item, index) for index, item in enumerate(parsed)]

def build_audit_findings_fallback(error: BaseException | None = None) -> list[AuditFinding]:
    detail = str(error or "").strip()
    evidence = AUDIT_JSON_FALLBACK_EVIDENCE
    if detail:
        evidence = f"{evidence} 解析错误：{detail}"
    return [
        AuditFinding(
            evidence=evidence,
            fix_hint=AUDIT_JSON_FALLBACK_FIX_HINT,
        )
    ]


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

def coerce_audit_findings(
    raw_content: str,
    *,
    fallback_on_error: bool = False,
) -> list[AuditFinding]:
    try:
        return filter_noop_audit_findings(parse_audit_findings(raw_content))
    except GenerationAgentProtocolError as first_error:
        try:
            return filter_noop_audit_findings(
                _normalize_audit_findings_value(_load_relaxed_audit_value(raw_content))
            )
        except GenerationAgentProtocolError as exc:
            if fallback_on_error:
                return build_audit_findings_fallback(exc)
            raise first_error from exc


def parse_content_agent_final_output(raw_content: str) -> ContentAgentFinalOutput:
    parsed = _load_json_value(raw_content, "{", "}")
    if not isinstance(parsed, dict):
        raise GenerationAgentProtocolError(
            f"content_agent 最终输出必须是 JSON 对象，实际为 {type(parsed).__name__}"
        )
    try:
        return ContentAgentFinalOutput.model_validate(parsed)
    except ValueError as exc:
        raise GenerationAgentProtocolError(
            "content_agent 最终输出必须包含非空 polished_text"
        ) from exc


__all__ = [
    "build_audit_findings_fallback",
    "coerce_audit_findings",
    "filter_noop_audit_findings",
    "is_contract_placeholder_text",
    "parse_audit_findings",
    "parse_content_agent_final_output",
]
