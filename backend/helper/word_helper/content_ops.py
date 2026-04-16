"""
content_ops — Word 文档内容插入与格式化。

从 update_word、gjgk_update_word、gngk_fw_zc_update_word 中提取的通用内容操作函数。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from backend.util.word_util import (
    WORD_MANUAL_LINE_BREAK,
    normalize_word_insert_text,
    wdCollapseEnd,
    wdCollapseStart,
    wdLineSpace1pt5,
    wdOutlineLevelBodyText,
    wdWithInTable,
)

from backend.helper.word_helper.range_utils import (
    ensure_editable_insert_range,
)


# ---------------------------------------------------------------------------
# 格式化
# ---------------------------------------------------------------------------

def apply_standard_insert_format(
    inserted_rng,
    *,
    font_name: str = "宋体",
    font_size: int = 12,
) -> None:
    """
    对插入的 Range 应用标准格式（宋体、指定字号、1.5 倍行距、无缩进等）。

    采用 gjgk_update_word 中的超集版本（含 PageBreakBefore 等额外属性）。
    """
    inserted_rng.Font.Name = font_name
    inserted_rng.Font.Size = font_size
    inserted_rng.Font.Bold = False

    paragraph_format = inserted_rng.ParagraphFormat
    paragraph_format.LineSpacingRule = wdLineSpace1pt5
    paragraph_format.LeftIndent = 0
    paragraph_format.FirstLineIndent = 0
    paragraph_format.OutlineLevel = wdOutlineLevelBodyText

    for attr, value in (
        ("SpaceBeforeAuto", False),
        ("SpaceAfterAuto", False),
        ("SpaceBefore", 0),
        ("SpaceAfter", 0),
        ("PageBreakBefore", False),
        ("KeepWithNext", False),
        ("KeepTogether", False),
        ("WidowControl", False),
    ):
        try:
            setattr(paragraph_format, attr, value)
        except Exception:
            continue


# ---------------------------------------------------------------------------
# 文本插入
# ---------------------------------------------------------------------------

def insert_content_with_formatting(
    doc,
    insert_range,
    line: str,
    *,
    bound_start: int,
    get_bound_end: Callable[[], int],
    font_name: str = "宋体",
    font_size: int = 12,
):
    """
    向 insert_range 处插入一行文本并应用标准格式。

    Returns:
        插入后的 Range 对象
    """
    ensure_editable_insert_range(doc, insert_range, bound_start, get_bound_end)
    start_pos = insert_range.End
    insert_range.InsertAfter(normalize_word_insert_text(line) + "\r")
    end_pos = insert_range.End
    inserted_rng = doc.Range(start_pos, end_pos - 1)

    apply_standard_insert_format(
        inserted_rng, font_name=font_name, font_size=font_size
    )

    insert_range.Collapse(wdCollapseEnd)
    return inserted_rng


# ---------------------------------------------------------------------------
# 表格插入
# ---------------------------------------------------------------------------

def insert_table_with_formatting(
    doc,
    insert_range,
    rows: List[List[str]],
    *,
    get_bound_end: Optional[Callable[[], int]] = None,
    font_name: str = "宋体",
    font_size: int = 12,
):
    """
    在 insert_range 处插入 Markdown 表格，填充内容并应用标准格式。

    Args:
        doc: Word Document COM 对象
        insert_range: 当前插入游标 Range
        rows: 二维列表 [[cell, cell, ...], ...]
        get_bound_end: 可选，获取当前插入边界末尾位置的回调
        font_name: 字体名称
        font_size: 字号

    Returns:
        创建的 Table 对象，如果 rows 为空则返回 None
    """
    if not rows:
        return None

    # 如果 insert_range 在表格内，先跳出
    try:
        if insert_range.Information(wdWithInTable):
            parent_tables = insert_range.Tables
            if parent_tables.Count > 0:
                host_table = parent_tables(1)
                end_pos = int(host_table.Range.End)
                if get_bound_end is not None:
                    bound_end = int(get_bound_end())
                    if end_pos > bound_end:
                        end_pos = bound_end
                insert_range.SetRange(end_pos, end_pos)
                insert_range.Collapse(wdCollapseStart)
    except Exception:
        pass

    cols = max(len(r) for r in rows)
    start_pos = insert_range.End
    table_range = doc.Range(start_pos, start_pos)
    table = doc.Tables.Add(table_range, len(rows), cols)
    try:
        table.Borders.Enable = True
    except Exception:
        pass

    # 填充所有行的所有单元格
    for r_idx, row in enumerate(rows):
        for c_idx in range(cols):
            val = row[c_idx] if c_idx < len(row) else ""
            try:
                cell = table.Cell(r_idx + 1, c_idx + 1)
                cell_range = cell.Range
                if cell_range.End > cell_range.Start + 1:
                    delete_range = doc.Range(cell_range.Start, cell_range.End - 1)
                    delete_range.Delete()

                cell_range = cell.Range
                cell_text = "" if val is None else str(val)
                cell_text = normalize_word_insert_text(cell_text, break_char="\r")
                cell_range.InsertBefore(cell_text)

                cell_range = cell.Range
                apply_standard_insert_format(
                    cell_range, font_name=font_name, font_size=font_size
                )
                cell_range.ParagraphFormat.Alignment = 0
                cell.VerticalAlignment = 1
            except Exception:
                pass

    try:
        insert_range.SetRange(table.Range.End, table.Range.End)
    except Exception:
        insert_range.Collapse(wdCollapseEnd)
        insert_range.Start = table.Range.End
        insert_range.End = table.Range.End
    insert_range.Collapse(wdCollapseEnd)
    return table


# ---------------------------------------------------------------------------
# 付款方式后插入位置
# ---------------------------------------------------------------------------

def resolve_following_insert_pos(
    *,
    content_end: int,
    paragraph_end: int,
    bound_end: int,
    find_next_editable_pos_bounded: Callable[..., Optional[int]],
    find_prev_editable_pos: Optional[Callable[..., Optional[int]]] = None,
    max_lookahead: int = 20000,
    max_lookback: int = 20000,
) -> tuple[int, bool]:
    """
    解析“字段后续内容”的优先插入位置。

    优先尝试字段所在段落结束后的独立段落位置；只有找不到安全位置时，
    才退回字段文本结束后的同段落位置，由调用侧决定是否继续内联降级。

    Returns:
        (safe_pos, prefer_distinct_paragraph)
    """
    content_end = int(content_end)
    paragraph_end = int(paragraph_end)
    bound_end = int(bound_end)

    preferred_start = min(max(content_end + 1, paragraph_end), bound_end)
    if preferred_start < bound_end:
        separate_pos = find_next_editable_pos_bounded(
            preferred_start,
            bound_end,
            max_lookahead=max_lookahead,
        )
        if separate_pos is not None and int(separate_pos) < bound_end:
            return int(separate_pos), True

    safe_pos: Optional[int] = None
    start_after_content = min(content_end + 1, bound_end)
    if start_after_content < bound_end:
        safe_pos = find_next_editable_pos_bounded(
            start_after_content,
            bound_end,
            max_lookahead=max_lookahead,
        )

    if (
        (safe_pos is None or int(safe_pos) >= bound_end)
        and callable(find_prev_editable_pos)
        and bound_end > content_end
    ):
        back = find_prev_editable_pos(bound_end - 1, max_lookback=max_lookback)
        if back is not None and int(back) >= content_end:
            safe_pos = int(back)

    if safe_pos is None:
        safe_pos = start_after_content

    return int(min(max(0, safe_pos), bound_end)), False


# ---------------------------------------------------------------------------
# 内联插入（段落末尾追加）
# ---------------------------------------------------------------------------

def insert_items_inline_at_end_of_paragraph(
    doc,
    para_rng,
    items: List[Dict[str, Any]],
    *,
    get_bound_end: Optional[Callable[[], int]] = None,
    font_name: str = "宋体",
    font_size: int = 12,
    log_parts: Optional[List[str]] = None,
) -> int:
    """
    在段落 Range 的末尾（冒号后），以 ManualLineBreak 分隔逐条追加 items。

    用于付款方式等字段后面空间被锁定时的内联降级插入。

    Returns:
        成功插入的 item 数量
    """
    try:
        t = para_rng.Text
        trim = 0
        while t.endswith("\r") or t.endswith("\a"):
            t = t[:-1]
            trim += 1
        pos = int(para_rng.End) - trim
    except Exception:
        pos = int(getattr(para_rng, "End", 0))

    try:
        if pos < int(para_rng.Start):
            pos = int(para_rng.End) - 1
    except Exception:
        pass

    pos = max(0, pos)
    rng = doc.Range(pos, pos)
    rng.Collapse(wdCollapseStart)
    inserted = 0

    for item in items:
        if item["type"] == "text":
            s = WORD_MANUAL_LINE_BREAK + normalize_word_insert_text(item["line"])
            st = int(rng.Start)
            rng.InsertAfter(s)
            ed = int(rng.End)
            try:
                ins = doc.Range(st, ed)
                ins.Font.Name = font_name
                ins.Font.Size = font_size
                ins.Font.Bold = False
            except Exception:
                pass
            rng.Collapse(wdCollapseEnd)
            inserted += 1
        elif item["type"] == "table":
            try:
                insert_table_with_formatting(
                    doc,
                    rng,
                    item["rows"],
                    get_bound_end=get_bound_end,
                    font_name=font_name,
                    font_size=font_size,
                )
                inserted += 1
            except Exception as e:
                if log_parts is not None:
                    log_parts.append(f"    警告: 内联插入表格失败，改为文本: {e}")
                for row in item["rows"]:
                    s = WORD_MANUAL_LINE_BREAK + normalize_word_insert_text(
                        " | ".join(row)
                    )
                    rng.InsertAfter(s)
                    rng.Collapse(wdCollapseEnd)
                    inserted += 1
    return inserted
