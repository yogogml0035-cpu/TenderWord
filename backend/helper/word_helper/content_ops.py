"""
content_ops — Word 文档内容插入与格式化。

从 update_word、gjgk_update_word、gngk_fw_zc_update_word 中提取的通用内容操作函数。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from backend.util.word_util import (
    normalize_word_body_text,
    normalize_word_cell_text,
    wdCollapseEnd,
    wdCollapseStart,
    wdLineSpace1pt5,
    wdOutlineLevelBodyText,
    wdWithInTable,
)

from backend.helper.word_helper.range_utils import (
    ensure_editable_insert_range,
)
from backend.helper.word_helper.paragraph_boundary_ops import (
    ensure_paragraph_break_after_paragraph,
    is_writable_body_paragraph_pos,
)

GENERATED_TEXT_FONT_RESET_VERSION = "font_sanitize_v1"
GENERATED_TEXT_DEFAULT_COLOR = 0
GENERATED_TEXT_DEFAULT_HIGHLIGHT = 0
GENERATED_TEXT_DEFAULT_UNDERLINE = 0


# ---------------------------------------------------------------------------
# 格式化
# ---------------------------------------------------------------------------

def _format_range_label(range_obj) -> str:
    try:
        start = int(getattr(range_obj, "Start"))
        end = int(getattr(range_obj, "End"))
    except Exception:
        return "unknown"
    return f"{start}-{end}"


def reset_generated_text_font_format(
    range_obj,
    *,
    font_name: str = "宋体",
    font_size: int = 12,
    log_parts: Optional[List[str]] = None,
    raise_on_failure: bool = True,
) -> None:
    """
    Reset generated text to a clean character-format baseline before optional style writeback.

    This helper intentionally avoids ParagraphFormat; layout remains the
    caller's responsibility.
    """
    failures: list[str] = []
    try:
        font = getattr(range_obj, "Font", None)
    except Exception as exc:
        font = None
        failures.append(f"Font:{exc}")

    if font is None:
        failures.append("Font:missing")
    else:
        for attr, value in (
            ("Name", font_name),
            ("Size", font_size),
            ("Bold", False),
            ("Italic", False),
            ("Underline", GENERATED_TEXT_DEFAULT_UNDERLINE),
            ("StrikeThrough", False),
            ("Color", GENERATED_TEXT_DEFAULT_COLOR),
        ):
            try:
                setattr(font, attr, value)
            except Exception as exc:
                failures.append(f"{attr}:{exc}")

    try:
        setattr(range_obj, "HighlightColorIndex", GENERATED_TEXT_DEFAULT_HIGHLIGHT)
    except Exception as exc:
        failures.append(f"HighlightColorIndex:{exc}")

    if not failures:
        return

    message = (
        f"generated_insert_format_reset_version={GENERATED_TEXT_FONT_RESET_VERSION}; "
        f"range={_format_range_label(range_obj)}; failures={';'.join(failures)}"
    )
    if log_parts is not None:
        log_parts.append(f"  警告: 生成文本字体清洗失败: {message}")
    if raise_on_failure:
        raise RuntimeError(message)


def apply_standard_insert_format(
    inserted_rng,
    *,
    font_name: str = "宋体",
    font_size: int = 12,
    log_parts: Optional[List[str]] = None,
) -> None:
    """
    对插入的 Range 应用标准格式（宋体、指定字号、1.5 倍行距、无缩进等）。

    采用 gjgk_update_word 中的超集版本（含 PageBreakBefore 等额外属性）。
    """
    reset_generated_text_font_format(
        inserted_rng,
        font_name=font_name,
        font_size=font_size,
        log_parts=log_parts,
    )

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
    log_parts: Optional[List[str]] = None,
):
    """
    向 insert_range 处插入一行文本并应用标准格式。

    Returns:
        插入后的 Range 对象
    """
    ensure_editable_insert_range(doc, insert_range, bound_start, get_bound_end)
    start_pos = insert_range.End
    insert_range.InsertAfter(normalize_word_body_text(line) + "\r")
    end_pos = insert_range.End
    inserted_rng = doc.Range(start_pos, end_pos - 1)

    apply_standard_insert_format(
        inserted_rng,
        font_name=font_name,
        font_size=font_size,
        log_parts=log_parts,
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
    log_parts: Optional[List[str]] = None,
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
                cell_text = normalize_word_cell_text(cell_text)
                cell_range.InsertBefore(cell_text)

                cell_range = cell.Range
                apply_standard_insert_format(
                    cell_range,
                    font_name=font_name,
                    font_size=font_size,
                    log_parts=log_parts,
                )
                cell_range.ParagraphFormat.Alignment = 0
                cell.VerticalAlignment = 1
            except Exception as exc:
                if log_parts is not None:
                    log_parts.append(
                        f"    警告: 表格单元格格式化失败 "
                        f"r={r_idx + 1}, c={c_idx + 1}: {exc}"
                    )

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


def create_distinct_body_paragraph_after_range(
    doc,
    anchor_range,
    *,
    creation_anchor: Optional[int] = None,
    get_bound_end: Callable[[], int],
    find_next_editable_pos_bounded: Callable[..., Optional[int]],
    tender_type: Optional[str] = None,
    field_label: str = "字段",
    log_parts: Optional[List[str]] = None,
    max_lookahead: int = 20000,
) -> int:
    """
    在字段所在段落后确定一个可写的正文段落落点。

    优先让 helper 保证“可写独立正文段”存在（可能复用已有边界、也可能拆段）；
    若 helper 失败（例如 gngk 模板里付款方式后的标题段被 SDT 锁住、连 pilcrow
    前都不可写），退回 **向后扫描可编辑位置** 作为兜底——这是旧代码在这类模板
    上能跑通的唯一路径，比直接 fail-fast 更稳。

    全程严禁软回车（wdLineBreak / ``\\v``）兜底。
    """

    content_end = int(getattr(anchor_range, "End", 0))
    try:
        paragraph_range = anchor_range.Paragraphs(1).Range
    except Exception:
        paragraph_range = anchor_range

    paragraph_end = int(
        getattr(paragraph_range, "End", getattr(anchor_range, "End", 0))
    )
    bound_end_before = int(get_bound_end())
    if paragraph_end > bound_end_before:
        raise ValueError(f"{field_label}段落末尾超出插入边界，无法创建独立正文段落")

    del creation_anchor

    def _log(message: str) -> None:
        if log_parts is not None:
            log_parts.append(message)

    inserted_break, writable_pos = ensure_paragraph_break_after_paragraph(
        doc,
        paragraph_range,
        scan_bound_end=bound_end_before,
        tender_type=tender_type,
        field_name=field_label,
        max_scan_chars=max_lookahead,
        require_writable=True,
        log=_log,
    )

    bound_end_after = int(get_bound_end())
    if bound_end_after <= content_end:
        raise ValueError(f"在{field_label}后创建正文段落失败：插入边界未向后扩展")

    if writable_pos is None:
        # helper 走不通（典型：gngk 模板里付款方式后的标题段被 SDT 锁住，
        # pilcrow 前也锁，段内拆段失败）。退回向后扫描找第一个可编辑位置，
        # 和旧代码在这类模板上的行为对齐。
        fallback_start = min(max(content_end + 1, 0), bound_end_after)
        fallback_pos = find_next_editable_pos_bounded(
            fallback_start,
            bound_end_after,
            max_lookahead=max_lookahead,
        )
        if fallback_pos is None:
            raise ValueError(
                f"在{field_label}后创建正文段落失败：未找到可写独立正文段"
            )
        writable_pos = int(fallback_pos)
        if log_parts is not None:
            log_parts.append(
                f"    {field_label}后 helper 未能造段（下一段可能被 SDT 锁定），"
                f"回退到向后扫描的可编辑位置 {writable_pos}"
            )

    created_pos = int(writable_pos)
    if created_pos < content_end or created_pos >= bound_end_after:
        raise ValueError(
            f"在{field_label}后创建正文段落失败：新段落位置 {created_pos} 越界"
            f"（content_end={content_end}, bound_end={bound_end_after}）"
        )

    if log_parts is not None and writable_pos is not None:
        if inserted_break:
            log_parts.append(
                f"    {field_label}后无现成独立正文段，已主动造段，位置 {created_pos}"
            )
        elif created_pos == int(paragraph_end):
            log_parts.append(
                f"    {field_label}后复用已有可写正文段，位置 {created_pos}"
            )
    return created_pos


def ensure_following_body_paragraph_insert_pos(
    doc,
    anchor_range,
    *,
    bound_end: int,
    get_bound_end: Callable[[], int],
    find_next_editable_pos_bounded: Callable[..., Optional[int]],
    find_prev_editable_pos: Optional[Callable[..., Optional[int]]] = None,
    tender_type: Optional[str] = None,
    field_label: str = "字段",
    log_parts: Optional[List[str]] = None,
    max_lookahead: int = 20000,
    max_lookback: int = 20000,
) -> tuple[int, bool]:
    """
    返回字段后安全的正文段落插入位置。

    优先复用现成的“可写独立正文段”（例如交付日期后本就存在的空正文段）；
    若不存在或仅存在段落边界但紧邻段不可写（例如付款方式后紧跟标题段），
    则走 create_distinct_body_paragraph_after_range，由 helper 在字段段内部拆段。

    Returns:
        (insert_pos, created_new_paragraph)
    """

    content_end = int(getattr(anchor_range, "End", 0))
    if content_end > int(bound_end):
        raise ValueError(f"{field_label}字段位置超出插入边界，停止以避免侵入后置章节")

    paragraph_end = content_end
    try:
        paragraph_end = int(anchor_range.Paragraphs(1).Range.End)
    except Exception:
        paragraph_end = content_end

    safe_pos, prefer_distinct_paragraph = resolve_following_insert_pos(
        content_end=content_end,
        paragraph_end=paragraph_end,
        bound_end=int(bound_end),
        find_next_editable_pos_bounded=find_next_editable_pos_bounded,
        find_prev_editable_pos=find_prev_editable_pos,
        max_lookahead=max_lookahead,
        max_lookback=max_lookback,
    )

    # 只有当“现成独立段”确认是可写正文段时才复用；否则交给 helper 兜底。
    if prefer_distinct_paragraph:
        safe_pos = int(safe_pos)
        if safe_pos < int(get_bound_end()) and is_writable_body_paragraph_pos(
            doc, safe_pos
        ):
            if log_parts is not None:
                log_parts.append(
                    f"    优先在{field_label}段落后插入现成的可写正文段，位置 {safe_pos}"
                )
            return safe_pos, False
        if log_parts is not None:
            log_parts.append(
                f"    {field_label}后存在段落边界但并非可写正文段，改走主动造段"
            )

    created_pos = create_distinct_body_paragraph_after_range(
        doc,
        anchor_range,
        creation_anchor=safe_pos,
        get_bound_end=get_bound_end,
        find_next_editable_pos_bounded=find_next_editable_pos_bounded,
        tender_type=tender_type,
        field_label=field_label,
        log_parts=log_parts,
        max_lookahead=max_lookahead,
    )
    return created_pos, True


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
    在段落 Range 的末尾（冒号后）逐条追加正文 item。

    正文区域禁用手动换行；调用该 helper 时也会统一改成追加正文段落。

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
            s = "\r" + normalize_word_body_text(item["line"])
            st = int(rng.Start)
            rng.InsertAfter(s)
            ed = int(rng.End)
            ins = doc.Range(st, ed)
            reset_generated_text_font_format(
                ins,
                font_name=font_name,
                font_size=font_size,
                log_parts=log_parts,
            )
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
                    log_parts=log_parts,
                )
                inserted += 1
            except Exception as e:
                if log_parts is not None:
                    log_parts.append(f"    警告: 内联插入表格失败，改为文本: {e}")
                for row in item["rows"]:
                    s = "\r" + normalize_word_body_text(" | ".join(row))
                    st = int(rng.Start)
                    rng.InsertAfter(s)
                    ed = int(rng.End)
                    ins = doc.Range(st, ed)
                    reset_generated_text_font_format(
                        ins,
                        font_name=font_name,
                        font_size=font_size,
                        log_parts=log_parts,
                    )
                    rng.Collapse(wdCollapseEnd)
                    inserted += 1
    return inserted
