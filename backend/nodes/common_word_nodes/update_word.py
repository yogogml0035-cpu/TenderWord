"""
统一的 Word 文档更新节点

将修改后的文本插入到 Word 文档中，支持多种招标类型。
使用 anchor_utils.find_anchor_range() 进行锚点定位。
"""

from __future__ import annotations

import re
from typing import Optional, Dict, Any
import time
import pathlib
import shutil
import sys

# 添加仓库根目录到 sys.path，便于直接运行当前脚本进行本地调试
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.states import TenderGraphStateBase
from backend.config.tender_config import (
    CONTENT_UPDATE_MODE_DIRECT_REPLACE,
    get_anchor_target_sizes,
    get_content_update_mode,
    get_default_anchor_texts,
)
from backend.util.word_util import (
    create_word_application,
    close_word_application,
    open_document_with_retry,
    unprotect_document,
)
from backend.util.word_util import (
    wdGoToPage,
    wdGoToAbsolute,
    wdLineSpace1pt5,
    wdOutlineLevelBodyText,
    wdCollapseStart,
    wdCollapseEnd,
    wdActiveEndPageNumber,
    wdFindStop,
    wdWithInTable,
)
from backend.util.word_util.anchor_utils import (
    find_anchor_range,
    resolve_anchor_content_range,
)


REQUIRED_PROTECTED_FIELD_KEYWORDS = ("交付日期", "付款方式")
PROTECTED_FIELD_SCAN_MARGIN = 400


def _is_keyword_paragraph(text: str, keyword: str) -> bool:
    return keyword in text and ("：" in text or ":" in text)


def _scan_protected_fields_in_range(doc, keywords, range_start: int, range_end: int):
    found = {}
    if range_end <= range_start:
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


def _collect_protected_fields(
    doc,
    keywords,
    target_range,
    fallback_range,
    boundary_margin: int = PROTECTED_FIELD_SCAN_MARGIN,
):
    found = {}
    scan_ranges = [target_range, fallback_range]

    if fallback_range:
        doc_end = int(getattr(getattr(doc, "Content", None), "End", fallback_range[1]))
        expanded_start = max(0, int(fallback_range[0]) - boundary_margin)
        expanded_end = min(doc_end, int(fallback_range[1]) + boundary_margin)
        expanded_range = (expanded_start, expanded_end)
        if expanded_range not in scan_ranges:
            scan_ranges.append(expanded_range)

    for scan_start, scan_end in scan_ranges:
        missing = [keyword for keyword in keywords if keyword not in found]
        if not missing:
            break
        found.update(_scan_protected_fields_in_range(doc, missing, scan_start, scan_end))

    return found


def _refresh_protected_fields(
    doc,
    keywords,
    range_start: int,
    range_end: int,
    existing_fields: Optional[Dict[str, Any]] = None,
):
    """在删除可编辑内容后，按最新文档位置重新绑定受保护字段段落。"""

    refreshed = dict(existing_fields or {})
    refreshed.update(
        _scan_protected_fields_in_range(doc, keywords, int(range_start), int(range_end))
    )
    return refreshed


def _validate_required_protected_fields(
    protected_fields, required_keywords=REQUIRED_PROTECTED_FIELD_KEYWORDS
):
    missing = [keyword for keyword in required_keywords if keyword not in protected_fields]
    if missing:
        raise ValueError(f"缺少关键受保护字段: {', '.join(missing)}")


def _inject_local_gap_before_anchor(
    doc,
    *,
    cursor_pos: int,
    bound_start: int,
    bound_end: int,
) -> Optional[int]:
    """在当前位置或后置锚点前补一个局部段落空位，供零宽插入点重试使用。"""

    safe_start = int(bound_start)
    safe_end = int(bound_end)
    if safe_end < safe_start:
        return None

    preferred = min(max(int(cursor_pos), safe_start), safe_end)
    candidates: list[int] = []
    for pos in (preferred, safe_end):
        if safe_start <= pos <= safe_end and pos not in candidates:
            candidates.append(pos)

    for pos in candidates:
        try:
            doc.Range(pos, pos).InsertBefore("\r")
            return pos
        except Exception:
            continue
    return None


def _resolve_block_flow(protected_fields: Dict[str, Any]) -> Dict[str, Any]:
    """根据已识别的受保护字段，返回与 master 对齐的块插入控制流。"""

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




def split_polished_text_into_blocks(polished_text: str) -> Dict[str, Any]:
    """
    将修改文本按关键字（交付日期、付款方式）拆分为三个块。

    Args:
        polished_text: 修改后的文本内容

    Returns:
        包含拆分结果的字典：
        - content_list: 所有内容行列表
        - delivery_date_line: 交付日期行
        - payment_method_line: 付款方式行
        - delivery_prefix: 交付日期前缀
        - delivery_value: 交付日期值
        - payment_prefix: 付款方式前缀
        - payment_value: 付款方式值
        - block1: 交付日期之前的内容
        - block2: 交付日期和付款方式之间的内容
        - block3: 付款方式之后的内容
    """
    polished_text_norm = polished_text.replace("\r\n", "\n").replace("\r", "\n")
    raw_lines = polished_text_norm.split("\n")
    content_list = [line.rstrip() for line in raw_lines if line.strip() != ""]

    def parse_keyword_line(line: Optional[str], keyword: str):
        if not line or keyword not in line:
            return "", None
        m = re.search(
            rf"^(?P<prefix>.*?){re.escape(keyword)}\s*([：:])(?P<value>.*)$", line
        )
        if m:
            return m.group("prefix"), m.group("value")
        idx = line.find(keyword)
        prefix = line[:idx]
        rest = line[idx + len(keyword) :]
        rest = rest.lstrip()
        if rest.startswith("：") or rest.startswith(":"):
            rest = rest[1:]
        return prefix, rest

    delivery_date_idx = next(
        (i for i, line in enumerate(content_list) if "交付日期" in line), None
    )
    payment_method_idx = next(
        (i for i, line in enumerate(content_list) if "付款方式" in line), None
    )

    delivery_date_line = (
        content_list[delivery_date_idx] if delivery_date_idx is not None else None
    )
    payment_method_line = (
        content_list[payment_method_idx] if payment_method_idx is not None else None
    )

    delivery_prefix, delivery_value = parse_keyword_line(delivery_date_line, "交付日期")
    payment_prefix, payment_value = parse_keyword_line(payment_method_line, "付款方式")

    block1 = (
        content_list[:delivery_date_idx]
        if delivery_date_idx is not None
        else (content_list[:] if content_list else [])
    )
    block2 = (
        content_list[delivery_date_idx + 1 : payment_method_idx]
        if delivery_date_idx is not None and payment_method_idx is not None
        else (
            content_list[delivery_date_idx + 1 :]
            if delivery_date_idx is not None
            else []
        )
    )
    block3 = (
        content_list[payment_method_idx + 1 :] if payment_method_idx is not None else []
    )

    return {
        "content_list": content_list,
        "delivery_date_line": delivery_date_line,
        "payment_method_line": payment_method_line,
        "delivery_prefix": delivery_prefix,
        "delivery_value": delivery_value,
        "payment_prefix": payment_prefix,
        "payment_value": payment_value,
        "block1": block1,
        "block2": block2,
        "block3": block3,
    }


def _is_table_separator_line(line: str) -> bool:
    return bool(re.match(r"^\s*\|\s*:?-{3,}.*\|\s*$", line))


def _parse_table_row(line: str) -> list[str]:
    cells = [cell.strip() for cell in line.split("|")]
    if cells and cells[0] == "":
        cells = cells[1:]
    if cells and cells[-1] == "":
        cells = cells[:-1]
    return cells


def _looks_like_table_row(line: str) -> bool:
    stripped = (line or "").strip()
    if "|" not in stripped:
        return False
    return len(_parse_table_row(stripped)) >= 2


def _parse_table_block(lines: list[str], start_idx: int) -> tuple[Optional[list[list[str]]], int]:
    table_lines: list[str] = []
    idx = start_idx
    while idx < len(lines) and lines[idx].strip().startswith("|"):
        table_lines.append(lines[idx].strip())
        idx += 1

    if len(table_lines) >= 2 and _is_table_separator_line(table_lines[1]):
        header = table_lines[0]
        data_lines = table_lines[2:] if len(table_lines) > 2 else []
        all_lines = [header] + data_lines
        return [_parse_table_row(line) for line in all_lines], idx

    fallback_lines: list[str] = []
    idx = start_idx
    while idx < len(lines) and _looks_like_table_row(lines[idx]):
        fallback_lines.append(lines[idx].strip())
        idx += 1
    if len(fallback_lines) >= 2:
        return [_parse_table_row(line) for line in fallback_lines], idx

    return None, start_idx


def _build_direct_replace_items(polished_text: str) -> list[Dict[str, Any]]:
    """按 gjgk 直插语义切分内容：仅抽离 Markdown 表格，其余文本块保留原始换行。"""

    normalized = polished_text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized:
        return []

    lines_with_endings = normalized.splitlines(keepends=True)
    line_texts = [
        line[:-1] if line.endswith("\n") else line for line in lines_with_endings
    ]

    line_offsets = [0]
    for line in lines_with_endings:
        line_offsets.append(line_offsets[-1] + len(line))

    items: list[Dict[str, Any]] = []
    prev_char = 0
    idx = 0
    while idx < len(line_texts):
        table_rows, next_idx = _parse_table_block(line_texts, idx)
        if table_rows:
            table_start = line_offsets[idx]
            if table_start > prev_char:
                items.append(
                    {
                        "type": "text_block",
                        "text": normalized[prev_char:table_start],
                    }
                )
            table_end = line_offsets[next_idx]
            items.append({"type": "table", "rows": table_rows})
            prev_char = table_end
            idx = next_idx
            continue
        idx += 1

    if prev_char < len(normalized):
        items.append({"type": "text_block", "text": normalized[prev_char:]})

    return [
        item
        for item in items
        if item["type"] != "text_block" or item.get("text") != ""
    ]


def _advance_direct_insert_bound(
    current_bound: int,
    *,
    marker_start: Optional[int] = None,
    inserted_end: Optional[int] = None,
) -> int:
    """在 Word 锚点回传滞后时，保证 gjgk 直插边界只向前推进。"""

    updated = int(current_bound)
    if marker_start is not None:
        updated = max(updated, int(marker_start))
    if inserted_end is not None:
        updated = max(updated, int(inserted_end))
    return updated


def _apply_standard_insert_format(
    inserted_rng,
    *,
    font_name: str,
    font_size: int,
) -> None:
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
    ):
        try:
            setattr(paragraph_format, attr, value)
        except Exception:
            continue


def _resolve_table_host_range(
    start_pos: int,
    *,
    doc_end: int,
    prefer_paragraph_host: bool,
) -> tuple[int, int]:
    """为表格插入生成宿主 Range。必要时改用前一个段落标记，而不是零宽边界点。"""

    start = max(0, int(start_pos))
    end = start
    if prefer_paragraph_host:
        if start > 0:
            return start - 1, start
        if int(doc_end) > start:
            end = min(start + 1, int(doc_end))
    return start, end


def _resolve_post_table_cursor(
    table_end: int,
    *,
    gap_pos: Optional[int] = None,
    appended_paragraph: bool = False,
) -> int:
    """为表格后的续写游标选一个不再停留在表格行尾语义里的位置。"""

    if gap_pos is not None:
        return int(gap_pos)
    if appended_paragraph:
        return int(table_end) + 1
    return int(table_end)


def update_word(state: TenderGraphStateBase, config) -> TenderGraphStateBase:
    """
    在指定锚点位置将修改后的文本插入到 Word 文档中。

    统一支持 xjcg（询价采购）和 gngk（国内公开）两种招标类型，
    根据状态中的 tender_type 自动选择对应的字体大小进行锚点定位。

    Args:
        state: 图状态，包含 prepared_doc_path、polished_text、
               insertion_before_text、insertion_after_text 等字段
        config: LangGraph 配置

    Returns:
        更新后的状态，包含 insertion_log
    """
    start_time = time.perf_counter()

    print("[update_word] 开始执行...")

    prepared_doc_path = state.get("prepared_doc_path")
    polished_text = state.get("polished_text")
    insertion_before_text = state.get("insertion_before_text")
    insertion_after_text = state.get("insertion_after_text")
    tender_type = state.get("tender_type", "xjcg")

    if not prepared_doc_path:
        raise ValueError("需要 prepared_doc_path 来插入内容到 Word 文档")
    if not polished_text:
        raise ValueError("需要 polished_text 来插入内容到 Word 文档")
    if not insertion_before_text or not insertion_after_text:
        raise ValueError(
            "insertion_before_text 和 insertion_after_text 必须提供，用于定位插入范围"
        )

    before_size, after_size = get_anchor_target_sizes(str(tender_type or "xjcg"))
    content_update_mode = get_content_update_mode(str(tender_type or "xjcg"))
    if content_update_mode == CONTENT_UPDATE_MODE_DIRECT_REPLACE:
        split_result = None
        content_list = []
        direct_replace_items = _build_direct_replace_items(polished_text)
    else:
        split_result = split_polished_text_into_blocks(polished_text)
        content_list = split_result["content_list"]
        direct_replace_items = []

    insertion_log_parts = []
    word = None
    doc = None
    com_initialized = False

    try:
        # 使用统一的工具函数创建 Word 应用程序
        word, com_initialized = create_word_application(
            initial_delay=0.0,
            post_init_delay=1.0,
            use_existing=False,
            verify=False,
            node_name="update_word",
        )

        try:
            # 使用统一的工具函数打开文档（带重试机制）
            doc = open_document_with_retry(
                word_app=word,
                file_path=prepared_doc_path,
                read_only=False,
                node_name="update_word",
            )
            insertion_log_parts.append(f"已打开文档: {prepared_doc_path}")

            # 使用统一的工具函数取消文档保护
            if unprotect_document(doc, node_name="update_word"):
                insertion_log_parts.append("已取消文档保护")

            # 使用 anchor_utils 的统一函数查找锚点
            insertion_log_parts.append(
                f"查找锚点（前置字号: {before_size}, 后置字号: {after_size}）..."
            )
            before_hit, after_hit = find_anchor_range(
                doc,
                insertion_before_text,
                insertion_after_text,
                before_size=before_size,
                after_size=after_size,
                prefer_before="last",  # 前置锚点选页码最大的（避开目录）
                prefer_after="first",  # 后置锚点选页码最小的（第一个后续章节）
            )

            if not before_hit:
                raise ValueError(f"未找到前置锚点段落: {insertion_before_text}")
            if not after_hit:
                raise ValueError(f"未找到后置锚点段落: {insertion_after_text}")

            before_anchor_start = before_hit["start"]
            before_anchor_end = before_hit["end"]
            before_anchor_page = before_hit["page"]

            after_anchor_start = after_hit["start"]
            after_anchor_end = after_hit["end"]
            after_anchor_page = after_hit["page"]

            insertion_log_parts.append(
                f"✅ 前置锚点: 页={before_anchor_page}, {before_anchor_start}-{before_anchor_end}, "
                f"字体={before_hit['font']}, 字号={before_hit['size']}"
            )
            insertion_log_parts.append(
                f"✅ 后置锚点: 页={after_anchor_page}, {after_anchor_start}-{after_anchor_end}, "
                f"字体={after_hit['font']}, 字号={after_hit['size']}"
            )

            content_range = resolve_anchor_content_range(
                doc=doc,
                word_app=word,
                before_hit=before_hit,
                after_hit=after_hit,
                tender_type=str(tender_type or "xjcg"),
                allow_empty=True,
            )
            insertion_bound_start = int(content_range["range_start"])
            insertion_bound_end = int(content_range["range_end"])
            computed_start_page = int(content_range["start_page"])
            computed_end_page = int(content_range["end_page"])

            after_anchor_marker = doc.Range(
                int(after_anchor_start), int(after_anchor_start)
            )
            effective_bound_end = int(insertion_bound_end)

            def get_insertion_bound_end(inserted_end: Optional[int] = None) -> int:
                nonlocal effective_bound_end
                marker_start = None
                try:
                    marker_start = int(after_anchor_marker.Start)
                except Exception:
                    marker_start = None
                effective_bound_end = _advance_direct_insert_bound(
                    effective_bound_end,
                    marker_start=marker_start,
                    inserted_end=inserted_end,
                )
                return int(effective_bound_end)

            insertion_log_parts.append(
                f"锚点范围(字符位置): {insertion_bound_start} - {insertion_bound_end}"
            )

            # 优先使用 extract_tender_params 已计算好的页范围
            start_page = state.get("start_page")
            end_page = state.get("end_page")

            if start_page is None or end_page is None:
                start_page = computed_start_page
                end_page = computed_end_page
                insertion_log_parts.append(f"回退计算页范围: {start_page} - {end_page}")
            else:
                insertion_log_parts.append(
                    f"使用预计算页范围: {start_page} - {end_page}"
                )

            if start_page is None or end_page is None:
                raise ValueError("无法确定插入页范围")
            if end_page < start_page:
                raise ValueError(f"插入页范围非法: {start_page} - {end_page}")

            # 检查是否有章节标题
            try:
                region_text = doc.Range(insertion_bound_start, insertion_bound_end).Text
                if re.search(r"第[一二三四五六七八九十0-9]+章", region_text):
                    raise ValueError(
                        "锚点之间检测到章节标题，停止插入以避免侵入其他章节"
                    )
            except Exception as _region_e:
                if isinstance(_region_e, ValueError):
                    raise

            selection = word.Selection

            # 处理目标页
            target_page = start_page
            insertion_log_parts.append(f"处理目标页 {target_page}")

            selection = word.Selection

            # 导航到目标页起始位置
            selection.GoTo(wdGoToPage, wdGoToAbsolute, target_page)
            page_start = selection.Start
            page_start_page = selection.Information(wdActiveEndPageNumber)

            # 查找目标页的结束位置
            next_page = target_page + 1
            selection.GoTo(wdGoToPage, wdGoToAbsolute, next_page)
            page_end = selection.Start
            page_end_page = selection.Information(wdActiveEndPageNumber)

            # 如果目标页不存在或已到达文档末尾
            if page_start_page != target_page or page_end == page_start:
                page_end = doc.Content.End
            elif page_end_page == next_page:
                pass
            else:
                page_end = doc.Content.End

            if page_end <= page_start:
                raise ValueError(
                    f"目标页 {target_page} 范围为空，无法定位受保护字段"
                )

            # 为目标页创建范围
            if page_end > page_start:
                page_rng = doc.Range(page_start, page_end)

                # 步骤1：优先在目标页定位受保护字段，必要时回查锚点边界范围
                use_direct_replace = (
                    content_update_mode == CONTENT_UPDATE_MODE_DIRECT_REPLACE
                )
                protected_keywords = (
                    []
                    if use_direct_replace
                    else list(REQUIRED_PROTECTED_FIELD_KEYWORDS)
                )
                target_range = (int(page_start), int(page_end))
                fallback_range = (
                    int(insertion_bound_start),
                    int(get_insertion_bound_end()),
                )
                if use_direct_replace:
                    insertion_log_parts.append(
                        "步骤1：gjgk direct_replace 模式，跳过受保护字段定位。"
                    )
                    protected_fields = {}
                else:
                    insertion_log_parts.append(
                        "步骤1：定位关键受保护字段..."
                        f" 目标页={target_page}({target_range[0]}-{target_range[1]})，"
                        f" 边界范围={fallback_range[0]}-{fallback_range[1]}"
                    )

                    protected_fields = _collect_protected_fields(
                        doc=doc,
                        keywords=protected_keywords,
                        target_range=target_range,
                        fallback_range=fallback_range,
                    )
                    if not protected_fields:
                        insertion_log_parts.append(
                            "  未在目标范围内找到受保护字段，将按可编辑边界继续插入。"
                        )
                    else:
                        for keyword, para_rng in protected_fields.items():
                            insertion_log_parts.append(
                                f"  找到受保护字段: {keyword} ({int(para_rng.Start)}-{int(para_rng.End)})"
                            )

                def _range_overlaps(
                    a_start: int, a_end: int, b_start: int, b_end: int
                ) -> bool:
                    return not (a_end <= b_start or b_end <= a_start)

                def is_protected_range(rng) -> bool:
                    try:
                        s = int(rng.Start)
                        e = int(rng.End)
                    except Exception:
                        return False
                    for pr in protected_fields.values():
                        try:
                            ps = int(pr.Start)
                            pe = int(pr.End)
                        except Exception:
                            continue
                        if _range_overlaps(s, e, ps, pe):
                            return True
                    return False

                # 步骤2：根据受保护字段将内容列表拆分为块
                insertion_log_parts.append(
                    "步骤2：按字段拆分内容块..."
                    if not use_direct_replace
                    else "步骤2：gjgk direct_replace 模式，按完整正文顺序插入。"
                )

                if use_direct_replace:
                    delivery_date_line = None
                    payment_method_line = None
                    delivery_prefix = ""
                    delivery_value = None
                    payment_prefix = ""
                    payment_value = None
                    block1 = []
                    block2 = []
                    block3 = []
                    insertion_log_parts.append(
                        "  same-page direct insert：仅抽离 Markdown 表格，其余文本块保留原始换行。"
                    )
                    insertion_log_parts.append(
                        f"  direct_replace 条目数: {len(direct_replace_items)}"
                    )
                else:
                    assert split_result is not None
                    delivery_date_line = split_result["delivery_date_line"]
                    payment_method_line = split_result["payment_method_line"]
                    delivery_prefix = split_result["delivery_prefix"]
                    delivery_value = split_result["delivery_value"]
                    payment_prefix = split_result["payment_prefix"]
                    payment_value = split_result["payment_value"]
                    block1 = split_result["block1"]
                    block2 = split_result["block2"]
                    block3 = split_result["block3"]
                    insertion_log_parts.append(f"  块1: {len(block1)} 条（交付日期之前）")
                    insertion_log_parts.append(f"  块2: {len(block2)} 条（交付日期区段）")
                    insertion_log_parts.append(f"  块3: {len(block3)} 条（付款方式之后）")
                    if delivery_prefix.strip():
                        insertion_log_parts.append(
                            f"  交付日期前缀: {delivery_prefix.strip()}"
                        )
                    if payment_prefix.strip():
                        insertion_log_parts.append(
                            f"  付款方式前缀: {payment_prefix.strip()}"
                        )

                # 步骤3：删除所有可编辑内容
                bound_start_for_delete = int(insertion_bound_start)
                bound_end_for_delete = int(get_insertion_bound_end())
                deletion_rng = doc.Range(bound_start_for_delete, bound_end_for_delete)
                insertion_log_parts.append(
                    f"步骤3：清理插入区间可编辑内容（{bound_start_for_delete} - {bound_end_for_delete}）..."
                )

                # 先删除插入区间内不包含受保护关键字的表格
                deleted_tables = 0
                try:
                    tables = deletion_rng.Tables
                    for t_idx in range(tables.Count, 0, -1):
                        try:
                            tbl = tables(t_idx)
                            if is_protected_range(tbl.Range):
                                continue
                            tbl.Range.Delete()
                            deleted_tables += 1
                        except Exception:
                            continue
                except Exception:
                    pass

                # 再删除插入区间内不受保护的段落内容
                paras = list(deletion_rng.Paragraphs)
                deleted_paras = 0
                for i in range(len(paras) - 1, -1, -1):
                    try:
                        para = paras[i]
                        para_text = para.Range.Text.strip()
                        if (
                            not para_text
                            or para_text == "\r"
                            or para_text == "\n"
                            or len(para_text) == 0
                        ):
                            continue
                        if is_protected_range(para.Range):
                            continue
                        try:
                            para.Range.Delete()
                            deleted_paras += 1
                        except Exception:
                            continue
                    except Exception:
                        continue

                insertion_log_parts.append(
                    f"步骤3完成：已删除表格 {deleted_tables} 个，删除段落 {deleted_paras} 个。"
                )

                # 步骤4：按块插入内容
                insertion_log_parts.append("步骤4：按块插入内容...")

                # 删除后重新获取页面范围
                if use_direct_replace:
                    page_start_after = int(insertion_bound_start)
                    page_end_after = int(get_insertion_bound_end())
                else:
                    selection.GoTo(wdGoToPage, wdGoToAbsolute, target_page)
                    page_start_after = selection.Start
                    selection.GoTo(wdGoToPage, wdGoToAbsolute, next_page)
                    page_end_after = (
                        selection.Start
                        if selection.Information(wdActiveEndPageNumber) == next_page
                        else doc.Content.End
                    )
                bound_end_for_search = int(get_insertion_bound_end())
                if int(page_end_after) < bound_end_for_search:
                    page_end_after = bound_end_for_search
                page_rng_after = doc.Range(page_start_after, page_end_after)

                # 步骤3附加：删除页面中完全空白、且不包含受保护关键字的表格
                try:
                    deleted_tables = 0
                    tables = page_rng_after.Tables
                    for t_idx in range(tables.Count, 0, -1):
                        try:
                            tbl = tables(t_idx)
                            tbl_text = tbl.Range.Text
                            if is_protected_range(tbl.Range):
                                continue
                            cleaned = (
                                tbl_text.replace("\r", "")
                                .replace("\n", "")
                                .replace("\x07", "")
                                .replace(" ", "")
                                .replace("\t", "")
                            ).strip()
                            if not cleaned:
                                tbl.Range.Delete()
                                deleted_tables += 1
                        except Exception:
                            continue
                    if deleted_tables > 0:
                        insertion_log_parts.append(
                            f"步骤3附加：删除空白表格 {deleted_tables} 个。"
                        )
                except Exception:
                    pass

                def refind_protected_paragraph(keyword: str):
                    bound_end = int(get_insertion_bound_end())
                    search_rng = doc.Range(int(insertion_bound_start), bound_end)
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
                        if int(insertion_bound_start) <= pos <= bound_end:
                            para_rng = doc.Range(pos, pos).Paragraphs(1).Range
                            para_text = para_rng.Text.strip()
                            if keyword in para_text and (
                                "：" in para_text or ":" in para_text
                            ):
                                return para_rng
                        search_rng.Collapse(wdCollapseEnd)
                    return None

                # 删除阶段可能补回段落边界，这里先整体重绑一次字段位置，
                # 后续块插入仍按最新段落范围操作。
                protected_fields = _refresh_protected_fields(
                    doc=doc,
                    keywords=protected_keywords,
                    range_start=int(insertion_bound_start),
                    range_end=int(get_insertion_bound_end()),
                    existing_fields=protected_fields,
                )
                if protected_fields:
                    for keyword, para_rng in protected_fields.items():
                        insertion_log_parts.append(
                            f"  重定位受保护字段: {keyword} ({int(para_rng.Start)}-{int(para_rng.End)})"
                        )
                else:
                    insertion_log_parts.append(
                        "  重定位未命中受保护字段，将按回退路径插入。"
                    )

                def is_range_locked(rng) -> bool:
                    try:
                        if hasattr(rng, "Locked") and rng.Locked:
                            return True
                    except Exception:
                        pass
                    try:
                        fields = rng.Fields
                        count = fields.Count
                        for i in range(1, count + 1):
                            try:
                                field = fields(i)
                                if hasattr(field, "Locked") and field.Locked:
                                    return True
                            except Exception:
                                continue
                    except Exception:
                        pass
                    try:
                        marker = "\u200b"
                        test_pos = rng.End
                        probe_rng = doc.Range(test_pos, test_pos)
                        probe_rng.InsertAfter(marker)
                        inserted = doc.Range(test_pos, test_pos + 1)
                        if inserted.Text == marker:
                            inserted.Delete()
                            return False
                        return True
                    except Exception as probe_e:
                        err = str(probe_e).lower()
                        if "锁定" in err or "locked" in err or "-2146823683" in err:
                            return True
                        return True

                def find_editable_insertion_pos(
                    start_pos: int, max_lookahead: int = 400
                ) -> int:
                    bound_end = int(get_insertion_bound_end())
                    bound_start = int(insertion_bound_start)
                    doc_end = int(doc.Content.End)
                    scan_end = min(doc_end, bound_end)
                    pos = min(max(0, int(start_pos)), scan_end)
                    if pos < bound_start:
                        pos = bound_start
                    for _ in range(max_lookahead + 1):
                        try:
                            probe = doc.Range(pos, pos)
                            if not is_range_locked(probe):
                                return pos
                        except Exception:
                            pass
                        if pos >= scan_end:
                            break
                        pos += 1
                    return min(max(0, int(start_pos)), scan_end)

                def find_next_editable_pos(
                    after_pos: int, max_paragraphs: int = 250
                ) -> int:
                    bound_end = int(get_insertion_bound_end())
                    bound_start = int(insertion_bound_start)
                    doc_end = int(doc.Content.End)
                    scan_end = min(doc_end, bound_end)
                    start = min(max(0, int(after_pos)), scan_end)
                    if start < bound_start:
                        start = bound_start
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
                                if not is_range_locked(doc.Range(candidate, candidate)):
                                    return candidate
                            except Exception:
                                continue
                    except Exception:
                        pass
                    return find_editable_insertion_pos(start, max_lookahead=20000)

                def find_next_editable_pos_bounded(
                    start_pos: int, bound_end: int, max_lookahead: int = 4000
                ) -> Optional[int]:
                    doc_end = int(doc.Content.End)
                    start = int(min(max(0, start_pos), doc_end))
                    end = int(min(max(0, bound_end), doc_end))
                    if end < start:
                        return None
                    pos = start
                    look = min(max_lookahead, end - start)
                    for _ in range(look + 1):
                        try:
                            if not is_range_locked(doc.Range(pos, pos)):
                                return pos
                        except Exception:
                            pass
                        pos += 1
                        if pos > end:
                            break
                    return None

                def find_prev_editable_pos(
                    before_pos: int, max_lookback: int = 4000
                ) -> Optional[int]:
                    doc_end = int(doc.Content.End)
                    pos = int(min(max(0, before_pos), doc_end))
                    for _ in range(max_lookback + 1):
                        try:
                            if not is_range_locked(doc.Range(pos, pos)):
                                return pos
                        except Exception:
                            pass
                        if pos <= 0:
                            break
                        pos -= 1
                    return None

                def is_locked_exception(e: Exception) -> bool:
                    err = str(e).lower()
                    return (
                        ("锁定" in err) or ("locked" in err) or ("-2146823683" in err)
                    )

                def ensure_editable_insert_range(insert_range) -> None:
                    try:
                        insert_range.Collapse(wdCollapseStart)
                    except Exception:
                        pass
                    try:
                        pos = int(insert_range.Start)
                    except Exception:
                        pos = 0
                    try:
                        bound_end = int(get_insertion_bound_end())
                        bound_start = int(insertion_bound_start)
                        if pos < bound_start:
                            pos = bound_start
                            insert_range.SetRange(pos, pos)
                            insert_range.Collapse(wdCollapseStart)
                        if pos > bound_end:
                            pos = bound_end
                            insert_range.SetRange(pos, pos)
                            insert_range.Collapse(wdCollapseStart)
                        if is_range_locked(doc.Range(pos, pos)):
                            pos2 = find_next_editable_pos_bounded(
                                pos + 1, bound_end, max_lookahead=20000
                            )
                            if pos2 is not None and pos2 > pos:
                                insert_range.SetRange(pos2, pos2)
                                insert_range.Collapse(wdCollapseStart)
                    except Exception:
                        pass

                # 格式设置
                insert_font_name = "宋体"
                insert_font_size = 12

                def convert_lines_to_items(lines):
                    items = []
                    idx = 0
                    while idx < len(lines):
                        line = lines[idx]
                        maybe_table, next_idx = _parse_table_block(lines, idx)
                        if maybe_table:
                            items.append({"type": "table", "rows": maybe_table})
                            idx = next_idx
                        else:
                            items.append({"type": "text", "line": line})
                            idx += 1
                    return items

                def _format_inserted_range(inserted_rng) -> None:
                    _apply_standard_insert_format(
                        inserted_rng,
                        font_name=insert_font_name,
                        font_size=insert_font_size,
                    )

                def insert_content_with_formatting(insert_range, line):
                    ensure_editable_insert_range(insert_range)
                    start_pos = insert_range.End
                    insert_range.InsertAfter(line + "\r")
                    end_pos = insert_range.End
                    inserted_rng = doc.Range(start_pos, end_pos - 1)
                    _format_inserted_range(inserted_rng)
                    insert_range.Collapse(wdCollapseEnd)
                    return inserted_rng

                def insert_text_block_with_formatting(insert_range, text_block: str):
                    ensure_editable_insert_range(insert_range)
                    normalized_block = text_block.replace("\r\n", "\n").replace("\r", "\n")
                    if normalized_block == "":
                        return None

                    word_text = normalized_block.replace("\n", "\r")

                    try:
                        cursor_pos = int(insert_range.Start)
                    except Exception:
                        cursor_pos = int(insertion_bound_start)

                    bound_end_before = int(get_insertion_bound_end())
                    if cursor_pos >= bound_end_before:
                        start_pos = bound_end_before
                        boundary_rng = doc.Range(start_pos, start_pos)
                        boundary_rng.InsertBefore(word_text)
                        end_pos = int(get_insertion_bound_end(start_pos + len(word_text)))
                        inserted_rng = doc.Range(start_pos, end_pos)
                    else:
                        start_pos = cursor_pos
                        insert_range.InsertAfter(word_text)
                        try:
                            end_pos = int(insert_range.End)
                        except Exception:
                            end_pos = start_pos + len(word_text)
                        end_pos = int(get_insertion_bound_end(end_pos))
                        inserted_rng = doc.Range(start_pos, end_pos)

                    _format_inserted_range(inserted_rng)
                    insert_range.SetRange(end_pos, end_pos)
                    insert_range.Collapse(wdCollapseStart)
                    return inserted_rng

                def _ensure_trailing_paragraph_after_table(table) -> bool:
                    last_exc = None
                    try:
                        tail_range = table.Range.Duplicate
                        tail_range.Collapse(wdCollapseEnd)
                        tail_range.InsertParagraphAfter()
                        return True
                    except Exception as exc:
                        last_exc = exc

                    try:
                        table.Range.InsertParagraphAfter()
                        return True
                    except Exception as exc:
                        last_exc = exc

                    if last_exc is not None:
                        insertion_log_parts.append(
                            f"    警告: gjgk 表格后补可编辑段落失败: {last_exc}"
                        )
                    return False

                def insert_table_with_formatting(
                    insert_range,
                    rows,
                    *,
                    keep_trailing_gap: bool = False,
                ):
                    if not rows:
                        return None

                    ensure_editable_insert_range(insert_range)

                    try:
                        start_pos = int(insert_range.End)
                    except Exception:
                        start_pos = int(insertion_bound_start)

                    prefer_paragraph_host = False
                    if use_direct_replace:
                        needs_host_paragraph = start_pos >= int(get_insertion_bound_end())
                        if not needs_host_paragraph:
                            try:
                                needs_host_paragraph = is_range_locked(
                                    doc.Range(start_pos, start_pos)
                                )
                            except Exception:
                                needs_host_paragraph = False

                        if needs_host_paragraph:
                            prefer_paragraph_host = True
                            has_existing_paragraph_host = False
                            if start_pos > 0:
                                insertion_log_parts.append(
                                    f"    gjgk 表格插入改用位置 {start_pos} 前一个段落标记建表。"
                                )
                                try:
                                    prev_text = str(doc.Range(start_pos - 1, start_pos).Text or "")
                                    has_existing_paragraph_host = (
                                        "\r" in prev_text or "\n" in prev_text
                                    )
                                except Exception:
                                    pass
                            if not has_existing_paragraph_host:
                                gap_pos = _inject_local_gap_before_anchor(
                                    doc,
                                    cursor_pos=start_pos,
                                    bound_start=int(insertion_bound_start),
                                    bound_end=int(get_insertion_bound_end()),
                                )
                                if gap_pos is not None:
                                    try:
                                        marker_after_gap = int(after_anchor_marker.Start)
                                    except Exception:
                                        marker_after_gap = int(gap_pos) + 1
                                    start_pos = max(0, int(marker_after_gap))
                                    insertion_log_parts.append(
                                        f"    gjgk 表格插入前已在位置 {start_pos} 前预留宿主段落。"
                                    )
                                    try:
                                        insert_range.SetRange(start_pos, start_pos)
                                        insert_range.Collapse(wdCollapseStart)
                                    except Exception:
                                        pass

                    try:
                        if insert_range.Information(wdWithInTable):
                            parent_tables = insert_range.Tables
                            if parent_tables.Count > 0:
                                host_table = parent_tables(1)
                                end_pos = int(host_table.Range.End)
                                bound_end = int(get_insertion_bound_end())
                                if end_pos > bound_end:
                                    end_pos = bound_end
                                insert_range.SetRange(end_pos, end_pos)
                                insert_range.Collapse(wdCollapseStart)
                                start_pos = end_pos
                    except Exception:
                        pass

                    cols = max(len(r) for r in rows)
                    table_start, table_end = _resolve_table_host_range(
                        start_pos,
                        doc_end=int(doc.Content.End),
                        prefer_paragraph_host=prefer_paragraph_host,
                    )
                    table_range = doc.Range(table_start, table_end)
                    table = doc.Tables.Add(table_range, len(rows), cols)
                    try:
                        table.Borders.Enable = True
                    except Exception:
                        pass

                    # 填充所有行的所有单元格
                    for r_idx, row in enumerate(rows):
                        for c_idx, val in enumerate(row):
                            try:
                                cell = table.Cell(r_idx + 1, c_idx + 1)
                                cell_range = cell.Range
                                if cell_range.End > cell_range.Start + 1:
                                    delete_range = doc.Range(
                                        cell_range.Start, cell_range.End - 1
                                    )
                                    delete_range.Delete()

                                cell_range = cell.Range
                                cell_text = "" if val is None else str(val)
                                cell_text = re.sub(r"(?i)<br\s*/?>", "\r", cell_text)
                                cell_range.InsertBefore(cell_text)

                                cell_range = cell.Range
                                _apply_standard_insert_format(
                                    cell_range,
                                    font_name=insert_font_name,
                                    font_size=insert_font_size,
                                )
                                cell_range.ParagraphFormat.Alignment = 0
                                cell.VerticalAlignment = 1
                            except Exception:
                                pass

                    try:
                        table_end = int(table.Range.End)
                    except Exception:
                        table_end = int(insert_range.End)

                    post_table_cursor = None
                    if keep_trailing_gap and use_direct_replace:
                        bound_end_for_gap = int(get_insertion_bound_end(table_end))
                        gap_pos = _inject_local_gap_before_anchor(
                            doc,
                            cursor_pos=table_end,
                            bound_start=int(insertion_bound_start),
                            bound_end=bound_end_for_gap,
                        )
                        if gap_pos is not None:
                            post_table_cursor = _resolve_post_table_cursor(
                                table_end,
                                gap_pos=gap_pos,
                            )
                            insertion_log_parts.append(
                                f"    gjgk 表格后续写改用位置 {post_table_cursor} 的可编辑宿主段落。"
                            )
                        elif _ensure_trailing_paragraph_after_table(table):
                            post_table_cursor = _resolve_post_table_cursor(
                                table_end,
                                appended_paragraph=True,
                            )
                            insertion_log_parts.append(
                                f"    gjgk 表格后续写游标前推到位置 {post_table_cursor}。"
                            )

                    if post_table_cursor is not None:
                        table_end = post_table_cursor

                    table_end = int(get_insertion_bound_end(table_end))

                    try:
                        insert_range.SetRange(table_end, table_end)
                    except Exception:
                        insert_range.Collapse(wdCollapseEnd)
                        insert_range.Start = table_end
                        insert_range.End = table_end
                    insert_range.Collapse(wdCollapseEnd)
                    return table

                def insert_item_with_optional_local_gap(
                    insert_range,
                    item,
                    *,
                    keep_trailing_gap: bool = False,
                ):
                    def _insert_once():
                        if item["type"] == "text":
                            return insert_content_with_formatting(
                                insert_range, item["line"]
                            )
                        if item["type"] == "text_block":
                            return insert_text_block_with_formatting(
                                insert_range, item["text"]
                            )
                        if item["type"] == "table":
                            return insert_table_with_formatting(
                                insert_range,
                                item["rows"],
                                keep_trailing_gap=keep_trailing_gap,
                            )
                        raise ValueError(f"未知插入项类型: {item['type']}")

                    try:
                        return _insert_once()
                    except Exception as exc:
                        if not use_direct_replace or not is_locked_exception(exc):
                            raise

                        try:
                            cursor_pos = int(insert_range.Start)
                        except Exception:
                            cursor_pos = int(insertion_bound_start)

                        gap_pos = _inject_local_gap_before_anchor(
                            doc,
                            cursor_pos=cursor_pos,
                            bound_start=int(insertion_bound_start),
                            bound_end=int(get_insertion_bound_end()),
                        )
                        if gap_pos is None:
                            raise

                        insertion_log_parts.append(
                            f"    gjgk 插入点受阻，已在位置 {gap_pos} 局部补一个段落空位后重试。"
                        )
                        insert_range.SetRange(gap_pos, gap_pos)
                        insert_range.Collapse(wdCollapseStart)
                        return _insert_once()

                def insert_prefix_before_keyword(keyword: str, prefix: str):
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
                        insertion_log_parts.append(
                            f"  警告: 插入前缀失败 '{keyword}': {e}"
                        )
                        return False

                def update_protected_field(keyword: str, new_value: Optional[str]):
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
                        value_rng.Font.Name = insert_font_name
                        value_rng.Font.Size = insert_font_size
                        insertion_log_parts.append(
                            f"  已更新受保护字段 '{keyword}': {new_value_clean[:50]}..."
                        )
                        return True
                    except Exception as e:
                        insertion_log_parts.append(f"  警告: 无法更新 '{keyword}': {e}")
                        return False

                def insert_items_inline_at_end_of_paragraph(para_rng, items) -> int:
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
                            s = chr(11) + item["line"]
                            st = int(rng.Start)
                            rng.InsertAfter(s)
                            ed = int(rng.End)
                            try:
                                ins = doc.Range(st, ed)
                                ins.Font.Name = insert_font_name
                                ins.Font.Size = insert_font_size
                                ins.Font.Bold = False
                            except Exception:
                                pass
                            rng.Collapse(wdCollapseEnd)
                            inserted += 1
                        elif item["type"] == "table":
                            try:
                                insert_table_with_formatting(rng, item["rows"])
                                inserted += 1
                            except Exception as e:
                                insertion_log_parts.append(
                                    f"    警告: 内联插入表格失败，改为文本: {e}"
                                )
                                for row in item["rows"]:
                                    s = chr(11) + " | ".join(row)
                                    st = int(rng.Start)
                                    rng.InsertAfter(s)
                                    rng.Collapse(wdCollapseEnd)
                                    inserted += 1
                    return inserted

                def describe_item(item: Dict[str, Any]) -> str:
                    if item["type"] == "table":
                        return f"表格，行数 {len(item['rows'])}"
                    if item["type"] == "text_block":
                        text = item.get("text", "")
                    else:
                        text = item.get("line", "")
                    text = text.replace("\r", "\\r").replace("\n", "\\n").strip()
                    return f"{text[:50]}..." if len(text) > 50 else text

                flow = _resolve_block_flow(protected_fields)

                # 插入块1（始终执行，优先在交付日期前，否则回退到目标页起始可编辑位置）
                insertion_log_parts.append("  正在插入块1...")
                if use_direct_replace:
                    insert_rng = doc.Range(
                        int(insertion_bound_start), int(insertion_bound_start)
                    )
                    insert_rng.Collapse(wdCollapseStart)
                    insertion_log_parts.append(
                        f"    direct_replace 从锚点后位置开始插入，位置 {int(insertion_bound_start)}"
                    )
                else:
                    selection.GoTo(wdGoToPage, wdGoToAbsolute, target_page)
                    insert_rng = selection.Range
                    insert_rng.Collapse(wdCollapseStart)

                if flow["has_delivery"]:
                    delivery_date_rng = protected_fields["交付日期"]
                    before_pos = int(delivery_date_rng.Start)
                    safe_before = find_prev_editable_pos(before_pos, max_lookback=20000)
                    if safe_before is None:
                        safe_before = find_editable_insertion_pos(
                            int(page_start_after), max_lookahead=20000
                        )
                    insert_rng.SetRange(safe_before, safe_before)
                    insert_rng.Collapse(wdCollapseStart)

                block1_items = (
                    direct_replace_items
                    if use_direct_replace
                    else convert_lines_to_items(block1)
                )
                for item_idx, item in enumerate(block1_items):
                    try:
                        if item["type"] in {"text", "text_block"}:
                            insert_item_with_optional_local_gap(insert_rng, item)
                            insertion_log_parts.append(
                                f"    已插入: {describe_item(item)}"
                            )
                        elif item["type"] == "table":
                            keep_trailing_gap = any(
                                later_item["type"] in {"text", "text_block", "table"}
                                for later_item in block1_items[item_idx + 1 :]
                            )
                            insert_item_with_optional_local_gap(
                                insert_rng,
                                item,
                                keep_trailing_gap=keep_trailing_gap,
                            )
                            insertion_log_parts.append(
                                f"    已插入表格，行数 {len(item['rows'])}。"
                            )
                    except Exception as e:
                        insertion_log_parts.append(f"    插入项出错: {e}")

                if flow["has_delivery"]:
                    insert_prefix_before_keyword("交付日期", delivery_prefix)
                    protected_fields["交付日期"] = (
                        refind_protected_paragraph("交付日期")
                        or protected_fields["交付日期"]
                    )
                    update_protected_field("交付日期", delivery_value)

                    # 插入块2（与 master 对齐：双字段时插中间，仅交付日期时插其后）
                    insertion_log_parts.append("  插入块2...")
                    if flow["block2_mode"] == "between_delivery_payment":
                        delivery_date_rng = protected_fields["交付日期"]
                        protected_fields["付款方式"] = (
                            refind_protected_paragraph("付款方式")
                            or protected_fields["付款方式"]
                        )
                        payment_method_rng = protected_fields["付款方式"]

                        start_between = int(delivery_date_rng.End)
                        end_between = int(payment_method_rng.Start)
                        if end_between < start_between:
                            raise ValueError(
                                "付款方式字段位于交付日期之前，停止以避免错误插入"
                            )

                        safe_between = find_next_editable_pos_bounded(
                            start_between, end_between, max_lookahead=20000
                        )
                        if safe_between is None:
                            safe_between = find_next_editable_pos(start_between)
                        insert_rng.SetRange(safe_between, safe_between)
                        insert_rng.Collapse(wdCollapseStart)

                        block2_items = convert_lines_to_items(block2)
                        for item in block2_items:
                            try:
                                if item["type"] == "text":
                                    inserted_rng = insert_content_with_formatting(
                                        insert_rng, item["line"]
                                    )
                                    insertion_log_parts.append(
                                        f"    已插入: {item['line'][:50]}..."
                                    )
                                elif item["type"] == "table":
                                    insert_table_with_formatting(insert_rng, item["rows"])
                                    insertion_log_parts.append(
                                        f"    已插入表格，行数 {len(item['rows'])}。"
                                    )
                            except Exception as e:
                                insertion_log_parts.append(f"    插入项出错: {e}")
                    elif flow["block2_mode"] == "after_delivery":
                        delivery_date_rng = protected_fields["交付日期"]
                        start_after = int(delivery_date_rng.End)
                        safe_after = find_next_editable_pos(start_after)
                        insert_rng.SetRange(safe_after, safe_after)
                        insert_rng.Collapse(wdCollapseStart)

                        block2_items = convert_lines_to_items(block2)
                        for item in block2_items:
                            try:
                                if item["type"] == "text":
                                    inserted_rng = insert_content_with_formatting(
                                        insert_rng, item["line"]
                                    )
                                    insertion_log_parts.append(
                                        f"    已插入: {item['line'][:50]}..."
                                    )
                                elif item["type"] == "table":
                                    insert_table_with_formatting(insert_rng, item["rows"])
                                    insertion_log_parts.append(
                                        f"    已插入表格，行数 {len(item['rows'])}。"
                                    )
                            except Exception as e:
                                insertion_log_parts.append(f"    插入项出错: {e}")

                    if flow["has_payment"]:
                        insert_prefix_before_keyword("付款方式", payment_prefix)
                        protected_fields["付款方式"] = (
                            refind_protected_paragraph("付款方式")
                            or protected_fields["付款方式"]
                        )
                        update_protected_field("付款方式", payment_value)

                # 插入块3（有付款方式则插其后，否则回退到后置锚点前）
                if use_direct_replace:
                    block3_items = []
                    insertion_log_parts.append(
                        "  gjgk direct_replace 已在块1消费完整正文，跳过 legacy 块3 路径。"
                    )
                else:
                    block3_items = convert_lines_to_items(block3)
                insertion_log_parts.append(f"  插入块3（{len(block3_items)} 条）...")
                if len(block3_items) == 0:
                    insertion_log_parts.append("    警告：块3为空，无需插入")
                else:
                    insertion_log_parts.append(
                        f"    块3内容: "
                        f"{[item['line'][:30] + '...' if item['type'] == 'text' and len(item['line']) > 30 else item['line'] if item['type'] == 'text' else '<表格>' for item in block3_items]}"
                    )

                if flow["block3_anchor"] == "after_payment" and "付款方式" in protected_fields:
                    protected_fields["付款方式"] = (
                        refind_protected_paragraph("付款方式")
                        or protected_fields["付款方式"]
                    )
                    payment_method_rng = protected_fields["付款方式"]
                    bound_end_now = int(get_insertion_bound_end())
                    if int(payment_method_rng.End) > bound_end_now:
                        raise ValueError(
                            "付款方式字段位置超出插入边界，停止以避免侵入后置章节"
                        )
                    payment_end = int(payment_method_rng.End)
                    start_after_payment = min(payment_end + 1, bound_end_now)
                    safe_pos = None
                    if start_after_payment < bound_end_now:
                        safe_pos = find_next_editable_pos_bounded(
                            start_after_payment, bound_end_now, max_lookahead=20000
                        )
                    if safe_pos is None or safe_pos >= bound_end_now:
                        if bound_end_now > payment_end:
                            back = find_prev_editable_pos(
                                bound_end_now - 1, max_lookback=20000
                            )
                            if back is not None and back >= payment_end:
                                safe_pos = back
                    if safe_pos is None:
                        safe_pos = start_after_payment
                    insert_rng.Start = min(max(0, safe_pos), doc.Content.End)
                    insert_rng.End = insert_rng.Start
                    insert_rng.Collapse(wdCollapseStart)
                    insertion_log_parts.append(
                        f"    在付款方式字段后插入，位置 {insert_rng.Start}"
                    )
                else:
                    safe_pos = int(get_insertion_bound_end())
                    insert_rng.SetRange(safe_pos, safe_pos)
                    insert_rng.Collapse(wdCollapseStart)
                    insertion_log_parts.append(
                        f"    未找到付款方式字段，插入到后置锚点前，位置 {insert_rng.Start}"
                    )

                use_inline = False
                try:
                    if is_range_locked(
                        doc.Range(int(insert_rng.Start), int(insert_rng.Start))
                    ):
                        use_inline = True
                except Exception:
                    pass

                inserted_count = 0
                if use_inline and "付款方式" in protected_fields:
                    insertion_log_parts.append(
                        "    块3将以内联换行追加到付款方式段落末尾"
                    )
                    inserted_count = insert_items_inline_at_end_of_paragraph(
                        protected_fields["付款方式"], block3_items
                    )
                else:
                    for item in block3_items:
                        attempts = 0
                        while attempts < 80:
                            attempts += 1
                            try:
                                ensure_editable_insert_range(insert_rng)
                                if item["type"] == "text":
                                    inserted_rng = insert_item_with_optional_local_gap(
                                        insert_rng, item
                                    )
                                    inserted_count += 1
                                    insertion_log_parts.append(
                                        f"    [{inserted_count}/{len(block3_items)}] 已插入: {item['line'][:50]}..."
                                    )
                                    break
                                elif item["type"] == "table":
                                    insert_item_with_optional_local_gap(
                                        insert_rng, item
                                    )
                                    inserted_count += 1
                                    insertion_log_parts.append(
                                        f"    [{inserted_count}/{len(block3_items)}] 已插入表格，行数 {len(item['rows'])}。"
                                    )
                                    break
                            except Exception as e:
                                if is_locked_exception(e):
                                    try:
                                        cur = int(insert_rng.Start)
                                    except Exception:
                                        cur = 0
                                    bound_end_retry = int(get_insertion_bound_end())
                                    nxt = find_next_editable_pos_bounded(
                                        cur + 1,
                                        bound_end_retry,
                                        max_lookahead=20000,
                                    )
                                    if nxt is None or nxt <= cur:
                                        insertion_log_parts.append(
                                            f"    插入项出错: {e}"
                                        )
                                        break
                                    try:
                                        insert_rng.SetRange(nxt, nxt)
                                        insert_rng.Collapse(wdCollapseStart)
                                        continue
                                    except Exception:
                                        insertion_log_parts.append(
                                            f"    插入项出错: {e}"
                                        )
                                        break
                                insertion_log_parts.append(f"    插入项出错: {e}")
                                break

                insertion_log_parts.append(
                    f"  块3插入完成: {inserted_count}/{len(block3_items)} 条。"
                )

                # 步骤5：从所有可编辑内容中移除空段落和换行符
                if use_direct_replace:
                    insertion_log_parts.append(
                        "步骤5：gjgk same-page direct insert，跳过 legacy 空段/换行清理。"
                    )
                else:
                    insertion_log_parts.append("步骤5：清理空段落与换行...")

                    max_passes = 5
                    total_empty_deleted = 0

                    for pass_num in range(1, max_passes + 1):
                        insertion_log_parts.append(
                            f"  步骤5.1 第 {pass_num} 轮：删除空段落..."
                        )

                        selection.GoTo(wdGoToPage, wdGoToAbsolute, target_page)
                        page_start_final = selection.Start
                        selection.GoTo(wdGoToPage, wdGoToAbsolute, next_page)
                        page_end_final = (
                            selection.Start
                            if selection.Information(wdActiveEndPageNumber) == next_page
                            else doc.Content.End
                        )
                        page_rng_final = doc.Range(page_start_final, page_end_final)

                        paras_final = list(page_rng_final.Paragraphs)
                        empty_deleted = 0

                        for i in range(len(paras_final) - 1, -1, -1):
                            try:
                                para = paras_final[i]

                                if para.Range.Information(wdWithInTable):
                                    continue

                                is_protected = is_protected_range(para.Range)

                                if not is_protected:
                                    raw_text = para.Range.Text
                                    raw_text_no_mark = raw_text.rstrip("\r\n")

                                    raw_cleaned = (
                                        raw_text_no_mark.replace("\r", "")
                                        .replace("\n", "")
                                        .replace(" ", "")
                                        .replace("\t", "")
                                        .replace("\u00a0", "")
                                        .replace("\u2000", "")
                                        .replace("\u2001", "")
                                        .replace("\u2002", "")
                                        .replace("\u2003", "")
                                        .replace("\u2004", "")
                                        .replace("\u2005", "")
                                        .replace("\u2006", "")
                                        .replace("\u2007", "")
                                        .replace("\u2008", "")
                                        .replace("\u2009", "")
                                        .replace("\u200a", "")
                                        .replace("\u200b", "")
                                        .strip()
                                    )

                                    if len(raw_cleaned) == 0:
                                        try:
                                            para.Range.Delete()
                                            empty_deleted += 1
                                            insertion_log_parts.append(
                                                f"    删除空段落，索引 {i}"
                                            )
                                        except Exception as e:
                                            insertion_log_parts.append(
                                                f"    警告: 无法删除索引 {i} 的段落: {e}"
                                            )
                            except Exception as e:
                                insertion_log_parts.append(
                                    f"    处理第 {i} 段出错: {e}"
                                )

                        total_empty_deleted += empty_deleted
                        insertion_log_parts.append(
                            f"  第 {pass_num} 轮完成：删除空段 {empty_deleted} 个。"
                        )

                        if empty_deleted == 0:
                            insertion_log_parts.append(
                                f"  未再发现空段，第 {pass_num} 轮后停止。"
                            )
                            break

                    insertion_log_parts.append(
                        f"  步骤5.1完成：共删除空段 {total_empty_deleted} 个，用时 {pass_num} 轮。"
                    )

                    # 第二轮：从可编辑段落中移除换行符
                    insertion_log_parts.append("  步骤5.2：清理可编辑段落中的换行...")

                    selection.GoTo(wdGoToPage, wdGoToAbsolute, target_page)
                    page_start_clean = selection.Start
                    selection.GoTo(wdGoToPage, wdGoToAbsolute, next_page)
                    page_end_clean = (
                        selection.Start
                        if selection.Information(wdActiveEndPageNumber) == next_page
                        else doc.Content.End
                    )
                    page_rng_clean = doc.Range(page_start_clean, page_end_clean)

                    cleaned_count = 0
                    paras_to_delete = []

                    for para in page_rng_clean.Paragraphs:
                        if para.Range.Information(wdWithInTable):
                            continue

                        para_text = para.Range.Text.strip()

                        if not para_text or para_text == "\r" or para_text == "\n":
                            continue

                        is_protected = is_protected_range(para.Range)

                        if not is_protected:
                            try:
                                para_rng = para.Range
                                full_text = para_rng.Text

                                text_without_mark = full_text.rstrip("\r\n")

                                if (
                                    not text_without_mark
                                    or len(text_without_mark.strip()) == 0
                                ):
                                    continue

                                cleaned_text = (
                                    text_without_mark.replace("\r", "")
                                    .replace("\n", "")
                                    .replace("\r\n", "")
                                )

                                cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()

                                if (
                                    cleaned_text
                                    and len(cleaned_text) > 0
                                    and cleaned_text != text_without_mark
                                ):
                                    para_rng.Text = cleaned_text + "\r"
                                    cleaned_count += 1
                                    insertion_log_parts.append(
                                        f"    已清理: {cleaned_text[:50]}..."
                                    )
                                elif cleaned_text and len(cleaned_text) > 0:
                                    pass
                                else:
                                    if len(cleaned_text) == 0:
                                        paras_to_delete.append(para_rng)
                                        insertion_log_parts.append(
                                            f"    标记删除（清理后为空）: '{para_text[:50]}...'"
                                        )
                            except Exception as e:
                                insertion_log_parts.append(
                                    f"    警告: 无法清理段落 '{para_text[:50]}...': {e}"
                                )

                    if paras_to_delete:
                        insertion_log_parts.append(
                            f"  删除清理后变空的段落 {len(paras_to_delete)} 个..."
                        )
                        for para_rng in reversed(paras_to_delete):
                            try:
                                para_rng.Delete()
                            except Exception as e:
                                insertion_log_parts.append(
                                    f"    警告: 无法删除段落: {e}"
                                )

                    insertion_log_parts.append(
                        f"  步骤5.2完成：清理 {cleaned_count} 段，删除 {len(paras_to_delete)} 个空段。"
                    )

                    # 最终轮：再次检查是否有剩余的空段落
                    insertion_log_parts.append("  步骤5.3：最终检查剩余空段落...")
                    selection.GoTo(wdGoToPage, wdGoToAbsolute, target_page)
                    page_start_final = selection.Start
                    selection.GoTo(wdGoToPage, wdGoToAbsolute, next_page)
                    page_end_final = (
                        selection.Start
                        if selection.Information(wdActiveEndPageNumber) == next_page
                        else doc.Content.End
                    )
                    page_rng_final = doc.Range(page_start_final, page_end_final)

                    final_empty_deleted = 0
                    paras_final = list(page_rng_final.Paragraphs)
                    for i in range(len(paras_final) - 1, -1, -1):
                        try:
                            para = paras_final[i]

                            if para.Range.Information(wdWithInTable):
                                continue

                            is_protected = is_protected_range(para.Range)

                            if not is_protected:
                                raw_text = para.Range.Text
                                raw_text_no_mark = raw_text.rstrip("\r\n")
                                raw_cleaned = (
                                    raw_text_no_mark.replace("\r", "")
                                    .replace("\n", "")
                                    .replace(" ", "")
                                    .replace("\t", "")
                                    .replace("\u00a0", "")
                                    .strip()
                                )

                                if len(raw_cleaned) == 0:
                                    try:
                                        para.Range.Delete()
                                        final_empty_deleted += 1
                                    except Exception:
                                        pass
                        except Exception:
                            pass

                    if final_empty_deleted > 0:
                        insertion_log_parts.append(
                            f"  步骤5.3完成：删除剩余空段 {final_empty_deleted} 个。"
                        )
                    else:
                        insertion_log_parts.append("  步骤5.3完成：未发现剩余空段。")

                # 步骤5.4：清理插入区间内表格尾部的空白行
                try:

                    def _visible_text(s: str) -> str:
                        if not s:
                            return ""
                        return (
                            s.replace("\r", "")
                            .replace("\n", "")
                            .replace("\x07", "")
                            .replace("\x0b", "")
                            .replace("\x0c", "")
                            .replace("\a", "")
                            .replace(" ", "")
                            .replace("\t", "")
                            .replace("\u00a0", "")
                            .replace("\u3000", "")
                            .replace("\u2000", "")
                            .replace("\u2001", "")
                            .replace("\u2002", "")
                            .replace("\u2003", "")
                            .replace("\u2004", "")
                            .replace("\u2005", "")
                            .replace("\u2006", "")
                            .replace("\u2007", "")
                            .replace("\u2008", "")
                            .replace("\u2009", "")
                            .replace("\u200a", "")
                            .replace("\u200b", "")
                            .replace("\ufeff", "")
                            .strip()
                        )

                    def _row_is_empty(row) -> bool:
                        try:
                            cells = row.Cells
                            for c in range(1, cells.Count + 1):
                                try:
                                    txt = cells(c).Range.Text
                                except Exception:
                                    txt = ""
                                if _visible_text(txt):
                                    return False
                            return True
                        except Exception:
                            return False

                    def _trim_table_trailing_empty_rows(tbl) -> int:
                        removed = 0
                        try:
                            for r in range(tbl.Rows.Count, 0, -1):
                                try:
                                    row = tbl.Rows(r)
                                    if _row_is_empty(row):
                                        row.Delete()
                                        removed += 1
                                    else:
                                        break
                                except Exception:
                                    break
                        except Exception:
                            return removed
                        return removed

                    bound_start = int(insertion_bound_start)
                    bound_end = int(get_insertion_bound_end())
                    tbl_rng = doc.Range(bound_start, bound_end)
                    tables = tbl_rng.Tables
                    trimmed_tables = 0
                    trimmed_rows_total = 0
                    deleted_empty_tables = 0

                    for t_idx in range(tables.Count, 0, -1):
                        try:
                            tbl = tables(t_idx)
                            removed_rows = _trim_table_trailing_empty_rows(tbl)
                            if removed_rows > 0:
                                trimmed_tables += 1
                                trimmed_rows_total += removed_rows

                            try:
                                cleaned_tbl_text = _visible_text(tbl.Range.Text)
                            except Exception:
                                cleaned_tbl_text = "x"
                            if not cleaned_tbl_text:
                                tbl.Range.Delete()
                                deleted_empty_tables += 1
                        except Exception:
                            continue

                    if trimmed_tables > 0 or deleted_empty_tables > 0:
                        insertion_log_parts.append(
                            f"  步骤5.4完成：修剪表格 {trimmed_tables} 个，删除尾部空行 {trimmed_rows_total} 行，删除空表格 {deleted_empty_tables} 个。"
                        )
                except Exception:
                    pass

                if use_direct_replace:
                    insertion_log_parts.append(
                        "步骤5完成：gjgk 已跳过 legacy 文本清理，仅执行边界内表格修剪。"
                    )
                else:
                    insertion_log_parts.append(
                        "步骤5完成：已清理可编辑内容中的空段落与多余换行。"
                    )
                insertion_log_parts.append("内容处理成功。")

                # 步骤6：根据 polished_comments 插入批注
                polished_comments = state.get("polished_comments") or []
                if polished_comments:
                    insertion_log_parts.append(
                        "步骤6：根据 polished_comments 插入批注..."
                    )
                    bound_start = int(insertion_bound_start)
                    bound_end = int(get_insertion_bound_end())

                    def _ranges_overlap(
                        a_start: int, a_end: int, b_start: int, b_end: int
                    ) -> bool:
                        return not (a_end <= b_start or b_end <= a_start)

                    def _has_comment_on_range(target_rng) -> bool:
                        try:
                            comments = doc.Comments
                        except Exception:
                            return False
                        try:
                            count = comments.Count
                        except Exception:
                            return False
                        for i in range(1, count + 1):
                            try:
                                c = comments(i)
                            except Exception:
                                continue
                            c_rng = None
                            for attr in ("Scope", "Reference", "Range"):
                                try:
                                    c_rng = getattr(c, attr)
                                except Exception:
                                    c_rng = None
                                if c_rng is not None:
                                    break
                            if c_rng is None:
                                continue
                            try:
                                cs = int(c_rng.Start)
                                ce = int(c_rng.End)
                                ts = int(target_rng.Start)
                                te = int(target_rng.End)
                            except Exception:
                                continue
                            if _ranges_overlap(cs, ce, ts, te):
                                return True
                        return False

                    last_used_end_by_ref = {}
                    comments_added = 0

                    for idx, instr in enumerate(polished_comments):
                        ref_text = (instr.get("reference_text") or "").strip()
                        comment_text = (instr.get("comment_text") or "").strip()
                        if not ref_text or not comment_text:
                            continue

                        search_texts = [ref_text]
                        if "\n" in ref_text:
                            search_texts.append(ref_text.replace("\n", "\r"))

                        inserted_here = False
                        for find_text in search_texts:
                            cur_start = int(
                                last_used_end_by_ref.get(ref_text, bound_start)
                            )
                            while cur_start < bound_end:
                                find_rng = doc.Range(cur_start, bound_end)
                                finder = find_rng.Find
                                finder.ClearFormatting()
                                finder.Text = find_text
                                finder.Forward = True
                                finder.Wrap = wdFindStop
                                finder.MatchCase = False
                                finder.MatchWholeWord = False

                                if not finder.Execute():
                                    break

                                try:
                                    match_start = int(find_rng.Start)
                                    match_end = int(find_rng.End)
                                except Exception:
                                    break

                                if _has_comment_on_range(find_rng):
                                    insertion_log_parts.append(
                                        f"  批注 [{idx + 1}] 位置已存在批注，继续向后查找 reference_text={ref_text[:40]}..."
                                    )
                                    cur_start = max(match_end, cur_start + 1)
                                    continue

                                try:
                                    doc.Comments.Add(
                                        Range=find_rng.Duplicate, Text=comment_text
                                    )
                                    comments_added += 1
                                    last_used_end_by_ref[ref_text] = match_end
                                    insertion_log_parts.append(
                                        f"  批注 [{idx + 1}] 已添加: reference_text={ref_text[:40]}... -> comment_text={comment_text[:40]}..."
                                    )
                                    inserted_here = True
                                except Exception as comment_e:
                                    insertion_log_parts.append(
                                        f"  批注 [{idx + 1}] 添加失败 (reference_text={ref_text[:40]}...): {comment_e}"
                                    )
                                break

                            if inserted_here:
                                break

                        if not inserted_here:
                            insertion_log_parts.append(
                                f"  批注 [{idx + 1}] 未找到可插入的位置或未匹配到引用文本: {ref_text[:50]}..."
                            )

                    insertion_log_parts.append(
                        f"步骤6完成：成功添加 {comments_added}/{len(polished_comments)} 条批注。"
                    )
                else:
                    insertion_log_parts.append(
                        "步骤6：无 polished_comments，跳过批注插入。"
                    )

            doc.Save()
            insertion_log_parts.append("文档已保存。")

        except Exception as e:
            error_msg = f"Word 处理过程中出错: {e}"
            insertion_log_parts.append(error_msg)
            raise
        finally:
            close_word_application(
                word_app=word,
                doc=doc,
                com_initialized=com_initialized,
                wait_time=0.0,
                node_name="update_word",
            )

    except Exception as e:
        error_msg = f"初始化 Word COM 时出错: {e}"
        insertion_log_parts.append(error_msg)
        raise

    # 使用插入日志更新状态
    new_state_dict = dict(state)
    insertion_log = "; ".join(insertion_log_parts)
    new_state_dict["insertion_log"] = insertion_log
    new_state = TenderGraphStateBase(**new_state_dict)

    try:
        print("[update_word] 插入日志:")
        for line in insertion_log_parts:
            print(f"[update_word] {line}")
    except Exception:
        pass

    duration = time.perf_counter() - start_time
    duration_ms = duration * 1000
    print(f"[update_word] 执行完成，耗时: {duration:.2f} 秒 ({duration_ms:.0f} 毫秒)")
    return new_state


def _build_manual_gjgk_test_text() -> str:
    return """一、设备名称及数量：ERCP专用X线透视摄影系统/壹套
二、交货日期：
1、中华人民共和国关境外交付的货物：信用证开立后30天内
2、中华人民共和国关境内交付的货物：合同签订后30天内
3、若因招标人原因（包括但不限于机房不具备装机条件、免税办理时效等情况），造成在前述交货期内不具备收货条件，从而导致交货延迟的，则交货期应顺延至收货条件完备后，但不得晚于招标人出具的书面交货通知后30天内。
三、交货地点：上海市第六人民医院临港院区
四、主要技术规格及系统概述：
| 1 | 设备用途 |
| --- | --- |
| 1.1 | 基本功能：适用于胃肠造影、DR摄影、ERCP、妇产科子宫输卵管造影、呼吸科支气管镜穿刺活检、泌尿科介入检查以及全身外周介入治疗等。 |
| 2 | 配置要求 |
| 2.1 | X线球管及控制系统 |
| 2.2 | 平板成像系统 |
| 2.3 | 床及机械臂运动系统 |
| 2.4 | 数字化图像采集系统 |
| 2.5 | 图像处理功能 |
| 2.6 | ERCP专用配置功能 |
| 2.7 | 内镜专业用显视器及吊架 |
| 2.8 | 高频手术系统 |
| 2.9 | 超声诊断设备 |
| 2.10 | 双频探头 |
| 3 | 技术参数要求 |
| 3.1 | X线球管及控制系统 |
| 3.1.1 | 最大管电流：≥1000mA |
| 3.1.2 | 最大管电压：≥120kV |
| 3.1.3 | 具备全自动控制，具有管电压自动适应功能 |
| 3.1.4 | 具备双焦点球管:微焦点≤0.4 ，较小焦点≤1.0mm |
| ★3.1.5 | 具备栅控球管 |
| ★3.1.6 | 阳极热容量≥1000kHU |
| 3.1.7 | 最短曝光时间≤1ms |
| 3.1.8 | 具备脉冲透视，最低脉冲频率≤1fps |
| 3.1.9 | 剂量调整过滤器≥2种金属 |
| 3.1.10 | 高压发生器功率≥80kW |
| ★3.1.11 | 球管类型为下球管 |
| 3.2 | 平板成像系统 |
| ★3.2.1 | 平板尺寸≥40×40 cm |
| 3.2.2 | 可变视野≥4种 |
| ★3.2.3 | 平板像素尺寸≤150 µm |
| 3.2.4 | DQE（量子检出率）≥60% |
| 3.2.5 | 平板为CsI（非晶硅）材质结构 |
| 3.3 | 床及机械臂运动系统 |
| ★3.3.1 | 要求可倾斜床面遥控检查床，床面可升降，采用低吸收剂量的高强度碳纤维床板，检查床与设备一体化。 |
| ★3.3.2 | 床面倾倒范围≥110° |
| 3.3.3 | 床面横向移动范围≥30cm |
| 3.3.4 | 床面和球管相对纵向移动范围≥110cm |
| 3.3.5 | 诊断床面可升降，距地面最低高度≤60cm |
| 3.3.6 | 可调SID（X线焦点到影像接收器距离)，可调范围≥30cm |
| 3.3.7 | 具有密度补偿滤过片 |
| 3.3.8 | 具备落地式C臂结构 |
| ★3.3.8.1 | 机械臂旋转范围：RAO（右前斜位）≥90°，LAO（左前斜位）≥45° |
| 3.3.8.2 | 机械臂旋转范围：CRA（头位）/CAU（足位）≥45°/45° |
| 3.4 | 数字化图像采集系统 |
| 3.4.1 | 最大数字采集分辨率≥2560×2560，16bit |
| 3.4.2 | 数模转换≥14bit |
| 3.4.3 | 具备1024×1024矩阵连续摄片，采集速度≥15fps |
| 3.4.4 | 能控制设备机械运动功能，拍片、透视等功能 |
| 3.4.5 | 具有医用单色LCD监视器 |
| 3.4.6 | 图像传输网络：具有DICOM接口功能 |
| 3.4.7 | 隔室图像监视器两台，≥19英寸液晶显示器（≥1248×1024） |
| 3.5 | 图像处理功能 |
| 3.5.1 | 动态采集图像在回放时，可进行；空间滤过功能；窗宽窗位调整功能；自动窗口功能；正反像切换功能；漫游放大图像旋转功能；电子光圈处理功能；文字标注，比例尺显示，测量功能，箭头指示功能；散射校正，对比强化功能；同一视野可多幅显示图像 ≥36幅（6×6） |
| 3.5.2 | 采集图像电影回放：回放速度任意可调1 fps~7.5 fps |
| 3.5.3 | 具备血管直径，病变大小测量等功能 |
| 3.5.4 | 具备数字滤过补偿功能：实时透视时候调整图像质量，可以使图像过黑或者过白区域的图像得以重建。 |
| 3.5.5 | 具备降噪软件功能:实时图像处理技术和低剂量技术，提供高画质的同时降低球管发射剂量。 |
| 3.6 | ERCP专用配置功能 |
| 3.6.1 | 具备床侧端防护帘。 |
| 3.6.2 | 具备带平板防护屏。 |
| 3.6.3 | 具备ERCP专用图像优化协议系统 |
| 3.6.4 | 具有床旁透视/摄影双功能脚闸 |
| 3.6.5 | 具备床旁智能操作手柄 |
| 3.7 | 内镜专业用显视器及吊架 |
| 3.7.1 | 具备手术室内镜专用监视器大小≥55寸 |
| 3.7.2 | 分辨率≥3840×2160 ，色深10 bit |
| 3.7.3 | 亮度≥1200 cd/m² |
| 3.7.4 | 对比度≥500000：1 |
| 3.7.5 | 响应时间≤5 ms |
| 3.7.6 | 可拓展视频输入接口≥7路HDMI |
| 3.7.7 | 支持单画面，PIP，PBP，三画面以及四画面显示 |
| 3.7.8 | 显示器吊架承重≥30kg |
| 3.8 | 高频手术系统 |
| 3.8.1 | 单极切割模式：1. 切割模式≥6种<br>2．要求有内镜专用切割模式即ENDO CUT IQ,分别适用于内镜下十二指肠乳头切开和息肉切除。 |
| 3.8.2 | 低电压设计：单极凝血最高电压≤4300V |
| 3.8.3 | 单极电凝功率：0~120W可调 |
| 3.8.4 | 单极电凝模式：≥3种，1．柔和电凝；2．强力电凝；3．快速电凝 |
| 3.8.5 | 双极切割功率：0~120W功率可调 |
| 3.8.6 | 双极凝血控制模式：≥2种，1．脚踏开关控制；2．自动启动； |
| 3.8.7 | 双极射频消融模式：1.脚踏开关控制；2.可兼容射频消融导管，适用于恶性胆道梗阻的消融。 |
| 3.8.8 | 具备开机自检功能 |
| 3.8.9 | 具备最小功率输出控制系统和功率峰值补偿系统 |
| 3.8.10 | 具备中性电极安全监测系统 |
| 3.8.11 | 具备输出错误监测系统 |
| 3.8.12 | 具备时间限制检测系统 |
| 3.8.13 | 具备错误代码储存功能 |
| 3.8.14 | 具备程序存储和程序控制功能 |
| 3.9 | 超声诊断设备 |
| 3.9.1 | 成像模式：B模式 |
| ★3.9.2 | 产品形态：一体便携式 |
| 3.9.3 | 图像旋转：在图像冻结状态下，支持360°任意方向、角度旋转 |
| ★3.9.4 | 图像回放：可实现≥1000帧图像回放。图像回放帧数直接影响动态影像的连续性，较高的帧数可更精准捕捉病变的实时动态特征，为提升诊断准确性、降低漏诊风险并辅助术中精准定位与评估，图像回放帧数越高越好 |
| 3.9.5 | 图像标注：在图像冻结状态下，支持在图像上进行箭头和文字标注操作，单幅图像≥26组 |
| 3.9.6 | 长度测量：在图像冻结状态下，支持单幅图像上两点之间长度测量≥26组，通过多维度采样显著提升病变范围量化精度，降低单次测量误差导致的误判风险，为精准分期、手术规划及疗效评估提供统计学支持 |
| ★3.9.7 | 面积和周长测量：在图像冻结状态下，支持单幅图像上周长和面积测量数据≥26组，多维度的数据帮助医生精准诊断病情、制定个性化治疗方案、评估治疗效果、赋能教学与科研等 |
| 3.9.8 | TGC分段增益：支持≥8段TGC明暗调节功能，每段1-20档超声图像增益可调 |
| 3.9.9 | 对比度：支持1-8档超声图像对比度可调，通过多层级灰度区分强化组织界面辨识度 |
| 3.9.10 | 画中画：支持超声图像和内镜图像的同屏同步同尺寸实时显示 |
| 3.9.11 | 超声图像支持灰阶图、伪彩图，增加对灰阶超声图像的视觉分辨率，有效减少黏膜早期癌变的漏诊 |
| 3.9.12 | 4B模式：支持4幅图像同时显示，每幅图像均可独立进行切帧显示 |
| 3.9.13 | 局部放大：支持图像局部放大，呈现更清晰的组织细节 |
| 3.9.14 | 内置存储硬盘≥1TB，支持存储手术视频录像，方便术后复查及病例追溯 |
| 3.9.15 | 患者检查信息管理：支持对患者检查信息库进行检索、查看、编辑、保存、 预览、报告打印 |
| 3.9.16 | 数据接口：传输协议支持USB2.0、USB 3.0、TCP/IP、DIC0M协议；存储格式支持BMP、PNG、JPG、TIFF、Run（AVI、WMV）、DICOMDIR等格式，视频输出支持HDMI、SDI、DP、S-Video、CVBS等多种模式 |
| 3.9.17 | 记录回放原始数据：支持记录和回放采集到的超声原始数据，可在离线模式下使用范围调节、对比度调节、TGC调节、标注、测量功能 |
| 3.9.18 | 快速标记：可以设置并使用自定义按键，在图像上可快速进行标识，并支持标识编辑 |
| ★3.9.19 | 支持一键切换两种探头频率，不用更换探头，完成“从表及里”的全面评估满足对消化道肿瘤精准的分期诊断 |
| ★3.9.20 | 内置可充电锂离子电池，充满最长待机90分钟 |
| ★3.9.21 | 兼容性：兼容消化、变频消化、小肠、胆胰、变频胆胰探头，满足多场景应用需求 |
| ★3.9.22 | 主机使用年限应≥10年 |
| 3.10 | 双频探头 |
| 3.10.1 | 工作频率：12MHz+20MHz，支持两个频率一键切换 |
| 3.10.2 | 图像几何畸变：≤10% |
| 3.10.3 | 扫描角度：环形360° |
| 3.10.4 | 工作长度：2100mm±10% |
| 3.10.5 | 探头先端部外径：≤2.0mm |
| 4 | 售后服务要求 |
| 4.1 | 供应商负责设备到货搬运和安装就位，并提供详细的验收标准、验收手册（由此产生的费用由供应商承担）。 |
| ★4.2 | 整机保修期≥60个月，保修期自设备安装调试使用验收合格后起算。软件终身免费升级。 |
| 4.3 | 维修及服务响应时间：对采购人的售后服务要求应在2小时内响应，工程师于24小时内到达现场给出解决方案。 |
| 4.4 | 在保质期内出现问题所产生的维修费用（包括零部件费用、运返费用等费用）均由供应商承担，保修期外维修免收人工费、差旅费。 |
| 4.5 | 技术培训：供应商应免费对采购人操作、维修人员进行一定时期的正规的整套设备操作、维护保养、检测等内容的技术培训。 |
| 4.6 | 质量保证：供应商按配置要求，提供原装全新设备，确保其产品品质、性能及技术参数要求达到采购人的要求；否则采购人有权向供应商提出更换。 |

一、设备名称及数量：内镜主机/贰套
二、交货日期：
1、中华人民共和国关境外交付的货物：信用证开立后30天内
2、中华人民共和国关境内交付的货物：合同签订后30天内
3、若因招标人原因（包括但不限于机房不具备装机条件、免税办理时效等情况），造成在前述交货期内不具备收货条件，从而导致交货延迟的，则交货期应顺延至收货条件完备后，但不得晚于招标人出具的书面交货通知后30天内。
三、交货地点：上海市第六人民医院临港院区
四、主要技术规格及系统概述：
| 1 | 设备用途 |
| --- | --- |
| 1.1 | 用于消化道检查与治疗 |
| 2 | 配置要求 |
| 2.1 | 内窥镜主机×2台 |
| 2.2 | 液晶医用监视器×2台 |
| 3 | 技术参数要求 |
| 3.1 | 内窥镜主机 |
| 3.1.1 | HDTV信号输出模式：16：9和16：10，并可兼容HDTV监视器。可支持模拟、HD-SDI和DVI信号输出 |
| 3.1.2 | 具备自动白平衡调节 |
| ★3.1.3 | 具备窄带成像功能，用于早期癌的诊断 |
| ★3.1.4 | 具备双红光观察模式 |
| ★3.1.5 | 具备荧光观察模式 |
| 3.1.6 | 观察模式：对色调、构造和亮度进行联合强调 |
| 3.1.7 | 色调调节：红色调节≥±8档，蓝色调节≥±8档，色度调节≥±8档 |
| 3.1.8 | 具备增益自动控制 |
| 3.1.9 | 具备画中画功能 |
| 3.1.10 | 可兼容便携式存储器，并可简单连接及上传数据 |
| 3.1.11 | 可以设定图像对比度 |
| 3.1.12 | 测光模式：平均测光、峰值测光、全自动测光 |
| 3.1.13 | 具备图像强调设定功能：电子强调内镜图像的细微形态或轮廓来提高图像锐度。<br>构造强调A：强调内镜图像的细微形态和轮廓<br>构造强调B：比构造强调A强调更精细的部分 |
| 3.1.14 | 具备图像大小选择功能：可以改变内镜图像的大小 |
| 3.1.15 | 具备快速实时冻结功能：可以从按下冻结键之前的图像中挑选色差最小的图像显示出来 |
| 3.1.16 | 患者数据输入功能：可以在术前输入患者的数据≤50名 |
| 3.1.17 | 具备内镜信息记忆功能：存储在内镜记忆芯片中的与内镜相关的数据可以调用并显示在屏幕上 |
| 3.1.18 | 具备自定义按钮功能，给以下按钮分配指定功能：内镜遥控按钮≥5个，脚踏开关≥2个，键盘自定义按钮≥4个 |
| 3.1.19 | 电子放大：即使不使用放大内镜，也能够进行电子放大观察 |
| 3.1.20 | 设定存储：图像处理中心关闭后，设定仍可被存储 |
| ★3.1.21 | LED光源：≥5色 |
| 3.1.22 | LED光源和图像处理装置集成一体化设计 |
| 3.2 | 液晶医用监视器 |
| 3.2.1 | 液晶面板：高清晰度电视（HDTV）显示 |
| 3.2.2 | 屏幕尺寸：≥31.5英寸 |
| 3.2.3 | 视角：垂直≥170°，水平≥170° |
| 3.2.4 | 分辨率：≥3840×2160高分辨率 |
| 3.2.5 | 显示设备：TFT有效矩阵 |
| 3.2.6 | 输出信号格式：≥2种，具备12G-SDI、DVI-D等 |
| 4 | 售后服务要求 |
| 4.1 | 供应商负责设备到货搬运和安装就位，并提供详细的验收标准、验收手册（由此产生的费用由供应商承担）。 |
| ★4.2 | 整机保修期≥36个月，保修期自设备安装调试使用验收合格后起算。软件终身免费升级。 |
| 4.3 | 维修及服务响应时间：对采购人的售后服务要求应在2小时内响应，工程师于24小时内到达现场给出解决方案。 |
| 4.4 | 在保质期内出现问题所产生的维修费用（包括零部件费用、运返费用等费用）均由供应商承担，保修期外维修免收人工费、差旅费。 |
| 4.5 | 技术培训：供应商应免费对采购人操作、维修人员进行一定时期的正规的整套设备操作、维护保养、检测等内容的技术培训。 |
| 4.6 | 质量保证：供应商按配置要求，提供原装全新设备，确保其产品品质、性能及技术参数要求达到采购人的要求；否则采购人有权向供应商提出更换。 |"""


def main() -> None:
    """本地调试 gjgk update_word：复制样本 -> 删除正文区间 -> 用硬编码文本回填。"""

    from backend.nodes.common_word_nodes.delete_tender_param import delete_tender_param

    print("=" * 80)
    print("开始测试 update_word 节点 (gjgk)")
    print("=" * 80)

    tender_type = "gjgk"
    source_doc_path = (
        BACKEND_ROOT / "test_doc" / "254DSITC2512-招标文件-发售稿-财政模板.doc"
    )
    before_text, after_text = get_default_anchor_texts(tender_type)
    test_doc_path = source_doc_path.with_name(
        f"{source_doc_path.stem}-update-word-test{source_doc_path.suffix}"
    )
    polished_text = _build_manual_gjgk_test_text()

    if not source_doc_path.exists():
        print(f"错误: 测试文件不存在: {source_doc_path}")
        raise SystemExit(1)

    shutil.copy2(source_doc_path, test_doc_path)

    print(f"测试类型: {tender_type} (国际公开)")
    print(f"源文件: {source_doc_path}")
    print(f"测试副本: {test_doc_path}")
    print(f"前置锚点: {before_text}")
    print(f"后置锚点: {after_text}")
    print(f"回填文本长度: {len(polished_text)}")
    print()

    test_state: TenderGraphStateBase = {
        "tender_type": tender_type,
        "prepared_doc_path": str(test_doc_path),
        "insertion_before_text": before_text,
        "insertion_after_text": after_text,
    }

    try:
        print("步骤1/2: 先执行 delete_tender_param 清理锚点区间")
        print("-" * 80)
        cleared_state = delete_tender_param(test_state, config=None)
        print("-" * 80)
        print()

        cleared_state = dict(cleared_state)
        cleared_state["polished_text"] = polished_text
        cleared_state["polished_comments"] = []

        print("步骤2/2: 执行 update_word 回填硬编码文本")
        print("-" * 80)
        result_state = update_word(cleared_state, config=None)
        print("-" * 80)
        print()

        print("✅ update_word 调试执行完成")
        print(f"结果文件: {test_doc_path}")
        insertion_log = result_state.get("insertion_log") or ""
        if insertion_log:
            print()
            print("插入日志摘要:")
            for part in str(insertion_log).split("; "):
                print(f"  - {part}")
    except Exception as exc:
        print()
        print("❌ update_word 调试失败")
        print(f"错误信息: {exc}")
        import traceback

        print()
        print("详细错误堆栈:")
        traceback.print_exc()
        raise SystemExit(1) from exc

    print()
    print("=" * 80)
    print("测试完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
