"""
国际公开（gjgk）专用的同页 Word 回填节点。

该节点既接入当前 `gjgk` graph，也保留手工调试和同页直插回归入口。
逻辑目标：
1. 使用 gjgk 的双锚点双字号定位正文范围；
2. 直接删除前后锚点之间的原正文；
3. 将硬编码/传入文本按“文本 + Markdown 表格”的顺序回填到前置锚点后的同页正文起点；
4. 避免额外空白段落、表格顺序错乱和插入漂移到下一页。
"""

from __future__ import annotations

import os
import pathlib
import re
import shutil
import stat
import sys
import time
from typing import Any, Callable, Dict, List, Optional

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config.tender_config import (  # noqa: E402
    get_anchor_target_sizes,
    get_default_anchor_texts,
)
from backend.nodes.common_word_nodes.comment_writeback import (  # noqa: E402
    write_polished_comments,
)
from backend.states import GjgkTenderGraphState  # noqa: E402
from backend.util.log_util.progress_log import progress_log  # noqa: E402
from backend.util.word_util import (  # noqa: E402
    close_word_application,
    create_word_application,
    open_document_with_retry,
    save_document_with_retry,
    unprotect_document,
    normalize_word_insert_text,
    wdActiveEndPageNumber,
    wdCollapseEnd,
    wdCollapseStart,
    wdWithInTable,
)
from backend.util.word_util.anchor_utils import (  # noqa: E402
    find_anchor_range,
    resolve_anchor_content_range,
)
from backend.helper.word_helper.range_utils import (  # noqa: E402
    is_range_locked,
    is_locked_exception,
    range_overlaps,
)
from backend.helper.word_helper.text_parsing import (  # noqa: E402
    parse_table_block,
)
from backend.helper.word_helper.content_ops import (  # noqa: E402
    apply_standard_insert_format,
)
from backend.helper.word_helper.cleanup_ops import (  # noqa: E402
    normalize_cleanup_text,
    cleanup_blank_paragraphs,
)
from backend.helper.word_helper.inline_style_ops import (  # noqa: E402
    apply_inline_style_fragments,
    summarize_style_writeback_result,
)

NODE_NAME = "gjgk_update_word"
INSERT_FONT_NAME = "宋体"
INSERT_FONT_SIZE = 12
CONTROL_CHARS = {"\r", "\n", "\v", "\f", "\a"}
DEFAULT_TEST_SOURCE_DOC = (
    BACKEND_ROOT / "test_doc" / "254DSITC2512-招标文件-发售稿-财政模板.doc"
)
DEFAULT_TEST_UPDATE_SOURCE_DOC = (
    BACKEND_ROOT / "test_doc" / "1.doc"
)
DEFAULT_TEST_SUFFIX = "-gjgk-update-test"
DEFAULT_DELETE_TEST_SUFFIX = "-gjgk-delete-test"
DEFAULT_DIAG_SUFFIX = "-gjgk-lock-diagnose"
BOOTSTRAP_MARKER_PREFIX = "[[GJGK_BOOTSTRAP_"
MANUAL_TEST_INSERT_TEXT = """1、设备名称及数量：
2、交付日期：合同签订后30天内
3、交付地点：一、项目概述
采购人指定地点
4、付款方式：货到验收合格（出具合同验收单或验收报告）且采购人收到其发票后三个月内，支付全部货款（100%）。

二、技术需求
须提供详细技术需求。

三、售后要求
1、★质保期：验收合格后整机免费质保≥3年。
2、★售后服务：提供报价设备均需提供原厂（制造商）售后，并出具相关证明文件。
3、医疗设备必须符合 IHE 医疗信息系统集成规范，并免费提供信息系统接口，医学影像设备须提供 DICOM软硬件接口，数字化医疗设备须提供HL7软硬件接口，并由供应商承担相应信息系统联机费用。

四、每套配置要求
注：供应商按上述配置要求自行提供响应设备的配置清单。
"""


def _visible_log(message: str) -> None:
    progress_log.info(f"[{NODE_NAME}] {message}")


def _build_insert_items(polished_text: str) -> List[Dict[str, Any]]:
    normalized_text = polished_text.replace("\r\n", "\n").replace("\r", "\n")
    raw_lines = [line.rstrip() for line in normalized_text.split("\n")]

    items: List[Dict[str, Any]] = []
    idx = 0
    while idx < len(raw_lines):
        if not raw_lines[idx].strip():
            items.append({"type": "text", "line": ""})
            idx += 1
            continue

        maybe_table, next_idx = parse_table_block(raw_lines, idx)
        if maybe_table:
            items.append({"type": "table", "rows": maybe_table})
            idx = next_idx
            continue

        items.append({"type": "text", "line": raw_lines[idx].strip()})
        idx += 1

    while items and items[-1].get("type") == "text" and items[-1].get("line") == "":
        items.pop()

    return items


def _resolve_gjgk_content_range(doc, word_app, before_hit, after_hit) -> Dict[str, int]:
    return resolve_anchor_content_range(
        doc=doc,
        word_app=word_app,
        before_hit=before_hit,
        after_hit=after_hit,
        tender_type="gjgk",
        allow_empty=True,
    )


def _set_collapsed_range(insert_range, position: int) -> None:
    insert_range.SetRange(int(position), int(position))
    insert_range.Collapse(wdCollapseStart)


def _build_bootstrap_marker() -> str:
    return f"{BOOTSTRAP_MARKER_PREFIX}{time.time_ns()}]]"


def _get_position_page(doc, position: int, fallback_page: int) -> int:
    try:
        doc_end = int(doc.Content.End)
        if doc_end <= 0:
            return int(fallback_page)
        probe_start = min(max(0, int(position)), max(0, doc_end - 1))
        probe_end = min(doc_end, probe_start + 1)
        probe_rng = doc.Range(probe_start, probe_end)
        return int(probe_rng.Information(wdActiveEndPageNumber))
    except Exception:
        return int(fallback_page)


def _find_next_editable_pos_bounded(
    doc,
    *,
    start_pos: int,
    bound_start: int,
    get_bound_end: Callable[[], int],
    max_lookahead: int = 20000,
    raise_on_missing: bool = True,
) -> Optional[int]:
    latest_end = int(get_bound_end())
    doc_end = int(doc.Content.End)
    scan_end = min(latest_end, doc_end)
    pos = min(max(int(start_pos), int(bound_start)), scan_end)

    for _ in range(max_lookahead + 1):
        try:
            if not is_range_locked(doc, doc.Range(pos, pos)):
                return pos
        except Exception:
            pass
        if pos >= scan_end:
            break
        pos += 1

    if raise_on_missing:
        raise ValueError("锚点范围内未找到可编辑插入位置")
    return None


def _pick_outermost_table(tables):
    try:
        count = int(getattr(tables, "Count", 0))
    except Exception:
        return None

    picked_table = None
    picked_span = -1
    for idx in range(1, count + 1):
        try:
            table = tables(idx)
            table_range = getattr(table, "Range", None)
            if table_range is None:
                continue
            table_start = int(table_range.Start)
            table_end = int(table_range.End)
            span = table_end - table_start
            if span >= picked_span:
                picked_table = table
                picked_span = span
        except Exception:
            continue
    return picked_table


def _is_within_table(rng) -> bool:
    try:
        return bool(rng.Information(wdWithInTable))
    except Exception:
        pass

    try:
        tables = getattr(rng, "Tables", None)
        return int(getattr(tables, "Count", 0)) > 0
    except Exception:
        return False


def _find_next_non_table_editable_pos_bounded(
    doc,
    *,
    start_pos: int,
    bound_start: int,
    get_bound_end: Callable[[], int],
    max_lookahead: int = 20000,
) -> int:
    latest_end = int(get_bound_end())
    doc_end = int(doc.Content.End)
    scan_end = min(latest_end, doc_end)
    pos = min(max(int(start_pos), int(bound_start)), scan_end)

    for _ in range(max_lookahead + 1):
        probe = doc.Range(pos, pos)
        try:
            if not _is_within_table(probe) and not is_range_locked(doc, probe):
                return pos
        except Exception:
            pass
        if pos >= scan_end:
            break
        pos += 1

    raise ValueError("表格后未找到表外可编辑插入位置")


def _move_insert_range_after_current_table(
    doc,
    insert_range,
    *,
    bound_start: int,
    get_bound_end: Callable[[], int],
) -> bool:
    max_hops = 8
    for _ in range(max_hops):
        try:
            if not _is_within_table(insert_range):
                return True
        except Exception:
            return False

        try:
            parent_tables = insert_range.Tables
        except Exception:
            return False

        host_table = _pick_outermost_table(parent_tables)
        if host_table is None:
            return False

        try:
            host_table.Range.InsertParagraphAfter()
        except Exception:
            pass

        latest_end = int(get_bound_end())
        next_pos = min(max(int(host_table.Range.End), int(bound_start)), latest_end)
        try:
            next_pos = _find_next_non_table_editable_pos_bounded(
                doc,
                start_pos=next_pos,
                bound_start=bound_start,
                get_bound_end=get_bound_end,
            )
        except ValueError:
            pass

        _set_collapsed_range(insert_range, next_pos)

        try:
            if not _is_within_table(insert_range):
                return True
        except Exception:
            return False

    return False


def _find_first_insert_position_on_anchor_page(
    doc,
    *,
    start_pos: int,
    bound_start: int,
    get_bound_end: Callable[[], int],
    anchor_page: int,
    max_lookahead: int = 20000,
) -> int:
    latest_end = int(get_bound_end())
    doc_end = int(doc.Content.End)
    scan_end = min(latest_end, doc_end)
    pos = min(max(int(start_pos), int(bound_start)), scan_end)

    is_within_table = globals().get("_is_within_table")

    for _ in range(max_lookahead + 1):
        if _get_position_page(doc, pos, anchor_page) != int(anchor_page):
            break

        probe = doc.Range(pos, pos)
        if is_range_locked(doc, probe):
            if pos >= scan_end:
                break
            pos += 1
            continue

        try:
            in_table = bool(is_within_table(probe)) if callable(is_within_table) else bool(probe.Information(wdWithInTable))
        except Exception:
            in_table = False
        if in_table:
            raise ValueError("删除正文后插入起点仍位于旧表格宿主内")

        return pos

    raise ValueError("前置锚点同页内未找到可编辑插入位置")


def _find_next_editable_pos_on_page_bounded(
    doc,
    *,
    start_pos: int,
    anchor_page: int,
    get_bound_end: Callable[[], int],
    max_lookahead: int = 50000,
) -> Optional[int]:
    try:
        doc_end = int(doc.Content.End)
    except Exception:
        return None

    scan_end = min(max(0, int(get_bound_end())), max(0, doc_end))
    pos = min(max(0, int(start_pos)), scan_end)
    for _ in range(max_lookahead + 1):
        if pos > scan_end:
            break
        if _get_position_page(doc, pos, anchor_page) != int(anchor_page):
            break
        probe = doc.Range(pos, pos)
        try:
            if (not _is_within_table(probe)) and (not is_range_locked(doc, probe)):
                return pos
        except Exception:
            pass
        pos += 1
    return None


def _reposition_insert_range_if_locked(
    doc,
    insert_range,
    *,
    insert_start: int,
    anchor_page: int,
    get_bound_end: Callable[[], int],
    log_parts: Optional[List[str]] = None,
) -> bool:
    try:
        cur_pos = int(insert_range.Start)
    except Exception:
        cur_pos = int(insert_start)

    try:
        if not is_range_locked(doc, doc.Range(cur_pos, cur_pos)):
            return False
    except Exception:
        return False

    next_pos = _find_next_editable_pos_bounded(
        doc,
        start_pos=cur_pos + 1,
        bound_start=insert_start,
        get_bound_end=get_bound_end,
        raise_on_missing=False,
    )
    if next_pos is None or next_pos <= cur_pos:
        next_pos = _find_next_editable_pos_on_page_bounded(
            doc,
            start_pos=cur_pos + 1,
            anchor_page=anchor_page,
            get_bound_end=get_bound_end,
        )

    if next_pos is None:
        return False

    _set_collapsed_range(insert_range, next_pos)
    if log_parts is not None:
        log_parts.append(f"游标后校验命中锁定，已重定位到 {next_pos}")
    return True


def _delete_original_content(
    doc,
    *,
    range_start: int,
    get_bound_end: Callable[[], int],
    log_parts: List[str],
) -> None:
    initial_end = int(get_bound_end())
    if initial_end <= int(range_start):
        log_parts.append("锚点区间为空，直接执行同页插入")
        return

    deleted_tables = 0
    skipped_tables = 0
    try:
        tables = doc.Range(int(range_start), initial_end).Tables
        for idx in range(tables.Count, 0, -1):
            try:
                table = tables(idx)
                table_start = int(table.Range.Start)
                table_end = int(table.Range.End)
                if not range_overlaps(table_start, table_end, range_start, initial_end):
                    continue
                if is_range_locked(doc, table.Range):
                    skipped_tables += 1
                    continue
                table.Range.Delete()
                deleted_tables += 1
            except Exception:
                continue
    except Exception:
        pass

    deleted_paragraphs = 0
    skipped_paragraphs = 0
    try:
        paragraphs = list(doc.Range(int(range_start), int(get_bound_end())).Paragraphs)
    except Exception:
        paragraphs = []

    for para in reversed(paragraphs):
        try:
            para_start = int(para.Range.Start)
            para_end = int(para.Range.End)
            if not range_overlaps(para_start, para_end, range_start, int(get_bound_end())):
                continue
            if is_range_locked(doc, para.Range):
                skipped_paragraphs += 1
                continue
            para.Range.Delete()
            deleted_paragraphs += 1
        except Exception:
            continue

    if deleted_tables or deleted_paragraphs or skipped_tables or skipped_paragraphs:
        log_parts.append(
            f"删除原内容: 表格 {deleted_tables} 个，段落 {deleted_paragraphs} 个"
            f"，跳过锁定表格 {skipped_tables} 个，锁定段落 {skipped_paragraphs} 个"
        )

    used_fallback_delete = False
    latest_end = int(get_bound_end())
    if latest_end > int(range_start):
        try:
            if not is_range_locked(doc, doc.Range(int(range_start), latest_end)):
                doc.Range(int(range_start), latest_end).Delete()
                used_fallback_delete = True
        except Exception:
            pass

    if used_fallback_delete:
        log_parts.append("执行整段可编辑删除")


def _ensure_insert_range(
    doc,
    insert_range,
    *,
    bound_start: int,
    get_bound_end: Callable[[], int],
) -> None:
    try:
        insert_range.Collapse(wdCollapseStart)
    except Exception:
        pass

    try:
        pos = int(insert_range.Start)
    except Exception:
        pos = int(bound_start)

    current_end = int(get_bound_end())
    if pos < bound_start:
        pos = bound_start
    if pos > current_end:
        pos = current_end
    _set_collapsed_range(insert_range, pos)

    try:
        if is_range_locked(doc, doc.Range(pos, pos)):
            pos2 = _find_next_editable_pos_bounded(
                doc,
                start_pos=pos + 1,
                bound_start=bound_start,
                get_bound_end=get_bound_end,
                raise_on_missing=False,
            )
            if pos2 is not None and pos2 > pos:
                _set_collapsed_range(insert_range, pos2)
    except Exception:
        pass


def _trim_leading_layout_controls(
    doc,
    *,
    range_start: int,
    get_bound_end: Callable[[], int],
    log_parts: List[str],
    max_scan: int = 16,
) -> int:
    cursor = max(0, int(range_start))
    removed = 0

    for _ in range(max_scan):
        current_end = int(get_bound_end())
        if cursor >= current_end or cursor >= int(doc.Content.End):
            break
        probe = doc.Range(cursor, min(cursor + 1, int(doc.Content.End)))
        probe_text = str(getattr(probe, "Text", "") or "")
        if probe_text not in CONTROL_CHARS:
            break
        probe.Delete()
        removed += 1

    if removed > 0:
        log_parts.append(f"局部清理起点控制符 {removed} 个")

    return cursor


def _prime_empty_insert_slot(
    doc,
    insert_range,
    *,
    bound_start: int,
    get_bound_end: Callable[[], int],
    log_parts: Optional[List[str]] = None,
) -> str:
    marker_text = _build_bootstrap_marker()
    if log_parts is not None:
        log_parts.append(
            "空区间首写引导：先写入一次性 bootstrap 标记，消耗 Word 的首条宿主漂移"
        )

    _insert_text_line(
        doc,
        insert_range,
        marker_text,
        bound_start=bound_start,
        get_bound_end=get_bound_end,
        log_parts=log_parts,
    )
    _set_collapsed_range(insert_range, bound_start)

    if log_parts is not None:
        log_parts.append(
            f"空区间首写引导：bootstrap 标记已写入，游标重置回 {bound_start}"
        )
    return marker_text


def _insert_text_line(
    doc,
    insert_range,
    line: str,
    *,
    bound_start: int,
    get_bound_end: Callable[[], int],
    log_parts: Optional[List[str]] = None,
):
    try:
        if _is_within_table(insert_range):
            _move_insert_range_after_current_table(
                doc,
                insert_range,
                bound_start=bound_start,
                get_bound_end=get_bound_end,
            )
    except Exception:
        pass

    _ensure_insert_range(
        doc,
        insert_range,
        bound_start=bound_start,
        get_bound_end=get_bound_end,
    )
    if log_parts is not None:
        log_parts.append(_describe_range_state(doc, insert_range, label="文本插入前"))
    start_pos = int(insert_range.Start)
    inserted_text = normalize_word_insert_text(line) + "\r"
    effective_start = start_pos
    live_end = start_pos

    try:
        insert_range.InsertAfter(inserted_text)
        try:
            live_start = int(getattr(insert_range, "Start", start_pos))
        except Exception:
            live_start = start_pos
        try:
            live_end = int(getattr(insert_range, "End", start_pos))
        except Exception:
            live_end = start_pos
        if live_end > start_pos and live_start > start_pos:
            effective_start = live_start
    except Exception as exc:
        if not is_locked_exception(exc):
            raise

        fallback_inserted = False
        for fallback_char in ("\r", "\v"):
            try:
                if _is_within_table(doc.Range(start_pos, start_pos)):
                    moved = _move_insert_range_after_current_table(
                        doc,
                        insert_range,
                        bound_start=bound_start,
                        get_bound_end=get_bound_end,
                    )
                    if moved:
                        start_pos = int(insert_range.Start)
                probe = doc.Range(start_pos, start_pos)
                probe.InsertAfter(fallback_char)
                effective_start = start_pos + 1
                _set_collapsed_range(insert_range, effective_start)
                insert_range.InsertAfter(inserted_text)
                try:
                    live_start = int(getattr(insert_range, "Start", effective_start))
                except Exception:
                    live_start = effective_start
                try:
                    live_end = int(getattr(insert_range, "End", effective_start))
                except Exception:
                    live_end = effective_start
                if live_end > effective_start and live_start > effective_start:
                    effective_start = live_start
                fallback_inserted = True
                if log_parts is not None:
                    log_parts.append(
                        f"文本插入触发锁定，已降级补控制符后重试成功（位置 {start_pos}）"
                    )
                break
            except Exception:
                continue

        if not fallback_inserted:
            raise

    end_pos = max(int(live_end), int(effective_start) + len(inserted_text))
    inserted_rng = doc.Range(effective_start, max(effective_start, end_pos - 1))
    apply_standard_insert_format(inserted_rng)
    _set_collapsed_range(insert_range, end_pos)
    _ensure_insert_range(
        doc,
        insert_range,
        bound_start=bound_start,
        get_bound_end=lambda: max(int(get_bound_end()), int(end_pos)),
    )
    if log_parts is not None and effective_start != start_pos:
        log_parts.append(
            f"文本插入 live range 实际起点已从 {start_pos} 重定位到 {effective_start}"
        )
    if log_parts is not None and live_end <= effective_start:
        log_parts.append(
            f"文本插入未返回 live range 末尾，按长度兜底推进游标到 {end_pos}"
        )
    return inserted_rng


def _insert_table(
    doc,
    insert_range,
    rows: List[List[str]],
    *,
    bound_start: int,
    get_bound_end: Callable[[], int],
    log_parts: Optional[List[str]] = None,
):
    if not rows:
        return None

    _ensure_insert_range(
        doc,
        insert_range,
        bound_start=bound_start,
        get_bound_end=get_bound_end,
    )
    if log_parts is not None:
        log_parts.append(_describe_range_state(doc, insert_range, label="表格插入前"))
    try:
        if _is_within_table(insert_range):
            moved_after_table = _move_insert_range_after_current_table(
                doc,
                insert_range,
                bound_start=bound_start,
                get_bound_end=get_bound_end,
            )
            if not moved_after_table:
                parent_tables = insert_range.Tables
                if int(getattr(parent_tables, "Count", 0)) > 0:
                    host_table = parent_tables(1)
                    end_pos = int(host_table.Range.End)
                    bound_end = int(get_bound_end())
                    if end_pos > bound_end:
                        end_pos = bound_end
                    _set_collapsed_range(insert_range, end_pos)
    except Exception:
        pass

    cols = max(len(row) for row in rows)
    start_pos = int(insert_range.End)
    table_range = doc.Range(start_pos, start_pos)
    table = doc.Tables.Add(table_range, len(rows), cols)

    try:
        table.Borders.Enable = True
    except Exception:
        pass

    for row_idx, row in enumerate(rows):
        for col_idx in range(cols):
            cell_value = row[col_idx] if col_idx < len(row) else ""
            try:
                cell = table.Cell(row_idx + 1, col_idx + 1)
                cell_range = cell.Range
                if cell_range.End > cell_range.Start + 1:
                    doc.Range(cell_range.Start, cell_range.End - 1).Delete()

                cell_range = cell.Range
                cell_text = normalize_word_insert_text(
                    str(cell_value or ""), break_char="\r"
                )
                cell_range.InsertBefore(cell_text)

                cell_range = cell.Range
                apply_standard_insert_format(cell_range)
                cell_range.ParagraphFormat.Alignment = 0
                cell.VerticalAlignment = 1
            except Exception:
                continue

    try:
        insert_range.SetRange(table.Range.End, table.Range.End)
    except Exception:
        insert_range.Collapse(wdCollapseEnd)
        insert_range.Start = table.Range.End
        insert_range.End = table.Range.End

    # Word COM 在表尾位置经常仍判定为表内，下一项若继续写入会把新文本/新表格灌进宿主表。
    moved_after_table = False
    try:
        insert_range.Collapse(wdCollapseEnd)
        moved_after_table = _move_insert_range_after_current_table(
            doc,
            insert_range,
            bound_start=bound_start,
            get_bound_end=get_bound_end,
        )
    except Exception:
        moved_after_table = False

    if not moved_after_table:
        _ensure_insert_range(
            doc,
            insert_range,
            bound_start=bound_start,
            get_bound_end=lambda: max(
                int(get_bound_end()),
                int(getattr(insert_range, "Start", start_pos)),
                int(getattr(insert_range, "End", start_pos)),
            ),
        )
    return table


def _remove_marker_paragraphs(
    doc,
    *,
    marker_text: str,
    search_start: int,
    search_end: int,
    log_parts: Optional[List[str]] = None,
) -> int:
    if not marker_text:
        return 0
    if int(search_end) <= int(search_start):
        return 0

    try:
        paragraphs = list(doc.Range(int(search_start), int(search_end)).Paragraphs)
    except Exception:
        return 0

    removed = 0
    for para in reversed(paragraphs):
        try:
            para_text = normalize_cleanup_text(getattr(para.Range, "Text", ""))
            if para_text != marker_text:
                continue
            para.Range.Delete()
            removed += 1
        except Exception:
            continue

    if removed > 0 and log_parts is not None:
        log_parts.append(f"已清理 bootstrap 标记段落 {removed} 个")
    return removed


def _build_manual_test_output_path(source_doc_path: pathlib.Path) -> pathlib.Path:
    return source_doc_path.with_name(
        f"{source_doc_path.stem}{DEFAULT_TEST_SUFFIX}{source_doc_path.suffix}"
    )


def _build_manual_delete_output_path(source_doc_path: pathlib.Path) -> pathlib.Path:
    return source_doc_path.with_name(
        f"{source_doc_path.stem}{DEFAULT_DELETE_TEST_SUFFIX}{source_doc_path.suffix}"
    )


def _build_manual_diag_output_path(source_doc_path: pathlib.Path) -> pathlib.Path:
    return source_doc_path.with_name(
        f"{source_doc_path.stem}{DEFAULT_DIAG_SUFFIX}{source_doc_path.suffix}"
    )


def _build_manual_delete_state(prepared_doc_path: str) -> GjgkTenderGraphState:
    before_text, after_text = get_default_anchor_texts("gjgk")
    return GjgkTenderGraphState(
        tender_type="gjgk",
        prepared_doc_path=str(prepared_doc_path),
        insertion_before_text=before_text,
        insertion_after_text=after_text,
    )


def _ensure_file_writable(file_path: pathlib.Path) -> None:
    """确保测试副本文档可写，避免继承源文件只读属性导致 Word 锁定。"""
    if not file_path.exists():
        raise FileNotFoundError(f"测试副本不存在，无法设置可写: {file_path}")

    try:
        current_mode = file_path.stat().st_mode
        file_path.chmod(current_mode | stat.S_IWRITE)
    except Exception as exc:
        raise RuntimeError(f"设置测试副本为可写失败: {file_path}") from exc


def _prepare_manual_test_copy(source_doc_path: pathlib.Path, output_path: pathlib.Path) -> None:
    """复制测试文档并在复制后显式清除只读标记。"""
    shutil.copy2(source_doc_path, output_path)
    _ensure_file_writable(output_path)


def _build_manual_test_state(prepared_doc_path: str) -> GjgkTenderGraphState:
    before_text, after_text = get_default_anchor_texts("gjgk")
    return GjgkTenderGraphState(
        tender_type="gjgk",
        prepared_doc_path=str(prepared_doc_path),
        polished_text=MANUAL_TEST_INSERT_TEXT,
        insertion_before_text=before_text,
        insertion_after_text=after_text,
    )


def _safe_int(value: Any, default: int = -1) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _describe_range_state(doc, rng, *, label: str = "") -> str:
    """返回当前位置的可读诊断信息，用于精确定位锁定触发点。"""
    try:
        start = int(getattr(rng, "Start", -1))
        end = int(getattr(rng, "End", -1))
    except Exception:
        start, end = -1, -1

    page = _get_position_page(doc, start if start >= 0 else 0, 1)
    within_table = False
    locked = False
    try:
        within_table = _is_within_table(rng)
    except Exception:
        pass
    try:
        locked = is_range_locked(doc, rng)
    except Exception:
        pass

    prefix = f"{label}: " if label else ""
    return (
        f"{prefix}range[{start},{end}] page={page} "
        f"in_table={within_table} locked={locked}"
    )


def diagnose_gjgk_lock(
    *,
    source_doc_path: pathlib.Path,
    before_text: str,
    after_text: str,
) -> Dict[str, Any]:
    """诊断 gjgk 模板锁定来源，输出可直接用于排查的结构化信息。"""
    if not source_doc_path.exists():
        raise FileNotFoundError(f"诊断源文件不存在: {source_doc_path}")

    diag_doc_path = _build_manual_diag_output_path(source_doc_path)
    _prepare_manual_test_copy(source_doc_path, diag_doc_path)

    report: Dict[str, Any] = {
        "diag_doc_path": str(diag_doc_path),
        "file_writable": os.access(diag_doc_path, os.W_OK),
    }

    word = None
    doc = None
    com_initialized = False

    try:
        word, com_initialized = create_word_application(
            initial_delay=0.0,
            post_init_delay=1.0,
            use_existing=False,
            verify=False,
            node_name=NODE_NAME,
        )
        doc = open_document_with_retry(
            word_app=word,
            file_path=str(diag_doc_path),
            read_only=False,
            node_name=NODE_NAME,
        )

        report["doc_read_only"] = bool(getattr(doc, "ReadOnly", False))
        report["doc_protection_type"] = _safe_int(getattr(doc, "ProtectionType", -1), -1)
        report["doc_protect_content"] = bool(getattr(doc, "ProtectContent", False))

        can_unprotect = unprotect_document(doc, node_name=NODE_NAME)
        report["unprotect_result"] = bool(can_unprotect)
        report["doc_protection_type_after_unprotect"] = _safe_int(
            getattr(doc, "ProtectionType", -1), -1
        )

        before_size, after_size = get_anchor_target_sizes("gjgk")
        before_hit, after_hit = find_anchor_range(
            doc,
            before_text,
            after_text,
            before_size=before_size,
            after_size=after_size,
            prefer_before="last",
            prefer_after="first",
        )
        if not before_hit or not after_hit:
            report["anchor_found"] = False
            report["before_hit"] = before_hit
            report["after_hit"] = after_hit
            return report

        report["anchor_found"] = True
        report["before_hit"] = before_hit
        report["after_hit"] = after_hit

        content_range = _resolve_gjgk_content_range(
            doc=doc,
            word_app=word,
            before_hit=before_hit,
            after_hit=after_hit,
        )
        range_start = int(content_range["range_start"])
        range_end = int(content_range["range_end"])
        report["content_range"] = content_range

        probe_positions: List[int] = [range_start]
        if range_end > range_start:
            probe_positions.append(min(range_start + 1, range_end))
            probe_positions.append(max(range_start, range_end - 1))

        unique_positions = []
        for p in probe_positions:
            if p not in unique_positions:
                unique_positions.append(p)

        probes: List[Dict[str, Any]] = []
        for pos in unique_positions:
            probe = doc.Range(pos, pos)
            probe_info: Dict[str, Any] = {
                "pos": pos,
                "page": _get_position_page(doc, pos, content_range.get("start_page", 1)),
                "is_within_table": _is_within_table(probe),
                "is_range_locked": is_range_locked(doc, probe),
            }

            try:
                test_text = f"[LOCK-DIAG-{pos}]"
                w_rng = doc.Range(pos, pos)
                w_rng.InsertAfter(test_text)
                delete_rng = doc.Range(pos, min(pos + len(test_text), int(doc.Content.End)))
                delete_rng.Delete()
                probe_info["write_probe"] = "ok"
            except Exception as exc:
                probe_info["write_probe"] = f"fail: {exc}"

            probes.append(probe_info)

        report["probes"] = probes

    finally:
        close_word_application(
            word_app=word,
            doc=doc,
            com_initialized=com_initialized,
            wait_time=1.0,
            node_name=NODE_NAME,
        )

    return report


def gjgk_update_word(state: GjgkTenderGraphState, config) -> GjgkTenderGraphState:
    start_time = time.perf_counter()

    prepared_doc_path = state.get("prepared_doc_path")
    polished_text = state.get("polished_text")
    insertion_before_text = state.get("insertion_before_text")
    insertion_after_text = state.get("insertion_after_text")

    if not prepared_doc_path:
        raise ValueError("需要 prepared_doc_path 来插入 gjgk 内容")
    if not polished_text:
        raise ValueError("需要 polished_text 来插入 gjgk 内容")
    if not insertion_before_text or not insertion_after_text:
        raise ValueError("gjgk 插入必须提供 insertion_before_text 和 insertion_after_text")

    before_size, after_size = get_anchor_target_sizes("gjgk")
    items = _build_insert_items(polished_text)
    if not items:
        raise ValueError("gjgk 插入内容为空，无法执行更新")

    has_explicit_blank_lines = any(
        item.get("type") == "text" and item.get("line") == "" for item in items
    )

    log_parts = [f"共解析插入项 {len(items)} 条"]
    word = None
    doc = None
    com_initialized = False
    comment_writeback_summary = ""
    comment_writeback_added = 0
    comment_writeback_failed = 0
    comment_writeback_skipped = 0
    comment_writeback_errors: list[dict[str, str]] = []
    style_writeback_summary = ""
    style_writeback_result = None

    try:
        _visible_log("开始执行 gjgk 同页回填")
        word, com_initialized = create_word_application(
            initial_delay=0.0,
            post_init_delay=1.0,
            use_existing=False,
            verify=False,
            node_name=NODE_NAME,
        )
        doc = open_document_with_retry(
            word_app=word,
            file_path=prepared_doc_path,
            read_only=False,
            node_name=NODE_NAME,
        )
        log_parts.append(f"已打开文档: {prepared_doc_path}")

        if unprotect_document(doc, node_name=NODE_NAME):
            log_parts.append("已取消文档保护")

        before_hit, after_hit = find_anchor_range(
            doc,
            insertion_before_text,
            insertion_after_text,
            before_size=before_size,
            after_size=after_size,
            prefer_before="last",
            prefer_after="first",
        )
        if not before_hit:
            raise ValueError(f"未找到前置锚点段落: {insertion_before_text}")
        if not after_hit:
            raise ValueError(f"未找到后置锚点段落: {insertion_after_text}")

        content_range = _resolve_gjgk_content_range(
            doc=doc,
            word_app=word,
            before_hit=before_hit,
            after_hit=after_hit,
        )
        range_start = int(content_range["range_start"])
        range_end = int(content_range["range_end"])
        start_page = int(content_range["start_page"])
        end_page = int(content_range["end_page"])

        log_parts.append(
            f"锚点范围 {range_start}-{range_end}，页码 {start_page}-{end_page}"
        )

        after_anchor_marker = doc.Range(int(after_hit["start"]), int(after_hit["start"]))
        insert_cursor_bound_end = [None]

        def get_insertion_bound_end() -> int:
            try:
                anchor_bound_end = int(after_anchor_marker.Start)
            except Exception:
                anchor_bound_end = int(range_end)

            cursor_bound_end = insert_cursor_bound_end[0]
            if cursor_bound_end is None:
                return anchor_bound_end
            return max(anchor_bound_end, int(cursor_bound_end))

        _delete_original_content(
            doc,
            range_start=range_start,
            get_bound_end=get_insertion_bound_end,
            log_parts=log_parts,
        )
        log_parts.append(
            f"删除阶段完成: start={range_start}, bound_end={int(get_insertion_bound_end())}, "
            f"anchor_after={int(after_hit['start'])}"
        )

        insert_start = _trim_leading_layout_controls(
            doc,
            range_start=range_start,
            get_bound_end=get_insertion_bound_end,
            log_parts=log_parts,
        )
        insert_start = _find_first_insert_position_on_anchor_page(
            doc,
            start_pos=insert_start,
            bound_start=range_start,
            get_bound_end=get_insertion_bound_end,
            anchor_page=start_page,
        )
        log_parts.append(f"同页插入起点定位为 {insert_start}（页 {start_page}）")
        log_parts.append(
            _describe_range_state(doc, doc.Range(insert_start, insert_start), label="插入起点状态")
        )
        insert_range = doc.Range(insert_start, insert_start)
        _set_collapsed_range(insert_range, insert_start)
        insert_cursor_bound_end[0] = int(insert_start)
        bootstrap_marker = None
        if range_start == range_end and items:
            bootstrap_marker = _prime_empty_insert_slot(
                doc,
                insert_range,
                bound_start=insert_start,
                get_bound_end=get_insertion_bound_end,
                log_parts=log_parts,
            )
            insert_cursor_bound_end[0] = int(insert_start)

        inserted_count = 0
        for item_idx, item in enumerate(items, start=1):
            attempts = 0
            while attempts < 80:
                attempts += 1
                try:
                    _ensure_insert_range(
                        doc,
                        insert_range,
                        bound_start=insert_start,
                        get_bound_end=get_insertion_bound_end,
                    )
                    item_type = item.get("type")
                    if item_type == "text":
                        log_parts.append(
                            f"准备插入[{item_idx}/{len(items)}] 文本, attempt={attempts}, "
                            f"cursor={int(insert_range.Start)}, bound_end={int(get_insertion_bound_end())}"
                        )
                        _insert_text_line(
                            doc,
                            insert_range,
                            item["line"],
                            bound_start=insert_start,
                            get_bound_end=get_insertion_bound_end,
                            log_parts=log_parts,
                        )
                        insert_cursor_bound_end[0] = max(
                            int(insert_cursor_bound_end[0] or insert_start),
                            int(insert_range.Start),
                            int(insert_range.End),
                        )
                        _reposition_insert_range_if_locked(
                            doc,
                            insert_range,
                            insert_start=insert_start,
                            anchor_page=start_page,
                            get_bound_end=get_insertion_bound_end,
                            log_parts=log_parts,
                        )
                        insert_cursor_bound_end[0] = max(
                            int(insert_cursor_bound_end[0] or insert_start),
                            int(insert_range.Start),
                            int(insert_range.End),
                        )
                        inserted_count += 1
                        log_parts.append(
                            f"[{inserted_count}/{len(items)}] 已插入文本: {item['line'][:40]} "
                            f"(游标 {int(insert_range.Start)} / 上界 {int(get_insertion_bound_end())})"
                        )
                        break

                    log_parts.append(
                        f"准备插入[{item_idx}/{len(items)}] 表格, attempt={attempts}, "
                        f"cursor={int(insert_range.Start)}, bound_end={int(get_insertion_bound_end())}, "
                        f"rows={len(item.get('rows', []))}"
                    )
                    _insert_table(
                        doc,
                        insert_range,
                        item["rows"],
                        bound_start=insert_start,
                        get_bound_end=get_insertion_bound_end,
                        log_parts=log_parts,
                    )
                    insert_cursor_bound_end[0] = max(
                        int(insert_cursor_bound_end[0] or insert_start),
                        int(insert_range.Start),
                        int(insert_range.End),
                    )
                    _reposition_insert_range_if_locked(
                        doc,
                        insert_range,
                        insert_start=insert_start,
                        anchor_page=start_page,
                        get_bound_end=get_insertion_bound_end,
                        log_parts=log_parts,
                    )
                    insert_cursor_bound_end[0] = max(
                        int(insert_cursor_bound_end[0] or insert_start),
                        int(insert_range.Start),
                        int(insert_range.End),
                    )
                    inserted_count += 1
                    log_parts.append(
                        f"[{inserted_count}/{len(items)}] 已插入表格，行数 {len(item['rows'])} "
                        f"(游标 {int(insert_range.Start)} / 上界 {int(get_insertion_bound_end())})"
                    )
                    break
                except Exception as exc:
                    try:
                        current_state = _describe_range_state(doc, insert_range, label="插入失败点")
                    except Exception:
                        current_state = "插入失败点状态获取失败"
                    log_parts.append(
                        f"插入异常 item={item_idx}/{len(items)} attempt={attempts}: {exc}; {current_state}"
                    )

                    if is_locked_exception(exc):
                        try:
                            cur_pos = int(insert_range.Start)
                        except Exception:
                            cur_pos = int(insert_start)

                        # L1: keep existing bounded recovery
                        next_pos = _find_next_editable_pos_bounded(
                            doc,
                            start_pos=cur_pos + 1,
                            bound_start=insert_start,
                            get_bound_end=get_insertion_bound_end,
                            raise_on_missing=False,
                        )

                        # L2: full same-page scan when bounded recovery fails
                        if next_pos is None or next_pos <= cur_pos:
                            next_pos = _find_next_editable_pos_on_page_bounded(
                                doc,
                                start_pos=cur_pos + 1,
                                anchor_page=start_page,
                                get_bound_end=get_insertion_bound_end,
                            )

                        # L3: reset to insert_start and retry from earliest editable point
                        if next_pos is None or next_pos <= cur_pos:
                            next_pos = _find_next_editable_pos_bounded(
                                doc,
                                start_pos=insert_start,
                                bound_start=insert_start,
                                get_bound_end=get_insertion_bound_end,
                                raise_on_missing=False,
                            )

                        if next_pos is None:
                            log_parts.append(
                                "锁定降级失败: bounded/同页扫描/回退insert_start均未找到可编辑点位，终止当前插入"
                            )
                            raise

                        _set_collapsed_range(insert_range, next_pos)
                        log_parts.append(
                            f"锁定降级: 游标从 {cur_pos} 移动到 {next_pos} 后重试"
                        )
                        insert_cursor_bound_end[0] = max(
                            int(insert_cursor_bound_end[0] or insert_start),
                            int(insert_range.Start),
                            int(insert_range.End),
                        )
                        continue
                    raise

        inserted_end = int(insert_range.Start)
        if bootstrap_marker:
            bootstrap_search_end = max(
                int(inserted_end),
                int(get_insertion_bound_end()),
                int(after_hit["start"]),
            )
            removed_bootstrap = _remove_marker_paragraphs(
                doc,
                marker_text=bootstrap_marker,
                search_start=insert_start,
                search_end=bootstrap_search_end,
                log_parts=log_parts,
            )
            if removed_bootstrap == 0:
                removed_bootstrap = _remove_marker_paragraphs(
                    doc,
                    marker_text=bootstrap_marker,
                    search_start=0,
                    search_end=int(doc.Content.End),
                    log_parts=log_parts,
                )
                if removed_bootstrap > 0:
                    log_parts.append("bootstrap 标记未在插入边界内命中，已回退到全文清理")

        inserted_end = int(insert_range.Start)
        if has_explicit_blank_lines:
            log_parts.append("检测到输入包含显式空行，跳过空白段落清理")
        else:
            cleanup_blank_paragraphs(
                doc,
                range_start=insert_start,
                range_end=inserted_end,
                log_parts=log_parts,
            )

        comment_step_label = "步骤6"
        if "inline_style_fragments" in state:
            style_writeback_result = apply_inline_style_fragments(
                doc=doc,
                inline_style_fragments=state.get("inline_style_fragments"),
                bound_start=int(range_start),
                bound_end=int(get_insertion_bound_end()),
                log_parts=log_parts,
                step_label="步骤6",
            )
            style_writeback_summary = summarize_style_writeback_result(
                style_writeback_result
            )
            comment_step_label = "步骤7"

        # Capture comment writeback result for tracking and failure detection
        polished_comments = state.get("polished_comments") or []
        generated_count = state.get("generated_comment_count", 0)

        comment_writeback_result = write_polished_comments(
            doc=doc,
            polished_comments=polished_comments,
            bound_start=int(range_start),
            bound_end=int(get_insertion_bound_end()),
            log_parts=log_parts,
            step_label=comment_step_label,
        )

        # Extract writeback stats
        added = comment_writeback_result.get("added", 0)
        failed = comment_writeback_result.get("failed", 0)
        skipped = comment_writeback_result.get("skipped", 0)
        issues = comment_writeback_result.get("issues", [])

        # Build summary for logging and state
        summary = f"AI批注写入: 生成={generated_count}, 成功={added}, 失败={failed}, 跳过={skipped}"
        progress_log.info(summary)

        # Hard fail: if AI generated comments exist but zero were written back
        if generated_count > 0 and added == 0:
            error_msg = f"批注生成成功但写入失败: 生成{generated_count}条, 成功写入0条"
            progress_log.error(error_msg)
            raise ValueError(error_msg)

        # Store detailed results in state for visibility
        comment_writeback_summary = summary
        comment_writeback_added = added
        comment_writeback_failed = failed
        comment_writeback_skipped = skipped
        comment_writeback_errors = [
            {
                "reference_text": issue.get("reference_text", ""),
                "reason": issue.get("reason", ""),
                "error": issue.get("error", "")
            }
            for issue in issues
        ]

        save_document_with_retry(doc, node_name=NODE_NAME)
        log_parts.append("文档已保存")
        _visible_log("gjgk 同页回填完成")
    except Exception as exc:
        try:
            if doc is not None:
                log_parts.append(_describe_range_state(doc, doc.Content, label="异常时文档内容范围"))
        except Exception:
            pass
        error_message = f"gjgk Word 更新失败: {exc}"
        log_parts.append(error_message)
        _visible_log(error_message)
        recent_logs = " | ".join(log_parts[-25:])
        raise RuntimeError(f"{error_message}; 最近日志: {recent_logs}") from exc
    finally:
        close_word_application(
            word_app=word,
            doc=doc,
            com_initialized=com_initialized,
            wait_time=1.0,
            node_name=NODE_NAME,
        )

    duration_ms = (time.perf_counter() - start_time) * 1000
    log_parts.append(f"节点执行耗时 {duration_ms:.0f} 毫秒")

    new_state = dict(state)
    new_state["insertion_log"] = "; ".join(log_parts)
    new_state["comment_writeback_summary"] = comment_writeback_summary
    new_state["comment_writeback_added"] = comment_writeback_added
    new_state["comment_writeback_failed"] = comment_writeback_failed
    new_state["comment_writeback_skipped"] = comment_writeback_skipped
    new_state["comment_writeback_errors"] = comment_writeback_errors
    new_state["style_writeback_summary"] = style_writeback_summary
    new_state["style_writeback_result"] = style_writeback_result
    return GjgkTenderGraphState(**new_state)


def _print_manual_state(state: GjgkTenderGraphState) -> None:
    print("测试状态:")
    for key, value in state.items():
        if key == "polished_text":
            print(f"  {key}: {value[:80]}...")
        else:
            print(f"  {key}: {value}")



def _run_update_only_manual_scenario(
    source_doc_path: pathlib.Path,
    *,
    scenario_label: str = "[场景2] 预删模板回填产物",
    execution_mode: str = "复制预删除模板后直接运行 gjgk_update_word",
) -> pathlib.Path:
    if not source_doc_path.exists():
        raise FileNotFoundError(f"更新测试源文件不存在: {source_doc_path}")

    output_path = _build_manual_test_output_path(source_doc_path)
    _prepare_manual_test_copy(source_doc_path, output_path)
    update_state = _build_manual_test_state(str(output_path))

    print(scenario_label)
    print(f"源文件: {source_doc_path}")
    print(f"测试副本: {output_path}")
    print(f"执行模式: {execution_mode}")
    _print_manual_state(update_state)
    print("-" * 80)

    result_state = gjgk_update_word(update_state, config=None)
    print("✅ gjgk_update_word 执行完成")
    print(f"回填产物: {output_path}")
    print("插入日志:")
    for part in str(result_state.get("insertion_log", "")).split("; "):
        print(f"  - {part}")
    return output_path


def main() -> None:
    print("=" * 80)
    print("开始测试 gjgk 同页回填诊断场景")
    print("=" * 80)

    update_output_path: Optional[pathlib.Path] = None

    try:
        update_output_path = _run_update_only_manual_scenario(
            DEFAULT_TEST_UPDATE_SOURCE_DOC,
            scenario_label="[场景] 预删模板同页回填",
            execution_mode=(
        "仅复制删除模板测试文档并直接执行 gjgk_update_word"
            ),
        )
    except Exception as exc:
        print("❌ gjgk_update_word 执行失败")
        print(f"错误信息: {exc}")
        sys.exit(1)

    print("=" * 80)
    print("诊断完成")
    if update_output_path is not None:
        print(f"回填产物文件: {update_output_path}")

    print("预删模板同页回填场景执行成功")
    print("=" * 80)


if __name__ == "__main__":
    main()
