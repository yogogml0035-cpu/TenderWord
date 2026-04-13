"""
protected_fields — 受保护字段的扫描、定位、刷新与更新。

从 update_word、gngk_fw_zc_update_word 等节点中提取的通用受保护字段操作。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from backend.util.word_util import wdCollapseEnd, wdFindStop


# ---------------------------------------------------------------------------
# 扫描与收集
# ---------------------------------------------------------------------------

def _is_keyword_paragraph(text: str, keyword: str) -> bool:
    return keyword in text and ("：" in text or ":" in text)


def scan_protected_fields_in_range(
    doc,
    keywords: List[str],
    range_start: int,
    range_end: int,
) -> Dict[str, Any]:
    """在指定字符区间内扫描包含关键字的段落，返回 {keyword: para_range}。"""
    found: Dict[str, Any] = {}
    if int(range_end) <= int(range_start):
        return found

    try:
        paragraphs = doc.Range(int(range_start), int(range_end)).Paragraphs
    except Exception:
        return found

    for para in paragraphs:
        para_text = str(getattr(para.Range, "Text", "") or "").strip()
        if not para_text:
            continue
        for keyword in keywords:
            if keyword not in found and _is_keyword_paragraph(para_text, keyword):
                found[keyword] = para.Range
    return found


PROTECTED_FIELD_SCAN_MARGIN = 400


def collect_protected_fields(
    doc,
    keywords: List[str],
    target_range: tuple[int, int],
    fallback_range: Optional[tuple[int, int]],
    *,
    boundary_margin: int = PROTECTED_FIELD_SCAN_MARGIN,
) -> Dict[str, Any]:
    """
    优先在 target_range 查找受保护字段，不足时回退到 fallback_range 和扩展范围。

    Returns:
        {keyword: para_range} — 找到的受保护字段段落映射
    """
    found: Dict[str, Any] = {}
    scan_ranges = [target_range]
    if fallback_range:
        scan_ranges.append(fallback_range)
        doc_end = int(
            getattr(getattr(doc, "Content", None), "End", fallback_range[1])
        )
        expanded_start = max(0, int(fallback_range[0]) - boundary_margin)
        expanded_end = min(doc_end, int(fallback_range[1]) + boundary_margin)
        expanded_range = (expanded_start, expanded_end)
        if expanded_range not in scan_ranges:
            scan_ranges.append(expanded_range)

    for scan_start, scan_end in scan_ranges:
        missing = [keyword for keyword in keywords if keyword not in found]
        if not missing:
            break
        found.update(
            scan_protected_fields_in_range(doc, missing, scan_start, scan_end)
        )

    return found


def refresh_protected_fields(
    doc,
    keywords: List[str],
    range_start: int,
    range_end: int,
    existing_fields: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """在删除可编辑内容后，按最新文档位置重新绑定受保护字段段落。"""
    refreshed = dict(existing_fields or {})
    refreshed.update(
        scan_protected_fields_in_range(
            doc, keywords, int(range_start), int(range_end)
        )
    )
    return refreshed


def validate_required_protected_fields(
    protected_fields: Dict[str, Any],
    required_keywords: tuple[str, ...] | list[str],
) -> None:
    """验证是否缺少关键受保护字段，缺少则抛 ValueError。"""
    missing = [kw for kw in required_keywords if kw not in protected_fields]
    if missing:
        raise ValueError(f"缺少关键受保护字段: {', '.join(missing)}")


def resolve_block_flow(protected_fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    根据已识别的受保护字段，返回与 master 对齐的块插入控制流。

    用于 xjcg/common update_word 的交付日期+付款方式两字段场景。
    """
    has_delivery = "交付日期" in protected_fields
    has_payment = "付款方式" in protected_fields

    if has_delivery and has_payment:
        block2_mode = "between_delivery_payment"
    elif has_delivery:
        block2_mode = "after_delivery"
    else:
        block2_mode = "skip"

    block3_anchor = "after_payment" if has_payment else "before_after_anchor"
    return {
        "has_delivery": has_delivery,
        "has_payment": has_payment,
        "block2_mode": block2_mode,
        "block3_anchor": block3_anchor,
    }


# ---------------------------------------------------------------------------
# 字段重定位与更新
# ---------------------------------------------------------------------------

def refind_protected_paragraph(
    doc,
    keyword: str,
    bound_start: int,
    bound_end: int,
) -> Optional[Any]:
    """
    在 [bound_start, bound_end] 范围内重新查找包含 keyword 的受保护字段段落。

    Returns:
        找到的段落 Range，未找到返回 None
    """
    search_rng = doc.Range(int(bound_start), int(bound_end))
    finder = search_rng.Find
    finder.ClearFormatting()
    finder.Text = keyword
    finder.Forward = True
    finder.Wrap = wdFindStop
    finder.MatchCase = False
    finder.MatchWholeWord = False
    while finder.Execute():
        try:
            pos = int(search_rng.Start)
        except Exception:
            pos = search_rng.Start
        if int(bound_start) <= pos <= int(bound_end):
            para_rng = doc.Range(pos, pos).Paragraphs(1).Range
            para_text = para_rng.Text.strip()
            if keyword in para_text and ("：" in para_text or ":" in para_text):
                return para_rng
        search_rng.Collapse(wdCollapseEnd)
    return None


def insert_prefix_before_keyword(
    doc,
    keyword: str,
    prefix: str,
    protected_fields: Dict[str, Any],
    *,
    log_parts: Optional[List[str]] = None,
) -> bool:
    """
    在受保护字段段落中，在 keyword 之前插入前缀（如编号 "2、"）。

    如果前缀已存在则跳过。
    """
    if not prefix or not prefix.strip():
        return True
    if keyword not in protected_fields:
        return False
    try:
        para_rng = protected_fields[keyword]
        para_text = para_rng.Text
        idx = para_text.find(keyword)
        if idx < 0:
            return False
        before = para_text[:idx].replace("\r", "").replace("\a", "")
        prefix_clean = prefix.replace("\r", "").replace("\n", "")
        if before.endswith(prefix_clean):
            return True
        insert_pos = para_rng.Start + idx
        doc.Range(insert_pos, insert_pos).InsertBefore(prefix_clean)
        return True
    except Exception as e:
        if log_parts is not None:
            log_parts.append(f"  警告: 插入前缀失败 '{keyword}': {e}")
        return False


def update_protected_field(
    doc,
    keyword: str,
    new_value: Optional[str],
    protected_fields: Dict[str, Any],
    *,
    font_name: str = "宋体",
    font_size: int = 12,
    log_parts: Optional[List[str]] = None,
) -> bool:
    """
    更新受保护字段段落中 keyword 冒号后的值。

    例如："交付日期：旧值" → "交付日期：新值"
    """
    if keyword not in protected_fields:
        return False
    if new_value is None:
        return True

    try:
        para_rng = protected_fields[keyword]
        para_text = para_rng.Text
        idx_kw = para_text.find(keyword)
        if idx_kw < 0:
            return False

        colon_pos = para_text.find("：", idx_kw + len(keyword))
        if colon_pos < 0:
            colon_pos = para_text.find(":", idx_kw + len(keyword))

        if colon_pos >= 0:
            value_start = para_rng.Start + colon_pos + 1
        else:
            value_start = para_rng.Start + idx_kw + len(keyword)

        trim = 0
        while para_text.endswith("\r") or para_text.endswith("\a"):
            para_text = para_text[:-1]
            trim += 1
        value_end = para_rng.End - trim
        if value_end < value_start:
            value_end = value_start

        value_rng = doc.Range(value_start, value_end)
        new_value_clean = new_value.replace("\r", "").replace("\n", "")
        value_rng.Text = new_value_clean
        value_rng.Font.Name = font_name
        value_rng.Font.Size = font_size
        if log_parts is not None:
            log_parts.append(
                f"  已更新受保护字段 '{keyword}': {new_value_clean[:50]}..."
            )
        return True
    except Exception as e:
        if log_parts is not None:
            log_parts.append(f"  警告: 无法更新 '{keyword}': {e}")
        return False
