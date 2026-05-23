"""
delete_ops — Word 正文区间删除业务 helper。

这些 helper 面向 delete / update 节点复用。它们只处理 Word 正文范围内
“可删内容”的删除策略，不负责打开/保存文档、锚点定位或节点状态装配。
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, List, Optional

from backend.helper.word_helper.range_utils import (
    is_locked_exception,
    is_range_locked,
    range_overlaps,
)


LAYOUT_CONTROL_CHARS = {"\r", "\n", "\v", "\f", "\a"}


def _append_log(log_parts: Optional[List[str]], message: str) -> None:
    if log_parts is not None:
        log_parts.append(message)


def _iter_word_collection_reverse(collection: Any) -> Iterable[Any]:
    """按 Word COM collection 的 1-based 下标倒序迭代，失败时回退普通迭代。"""
    try:
        count = int(getattr(collection, "Count", 0))
    except Exception:
        count = 0

    if count > 0:
        for idx in range(count, 0, -1):
            try:
                yield collection(idx)
            except Exception:
                continue
        return

    try:
        items = list(collection)
    except Exception:
        return

    for item in reversed(items):
        yield item


def delete_range_content_preserving_locked_blocks(
    doc,
    *,
    range_start: int,
    get_bound_end: Callable[[], int],
    log_parts: Optional[List[str]] = None,
) -> dict[str, int | bool]:
    """
    删除 [range_start, get_bound_end()) 内可编辑内容，跳过锁定表格/段落。

    Word 在区间内含内容控件、字段或其它受保护对象时，整段 ``Range.Delete()``
    会直接失败。本 helper 先倒序删除可编辑表格和段落，最后仅当剩余整段可编辑时
    再执行兜底整段删除。
    """
    start = int(range_start)
    initial_end = int(get_bound_end())
    stats: dict[str, int | bool] = {
        "deleted_tables": 0,
        "skipped_tables": 0,
        "deleted_paragraphs": 0,
        "skipped_paragraphs": 0,
        "used_fallback_delete": False,
    }

    if initial_end <= start:
        _append_log(log_parts, "锚点区间为空，跳过删除")
        return stats

    try:
        tables = doc.Range(start, initial_end).Tables
        for table in _iter_word_collection_reverse(tables):
            try:
                table_rng = table.Range
                table_start = int(table_rng.Start)
                table_end = int(table_rng.End)
                if not range_overlaps(table_start, table_end, start, initial_end):
                    continue
                if is_range_locked(doc, table_rng):
                    stats["skipped_tables"] = int(stats["skipped_tables"]) + 1
                    continue
                table_rng.Delete()
                stats["deleted_tables"] = int(stats["deleted_tables"]) + 1
            except Exception:
                continue
    except Exception:
        pass

    try:
        current_end = int(get_bound_end())
        paragraphs = doc.Range(start, current_end).Paragraphs
        for paragraph in _iter_word_collection_reverse(paragraphs):
            try:
                paragraph_rng = paragraph.Range
                paragraph_start = int(paragraph_rng.Start)
                paragraph_end = int(paragraph_rng.End)
                if not range_overlaps(paragraph_start, paragraph_end, start, int(get_bound_end())):
                    continue
                if is_range_locked(doc, paragraph_rng):
                    stats["skipped_paragraphs"] = int(stats["skipped_paragraphs"]) + 1
                    continue
                paragraph_rng.Delete()
                stats["deleted_paragraphs"] = int(stats["deleted_paragraphs"]) + 1
            except Exception:
                continue
    except Exception:
        pass

    latest_end = int(get_bound_end())
    if latest_end > start:
        try:
            remaining_rng = doc.Range(start, latest_end)
            if not is_range_locked(doc, remaining_rng):
                remaining_rng.Delete()
                stats["used_fallback_delete"] = True
        except Exception:
            pass

    if (
        int(stats["deleted_tables"])
        or int(stats["deleted_paragraphs"])
        or int(stats["skipped_tables"])
        or int(stats["skipped_paragraphs"])
        or bool(stats["used_fallback_delete"])
    ):
        _append_log(
            log_parts,
            "删除原内容: "
            f"表格 {stats['deleted_tables']} 个，段落 {stats['deleted_paragraphs']} 个，"
            f"跳过锁定表格 {stats['skipped_tables']} 个，"
            f"跳过锁定段落 {stats['skipped_paragraphs']} 个，"
            f"整段兜底={bool(stats['used_fallback_delete'])}",
        )

    return stats


def trim_leading_layout_controls_preserving_locked_blocks(
    doc,
    *,
    range_start: int,
    get_bound_end: Callable[[], int],
    log_parts: List[str],
    max_scan: int = 16,
    control_chars: Optional[set[str]] = None,
) -> int:
    """
    从插入起点清理可编辑控制符；遇到锁定控制符时跳过。

    direct_replace 删除后，Word 模板可能只剩一个锁定段落边界或内容控件边界。
    这种边界不能删，但也不能阻止后续继续向后寻找可编辑插入点。
    """
    controls = LAYOUT_CONTROL_CHARS if control_chars is None else control_chars
    cursor = max(0, int(range_start))
    removed = 0
    skipped_locked = 0

    for _ in range(max_scan):
        current_end = int(get_bound_end())
        doc_end = int(doc.Content.End)
        if cursor >= current_end or cursor >= doc_end:
            break

        probe = doc.Range(cursor, min(cursor + 1, doc_end))
        probe_text = str(getattr(probe, "Text", "") or "")
        if probe_text not in controls:
            break

        try:
            if is_range_locked(doc, probe):
                skipped_locked += 1
                try:
                    collapsed_probe = doc.Range(cursor, cursor)
                    if not is_range_locked(doc, collapsed_probe):
                        break
                except Exception:
                    pass
                cursor += 1
                continue
        except Exception:
            pass

        try:
            probe.Delete()
            removed += 1
        except Exception as exc:
            if is_locked_exception(exc):
                skipped_locked += 1
                try:
                    collapsed_probe = doc.Range(cursor, cursor)
                    if not is_range_locked(doc, collapsed_probe):
                        break
                except Exception:
                    pass
                cursor += 1
                continue
            raise

    if removed > 0:
        log_parts.append(f"局部清理起点控制符 {removed} 个")
    if skipped_locked > 0:
        log_parts.append(f"跳过锁定起点控制符 {skipped_locked} 个")

    return cursor
