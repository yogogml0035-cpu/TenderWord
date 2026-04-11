from __future__ import annotations

import importlib
from types import FunctionType
from typing import Optional


_common_delete_tender_param = importlib.import_module(
    "backend.nodes.common_word_nodes.delete_tender_param"
)

_SERVICE_FIELD_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("服务地点", ("服务地点：", "服务地点:")),
    ("服务期限", ("服务期限：", "服务期限:")),
    ("付款方式", ("付款方式：", "付款方式:")),
)
_CLEANUP_INVISIBLE_CHARS = (
    "\r",
    "\n",
    "\t",
    "\x07",
    "\x0b",
    "\x0c",
    "\a",
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


def _normalize_cleanup_text(text: str) -> str:
    normalized = str(text or "")
    for invisible_char in _CLEANUP_INVISIBLE_CHARS:
        normalized = normalized.replace(invisible_char, "")
    return normalized.strip()


def _paragraph_contains_service_field(paragraph_text: str) -> bool:
    return any(
        marker in (paragraph_text or "")
        for _field_name, markers in _SERVICE_FIELD_MARKERS
        for marker in markers
    )


def _cleanup_service_field_residual_paragraphs(
    doc,
    cleanup_start: Optional[int],
    cleanup_end: Optional[int],
    *,
    log=_common_delete_tender_param._visible_log,
) -> int:
    if cleanup_start is None or cleanup_end is None:
        return 0

    try:
        normalized_start = max(0, int(cleanup_start))
        normalized_end = max(normalized_start, int(cleanup_end))
    except Exception:
        return 0

    paragraphs = getattr(doc, "Paragraphs", None)
    if paragraphs is None:
        return 0

    try:
        paragraph_iter = iter(paragraphs)
    except TypeError:
        try:
            paragraph_iter = (paragraphs(index) for index in range(1, paragraphs.Count + 1))
        except Exception:
            return 0

    paragraphs_to_delete = []
    for para in paragraph_iter:
        try:
            para_rng = para.Range
            para_start = int(para_rng.Start)
            para_end = int(para_rng.End)
        except Exception:
            continue

        if para_start < normalized_start or para_start >= normalized_end:
            continue

        para_text = str(getattr(para_rng, "Text", "") or "")
        if _paragraph_contains_service_field(para_text):
            continue
        paragraphs_to_delete.append(para_rng)

    deleted_count = 0
    for para_rng in reversed(paragraphs_to_delete):
        try:
            paragraph_text = str(getattr(para_rng, "Text", "") or "")
            para_rng.Delete()
            deleted_count += 1
            if log:
                if _normalize_cleanup_text(paragraph_text):
                    log(
                        "已删除服务三字段区间内的残留正文段落"
                    )
                else:
                    log(
                        "已删除服务三字段区间内的空白/分页痕迹段落"
                    )
        except Exception:
            continue

    return deleted_count


def _find_marker_offset(paragraph_text: str, markers: tuple[str, ...]) -> int:
    for marker in markers:
        position = paragraph_text.find(marker)
        if position >= 0:
            return position
    return _common_delete_tender_param._find_first_visible_insert_offset(paragraph_text)


def _has_paragraph_break_before(doc, insert_pos: int) -> bool:
    if insert_pos <= 0:
        return True
    try:
        previous_char = doc.Range(insert_pos - 1, insert_pos).Text
    except Exception:
        return False
    return previous_char == "\r"


def _insert_paragraph_break_before_field(
    doc,
    field_name: str,
    markers: tuple[str, ...],
    field_para_rng,
    fallback_pos: Optional[int],
    *,
    tender_type: str = "gngk_fw_zc",
    log=_common_delete_tender_param._visible_log,
) -> bool:
    if field_para_rng is not None:
        try:
            paragraph_text = str(getattr(field_para_rng, "Text", "") or "")
            paragraph_start = int(field_para_rng.Start)
            insert_offset = _find_marker_offset(paragraph_text, markers)
            keyword_pos = paragraph_start + insert_offset
            if _has_paragraph_break_before(doc, keyword_pos):
                return False

            safe_insert_pos = _common_delete_tender_param._find_safe_insert_position(
                doc,
                [keyword_pos, paragraph_start],
                max_forward_scan_chars=24
                if _common_delete_tender_param._uses_wide_scan_window(tender_type)
                else 8,
                field_name=field_name,
                log=log,
            )
            if safe_insert_pos is not None:
                doc.Range(safe_insert_pos, safe_insert_pos).InsertBefore("\r")
                return True
        except Exception:
            pass

    if fallback_pos is None:
        return False

    fallback_insert_pos = _common_delete_tender_param._find_safe_insert_position(
        doc,
        [fallback_pos],
        max_forward_scan_chars=24
        if _common_delete_tender_param._uses_wide_scan_window(tender_type)
        else 8,
        field_name=field_name,
        log=log,
    )
    if fallback_insert_pos is None:
        return False

    if _has_paragraph_break_before(doc, fallback_insert_pos):
        return False

    try:
        doc.Range(fallback_insert_pos, fallback_insert_pos).InsertParagraphAfter()
        return True
    except Exception:
        return False


def _ensure_paragraph_break_after_field(
    doc,
    field_name: str,
    field_para_rng,
    max_scan_chars: int = 4000,
    *,
    tender_type: str = "gngk_fw_zc",
    log=_common_delete_tender_param._visible_log,
) -> bool:
    if field_para_rng is None:
        return False

    try:
        field_end = int(field_para_rng.End)
        doc_end = int(doc.Content.End)
    except Exception:
        return False

    if field_end < doc_end:
        try:
            next_char = doc.Range(field_end, min(field_end + 1, doc_end)).Text
            if next_char == "\r":
                return False
        except Exception:
            pass

    max_pos = min(doc_end, field_end + max_scan_chars)
    safe_insert_pos = _common_delete_tender_param._find_safe_insert_position(
        doc,
        range(field_end, max_pos + 1),
        max_forward_scan_chars=8
        if _common_delete_tender_param._uses_wide_scan_window(tender_type)
        else 0,
        field_name=field_name,
        log=log,
    )
    if safe_insert_pos is None:
        return False

    try:
        doc.Range(safe_insert_pos, safe_insert_pos).InsertBefore("\r")
        return True
    except Exception:
        return False


def _restore_protected_field_paragraph_boundaries(
    doc,
    before_text: str,
    before_end_pos: Optional[int],
    *,
    target_size: float = 18.0,
    tender_type: str = "gngk_fw_zc",
    log=_common_delete_tender_param._visible_log,
) -> None:
    del before_text, target_size

    try:
        doc_end = int(doc.Content.End)
    except Exception:
        doc_end = 0

    search_start = min(max(0, int(before_end_pos or 0)), doc_end)
    search_window = 20000 if _common_delete_tender_param._uses_wide_scan_window(tender_type) else 12000
    search_end = min(doc_end, search_start + search_window)

    if log:
        log(f"开始修复服务三字段段落边界，扫描范围 {search_start}-{search_end}")

    paragraph_ranges: dict[str, object] = {}
    fallback_pos = before_end_pos

    for field_name, markers in _SERVICE_FIELD_MARKERS:
        paragraph_ranges[field_name] = _common_delete_tender_param._find_paragraph_containing_any(
            doc,
            markers,
            min_start=search_start,
            max_start=search_end,
        )
        if log:
            log(f'开始修复"{field_name}"前的段落边界')

        inserted = _insert_paragraph_break_before_field(
            doc,
            field_name=field_name,
            markers=markers,
            field_para_rng=paragraph_ranges[field_name],
            fallback_pos=fallback_pos,
            tender_type=tender_type,
            log=log,
        )
        if inserted:
            print(f'[delete_tender_param] 已补齐"{field_name}"前的段落边界')
            if log:
                log(f'已补齐"{field_name}"前的段落边界')
        else:
            print(f'[delete_tender_param] 提示: "{field_name}"前已存在段落边界或未找到可编辑位置')
            if log:
                log(f'"{field_name}"前已存在段落边界或未找到可编辑位置')

        para_rng = paragraph_ranges[field_name]
        if para_rng is not None:
            try:
                fallback_pos = int(para_rng.End)
            except Exception:
                pass

    payment_field_name, payment_markers = _SERVICE_FIELD_MARKERS[-1]
    payment_para_rng = _common_delete_tender_param._find_paragraph_containing_any(
        doc,
        payment_markers,
        min_start=search_start,
        max_start=search_end,
    )
    if log:
        log(f'开始修复"{payment_field_name}"后的回车')

    if _ensure_paragraph_break_after_field(
        doc,
        field_name=payment_field_name,
        field_para_rng=payment_para_rng,
        tender_type=tender_type,
        log=log,
    ):
        print(f'[delete_tender_param] 已补齐"{payment_field_name}"后的回车')
        if log:
            log(f'已补齐"{payment_field_name}"后的回车')
    else:
        print(f'[delete_tender_param] 提示: "{payment_field_name}"后已存在回车或未找到可编辑位置')
        if log:
            log(f'"{payment_field_name}"后已存在回车或未找到可编辑位置')

    payment_para_rng = _common_delete_tender_param._find_paragraph_containing_any(
        doc,
        payment_markers,
        min_start=search_start,
        max_start=search_end,
    )
    cleanup_end = None
    if payment_para_rng is not None:
        try:
            cleanup_end = int(payment_para_rng.End)
        except Exception:
            cleanup_end = None

    cleaned_count = _cleanup_service_field_residual_paragraphs(
        doc,
        cleanup_start=before_end_pos,
        cleanup_end=cleanup_end,
        log=log,
    )
    if cleaned_count > 0:
        print(f"[delete_tender_param] 已清理服务三字段区间残留段落 {cleaned_count} 个")
        if log:
            log(f"已清理服务三字段区间残留段落 {cleaned_count} 个")


_gngk_fw_zc_delete_tender_param_globals = dict(_common_delete_tender_param.__dict__)
_gngk_fw_zc_delete_tender_param_globals[
    "_restore_protected_field_paragraph_boundaries"
] = _restore_protected_field_paragraph_boundaries

gngk_fw_zc_delete_tender_param = FunctionType(
    _common_delete_tender_param.delete_tender_param.__code__,
    _gngk_fw_zc_delete_tender_param_globals,
    "gngk_fw_zc_delete_tender_param",
    _common_delete_tender_param.delete_tender_param.__defaults__,
    _common_delete_tender_param.delete_tender_param.__closure__,
)
gngk_fw_zc_delete_tender_param.__doc__ = (
    "复用 common 删除主流程，仅把 gngk_fw_zc 的服务三字段段落修复特化。"
)
gngk_fw_zc_delete_tender_param.__module__ = __name__
gngk_fw_zc_delete_tender_param.__annotations__ = dict(
    getattr(_common_delete_tender_param.delete_tender_param, "__annotations__", {})
)


__all__ = [
    "gngk_fw_zc_delete_tender_param",
    "_restore_protected_field_paragraph_boundaries",
]
