"""
cleanup_ops — 空段落清理、表格修剪、多轮清理循环。

从 update_word、gngk_fw_zc_update_word、gngk_fw_zc_delete_tender_param、
gjgk_update_word 中提取的通用清理操作。
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

from backend.util.word_util import wdWithInTable

from backend.helper.word_helper.range_utils import is_protected_range


# ---------------------------------------------------------------------------
# 文本清理工具
# ---------------------------------------------------------------------------

# 所有需要剥离的不可见 / 控制字符（超集）
_CLEANUP_INVISIBLE_CHARS = (
    "\r",
    "\n",
    "\t",
    "\x07",
    "\x0b",
    "\x0c",
    "\a",
    " ",
    "\u00a0",
    "\u2000",
    "\u2001",
    "\u2002",
    "\u2003",
    "\u2004",
    "\u2005",
    "\u2006",
    "\u2007",
    "\u2008",
    "\u2009",
    "\u200a",
    "\u200b",
    "\u3000",
    "\ufeff",
)


def normalize_cleanup_text(text: str) -> str:
    """
    将文本中的所有不可见/控制字符和空白剥离干净。

    统一了各节点中 `_visible_text`、`_normalize_cleanup_text` 等多个变体。
    """
    if not text:
        return ""
    result = str(text)
    for ch in _CLEANUP_INVISIBLE_CHARS:
        result = result.replace(ch, "")
    return result.strip()


def is_effectively_empty_text(text: str) -> bool:
    """判断文本在清理后是否为空。"""
    return normalize_cleanup_text(text) == ""


def _range_is_in_table(range_obj) -> bool:
    try:
        return bool(range_obj.Information(wdWithInTable))
    except Exception:
        return False


def _doc_range_is_in_table(doc, start: int, end: int) -> bool:
    try:
        return _range_is_in_table(doc.Range(int(start), int(end)))
    except Exception:
        return False


def _position_is_at_table(doc, pos: int) -> bool:
    pos = int(pos)
    if _doc_range_is_in_table(doc, pos, pos):
        return True
    return _doc_range_is_in_table(doc, pos, pos + 1)


def _is_table_separator_blank_paragraph(doc, paragraph_range) -> bool:
    try:
        if _range_is_in_table(paragraph_range):
            return False
        if not is_effectively_empty_text(paragraph_range.Text):
            return False
        start = int(paragraph_range.Start)
        end = int(paragraph_range.End)
    except Exception:
        return False

    if start <= 0:
        return False
    if not _doc_range_is_in_table(doc, start - 1, start):
        return False
    return _position_is_at_table(doc, end)


# ---------------------------------------------------------------------------
# 表格修剪
# ---------------------------------------------------------------------------

def row_is_empty(row) -> bool:
    """判断表格行的所有单元格是否为空（清理不可见字符后）。"""
    try:
        cells = row.Cells
        for c in range(1, cells.Count + 1):
            try:
                txt = cells(c).Range.Text
            except Exception:
                txt = ""
            if normalize_cleanup_text(txt):
                return False
        return True
    except Exception:
        return False


def trim_table_trailing_empty_rows(table) -> int:
    """从表格末尾向前删除空白行，返回删除的行数。"""
    removed = 0
    try:
        for r in range(table.Rows.Count, 0, -1):
            try:
                row = table.Rows(r)
                if row_is_empty(row):
                    row.Delete()
                    removed += 1
                else:
                    break
            except Exception:
                break
    except Exception:
        return removed
    return removed


# ---------------------------------------------------------------------------
# 空段落清理
# ---------------------------------------------------------------------------

def cleanup_blank_paragraphs(
    doc,
    *,
    range_start: int,
    range_end: int,
    is_protected_fn: Optional[Callable] = None,
    log_parts: Optional[List[str]] = None,
) -> int:
    """
    删除 [range_start, range_end] 范围内的空白段落。

    Args:
        is_protected_fn: 可选，判断段落 Range 是否受保护的回调

    Returns:
        删除的空段落数量
    """
    if int(range_end) <= int(range_start):
        return 0

    try:
        paragraphs = list(
            doc.Range(int(range_start), int(range_end)).Paragraphs
        )
    except Exception:
        return 0

    deleted = 0
    for para in reversed(paragraphs):
        try:
            if para.Range.Information(wdWithInTable):
                continue
            if is_protected_fn is not None and is_protected_fn(para.Range):
                continue
            if is_effectively_empty_text(para.Range.Text):
                if _is_table_separator_blank_paragraph(doc, para.Range):
                    continue
                para.Range.Delete()
                deleted += 1
        except Exception:
            continue

    if deleted > 0 and log_parts is not None:
        log_parts.append(f"清理空白段落 {deleted} 个")
    return deleted


def _cleanup_paragraph_linebreaks(
    doc,
    *,
    range_start: int,
    range_end: int,
    is_protected_fn: Optional[Callable] = None,
    log_parts: Optional[List[str]] = None,
) -> tuple[int, int]:
    """
    清理可编辑段落中的多余换行和空白字符。

    Returns:
        (cleaned_count, deleted_empty_count)
    """
    if int(range_end) <= int(range_start):
        return 0, 0

    cleaned_count = 0
    paras_to_delete = []

    try:
        paragraphs = doc.Range(int(range_start), int(range_end)).Paragraphs
    except Exception:
        return 0, 0

    for para in paragraphs:
        try:
            if para.Range.Information(wdWithInTable):
                continue
            para_text = para.Range.Text
            if is_effectively_empty_text(para_text):
                continue
            if is_protected_fn is not None and is_protected_fn(para.Range):
                continue

            para_range = para.Range
            full_text = para_range.Text
            text_without_mark = full_text.rstrip("\r\n\a")

            if is_effectively_empty_text(text_without_mark):
                continue

            cleaned_text = (
                text_without_mark.replace("\r", "")
                .replace("\n", "")
                .replace("\r\n", "")
                .replace("\x07", "")
                .replace("\x0b", "")
                .replace("\x0c", "")
            )
            cleaned_text = re.sub(
                r"[\t\u00a0\u2000-\u200b\u3000]+", " ", cleaned_text
            )
            cleaned_text = re.sub(r" {2,}", " ", cleaned_text).strip()

            if cleaned_text and cleaned_text != text_without_mark:
                para_range.Text = cleaned_text + "\r"
                cleaned_count += 1
                if log_parts is not None:
                    log_parts.append(f"    已清理: {cleaned_text[:50]}...")
            elif not cleaned_text:
                paras_to_delete.append(para_range)
                if log_parts is not None:
                    log_parts.append(
                        f"    标记删除（清理后为空）: '{para_text[:50]}...'"
                    )
        except Exception as e:
            if log_parts is not None:
                log_parts.append(f"    警告: 清理段落时出错: {e}")

    for prng in reversed(paras_to_delete):
        try:
            prng.Delete()
        except Exception as e:
            if log_parts is not None:
                log_parts.append(f"    警告: 无法删除段落: {e}")

    return cleaned_count, len(paras_to_delete)


# ---------------------------------------------------------------------------
# 空表格清理
# ---------------------------------------------------------------------------

def cleanup_empty_tables(
    doc,
    *,
    range_start: int,
    range_end: int,
    is_protected_fn: Optional[Callable] = None,
    log_parts: Optional[List[str]] = None,
) -> tuple[int, int, int]:
    """
    修剪表格尾部空行，并删除完全空的表格。

    Returns:
        (trimmed_tables, trimmed_rows, deleted_empty_tables)
    """
    if int(range_end) <= int(range_start):
        return 0, 0, 0

    try:
        tbl_rng = doc.Range(int(range_start), int(range_end))
        tables = tbl_rng.Tables
    except Exception:
        return 0, 0, 0

    trimmed_tables = 0
    trimmed_rows_total = 0
    deleted_empty_tables = 0

    for t_idx in range(tables.Count, 0, -1):
        try:
            tbl = tables(t_idx)
            if is_protected_fn is not None and is_protected_fn(tbl.Range):
                continue
            removed_rows = trim_table_trailing_empty_rows(tbl)
            if removed_rows > 0:
                trimmed_tables += 1
                trimmed_rows_total += removed_rows

            try:
                cleaned_text = normalize_cleanup_text(tbl.Range.Text)
            except Exception:
                cleaned_text = "x"
            if not cleaned_text:
                tbl.Range.Delete()
                deleted_empty_tables += 1
        except Exception:
            continue

    if log_parts is not None and (trimmed_tables > 0 or deleted_empty_tables > 0):
        log_parts.append(
            f"  修剪表格 {trimmed_tables} 个（删除空行 {trimmed_rows_total} 行），"
            f"删除空表格 {deleted_empty_tables} 个"
        )

    return trimmed_tables, trimmed_rows_total, deleted_empty_tables


# ---------------------------------------------------------------------------
# 多轮清理（统一封装）
# ---------------------------------------------------------------------------

def multi_pass_cleanup(
    doc,
    *,
    build_range_fn: Callable[[], tuple[int, int]],
    is_protected_fn: Optional[Callable] = None,
    log_parts: Optional[List[str]] = None,
    max_passes: int = 5,
    step_label: str = "步骤",
    cleanup_blank_paragraphs: bool = True,
    cleanup_paragraph_text: bool = True,
) -> Dict[str, int]:
    """
    多轮循环清理：删空段 → 清换行 → 再删空段 → 修剪表格。

    统一了 update_word(步骤5)、gngk_update(步骤4)、gngk_delete(步骤3) 的清理逻辑。

    Args:
        build_range_fn: 返回 (range_start, range_end) 的回调
        is_protected_fn: 判断 Range 是否受保护的回调
        log_parts: 日志列表
        max_passes: 最大轮数
        step_label: 日志前缀
        cleanup_blank_paragraphs: 是否删除空白段落
        cleanup_paragraph_text: 是否压平段落内换行/清理段落文本

    Returns:
        统计信息字典
    """
    # 形参 cleanup_blank_paragraphs / cleanup_paragraph_text 与本模块顶层的
    # 同名函数会互相遮蔽；一旦 caller 传入 False（例如显式保留空段场景），
    # 下面的 cleanup_blank_paragraphs(...) 调用就会变成“调用 bool”，直接抛
    # TypeError: 'bool' object is not callable。
    # 这里先把两个 flag 复制到不重名的局部变量，再对顶层函数做本地别名，
    # 彻底消除名字冲突。
    do_blank_cleanup = bool(cleanup_blank_paragraphs)
    do_text_cleanup = bool(cleanup_paragraph_text)
    _cleanup_blank_paragraphs = globals()["cleanup_blank_paragraphs"]

    total_empty_deleted = 0
    total_cleaned = 0
    total_linebreak_deleted = 0

    if not do_blank_cleanup and log_parts is not None:
        log_parts.append(f"  {step_label}.1：跳过空段落清理，保留显式空正文段落。")
    if not do_text_cleanup and log_parts is not None:
        log_parts.append(f"  {step_label}.2：跳过段落内换行清理，保留正文段落语义。")

    for pass_num in range(1, max_passes + 1):
        if not do_blank_cleanup:
            break

        range_start, range_end = build_range_fn()

        if log_parts is not None:
            log_parts.append(f"  {step_label}.1 第 {pass_num} 轮：删除空段落...")

        # 第一轮：删除空段落
        empty_deleted = _cleanup_blank_paragraphs(
            doc,
            range_start=range_start,
            range_end=range_end,
            is_protected_fn=is_protected_fn,
        )
        total_empty_deleted += empty_deleted
        if log_parts is not None:
            log_parts.append(
                f"  第 {pass_num} 轮完成：删除空段 {empty_deleted} 个。"
            )

        if empty_deleted == 0:
            if log_parts is not None:
                log_parts.append(
                    f"  未再发现空段，第 {pass_num} 轮后停止。"
                )
            break

        if not do_text_cleanup:
            continue

        # 第二轮：清理可编辑段落中的换行
        range_start, range_end = build_range_fn()
        if log_parts is not None:
            log_parts.append(f"  {step_label}.2：清理可编辑段落中的换行...")

        cleaned, lb_deleted = _cleanup_paragraph_linebreaks(
            doc,
            range_start=range_start,
            range_end=range_end,
            is_protected_fn=is_protected_fn,
            log_parts=log_parts,
        )
        total_cleaned += cleaned
        total_linebreak_deleted += lb_deleted

        if log_parts is not None:
            log_parts.append(
                f"  {step_label}.2完成：清理 {cleaned} 段，删除 {lb_deleted} 个空段。"
            )

        # 第三轮：最终检查剩余空段落
        range_start, range_end = build_range_fn()
        if log_parts is not None:
            log_parts.append(f"  {step_label}.3：最终检查剩余空段落...")

        final_deleted = _cleanup_blank_paragraphs(
            doc,
            range_start=range_start,
            range_end=range_end,
            is_protected_fn=is_protected_fn,
        )
        total_empty_deleted += final_deleted

        if log_parts is not None:
            if final_deleted > 0:
                log_parts.append(
                    f"  {step_label}.3完成：删除剩余空段 {final_deleted} 个。"
                )
            else:
                log_parts.append(f"  {step_label}.3完成：未发现剩余空段。")

    # 最后：修剪表格
    range_start, range_end = build_range_fn()
    t_tables, t_rows, d_tables = cleanup_empty_tables(
        doc,
        range_start=range_start,
        range_end=range_end,
        is_protected_fn=is_protected_fn,
        log_parts=log_parts,
    )

    if log_parts is not None:
        if cleanup_blank_paragraphs and cleanup_paragraph_text:
            log_parts.append(f"{step_label}完成：已清理可编辑内容中的空段落与多余换行。")
        elif cleanup_blank_paragraphs:
            log_parts.append(f"{step_label}完成：已清理多余空段落并保留正文段落语义。")
        elif cleanup_paragraph_text:
            log_parts.append(f"{step_label}完成：已清理段落文本噪音并保留显式空段。")
        else:
            log_parts.append(f"{step_label}完成：已跳过正文段落清理，仅修剪表格噪音。")

    return {
        "empty_deleted": total_empty_deleted,
        "cleaned_paragraphs": total_cleaned,
        "linebreak_deleted": total_linebreak_deleted,
        "trimmed_tables": t_tables,
        "trimmed_rows": t_rows,
        "deleted_empty_tables": d_tables,
    }
