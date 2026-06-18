from __future__ import annotations

import re
from typing import Any, Iterable

from backend.agents.generation.types import AuditFinding

# 行内或独立行均可命中；捕获 table_id（与 util.word_util.table_models 的字符集保持一致）。
TABLE_PLACEHOLDER_EXTRACT_RE = re.compile(r"\[\[TABLE:([A-Za-z0-9_-]+)\]\]")
NON_PLACEHOLDER_LINE_RE = re.compile(r"^\s*(?!\[\[TABLE:)(.+\S.*)$")
GENERIC_CONTEXT_LINE_RE = re.compile(r"^[\s\d一二三四五六七八九十、.．（）()：:；;/-]+$")
HEADING_CONTEXT_LINE_RE = re.compile(
    r"^\s*(?:[一二三四五六七八九十]+[、.．]|(?:\d+|（\d+）)[、.．)]?)"
)
SCORING_CONTEXT_RE = re.compile(
    r"投标评分细则|评分标准|评分要素|评审因素|分值|得分|评审价|评标基准价|评标方法|评审办法"
)


def extract_table_placeholders(text: Any) -> list[str]:
    """从任意文本中提取 `[[TABLE:<id>]]`，按首次出现顺序去重。"""
    raw = str(text or "")
    seen: set[str] = set()
    ordered: list[str] = []
    for match in TABLE_PLACEHOLDER_EXTRACT_RE.finditer(raw):
        table_id = match.group(1)
        if not table_id or table_id in seen:
            continue
        seen.add(table_id)
        ordered.append(table_id)
    return ordered


def find_missing_table_placeholders(
    tender_params: Any,
    target_text: Any,
) -> list[str]:
    """对比技术参数与待审核/最终正文，找出 target 中缺失的 table ids（保持技术参数顺序）。"""
    required = extract_table_placeholders(tender_params)
    if not required:
        return []
    present = set(extract_table_placeholders(target_text))
    return [table_id for table_id in required if table_id not in present]


def _split_table_blocks(text: Any) -> list[tuple[str, list[str]]]:
    lines = str(text or "").splitlines()
    blocks: list[tuple[str, list[str]]] = []
    context_buffer: list[str] = []

    for line in lines:
        placeholder_match = TABLE_PLACEHOLDER_EXTRACT_RE.search(line or "")
        if placeholder_match is None:
            cleaned = str(line or "").strip()
            if cleaned:
                context_buffer.append(cleaned)
                context_buffer = context_buffer[-8:]
            continue

        table_id = placeholder_match.group(1)
        if any(SCORING_CONTEXT_RE.search(raw_line) for raw_line in context_buffer):
            context_buffer = []
            continue

        context_lines: list[str] = []
        for raw_line in context_buffer:
            cleaned = raw_line.strip()
            if (
                cleaned
                and cleaned not in context_lines
                and _is_heading_context_line(cleaned)
                and not _is_generic_context_line(cleaned)
            ):
                context_lines.append(cleaned)
        for raw_line in reversed(context_buffer):
            non_placeholder = NON_PLACEHOLDER_LINE_RE.match(raw_line)
            if non_placeholder is None:
                continue
            cleaned = non_placeholder.group(1).strip()
            if cleaned not in context_lines:
                context_lines.append(cleaned)
            if len(context_lines) >= 4:
                break
        blocks.append((table_id, context_lines))
        context_buffer = []

    return blocks


def _is_table_projection_line(line: str) -> bool:
    return "/" in line or "|" in line


def _is_generic_context_line(line: str) -> bool:
    cleaned = str(line or "").strip()
    if len(cleaned) < 4:
        return True
    return bool(GENERIC_CONTEXT_LINE_RE.fullmatch(cleaned))


def _is_heading_context_line(line: str) -> bool:
    cleaned = str(line or "").strip()
    if _is_table_projection_line(cleaned):
        return False
    return bool(HEADING_CONTEXT_LINE_RE.match(cleaned)) or "：" in cleaned or ":" in cleaned


def _context_still_present(context_lines: list[str], target_text: str) -> bool:
    heading_lines = [
        line
        for line in context_lines
        if _is_heading_context_line(line) and not _is_generic_context_line(line)
    ]
    if heading_lines:
        return any(line in target_text for line in heading_lines)

    significant_lines = [
        line for line in context_lines if not _is_generic_context_line(line)
    ]
    if not significant_lines:
        return False
    if len(significant_lines) == 1:
        return significant_lines[0] in target_text
    return sum(1 for line in significant_lines if line in target_text) >= 2


def _line_matches_context(line: str, context_line: str) -> bool:
    stripped = line.strip()
    context = context_line.strip()
    return stripped == context or context in stripped


def _insert_table_placeholder(target_text: str, table_id: str, context_lines: list[str]) -> str:
    placeholder = f"[[TABLE:{table_id}]]"
    if placeholder in target_text:
        return target_text

    lines = target_text.splitlines()
    anchor_idx = -1
    for idx, line in enumerate(lines):
        if any(_line_matches_context(line, context_line) for context_line in context_lines):
            anchor_idx = idx
    if anchor_idx < 0:
        return target_text

    insert_idx = anchor_idx + 1
    while insert_idx < len(lines) and lines[insert_idx].strip().startswith("|"):
        insert_idx += 1
    lines.insert(insert_idx, placeholder)
    return "\n".join(lines)


def find_required_table_placeholders(
    tender_params: Any,
    target_text: Any,
) -> list[str]:
    """
    只要求保留那些在 target 中仍然能命中相邻上下文的结构化表。

    若模型把整段表及其上下文一起删除，不视为“缺失占位符”；
    若正文仍保留了该表的明显上下文，却删掉占位符，则视为硬错误。
    """
    target_raw = str(target_text or "")
    required_ids: list[str] = []
    for table_id, context_lines in _split_table_blocks(tender_params):
        if not context_lines:
            required_ids.append(table_id)
            continue
        if _context_still_present(context_lines, target_raw):
            required_ids.append(table_id)
    return required_ids


def restore_missing_table_placeholders(tender_params: Any, target_text: Any) -> str:
    text = str(target_text or "")
    present = set(extract_table_placeholders(text))
    for table_id, context_lines in _split_table_blocks(tender_params):
        if table_id in present or not _context_still_present(context_lines, text):
            continue
        text = _insert_table_placeholder(text, table_id, context_lines)
        present = set(extract_table_placeholders(text))
    return text


def raise_if_table_placeholders_missing(
    tender_params: Any,
    target_text: Any,
    *,
    error_prefix: str,
    error_cls: type[Exception] = ValueError,
) -> None:
    required_ids = find_required_table_placeholders(tender_params, target_text)
    if not required_ids:
        return
    present = set(extract_table_placeholders(target_text))
    missing_ids = [table_id for table_id in required_ids if table_id not in present]
    if not missing_ids:
        return
    missing_text = ", ".join(missing_ids)
    raise error_cls(
        f"{error_prefix}: {missing_text}。结构化表占位符缺失，禁止写回普通表格。"
    )


def _build_missing_table_finding(table_id: str) -> AuditFinding:
    return AuditFinding(
        evidence=(
            f"技术参数包含结构化表占位符 [[TABLE:{table_id}]]，"
            f"但待审核正文缺失该占位符。结构化表必须以占位符原样保留，"
            f"不得改写为 Markdown/手绘表格或省略。"
        ),
        fix_hint=(
            f"在对应位置补回占位符 [[TABLE:{table_id}]]，"
            f"保持技术参数中该表的原始位置与上下文；不要手工重绘表格。"
        ),
    )


def build_missing_table_placeholder_findings(
    missing_ids: Iterable[str],
) -> list[AuditFinding]:
    """将缺失的 table ids 转换为 AuditFinding 列表。"""
    return [_build_missing_table_finding(table_id) for table_id in missing_ids if table_id]


__all__ = [
    "TABLE_PLACEHOLDER_EXTRACT_RE",
    "extract_table_placeholders",
    "find_missing_table_placeholders",
    "find_required_table_placeholders",
    "restore_missing_table_placeholders",
    "raise_if_table_placeholders_missing",
    "build_missing_table_placeholder_findings",
]
