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
import sys

# 添加仓库根目录到 sys.path，便于直接运行当前脚本进行本地调试
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.states import TenderGraphStateBase
from backend.nodes.common_word_nodes.comment_writeback import write_polished_comments
from backend.config.tender_config import (
    get_anchor_target_sizes,
    get_protected_field_profile,
)
from backend.util.word_util import (
    create_word_application,
    close_word_application,
    open_document_with_retry,
    unprotect_document,
    WORD_MANUAL_LINE_BREAK,
    normalize_word_insert_text,
)
from backend.util.word_util import (
    wdGoToPage,
    wdGoToAbsolute,
    wdLineSpace1pt5,
    wdOutlineLevelBodyText,
    wdCollapseStart,
    wdCollapseEnd,
    wdActiveEndPageNumber,
    wdWithInTable,
)
from backend.util.word_util.anchor_utils import (
    find_anchor_range,
    resolve_anchor_content_range,
)
from backend.util.log_util.progress_log import progress_log

from backend.helper.word_helper.range_utils import (
    is_locked_exception,
    find_editable_insertion_pos,
    find_next_editable_pos,
    find_next_editable_pos_bounded,
    find_prev_editable_pos,
    ensure_editable_insert_range,
)
from backend.helper.word_helper.text_parsing import (
    parse_table_block,
    convert_lines_to_items,
    split_text_by_keywords,
)
from backend.helper.word_helper.protected_fields import (
    collect_profile_protected_fields,
    refresh_profile_protected_fields,
    normalize_protected_field_paragraphs,
    resolve_block_flow,
    refind_protected_paragraph,
    insert_prefix_before_keyword,
    update_protected_field,
)
from backend.helper.word_helper.content_ops import (
    apply_standard_insert_format,
    insert_content_with_formatting,
    insert_table_with_formatting,
    insert_items_inline_at_end_of_paragraph,
)
from backend.helper.word_helper.cleanup_ops import (
    multi_pass_cleanup,
    normalize_cleanup_text,
)
from backend.helper.word_helper.inline_style_ops import (
    apply_inline_style_fragments,
    summarize_style_writeback_result,
)


COMMON_TWO_FIELD_PROFILE = get_protected_field_profile("xjcg")
DELIVERY_DATE_MARKER, PAYMENT_METHOD_MARKER = (
    COMMON_TWO_FIELD_PROFILE.ordered_markers
)


def split_polished_text_into_blocks(
    polished_text: str,
    *,
    profile=COMMON_TWO_FIELD_PROFILE,
) -> Dict[str, Any]:
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
    delivery_marker, payment_marker = profile.ordered_markers
    split_data = split_text_by_keywords(
        polished_text,
        profile.ordered_markers,
        strip_empty_lines=True,
        require_all=profile.require_all,
        require_order=profile.require_order,
    )
    content_list = split_data["content_list"]
    keyword_lines = split_data["keyword_lines"]
    keyword_parsed = split_data["keyword_parsed"]
    blocks = split_data["blocks"]

    delivery_date_line = keyword_lines[delivery_marker]
    payment_method_line = keyword_lines[payment_marker]
    delivery_prefix = str(keyword_parsed[delivery_marker].get("prefix") or "")
    delivery_value = keyword_parsed[delivery_marker].get("value")
    payment_prefix = str(keyword_parsed[payment_marker].get("prefix") or "")
    payment_value = keyword_parsed[payment_marker].get("value")

    block1 = blocks[0] if len(blocks) > 0 else []
    block2 = blocks[1] if len(blocks) > 1 else []
    block3 = blocks[2] if len(blocks) > 2 else []

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


# ---- 向后兼容别名 ----
# gngk_fw_zc_update_word 之前从本文件 import _parse_table_block / _apply_standard_insert_format；
# 重构后已迁移到 helper，保留别名。
_parse_table_block = parse_table_block
_apply_standard_insert_format = apply_standard_insert_format


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
    protected_profile = get_protected_field_profile(str(tender_type or "xjcg"))

    if not prepared_doc_path:
        raise ValueError("需要 prepared_doc_path 来插入内容到 Word 文档")
    if not polished_text:
        raise ValueError("需要 polished_text 来插入内容到 Word 文档")
    if not insertion_before_text or not insertion_after_text:
        raise ValueError(
            "insertion_before_text 和 insertion_after_text 必须提供，用于定位插入范围"
        )

    before_size, after_size = get_anchor_target_sizes(str(tender_type or "xjcg"))

    split_result = split_polished_text_into_blocks(
        polished_text,
        profile=protected_profile,
    )
    content_list = split_result["content_list"]

    insertion_log_parts = []
    word = None
    doc = None
    com_initialized = False

    # Default comment writeback tracking (overwritten if write_polished_comments runs)
    comment_writeback_summary = ""
    comment_writeback_added = 0
    comment_writeback_failed = 0
    comment_writeback_skipped = 0
    comment_writeback_errors = []
    style_writeback_summary = ""
    style_writeback_result = None

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

            def get_insertion_bound_end() -> int:
                try:
                    return int(after_anchor_marker.Start)
                except Exception:
                    return int(insertion_bound_end)

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
                protected_markers = list(protected_profile.ordered_markers)
                target_range = (int(page_start), int(page_end))
                fallback_range = (
                    int(insertion_bound_start),
                    int(get_insertion_bound_end()),
                )
                insertion_log_parts.append(
                    "步骤1：定位关键受保护字段..."
                    f" 目标页={target_page}({target_range[0]}-{target_range[1]})，"
                    f" 边界范围={fallback_range[0]}-{fallback_range[1]}"
                )
                normalized_marker_count = normalize_protected_field_paragraphs(
                    doc,
                    protected_markers,
                    target_range[0],
                    fallback_range[1],
                    log_parts=insertion_log_parts,
                )
                if normalized_marker_count > 0:
                    insertion_log_parts.append(
                        f"  已预规范化受保护字段冒号 {normalized_marker_count} 处。"
                    )

                protected_fields = collect_profile_protected_fields(
                    doc=doc,
                    profile=protected_profile,
                    target_range=target_range,
                    fallback_range=fallback_range,
                )
                if not protected_fields:
                    insertion_log_parts.append(
                        "  未在目标范围内找到受保护字段，将按可编辑边界继续插入。"
                    )
                else:
                    for marker, para_rng in protected_fields.items():
                        insertion_log_parts.append(
                            f"  找到受保护字段: {marker} ({int(para_rng.Start)}-{int(para_rng.End)})"
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
                insertion_log_parts.append("步骤2：按字段拆分内容块...")

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

                def refind_field(marker: str):
                    return refind_protected_paragraph(
                        doc=doc,
                        marker=marker,
                        bound_start=int(insertion_bound_start),
                        bound_end=int(get_insertion_bound_end()),
                    )

                # 删除阶段可能补回段落边界，这里先整体重绑一次字段位置，
                # 后续块插入仍按最新段落范围操作。
                refreshed_marker_count = normalize_protected_field_paragraphs(
                    doc,
                    protected_markers,
                    int(insertion_bound_start),
                    int(get_insertion_bound_end()),
                    log_parts=insertion_log_parts,
                )
                if refreshed_marker_count > 0:
                    insertion_log_parts.append(
                        f"  重绑前再次规范化受保护字段冒号 {refreshed_marker_count} 处。"
                    )
                protected_fields = refresh_profile_protected_fields(
                    doc=doc,
                    profile=protected_profile,
                    range_start=int(insertion_bound_start),
                    range_end=int(get_insertion_bound_end()),
                    existing_fields=protected_fields,
                )
                if protected_fields:
                    for marker, para_rng in protected_fields.items():
                        insertion_log_parts.append(
                            f"  重定位受保护字段: {marker} ({int(para_rng.Start)}-{int(para_rng.End)})"
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

                def insert_content_with_formatting(insert_range, line):
                    ensure_editable_insert_range(insert_range)
                    start_pos = insert_range.End
                    insert_range.InsertAfter(normalize_word_insert_text(line) + "\r")
                    end_pos = insert_range.End
                    inserted_rng = doc.Range(start_pos, end_pos - 1)

                    inserted_rng.Font.Name = insert_font_name
                    inserted_rng.Font.Size = insert_font_size
                    inserted_rng.ParagraphFormat.LineSpacingRule = wdLineSpace1pt5
                    inserted_rng.ParagraphFormat.LeftIndent = 0
                    inserted_rng.ParagraphFormat.FirstLineIndent = 0
                    inserted_rng.ParagraphFormat.OutlineLevel = wdOutlineLevelBodyText

                    inserted_rng.Font.Bold = False

                    insert_range.Collapse(wdCollapseEnd)
                    return inserted_rng

                def insert_table_with_formatting(insert_range, rows):
                    if not rows:
                        return None

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
                                cell_text = normalize_word_insert_text(
                                    cell_text, break_char="\r"
                                )
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
                        insert_range.SetRange(table.Range.End, table.Range.End)
                    except Exception:
                        insert_range.Collapse(wdCollapseEnd)
                        insert_range.Start = table.Range.End
                        insert_range.End = table.Range.End
                    insert_range.Collapse(wdCollapseEnd)
                    return table

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
                            s = WORD_MANUAL_LINE_BREAK + normalize_word_insert_text(
                                item["line"]
                            )
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
                                    s = WORD_MANUAL_LINE_BREAK + normalize_word_insert_text(
                                        " | ".join(row)
                                    )
                                    st = int(rng.Start)
                                    rng.InsertAfter(s)
                                    rng.Collapse(wdCollapseEnd)
                                    inserted += 1
                    return inserted

                flow = resolve_block_flow(protected_fields)

                # 插入块1（始终执行，优先在交付日期前，否则回退到目标页起始可编辑位置）
                insertion_log_parts.append("  正在插入块1...")
                selection.GoTo(wdGoToPage, wdGoToAbsolute, target_page)
                insert_rng = selection.Range
                insert_rng.Collapse(wdCollapseStart)

                if flow["has_delivery"]:
                    delivery_date_rng = protected_fields[DELIVERY_DATE_MARKER]
                    before_pos = int(delivery_date_rng.Start)
                    safe_before = find_prev_editable_pos(before_pos, max_lookback=20000)
                    if safe_before is None:
                        safe_before = find_editable_insertion_pos(
                            int(page_start_after), max_lookahead=20000
                        )
                    insert_rng.SetRange(safe_before, safe_before)
                    insert_rng.Collapse(wdCollapseStart)

                block1_items = convert_lines_to_items(block1)
                for item in block1_items:
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

                if flow["has_delivery"]:
                    insert_prefix_before_keyword(DELIVERY_DATE_MARKER, delivery_prefix)
                    protected_fields[DELIVERY_DATE_MARKER] = (
                        refind_field(DELIVERY_DATE_MARKER)
                        or protected_fields[DELIVERY_DATE_MARKER]
                    )
                    update_protected_field(DELIVERY_DATE_MARKER, delivery_value)

                    # 插入块2（与 master 对齐：双字段时插中间，仅交付日期时插其后）
                    insertion_log_parts.append("  插入块2...")
                    if flow["block2_mode"] == "between_delivery_payment":
                        delivery_date_rng = protected_fields[DELIVERY_DATE_MARKER]
                        protected_fields[PAYMENT_METHOD_MARKER] = (
                            refind_field(PAYMENT_METHOD_MARKER)
                            or protected_fields[PAYMENT_METHOD_MARKER]
                        )
                        payment_method_rng = protected_fields[PAYMENT_METHOD_MARKER]

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
                        delivery_date_rng = protected_fields[DELIVERY_DATE_MARKER]
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
                        insert_prefix_before_keyword(PAYMENT_METHOD_MARKER, payment_prefix)
                        protected_fields[PAYMENT_METHOD_MARKER] = (
                            refind_field(PAYMENT_METHOD_MARKER)
                            or protected_fields[PAYMENT_METHOD_MARKER]
                        )
                        update_protected_field(PAYMENT_METHOD_MARKER, payment_value)

                # 插入块3（有付款方式则插其后，否则回退到后置锚点前）
                block3_items = convert_lines_to_items(block3)
                insertion_log_parts.append(f"  插入块3（{len(block3_items)} 条）...")
                if len(block3_items) == 0:
                    insertion_log_parts.append("    警告：块3为空，无需插入")
                else:
                    insertion_log_parts.append(
                        f"    块3内容: "
                        f"{[item['line'][:30] + '...' if item['type'] == 'text' and len(item['line']) > 30 else item['line'] if item['type'] == 'text' else '<表格>' for item in block3_items]}"
                    )

                if (
                    flow["block3_anchor"] == "after_payment"
                    and PAYMENT_METHOD_MARKER in protected_fields
                ):
                    protected_fields[PAYMENT_METHOD_MARKER] = (
                        refind_field(PAYMENT_METHOD_MARKER)
                        or protected_fields[PAYMENT_METHOD_MARKER]
                    )
                    payment_method_rng = protected_fields[PAYMENT_METHOD_MARKER]
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
                if use_inline and PAYMENT_METHOD_MARKER in protected_fields:
                    insertion_log_parts.append(
                        "    块3将以内联换行追加到付款方式段落末尾"
                    )
                    inserted_count = insert_items_inline_at_end_of_paragraph(
                        protected_fields[PAYMENT_METHOD_MARKER], block3_items
                    )
                else:
                    for item in block3_items:
                        attempts = 0
                        while attempts < 80:
                            attempts += 1
                            try:
                                ensure_editable_insert_range(insert_rng)
                                if item["type"] == "text":
                                    inserted_rng = insert_content_with_formatting(
                                        insert_rng, item["line"]
                                    )
                                    inserted_count += 1
                                    insertion_log_parts.append(
                                        f"    [{inserted_count}/{len(block3_items)}] 已插入: {item['line'][:50]}..."
                                    )
                                    break
                                elif item["type"] == "table":
                                    insert_table_with_formatting(insert_rng, item["rows"])
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

                insertion_log_parts.append(
                    "步骤5完成：已清理可编辑内容中的空段落与多余换行。"
                )
                insertion_log_parts.append("内容处理成功。")

                comment_step_label = "步骤6"
                if "inline_style_fragments" in state:
                    style_writeback_result = apply_inline_style_fragments(
                        doc=doc,
                        inline_style_fragments=state.get("inline_style_fragments"),
                        bound_start=int(insertion_bound_start),
                        bound_end=int(get_insertion_bound_end()),
                        log_parts=insertion_log_parts,
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
                    bound_start=int(insertion_bound_start),
                    bound_end=int(get_insertion_bound_end()),
                    log_parts=insertion_log_parts,
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
    new_state_dict["comment_writeback_summary"] = comment_writeback_summary
    new_state_dict["comment_writeback_added"] = comment_writeback_added
    new_state_dict["comment_writeback_failed"] = comment_writeback_failed
    new_state_dict["comment_writeback_skipped"] = comment_writeback_skipped
    new_state_dict["comment_writeback_errors"] = comment_writeback_errors
    new_state_dict["style_writeback_summary"] = style_writeback_summary
    new_state_dict["style_writeback_result"] = style_writeback_result
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
