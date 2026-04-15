"""
text_parsing — Markdown 表格解析、文本行转 item、关键字拆分。

从 update_word、gjgk_update_word、gngk_fw_zc_update_word 中提取的通用文本解析函数。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from backend.helper.word_helper.protected_fields import (
    extract_protected_field_name,
    find_suspicious_protected_field_lines,
    format_missing_protected_field_error,
    match_protected_field_line,
    normalize_protected_field_markers,
    normalize_protected_field_text,
)

# ---------------------------------------------------------------------------
# Markdown 表格解析
# ---------------------------------------------------------------------------


def is_table_separator_line(line: str) -> bool:
    """判断一行是否为 Markdown 表格分隔行（如 `| --- | --- |`）。"""
    return bool(re.match(r"^\s*\|\s*:?-{3,}.*\|\s*$", line))


def parse_table_row(line: str) -> List[str]:
    """解析 Markdown 表格行，返回各单元格内容列表。"""
    cells = [cell.strip() for cell in line.split("|")]
    if cells and cells[0] == "":
        cells = cells[1:]
    if cells and cells[-1] == "":
        cells = cells[:-1]
    return cells


def looks_like_table_row(line: str) -> bool:
    """判断一行是否像 Markdown 表格行。"""
    stripped = (line or "").strip()
    if "|" not in stripped:
        return False
    return len(parse_table_row(stripped)) >= 2


def parse_table_block(
    lines: List[str], start_idx: int
) -> tuple[Optional[List[List[str]]], int]:
    """
    从 lines[start_idx] 开始尝试解析 Markdown 表格块。

    Returns:
        (parsed_rows, next_idx) — parsed_rows 为 None 表示未解析到表格。
    """
    table_lines: List[str] = []
    idx = start_idx
    while idx < len(lines) and lines[idx].strip().startswith("|"):
        table_lines.append(lines[idx].strip())
        idx += 1

    if len(table_lines) >= 2 and is_table_separator_line(table_lines[1]):
        header = table_lines[0]
        data_lines = table_lines[2:] if len(table_lines) > 2 else []
        all_lines = [header] + data_lines
        return [parse_table_row(line) for line in all_lines], idx

    fallback_lines: List[str] = []
    idx = start_idx
    while idx < len(lines) and looks_like_table_row(lines[idx]):
        fallback_lines.append(lines[idx].strip())
        idx += 1
    if len(fallback_lines) >= 2:
        return [parse_table_row(line) for line in fallback_lines], idx

    return None, start_idx


# ---------------------------------------------------------------------------
# 文本行 → 插入 item 转换
# ---------------------------------------------------------------------------


def convert_lines_to_items(lines: List[str]) -> List[Dict[str, Any]]:
    """
    将文本行列表转换为插入 item 列表。

    每个 item 为：
    - {"type": "text", "line": "..."} — 普通文本行
    - {"type": "table", "rows": [[...]]} — 表格
    """
    items: List[Dict[str, Any]] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        maybe_table, next_idx = parse_table_block(lines, idx)
        if maybe_table:
            items.append({"type": "table", "rows": maybe_table})
            idx = next_idx
        else:
            items.append({"type": "text", "line": line})
            idx += 1
    return items


# ---------------------------------------------------------------------------
# 关键字拆分
# ---------------------------------------------------------------------------


def _parse_keyword_line(
    line: Optional[str], marker: str
) -> tuple[str, Optional[str]]:
    """
    解析包含受保护字段 marker 的行，返回 (prefix, value)。

    例如：`2、交付日期：合同签订后30天` -> (`2、`, `合同签订后30天`)
    """
    if not line:
        return "", None
    match = match_protected_field_line(line, marker)
    if not match:
        return "", None
    return str(match["prefix"]), match.get("value")


def split_text_by_keywords(
    polished_text: str,
    ordered_markers: tuple[str, ...],
    *,
    strip_empty_lines: bool = True,
    require_all: bool = True,
    require_order: bool = True,
) -> Dict[str, Any]:
    """
    将 polished_text 按有序受保护字段 marker 拆分为多个块。

    Args:
        polished_text: 待拆分文本
        ordered_markers: 按顺序排列的 canonical marker（如 (`交付日期：`, `付款方式：`)）
        strip_empty_lines: 是否过滤空行
        require_all: 为 True 时，缺少任一 marker 则抛 ValueError
        require_order: 为 True 时，marker 必须按顺序出现

    Returns:
        字典包含：
        - `content_list`: 所有非空内容行列表
        - `blocks`: 按 marker 切分的块列表，len = len(ordered_markers) + 1
        - `keyword_lines`: {marker: line_text} — 每个 marker 所在的行
        - `keyword_parsed`: {marker: {"prefix": ..., "value": ...}} — 解析后的前缀和值
    """
    canonical_markers = normalize_protected_field_markers(ordered_markers)
    normalized_text = normalize_protected_field_text(polished_text, canonical_markers)
    polished_text_norm = normalized_text.replace("\r\n", "\n").replace("\r", "\n")
    raw_lines = polished_text_norm.split("\n")
    if strip_empty_lines:
        content_list = [line.rstrip() for line in raw_lines if line.strip() != ""]
    else:
        content_list = [line.rstrip() for line in raw_lines]

    if require_all and not content_list:
        raise ValueError("polished_text 为空，无法拆分内容")

    field_indices: Dict[str, int] = {}
    field_matches: Dict[str, Dict[str, Any]] = {}
    last_index = -1
    suspicious_hits = find_suspicious_protected_field_lines(content_list, canonical_markers)
    for marker in canonical_markers:
        field_index = None
        field_match: Optional[Dict[str, Any]] = None
        for i, line in enumerate(content_list):
            matched = match_protected_field_line(line, marker)
            if matched:
                field_index = i
                field_match = matched
                break
        if field_index is None:
            if require_all:
                raise ValueError(
                    format_missing_protected_field_error(
                        [marker],
                        suspicious_hits,
                        prefix="polished_text 缺少关键字段",
                    )
                )
            continue
        if require_order and field_index <= last_index:
            readable_order = " -> ".join(canonical_markers)
            raise ValueError(
                f"polished_text 中关键字段顺序错误: {marker} 出现在前一个关键字之后；期望顺序: {readable_order}"
            )
        field_indices[marker] = field_index
        if field_match is not None:
            field_matches[marker] = field_match
        last_index = field_index

    found_markers = [marker for marker in canonical_markers if marker in field_indices]
    found_indices = [field_indices[marker] for marker in found_markers]

    blocks: List[List[str]] = []
    if found_indices:
        blocks.append(content_list[: found_indices[0]])
    else:
        blocks.append(content_list[:])

    for i in range(len(found_indices)):
        if i + 1 < len(found_indices):
            blocks.append(content_list[found_indices[i] + 1 : found_indices[i + 1]])
        else:
            blocks.append(content_list[found_indices[i] + 1 :])

    keyword_lines: Dict[str, str] = {}
    keyword_parsed: Dict[str, Dict[str, Any]] = {}
    for marker in found_markers:
        line = content_list[field_indices[marker]]
        keyword_lines[marker] = line
        matched = field_matches.get(marker)
        if matched:
            keyword_parsed[marker] = {
                "prefix": matched["prefix"],
                "value": matched["value"],
                "canonical_marker": matched["canonical_marker"],
                "source_marker": matched["source_marker"],
                "field_name": extract_protected_field_name(marker),
            }
        else:
            prefix, value = _parse_keyword_line(line, marker)
            keyword_parsed[marker] = {
                "prefix": prefix,
                "value": value,
                "canonical_marker": marker,
                "source_marker": marker,
                "field_name": extract_protected_field_name(marker),
            }

    return {
        "normalized_text": normalized_text,
        "content_list": content_list,
        "blocks": blocks,
        "keyword_lines": keyword_lines,
        "keyword_parsed": keyword_parsed,
        "keyword_indices": field_indices,
    }
