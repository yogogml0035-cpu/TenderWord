from __future__ import annotations

import re
from typing import Any

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


__all__ = [
    "TABLE_PLACEHOLDER_EXTRACT_RE",
    "extract_table_placeholders",
    "find_missing_table_placeholders",
    "find_required_table_placeholders",
]
