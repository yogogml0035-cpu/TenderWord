"""
protected_fields — 受保护字段的扫描、定位、刷新与更新。

从 update_word、gngk_fw_zc_update_word 等节点中提取的通用受保护字段操作。
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence

from backend.util.word_util import wdCollapseEnd, wdFindStop, wdWithInTable

CANONICAL_PROTECTED_FIELD_COLON = "："
_OPTIONAL_PREFIX_PATTERN = (
    r"(?:[（(]?[0-9一二三四五六七八九十]+[)）]\s*|"
    r"[0-9一二三四五六七八九十]+[、.．]\s*)?"
)


# ---------------------------------------------------------------------------
# marker 契约与格式化
# ---------------------------------------------------------------------------


def _is_markdown_table_line(text: str) -> bool:
    stripped = str(text or "").strip()
    return bool(stripped) and stripped.startswith("|") and stripped.count("|") >= 2


def _strip_paragraph_tail(text: str) -> str:
    stripped = str(text or "")
    while stripped.endswith("\r") or stripped.endswith("\a"):
        stripped = stripped[:-1]
    return stripped


def canonicalize_protected_field_marker(marker: str) -> str:
    field_name = str(marker or "").strip().rstrip(":：").strip()
    if not field_name:
        raise ValueError("受保护字段 marker 不能为空")
    return f"{field_name}{CANONICAL_PROTECTED_FIELD_COLON}"


def extract_protected_field_name(marker: str) -> str:
    return canonicalize_protected_field_marker(marker).rstrip(CANONICAL_PROTECTED_FIELD_COLON)


def normalize_protected_field_markers(markers: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for marker in markers:
        canonical = canonicalize_protected_field_marker(marker)
        if canonical in seen:
            continue
        seen.add(canonical)
        normalized.append(canonical)
    return tuple(normalized)


# ---------------------------------------------------------------------------
# 扫描与收集
# ---------------------------------------------------------------------------


def match_protected_field_line(
    text: str,
    marker: str,
) -> Optional[Dict[str, Any]]:
    """
    严格识别“受保护字段行”。

    命中规则：
    - 行语义起点可带可选编号前缀（如 `2、`、`2.`、`（二）`）
    - 紧跟字段关键字
    - 关键字后必须有冒号（中文或英文）
    - 输出统一回收到中文冒号 canonical marker
    """

    canonical_marker = canonicalize_protected_field_marker(marker)
    field_name = extract_protected_field_name(marker)
    visible_text = _strip_paragraph_tail(str(text or ""))
    if not visible_text.strip():
        return None
    if _is_markdown_table_line(visible_text):
        return None

    pattern = re.compile(
        rf"^(?P<leading_ws>\s*)(?P<prefix>{_OPTIONAL_PREFIX_PATTERN})(?P<field>{re.escape(field_name)})(?P<spacing>\s*)(?P<source_colon>[：:])(?P<value>.*)$"
    )
    match = pattern.match(visible_text)
    if not match:
        return None

    prefix = match.group("prefix") or ""
    value = (match.group("value") or "").lstrip()
    source_colon = match.group("source_colon") or CANONICAL_PROTECTED_FIELD_COLON
    source_marker = f"{field_name}{source_colon}"
    normalized_line = (
        f"{match.group('leading_ws') or ''}{prefix}{canonical_marker}{value}"
    )
    return {
        "prefix": prefix,
        "value": value,
        "line": visible_text.strip(),
        "visible_text": visible_text,
        "field_name": field_name,
        "canonical_marker": canonical_marker,
        "source_marker": source_marker,
        "source_colon": source_colon,
        "normalized_line": normalized_line,
        "field_start": match.start("field"),
        "field_end": match.end("field"),
        "colon_index": match.start("source_colon"),
    }


def normalize_protected_field_line(text: str, marker: str) -> Optional[str]:
    matched = match_protected_field_line(text, marker)
    if not matched:
        return None
    return str(matched["normalized_line"])


def normalize_protected_field_text(text: str, markers: Sequence[str]) -> str:
    normalized_text = str(text or "")
    if not normalized_text:
        return normalized_text

    canonical_markers = normalize_protected_field_markers(markers)
    normalized_lines: list[str] = []
    for line in normalized_text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        normalized_line = line
        for marker in canonical_markers:
            maybe_normalized = normalize_protected_field_line(normalized_line, marker)
            if maybe_normalized is not None:
                normalized_line = maybe_normalized
                break
        normalized_lines.append(normalized_line)
    return "\n".join(normalized_lines)


def find_suspicious_protected_field_lines(
    lines: Sequence[str],
    markers: Sequence[str],
) -> Dict[str, str]:
    suspicious: Dict[str, str] = {}
    for marker in normalize_protected_field_markers(markers):
        field_name = extract_protected_field_name(marker)
        for line in lines:
            visible_line = _strip_paragraph_tail(str(line or ""))
            if field_name not in visible_line:
                continue
            if match_protected_field_line(visible_line, marker):
                continue
            suspicious[marker] = visible_line.strip()
            break
    return suspicious


def collect_suspicious_protected_field_hits(
    doc,
    markers: Sequence[str],
    scan_ranges: Sequence[tuple[int, int]],
) -> Dict[str, str]:
    suspicious: Dict[str, str] = {}
    canonical_markers = normalize_protected_field_markers(markers)
    for marker in canonical_markers:
        field_name = extract_protected_field_name(marker)
        for scan_start, scan_end in scan_ranges:
            if int(scan_end) <= int(scan_start):
                continue
            try:
                paragraphs = doc.Range(int(scan_start), int(scan_end)).Paragraphs
            except Exception:
                continue
            for para in paragraphs:
                para_rng = getattr(para, "Range", None)
                if para_rng is None:
                    continue
                para_text = _strip_paragraph_tail(str(getattr(para_rng, "Text", "") or ""))
                if not para_text.strip() or field_name not in para_text:
                    continue
                if match_protected_field_line(para_text, marker):
                    continue
                suspicious[marker] = para_text.strip()
                break
            if marker in suspicious:
                break
    return suspicious


def format_missing_protected_field_error(
    missing_markers: Sequence[str],
    suspicious_hits: Optional[Dict[str, str]] = None,
    *,
    prefix: str,
) -> str:
    canonical_missing = normalize_protected_field_markers(missing_markers)
    message = f"{prefix}: {', '.join(canonical_missing)}"
    suspicious_parts: list[str] = []
    for marker in canonical_missing:
        snippet = str((suspicious_hits or {}).get(marker) or "").strip()
        if not snippet:
            continue
        suspicious_parts.append(f"{marker} -> {snippet[:80]}")
    if suspicious_parts:
        message = f"{message}；可疑命中: {'；'.join(suspicious_parts)}"
    return message


def _is_table_paragraph(para_rng: Any) -> bool:
    try:
        return bool(para_rng.Information(wdWithInTable))
    except Exception:
        return False


def normalize_protected_field_paragraphs(
    doc,
    markers: Sequence[str],
    range_start: int,
    range_end: int,
    *,
    log_parts: Optional[List[str]] = None,
) -> int:
    """仅将合法字段行中的英文冒号规范为中文冒号。"""
    if int(range_end) <= int(range_start):
        return 0

    canonical_markers = normalize_protected_field_markers(markers)
    updated_count = 0
    try:
        paragraphs = doc.Range(int(range_start), int(range_end)).Paragraphs
    except Exception:
        return 0

    for para in paragraphs:
        para_rng = getattr(para, "Range", None)
        if para_rng is None or _is_table_paragraph(para_rng):
            continue
        para_text = str(getattr(para_rng, "Text", "") or "")
        if not _strip_paragraph_tail(para_text).strip():
            continue
        for marker in canonical_markers:
            matched = match_protected_field_line(para_text, marker)
            if not matched:
                continue
            if matched["source_marker"] == marker:
                break
            colon_index = int(matched["colon_index"])
            try:
                colon_rng = doc.Range(
                    int(para_rng.Start) + colon_index,
                    int(para_rng.Start) + colon_index + 1,
                )
                colon_rng.Text = CANONICAL_PROTECTED_FIELD_COLON
                updated_count += 1
                if log_parts is not None:
                    log_parts.append(
                        f"  已规范受保护字段冒号: {marker} <- {matched['source_marker']}"
                    )
            except Exception as exc:
                if log_parts is not None:
                    log_parts.append(
                        f"  警告: 规范受保护字段冒号失败 '{marker}': {exc}"
                    )
            break
    return updated_count


def scan_protected_fields_in_range(
    doc,
    markers: List[str],
    range_start: int,
    range_end: int,
) -> Dict[str, Any]:
    """在指定字符区间内扫描包含 marker 的段落，返回 {marker: para_range}。"""
    found: Dict[str, Any] = {}
    if int(range_end) <= int(range_start):
        return found

    canonical_markers = normalize_protected_field_markers(markers)

    try:
        paragraphs = doc.Range(int(range_start), int(range_end)).Paragraphs
    except Exception:
        return found

    for para in paragraphs:
        para_rng = getattr(para, "Range", None)
        if para_rng is None or _is_table_paragraph(para_rng):
            continue
        para_text = str(getattr(para_rng, "Text", "") or "").strip()
        if not para_text:
            continue
        for marker in canonical_markers:
            if marker in found:
                continue
            if match_protected_field_line(para_text, marker):
                found[marker] = para_rng
    return found


PROTECTED_FIELD_SCAN_MARGIN = 400


def collect_protected_fields(
    doc,
    markers: List[str],
    target_range: tuple[int, int],
    fallback_range: Optional[tuple[int, int]],
    *,
    boundary_margin: int = PROTECTED_FIELD_SCAN_MARGIN,
) -> Dict[str, Any]:
    """
    优先在 target_range 查找受保护字段，不足时回退到 fallback_range 和扩展范围。

    Returns:
        {marker: para_range} — 找到的受保护字段段落映射
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

    canonical_markers = list(normalize_protected_field_markers(markers))
    for scan_start, scan_end in scan_ranges:
        missing = [marker for marker in canonical_markers if marker not in found]
        if not missing:
            break
        found.update(
            scan_protected_fields_in_range(doc, missing, scan_start, scan_end)
        )

    return found


def refresh_protected_fields(
    doc,
    markers: List[str],
    range_start: int,
    range_end: int,
    existing_fields: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """在删除可编辑内容后，按最新文档位置重新绑定受保护字段段落。"""
    refreshed = dict(existing_fields or {})
    refreshed.update(
        scan_protected_fields_in_range(
            doc, markers, int(range_start), int(range_end)
        )
    )
    return refreshed


def validate_required_protected_fields(
    protected_fields: Dict[str, Any],
    required_markers: tuple[str, ...] | list[str],
) -> None:
    """验证是否缺少关键受保护字段，缺少则抛 ValueError。"""
    canonical_required = normalize_protected_field_markers(required_markers)
    missing = [marker for marker in canonical_required if marker not in protected_fields]
    if missing:
        raise ValueError(
            format_missing_protected_field_error(
                missing,
                prefix="缺少关键受保护字段",
            )
        )


def resolve_block_flow(protected_fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    根据已识别的受保护字段，返回与 master 对齐的块插入控制流。

    用于 xjcg/common update_word 的交付日期+付款方式两字段场景。
    """
    delivery_marker = canonicalize_protected_field_marker("交付日期")
    payment_marker = canonicalize_protected_field_marker("付款方式")
    has_delivery = delivery_marker in protected_fields
    has_payment = payment_marker in protected_fields

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
    marker: str,
    bound_start: int,
    bound_end: int,
) -> Optional[Any]:
    """
    在 [bound_start, bound_end] 范围内重新查找包含 marker 的受保护字段段落。

    Returns:
        找到的段落 Range，未找到返回 None
    """
    field_name = extract_protected_field_name(marker)
    search_rng = doc.Range(int(bound_start), int(bound_end))
    finder = search_rng.Find
    finder.ClearFormatting()
    finder.Text = field_name
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
            if _is_table_paragraph(para_rng):
                search_rng.Collapse(wdCollapseEnd)
                continue
            para_text = str(getattr(para_rng, "Text", "") or "").strip()
            if match_protected_field_line(para_text, marker):
                return para_rng
        search_rng.Collapse(wdCollapseEnd)
    return None


def insert_prefix_before_keyword(
    doc,
    marker: str,
    prefix: str,
    protected_fields: Dict[str, Any],
    *,
    log_parts: Optional[List[str]] = None,
) -> bool:
    """
    在受保护字段段落中，在字段 marker 之前插入前缀（如编号 `2、`）。

    如果前缀已存在则跳过。
    """
    if not prefix or not prefix.strip():
        return True
    canonical_marker = canonicalize_protected_field_marker(marker)
    if canonical_marker not in protected_fields:
        return False
    try:
        para_rng = protected_fields[canonical_marker]
        para_text = str(getattr(para_rng, "Text", "") or "")
        matched = match_protected_field_line(para_text, canonical_marker)
        if not matched:
            return False
        visible_text = _strip_paragraph_tail(para_text)
        field_start = int(matched["field_start"])
        before = visible_text[:field_start].replace("\r", "").replace("\a", "")
        prefix_clean = prefix.replace("\r", "").replace("\n", "")
        if before.endswith(prefix_clean):
            return True
        insert_pos = int(para_rng.Start) + field_start
        doc.Range(insert_pos, insert_pos).InsertBefore(prefix_clean)
        return True
    except Exception as e:
        if log_parts is not None:
            log_parts.append(f"  警告: 插入前缀失败 '{canonical_marker}': {e}")
        return False


def update_protected_field(
    doc,
    marker: str,
    new_value: Optional[str],
    protected_fields: Dict[str, Any],
    *,
    font_name: str = "宋体",
    font_size: int = 12,
    log_parts: Optional[List[str]] = None,
) -> bool:
    """
    更新受保护字段段落中 marker 冒号后的值。

    例如：`交付日期：旧值` -> `交付日期：新值`
    """
    canonical_marker = canonicalize_protected_field_marker(marker)
    if canonical_marker not in protected_fields:
        return False
    if new_value is None:
        return True

    try:
        para_rng = protected_fields[canonical_marker]
        para_text = str(getattr(para_rng, "Text", "") or "")
        matched = match_protected_field_line(para_text, canonical_marker)
        if not matched:
            return False

        value_start = int(para_rng.Start) + int(matched["colon_index"]) + 1
        visible_text = _strip_paragraph_tail(para_text)
        trim = len(para_text) - len(visible_text)
        value_end = int(para_rng.End) - trim
        if value_end < value_start:
            value_end = value_start

        value_rng = doc.Range(value_start, value_end)
        new_value_clean = new_value.replace("\r", "").replace("\n", "")
        value_rng.Text = new_value_clean
        value_rng.Font.Name = font_name
        value_rng.Font.Size = font_size
        if log_parts is not None:
            log_parts.append(
                f"  已更新受保护字段 '{canonical_marker}': {new_value_clean[:50]}..."
            )
        return True
    except Exception as e:
        if log_parts is not None:
            log_parts.append(f"  警告: 无法更新 '{canonical_marker}': {e}")
        return False
