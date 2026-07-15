"""条款重要性标识规范化（确定性兜底）。

仅在段落/单元格行首，或「条款号 + 分隔符」之后，把三角类统一为 ▲、星类统一为 ★。
不处理 ΔT、5*6、型号与普通正文中的技术符号。
"""

from __future__ import annotations

import re
from typing import Iterable, Mapping

from backend.util.word_util.table_models import (
    StructuredTableModel,
    TableCellModel,
    normalize_structured_table_model,
)

# 显式白名单，不用 Unicode 名称模糊判断。
TRIANGLE_MARKERS = frozenset("▲△▴▵▶▷▸▹►▻▼▽▾▿◀◁◂◃◢◣◤◥∆Δ⊿")
STAR_MARKERS = frozenset(
    "*＊﹡∗※★☆✦✧✩✪✫✬✭✮✯✰✱✲✳✴✵✶✷✸❂❃❈❉❊❋"
)
CANONICAL_TRIANGLE = "▲"
CANONICAL_STAR = "★"
ALL_MARKERS = TRIANGLE_MARKERS | STAR_MARKERS

_MARKER_CLASS = re.escape("".join(sorted(ALL_MARKERS)))
# 条款号：阿拉伯层级号或中文序号
_CLAUSE_NUM = r"(?:\d+(?:\.\d+)*|[一二三四五六七八九十]+)"
# 条款号后允许的分隔：顿号、点、全角点、半/全角右括号、空白
_SEP = r"[、.．)）\s]+"
# 标识后必须像条款正文：数字、中文等；排除 ΔT 这类拉丁字母技术符号
_AFTER_MARKER = r"(?=[\d０-９一二三四五六七八九十\u4e00-\u9fff（(【\[])"

# 行首：可选空白 + 可选条款编号前缀 + 标识
# 编号前缀含 1.1、  1）  （1）  一、  等
_LINE_MARKER_RE = re.compile(
    rf"^(?P<head>\s*(?:"
    rf"{_CLAUSE_NUM}{_SEP}"
    rf"|（\d+）\s*"
    rf"|\(\d+\)\s*"
    rf")?)"
    rf"(?P<marker>[{_MARKER_CLASS}])"
    rf"{_AFTER_MARKER}"
)


def _canonical_marker(ch: str) -> str | None:
    if ch in TRIANGLE_MARKERS:
        return CANONICAL_TRIANGLE
    if ch in STAR_MARKERS:
        return CANONICAL_STAR
    return None


def normalize_clause_markers(text: str) -> tuple[str, list[tuple[str, str]]]:
    """规范化正文/单元格文本中的条款标识。

    Returns:
        (规范化后文本, [(原片段, 现片段), ...]) 仅包含实际发生替换的位置。
    """
    raw = str(text or "")
    if not raw:
        return "", []

    normalized_newlines = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized_newlines.split("\n")
    changes: list[tuple[str, str]] = []
    out_lines: list[str] = []

    for line in lines:
        match = _LINE_MARKER_RE.match(line)
        if match is None:
            out_lines.append(line)
            continue

        marker = match.group("marker")
        canon = _canonical_marker(marker)
        if canon is None or marker == canon:
            out_lines.append(line)
            continue

        start, end = match.start("marker"), match.end("marker")
        # 锚点取含标识的最小可读片段，便于 Word 定位
        snip_start = max(0, start - 4)
        snip_end = min(len(line), end + 28)
        old_snip = line[snip_start:snip_end]
        new_line = line[:start] + canon + line[end:]
        new_snip = new_line[snip_start : snip_start + len(old_snip)]
        changes.append((old_snip, new_snip))
        out_lines.append(new_line)

    if "\r\n" in raw and "\n" not in raw.replace("\r\n", ""):
        joiner = "\r\n"
    elif "\r" in raw and "\n" not in raw:
        joiner = "\r"
    else:
        joiner = "\n"

    return joiner.join(out_lines), changes


def build_marker_correction_comments(
    changes: Iterable[tuple[str, str]],
) -> list[dict[str, str]]:
    """把标识替换结果转成 CommentInstruction 候选。"""
    comments: list[dict[str, str]] = []
    for old_snip, new_snip in changes:
        old = str(old_snip or "").strip()
        new = str(new_snip or "").strip()
        if not old or not new or old == new:
            continue
        comments.append(
            {
                "reference_text": new,
                "comment_text": f'原技术参数为“{old}”，现改为“{new}”',
            }
        )
    return comments


def normalize_table_models_markers(
    models: Iterable[Mapping] | None,
) -> tuple[list[StructuredTableModel], list[tuple[str, str]]]:
    """规范化 tender_param_table_models 各单元格文本。"""
    if not models:
        return [], []

    out: list[StructuredTableModel] = []
    all_changes: list[tuple[str, str]] = []
    for raw_model in models:
        if not isinstance(raw_model, Mapping):
            continue
        model = normalize_structured_table_model(raw_model)
        if model is None:
            continue
        new_cells: list[TableCellModel] = []
        for cell in model["cells"]:
            new_text, cell_changes = normalize_clause_markers(cell.get("text") or "")
            all_changes.extend(cell_changes)
            new_cells.append(
                TableCellModel(
                    row=cell["row"],
                    col=cell["col"],
                    row_span=cell["row_span"],
                    col_span=cell["col_span"],
                    text=new_text,
                )
            )
        out.append(
            StructuredTableModel(
                table_id=model["table_id"],
                rows=model["rows"],
                cols=model["cols"],
                cells=new_cells,
            )
        )
    return out, all_changes


__all__ = [
    "TRIANGLE_MARKERS",
    "STAR_MARKERS",
    "CANONICAL_TRIANGLE",
    "CANONICAL_STAR",
    "normalize_clause_markers",
    "build_marker_correction_comments",
    "normalize_table_models_markers",
]
