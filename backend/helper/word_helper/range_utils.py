"""
range_utils — Word 文档范围/锁/可编辑位置判断与查找。

从 delete_tender_param、update_word、gjgk_update_word、gngk_fw_zc_update_word 中
提取的通用范围操作函数。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Optional

from backend.util.word_util import wdCollapseStart


# ---------------------------------------------------------------------------
# 基础判断
# ---------------------------------------------------------------------------

def range_overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """两个字符位置区间是否存在重叠。"""
    return not (int(a_end) <= int(b_start) or int(b_end) <= int(a_start))


def is_locked_exception(exc: Exception) -> bool:
    """判断异常是否属于 Word 锁定/保护类错误。"""
    error_text = str(exc).lower()
    return "锁定" in error_text or "locked" in error_text or "-2146823683" in error_text


def is_range_locked(doc, rng) -> bool:
    """
    检测 Word Range 是否被保护（含字段保护检测）。

    采用 gjgk_update_word 中最完整的实现：
    1. rng.Locked 属性检测
    2. Editors 检测（有编辑者说明可编辑）
    3. Fields 中逐个检测锁定
    4. ProtectionType 属性
    5. 写入探针（最终回退）
    """
    # 1. 直接属性检测
    try:
        if hasattr(rng, "Locked") and rng.Locked:
            return True
    except Exception:
        pass

    # 2. Editors 检测 — 有编辑者说明区域可编辑
    try:
        editors = getattr(rng, "Editors", None)
        editors_count = int(getattr(editors, "Count", 0))
        if editors_count > 0:
            return False
    except Exception:
        pass

    # 3. 逐字段检测锁定
    try:
        fields = rng.Fields
        count = int(getattr(fields, "Count", 0))
        for idx in range(1, count + 1):
            try:
                field = fields(idx)
                if hasattr(field, "Locked") and field.Locked:
                    return True
            except Exception:
                continue
    except Exception:
        pass

    # 4. 文档保护类型
    try:
        protection_type = int(getattr(doc, "ProtectionType", -1))
    except Exception:
        protection_type = -1

    # 5. 写入探针（最终回退）
    try:
        marker = "\u200b"
        test_pos = int(getattr(rng, "End", getattr(rng, "Start", 0)))
        probe_rng = doc.Range(test_pos, test_pos)
        probe_rng.InsertAfter(marker)
        inserted = doc.Range(test_pos, min(test_pos + 1, int(doc.Content.End)))
        if str(getattr(inserted, "Text", "") or "") == marker:
            inserted.Delete()
            return False
        return protection_type != -1
    except Exception as exc:
        return is_locked_exception(exc) or (protection_type != -1)


def is_protected_range(rng, protected_fields: Dict[str, Any]) -> bool:
    """判断 Range 是否与任一受保护字段段落重叠。"""
    try:
        rs = int(rng.Start)
        re_ = int(rng.End)
    except Exception:
        return False
    for prng in protected_fields.values():
        try:
            ps = int(prng.Start)
            pe = int(prng.End)
        except Exception:
            continue
        if range_overlaps(rs, re_, ps, pe):
            return True
    return False


# ---------------------------------------------------------------------------
# 可编辑位置查找
# ---------------------------------------------------------------------------

def find_editable_insertion_pos(
    doc,
    start_pos: int,
    bound_start: int,
    bound_end: int,
    *,
    max_lookahead: int = 400,
) -> int:
    """
    从 start_pos 开始向后查找首个可编辑插入位置。

    若超出边界仍未找到，返回 min(max(0, start_pos), scan_end)。
    """
    doc_end = int(doc.Content.End)
    scan_end = min(doc_end, int(bound_end))
    pos = min(max(0, int(start_pos)), scan_end)
    if pos < int(bound_start):
        pos = int(bound_start)
    for _ in range(max_lookahead + 1):
        try:
            probe = doc.Range(pos, pos)
            if not is_range_locked(doc, probe):
                return pos
        except Exception:
            pass
        if pos >= scan_end:
            break
        pos += 1
    return min(max(0, int(start_pos)), scan_end)


def find_next_editable_pos(
    doc,
    after_pos: int,
    bound_start: int,
    bound_end: int,
    *,
    max_paragraphs: int = 250,
) -> int:
    """
    从 after_pos 开始，按段落逐个查找可编辑位置。

    与 find_editable_insertion_pos 的区别在于优先按段落跳跃，效率更高。
    """
    doc_end = int(doc.Content.End)
    scan_end = min(doc_end, int(bound_end))
    start = min(max(0, int(after_pos)), scan_end)
    if start < int(bound_start):
        start = int(bound_start)
    try:
        scan_rng = doc.Range(start, scan_end)
        paras = scan_rng.Paragraphs
        count = paras.Count
        for i in range(1, min(count, max_paragraphs) + 1):
            try:
                p_rng = paras(i).Range
                p_start = int(p_rng.Start)
                candidate = max(p_start, start)
                if candidate > scan_end:
                    candidate = scan_end
                if not is_range_locked(doc, doc.Range(candidate, candidate)):
                    return candidate
            except Exception:
                continue
    except Exception:
        pass
    return find_editable_insertion_pos(
        doc, start, bound_start, bound_end, max_lookahead=20000
    )


def find_next_editable_pos_bounded(
    doc,
    start_pos: int,
    bound_end: int,
    *,
    max_lookahead: int = 4000,
) -> Optional[int]:
    """
    在 [start_pos, bound_end] 范围内查找首个可编辑位置。

    未找到时返回 None。
    """
    doc_end = int(doc.Content.End)
    start = int(min(max(0, start_pos), doc_end))
    end = int(min(max(0, bound_end), doc_end))
    if end < start:
        return None
    pos = start
    look = min(max_lookahead, end - start)
    for _ in range(look + 1):
        try:
            if not is_range_locked(doc, doc.Range(pos, pos)):
                return pos
        except Exception:
            pass
        pos += 1
        if pos > end:
            break
    return None


def find_prev_editable_pos(
    doc,
    before_pos: int,
    *,
    max_lookback: int = 4000,
) -> Optional[int]:
    """从 before_pos 向前查找首个可编辑位置。"""
    doc_end = int(doc.Content.End)
    pos = int(min(max(0, before_pos), doc_end))
    for _ in range(max_lookback + 1):
        try:
            if not is_range_locked(doc, doc.Range(pos, pos)):
                return pos
        except Exception:
            pass
        if pos <= 0:
            break
        pos -= 1
    return None


def find_prev_editable_pos_bounded(
    doc,
    before_pos: int,
    bound_start: int,
    *,
    max_lookback: int = 4000,
) -> Optional[int]:
    """在 [bound_start, before_pos] 范围内向前查找首个可编辑位置。"""
    doc_end = int(doc.Content.End)
    pos = int(min(max(0, before_pos), doc_end))
    lower_bound = int(min(max(0, bound_start), doc_end))
    lookback = min(max_lookback, max(0, pos - lower_bound))
    for _ in range(lookback + 1):
        try:
            if not is_range_locked(doc, doc.Range(pos, pos)):
                return pos
        except Exception:
            pass
        if pos <= lower_bound:
            break
        pos -= 1
    return None


def ensure_editable_insert_range(
    doc,
    insert_range,
    bound_start: int,
    get_bound_end: Callable[[], int],
) -> None:
    """
    确保 insert_range 处于可编辑状态。

    - 折叠到起始
    - 如果超出边界则拉回
    - 如果位置被锁定则向后查找可编辑位置
    """
    try:
        insert_range.Collapse(wdCollapseStart)
    except Exception:
        pass

    try:
        pos = int(insert_range.Start)
    except Exception:
        pos = 0

    try:
        bound_end = int(get_bound_end())
        b_start = int(bound_start)
        if pos < b_start:
            pos = b_start
            insert_range.SetRange(pos, pos)
            insert_range.Collapse(wdCollapseStart)
        if pos > bound_end:
            pos = bound_end
            insert_range.SetRange(pos, pos)
            insert_range.Collapse(wdCollapseStart)
        if is_range_locked(doc, doc.Range(pos, pos)):
            pos2 = find_next_editable_pos_bounded(
                doc, pos + 1, bound_end, max_lookahead=20000
            )
            if pos2 is not None and pos2 > pos:
                insert_range.SetRange(pos2, pos2)
                insert_range.Collapse(wdCollapseStart)
    except Exception:
        pass


def find_safe_insert_position(
    doc,
    candidate_positions: Iterable[Optional[int]],
    *,
    max_forward_scan_chars: int = 0,
    field_name: str = "",
    log=None,
) -> Optional[int]:
    """
    在候选位置中寻找首个可编辑插入点，必要时向后探测。

    来自 delete_tender_param 的 _find_safe_insert_position。
    """
    try:
        doc_end = int(doc.Content.End)
    except Exception:
        return None

    seen_positions: set[int] = set()
    locked_positions = 0

    for candidate in candidate_positions:
        if candidate is None:
            continue
        base_pos = min(max(0, int(candidate)), doc_end)
        for offset in range(max_forward_scan_chars + 1):
            pos = min(base_pos + offset, doc_end)
            if pos in seen_positions:
                continue
            seen_positions.add(pos)

            try:
                probe_rng = doc.Range(pos, pos)
            except Exception:
                continue

            if is_range_locked(doc, probe_rng):
                locked_positions += 1
                continue

            if log and offset > 0 and field_name:
                log(f"{field_name}字段候选位置受保护，改用偏移 {offset} 的可编辑位置")
            return pos

    if log and field_name and locked_positions > 0:
        log(f"{field_name}字段跳过了 {locked_positions} 个受保护位置")
    return None
