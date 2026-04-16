"""
国内公开（服务 / 自筹）Word 文档更新节点。

保留 common `update_word` 的 Word / 锁 / 批注回写 / 保存边界，
仅把 `gngk_fw_zc` 的服务三字段保护与四段插入顺序特化到本模块。
"""

from __future__ import annotations

import pathlib
import re
import shutil
import stat
import sys
import time
from typing import Any, Dict, Optional

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config.tender_config import (
    get_anchor_target_sizes,
    get_default_anchor_texts,
    get_protected_field_profile,
)
from backend.nodes.common_word_nodes.comment_writeback import write_polished_comments
from backend.helper.word_helper.protected_fields import (
    collect_profile_protected_fields,
    refresh_profile_protected_fields,
    normalize_protected_field_paragraphs,
    refind_protected_paragraph,
    insert_prefix_before_keyword,
    update_protected_field,
)
from backend.helper.word_helper.range_utils import (
    is_range_locked,
    is_locked_exception,
    range_overlaps,
    is_protected_range,
    find_editable_insertion_pos,
    find_next_editable_pos,
    find_next_editable_pos_bounded,
    find_prev_editable_pos,
    find_prev_editable_pos_bounded,
    ensure_editable_insert_range,
)
from backend.helper.word_helper.text_parsing import (
    parse_table_block,
    convert_lines_to_items,
    split_text_by_keywords,
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
    is_effectively_empty_text,
    row_is_empty,
    trim_table_trailing_empty_rows,
)
from backend.helper.word_helper.inline_style_ops import (
    apply_inline_style_fragments,
    summarize_style_writeback_result,
)
from backend.states import TenderGraphStateBase
from backend.util.log_util.progress_log import progress_log
from backend.util.word_util import (
    WORD_MANUAL_LINE_BREAK,
    close_word_application,
    create_word_application,
    normalize_word_insert_text,
    open_document_with_retry,
    unprotect_document,
    wdActiveEndPageNumber,
    wdCollapseEnd,
    wdCollapseStart,
    wdGoToAbsolute,
    wdGoToPage,
    wdLineSpace1pt5,
    wdOutlineLevelBodyText,
    wdWithInTable,
)
from backend.util.word_util.anchor_utils import (
    find_anchor_range,
    resolve_anchor_content_range,
)


GNGK_THREE_FIELD_PROFILE = get_protected_field_profile("gngk_fw_zc")
SERVICE_LOCATION_MARKER, SERVICE_TERM_MARKER, PAYMENT_METHOD_MARKER = (
    GNGK_THREE_FIELD_PROFILE.ordered_markers
)
NODE_NAME = "gngk_fw_zc_update_word"
DEFAULT_MANUAL_TEST_SOURCE_DOC = (
    BACKEND_ROOT
    / "test_doc"
    / "复旦大学附属华山医院虹桥院区VRV空调和分体式空调维护保养251498-招标文件-发售稿.doc"
)
DEFAULT_MANUAL_TEST_SUFFIX = "-gngk-fw-zc-update-test"
MANUAL_TEST_INSERT_TEXT = """一、项目概述
1、项目名称：复旦大学附属华山医院院本部1号楼急诊改扩建区域风机盘管空气过滤器更换及设备保养
2、服务地点：复旦大学附属华山医院院本部1号楼急诊改扩建区域
3、服务期限：2026年6月16日-2029年6月15日
4、付款方式：
11)前三季度维保费用的支付方式遵循季度结算原则。即甲方需按每季度（每三个月）一次的频率向乙方支付相应的维保服务费用。
2)最后一季度付款：年度维保工作结束后第三个月，经过甲方的考核评估，甲方向乙方支付相应的维保服务费用。
3)每次付款前，乙方的服务质量须经过甲方的考核评估。只有在满足合同约定的服务标准时，甲方方才承担支付当期维保费用的责任。
4)在考核过程中，若发现乙方存在违约或未达到约定服务标准的情形，甲方有权根据合同中规定的考核说明，对应付款项进行相应扣减。
5)扣款的具体数额及条件应详细列明于合同中的《维保项目管理考核表》章节中的考核说明，并以此为依据执行。任何扣款必须符合该等条款的规定，并且乙方应提前得到通知，明确扣款的原因及金额。
6)所有扣款处理应在当季度维保费用支付前完成，以确保支付金额的准确性。
7)甲方应于每次考核合格确认后的30个工作日内，将扣除相应扣款后的维保费用支付给乙方。
四、服务内容及要求
1、投标人需提供具体维保方案、维修方案、应急预案
2、基础维保内容包括但不限于：
| 序号 | 检 查 项 目 |
| --- | --- |
| 01 | 检查或清洗室内机盘管翅片 |
| 02 | 测量风速、温度 |
| 03 | 检查空调电脑板、除尘 |
| 04 | 检查各接线柱螺栓是否收紧 |
| 05 | 检查各接线插片、插头、插座是否牢固 |
| 06 | 检查空调机组运行高、低压力 |
| 07 | 检测控制箱，除垢处理 |
| 08 | 检查空调机组的运行电流 |
| 09 | 检查风机盘管的电动执行阀机构状况 |
| 10 | 检查风机盘管的水过滤器通过性 |
| 11 | 检查风机盘管的冷凝水排水是否畅通 |
| 12 | 检插或更换空调各易损件 |
| 13 | 温度传感器性能定期巡检及功能检查 |
| 14 | 检查线控器、遥控器 |"""


def _validate_block_window(range_start: int, range_end: int, *, label: str) -> None:
    if int(range_end) < int(range_start):
        raise ValueError(f"{label}字段区间非法，停止以避免错误插入")


def _resolve_block4_insert_start(payment_end: int, bound_end: int) -> int:
    payment_end = int(payment_end)
    bound_end = int(bound_end)
    if payment_end > bound_end:
        raise ValueError("付款方式字段位置超出插入边界，停止以避免侵入后置章节")
    return min(payment_end, bound_end)


def split_polished_text_into_blocks(
    polished_text: str,
    *,
    profile=GNGK_THREE_FIELD_PROFILE,
) -> Dict[str, Any]:
    """
    将 `gngk_fw_zc` 的 polished_text 按服务三字段拆成四个块。

    顺序固定为：
    block1 -> 服务地点 -> block2 -> 服务期限 -> block3 -> 付款方式 -> block4
    """

    if not str(polished_text or "").strip():
        raise ValueError("polished_text 为空，无法拆分服务三字段内容")

    service_location_marker, service_term_marker, payment_method_marker = (
        profile.ordered_markers
    )
    try:
        split_data = split_text_by_keywords(
            polished_text,
            profile.ordered_markers,
            strip_empty_lines=True,
            require_all=profile.require_all,
            require_order=profile.require_order,
        )
    except ValueError as error:
        message = str(error)
        if "关键字段顺序错误" in message:
            raise ValueError(
                "polished_text 中关键字段顺序必须为 服务地点： -> 服务期限： -> 付款方式："
            ) from None
        raise

    content_list = split_data["content_list"]
    keyword_lines = split_data["keyword_lines"]
    keyword_parsed = split_data["keyword_parsed"]
    blocks = split_data["blocks"]

    service_location_line = keyword_lines[service_location_marker]
    service_term_line = keyword_lines[service_term_marker]
    payment_method_line = keyword_lines[payment_method_marker]

    service_location_prefix = str(keyword_parsed[service_location_marker].get("prefix") or "")
    service_location_value = keyword_parsed[service_location_marker].get("value")
    service_term_prefix = str(keyword_parsed[service_term_marker].get("prefix") or "")
    service_term_value = keyword_parsed[service_term_marker].get("value")
    payment_prefix = str(keyword_parsed[payment_method_marker].get("prefix") or "")
    payment_value = keyword_parsed[payment_method_marker].get("value")

    return {
        "content_list": content_list,
        "service_location_line": service_location_line,
        "service_term_line": service_term_line,
        "payment_method_line": payment_method_line,
        "service_location_prefix": service_location_prefix,
        "service_location_value": service_location_value,
        "service_term_prefix": service_term_prefix,
        "service_term_value": service_term_value,
        "payment_prefix": payment_prefix,
        "payment_value": payment_value,
        "block1": blocks[0] if len(blocks) > 0 else [],
        "block2": blocks[1] if len(blocks) > 1 else [],
        "block3": blocks[2] if len(blocks) > 2 else [],
        "block4": blocks[3] if len(blocks) > 3 else [],
    }


def _convert_lines_to_items(lines: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        maybe_table, next_index = parse_table_block(lines, index)
        if maybe_table:
            items.append({"type": "table", "rows": maybe_table})
            index = next_index
        else:
            items.append({"type": "text", "line": lines[index]})
            index += 1
    return items


def gngk_fw_zc_update_word(
    state: TenderGraphStateBase, config
) -> TenderGraphStateBase:
    start_time = time.perf_counter()

    print("[update_word] 开始执行...")

    prepared_doc_path = state.get("prepared_doc_path")
    polished_text = state.get("polished_text")
    insertion_before_text = state.get("insertion_before_text")
    insertion_after_text = state.get("insertion_after_text")
    tender_type = state.get("tender_type", "gngk_fw_zc")
    protected_profile = get_protected_field_profile(str(tender_type or "gngk_fw_zc"))

    if not prepared_doc_path:
        raise ValueError("需要 prepared_doc_path 来插入内容到 Word 文档")
    if not polished_text:
        raise ValueError("需要 polished_text 来插入内容到 Word 文档")
    if not insertion_before_text or not insertion_after_text:
        raise ValueError(
            "insertion_before_text 和 insertion_after_text 必须提供，用于定位插入范围"
        )

    before_size, after_size = get_anchor_target_sizes(str(tender_type or "gngk_fw_zc"))
    split_result = split_polished_text_into_blocks(
        polished_text,
        profile=protected_profile,
    )

    insertion_log_parts: list[str] = []
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
        word, com_initialized = create_word_application(
            initial_delay=0.0,
            post_init_delay=1.0,
            use_existing=False,
            verify=False,
            node_name="update_word",
        )

        try:
            doc = open_document_with_retry(
                word_app=word,
                file_path=prepared_doc_path,
                read_only=False,
                node_name="update_word",
            )
            insertion_log_parts.append(f"已打开文档: {prepared_doc_path}")

            if unprotect_document(doc, node_name="update_word"):
                insertion_log_parts.append("已取消文档保护")

            insertion_log_parts.append(
                f"查找锚点（前置字号: {before_size}, 后置字号: {after_size}）..."
            )
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
                tender_type=str(tender_type or "gngk_fw_zc"),
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

            try:
                region_text = doc.Range(insertion_bound_start, insertion_bound_end).Text
                if re.search(r"第[一二三四五六七八九十0-9]+章", region_text):
                    raise ValueError("锚点之间检测到章节标题，停止插入以避免侵入其他章节")
            except Exception as region_error:
                if isinstance(region_error, ValueError):
                    raise

            selection = word.Selection
            target_page = start_page
            insertion_log_parts.append(f"处理目标页 {target_page}")

            selection.GoTo(wdGoToPage, wdGoToAbsolute, target_page)
            page_start = selection.Start
            page_start_page = selection.Information(wdActiveEndPageNumber)

            next_page = target_page + 1
            selection.GoTo(wdGoToPage, wdGoToAbsolute, next_page)
            page_end = selection.Start
            page_end_page = selection.Information(wdActiveEndPageNumber)

            if page_start_page != target_page or page_end == page_start:
                page_end = doc.Content.End
            elif page_end_page != next_page:
                page_end = doc.Content.End

            if page_end <= page_start:
                raise ValueError(f"目标页 {target_page} 范围为空，无法定位受保护字段")

            if page_end > page_start:
                protected_markers = list(protected_profile.ordered_markers)
                target_range = (int(page_start), int(page_end))
                fallback_range = (
                    int(insertion_bound_start),
                    int(get_insertion_bound_end()),
                )
                insertion_log_parts.append(
                    "步骤1：定位服务三字段..."
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
                        f"  已预规范化服务三字段冒号 {normalized_marker_count} 处。"
                    )

                protected_fields = collect_profile_protected_fields(
                    doc=doc,
                    profile=protected_profile,
                    target_range=target_range,
                    fallback_range=fallback_range,
                )
                for marker, para_rng in protected_fields.items():
                    insertion_log_parts.append(
                        f"  找到受保护字段: {marker} ({int(para_rng.Start)}-{int(para_rng.End)})"
                    )

                def range_overlaps(
                    a_start: int, a_end: int, b_start: int, b_end: int
                ) -> bool:
                    return not (a_end <= b_start or b_end <= a_start)

                def is_protected_range(rng) -> bool:
                    try:
                        range_start = int(rng.Start)
                        range_end = int(rng.End)
                    except Exception:
                        return False
                    for protected_range in protected_fields.values():
                        try:
                            protected_start = int(protected_range.Start)
                            protected_end = int(protected_range.End)
                        except Exception:
                            continue
                        if range_overlaps(
                            range_start,
                            range_end,
                            protected_start,
                            protected_end,
                        ):
                            return True
                    return False

                service_location_prefix = split_result["service_location_prefix"]
                service_location_value = split_result["service_location_value"]
                service_term_prefix = split_result["service_term_prefix"]
                service_term_value = split_result["service_term_value"]
                payment_prefix = split_result["payment_prefix"]
                payment_value = split_result["payment_value"]
                block1 = split_result["block1"]
                block2 = split_result["block2"]
                block3 = split_result["block3"]
                block4 = split_result["block4"]

                insertion_log_parts.append("步骤2：按服务三字段拆分内容块...")
                insertion_log_parts.append(f"  块1: {len(block1)} 条（服务地点之前）")
                insertion_log_parts.append(f"  块2: {len(block2)} 条（服务地点与服务期限之间）")
                insertion_log_parts.append(f"  块3: {len(block3)} 条（服务期限与付款方式之间）")
                insertion_log_parts.append(f"  块4: {len(block4)} 条（付款方式之后）")
                if service_location_prefix.strip():
                    insertion_log_parts.append(
                        f"  服务地点前缀: {service_location_prefix.strip()}"
                    )
                if service_term_prefix.strip():
                    insertion_log_parts.append(
                        f"  服务期限前缀: {service_term_prefix.strip()}"
                    )
                if payment_prefix.strip():
                    insertion_log_parts.append(
                        f"  付款方式前缀: {payment_prefix.strip()}"
                    )

                insertion_log_parts.append("步骤3：按服务三字段顺序插入内容...")

                def refind_field(marker: str):
                    return refind_protected_paragraph(
                        doc=doc,
                        marker=marker,
                        bound_start=int(insertion_bound_start),
                        bound_end=int(get_insertion_bound_end()),
                    )

                refreshed_marker_count = normalize_protected_field_paragraphs(
                    doc,
                    protected_markers,
                    int(insertion_bound_start),
                    int(get_insertion_bound_end()),
                    log_parts=insertion_log_parts,
                )
                if refreshed_marker_count > 0:
                    insertion_log_parts.append(
                        f"  重绑前再次规范化服务三字段冒号 {refreshed_marker_count} 处。"
                    )
                protected_fields = refresh_profile_protected_fields(
                    doc=doc,
                    profile=protected_profile,
                    range_start=int(insertion_bound_start),
                    range_end=int(get_insertion_bound_end()),
                    existing_fields=protected_fields,
                )
                for marker, para_rng in protected_fields.items():
                    insertion_log_parts.append(
                        f"  重定位受保护字段: {marker} ({int(para_rng.Start)}-{int(para_rng.End)})"
                    )

                def is_range_locked(rng) -> bool:
                    try:
                        if hasattr(rng, "Locked") and rng.Locked:
                            return True
                    except Exception:
                        pass

                    try:
                        fields = rng.Fields
                        for field_index in range(1, fields.Count + 1):
                            try:
                                field = fields(field_index)
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
                    except Exception as probe_error:
                        error_message = str(probe_error).lower()
                        if "锁定" in error_message or "locked" in error_message or "-2146823683" in error_message:
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
                        paragraphs = scan_rng.Paragraphs
                        for paragraph_index in range(
                            1, min(paragraphs.Count, max_paragraphs) + 1
                        ):
                            try:
                                paragraph_range = paragraphs(paragraph_index).Range
                                candidate = max(int(paragraph_range.Start), start)
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
                    start_pos: int,
                    bound_end: int,
                    max_lookahead: int = 4000,
                ) -> Optional[int]:
                    doc_end = int(doc.Content.End)
                    start = int(min(max(0, start_pos), doc_end))
                    end = int(min(max(0, bound_end), doc_end))
                    if end < start:
                        return None
                    pos = start
                    lookahead = min(max_lookahead, end - start)
                    for _ in range(lookahead + 1):
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

                def find_prev_editable_pos_bounded(
                    before_pos: int,
                    bound_start: int,
                    max_lookback: int = 4000,
                ) -> Optional[int]:
                    doc_end = int(doc.Content.End)
                    pos = int(min(max(0, before_pos), doc_end))
                    lower_bound = int(min(max(0, bound_start), doc_end))
                    lookback = min(max_lookback, max(0, pos - lower_bound))
                    for _ in range(lookback + 1):
                        try:
                            if not is_range_locked(doc.Range(pos, pos)):
                                return pos
                        except Exception:
                            pass
                        if pos <= lower_bound:
                            break
                        pos -= 1
                    return None

                def is_locked_exception(error: Exception) -> bool:
                    error_message = str(error).lower()
                    return (
                        "锁定" in error_message
                        or "locked" in error_message
                        or "-2146823683" in error_message
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
                            next_pos = find_next_editable_pos_bounded(
                                pos + 1, bound_end, max_lookahead=20000
                            )
                            if next_pos is not None and next_pos > pos:
                                insert_range.SetRange(next_pos, next_pos)
                                insert_range.Collapse(wdCollapseStart)
                    except Exception:
                        pass

                insert_font_name = "宋体"
                insert_font_size = 12

                def insert_content_with_formatting(insert_range, line: str):
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

                    cols = max(len(row) for row in rows)
                    start_pos = insert_range.End
                    table_range = doc.Range(start_pos, start_pos)
                    table = doc.Tables.Add(table_range, len(rows), cols)
                    try:
                        table.Borders.Enable = True
                    except Exception:
                        pass

                    for row_index, row in enumerate(rows):
                        for column_index, value in enumerate(row):
                            try:
                                cell = table.Cell(row_index + 1, column_index + 1)
                                cell_range = cell.Range
                                if cell_range.End > cell_range.Start + 1:
                                    delete_range = doc.Range(
                                        cell_range.Start,
                                        cell_range.End - 1,
                                    )
                                    delete_range.Delete()

                                cell_range = cell.Range
                                cell_text = "" if value is None else str(value)
                                cell_text = normalize_word_insert_text(
                                    cell_text, break_char="\r"
                                )
                                cell_range.InsertBefore(cell_text)

                                cell_range = cell.Range
                                apply_standard_insert_format(
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

                def insert_items(
                    insert_range,
                    items: list[dict[str, Any]],
                    *,
                    label: str,
                ) -> None:
                    for item in items:
                        try:
                            if item["type"] == "text":
                                insert_content_with_formatting(insert_range, item["line"])
                                insertion_log_parts.append(
                                    f"    {label} 已插入: {item['line'][:50]}..."
                                )
                            elif item["type"] == "table":
                                insert_table_with_formatting(insert_range, item["rows"])
                                insertion_log_parts.append(
                                    f"    {label} 已插入表格，行数 {len(item['rows'])}。"
                                )
                        except Exception as error:
                            insertion_log_parts.append(f"    {label} 插入项出错: {error}")

                def insert_prefix_before_keyword(keyword: str, prefix: str) -> bool:
                    if not prefix or not prefix.strip():
                        return True
                    if keyword not in protected_fields:
                        return False
                    try:
                        para_rng = protected_fields[keyword]
                        para_text = para_rng.Text
                        keyword_index = para_text.find(keyword)
                        if keyword_index < 0:
                            return False
                        before_keyword = para_text[:keyword_index].replace("\r", "").replace("\a", "")
                        prefix_clean = prefix.replace("\r", "").replace("\n", "")
                        if before_keyword.endswith(prefix_clean):
                            return True
                        insert_pos = para_rng.Start + keyword_index
                        doc.Range(insert_pos, insert_pos).InsertBefore(prefix_clean)
                        return True
                    except Exception as error:
                        insertion_log_parts.append(
                            f"  警告: 插入前缀失败 '{keyword}': {error}"
                        )
                        return False

                def update_protected_field(keyword: str, new_value: Optional[str]) -> bool:
                    if keyword not in protected_fields:
                        return False
                    if new_value is None:
                        return True

                    try:
                        para_rng = protected_fields[keyword]
                        para_text = para_rng.Text
                        keyword_index = para_text.find(keyword)
                        if keyword_index < 0:
                            return False

                        colon_pos = para_text.find("：", keyword_index + len(keyword))
                        if colon_pos < 0:
                            colon_pos = para_text.find(":", keyword_index + len(keyword))

                        if colon_pos >= 0:
                            value_start = para_rng.Start + colon_pos + 1
                        else:
                            value_start = para_rng.Start + keyword_index + len(keyword)

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
                    except Exception as error:
                        insertion_log_parts.append(f"  警告: 无法更新 '{keyword}': {error}")
                        return False

                def insert_items_inline_at_end_of_paragraph(para_rng, items) -> int:
                    try:
                        para_text = para_rng.Text
                        trim = 0
                        while para_text.endswith("\r") or para_text.endswith("\a"):
                            para_text = para_text[:-1]
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
                    inserted_count = 0
                    for item in items:
                        if item["type"] == "text":
                            insert_text = WORD_MANUAL_LINE_BREAK + normalize_word_insert_text(
                                item["line"]
                            )
                            start = int(rng.Start)
                            rng.InsertAfter(insert_text)
                            end = int(rng.End)
                            try:
                                inserted_rng = doc.Range(start, end)
                                inserted_rng.Font.Name = insert_font_name
                                inserted_rng.Font.Size = insert_font_size
                                inserted_rng.Font.Bold = False
                            except Exception:
                                pass
                            rng.Collapse(wdCollapseEnd)
                            inserted_count += 1
                        elif item["type"] == "table":
                            try:
                                insert_table_with_formatting(rng, item["rows"])
                                inserted_count += 1
                            except Exception as error:
                                insertion_log_parts.append(
                                    f"    警告: 内联插入表格失败，改为文本: {error}"
                                )
                                for row in item["rows"]:
                                    insert_text = WORD_MANUAL_LINE_BREAK + normalize_word_insert_text(
                                        " | ".join(row)
                                    )
                                    rng.InsertAfter(insert_text)
                                    rng.Collapse(wdCollapseEnd)
                                    inserted_count += 1
                    return inserted_count

                insert_rng = selection.Range
                insert_rng.Collapse(wdCollapseStart)

                block1_items = _convert_lines_to_items(block1)
                insertion_log_parts.append("  正在插入块1...")
                if block1_items:
                    service_location_rng = protected_fields[SERVICE_LOCATION_MARKER]
                    safe_before = find_prev_editable_pos_bounded(
                        int(service_location_rng.Start),
                        int(insertion_bound_start),
                        max_lookback=20000,
                    )
                    if safe_before is None:
                        raise ValueError("块1在服务地点字段前未找到可编辑插入点")
                    insert_rng.SetRange(safe_before, safe_before)
                    insert_rng.Collapse(wdCollapseStart)
                    insert_items(
                        insert_rng,
                        block1_items,
                        label="块1",
                    )
                else:
                    insertion_log_parts.append("    块1为空，跳过")

                insert_prefix_before_keyword(SERVICE_LOCATION_MARKER, service_location_prefix)
                protected_fields[SERVICE_LOCATION_MARKER] = (
                    refind_field(SERVICE_LOCATION_MARKER)
                    or protected_fields[SERVICE_LOCATION_MARKER]
                )
                update_protected_field(SERVICE_LOCATION_MARKER, service_location_value)

                block2_items = _convert_lines_to_items(block2)
                insertion_log_parts.append("  正在插入块2...")
                protected_fields[SERVICE_LOCATION_MARKER] = (
                    refind_field(SERVICE_LOCATION_MARKER)
                    or protected_fields[SERVICE_LOCATION_MARKER]
                )
                protected_fields[SERVICE_TERM_MARKER] = (
                    refind_field(SERVICE_TERM_MARKER)
                    or protected_fields[SERVICE_TERM_MARKER]
                )
                start_between = int(protected_fields[SERVICE_LOCATION_MARKER].End)
                end_between = int(protected_fields[SERVICE_TERM_MARKER].Start)
                _validate_block_window(
                    start_between,
                    end_between,
                    label="服务地点与服务期限之间",
                )

                if block2_items:
                    safe_between = find_next_editable_pos_bounded(
                        start_between, end_between, max_lookahead=20000
                    )
                    if safe_between is None:
                        raise ValueError("块2在服务地点与服务期限字段之间未找到可编辑插入点")
                    insert_rng.SetRange(safe_between, safe_between)
                    insert_rng.Collapse(wdCollapseStart)
                    insert_items(
                        insert_rng,
                        block2_items,
                        label="块2",
                    )
                else:
                    insertion_log_parts.append("    块2为空，跳过")

                insert_prefix_before_keyword(SERVICE_TERM_MARKER, service_term_prefix)
                protected_fields[SERVICE_TERM_MARKER] = (
                    refind_field(SERVICE_TERM_MARKER)
                    or protected_fields[SERVICE_TERM_MARKER]
                )
                update_protected_field(SERVICE_TERM_MARKER, service_term_value)

                block3_items = _convert_lines_to_items(block3)
                insertion_log_parts.append("  正在插入块3...")
                protected_fields[SERVICE_TERM_MARKER] = (
                    refind_field(SERVICE_TERM_MARKER)
                    or protected_fields[SERVICE_TERM_MARKER]
                )
                protected_fields[PAYMENT_METHOD_MARKER] = (
                    refind_field(PAYMENT_METHOD_MARKER)
                    or protected_fields[PAYMENT_METHOD_MARKER]
                )
                start_between = int(protected_fields[SERVICE_TERM_MARKER].End)
                end_between = int(protected_fields[PAYMENT_METHOD_MARKER].Start)
                _validate_block_window(
                    start_between,
                    end_between,
                    label="服务期限与付款方式之间",
                )

                if block3_items:
                    safe_between = find_next_editable_pos_bounded(
                        start_between, end_between, max_lookahead=20000
                    )
                    if safe_between is None:
                        raise ValueError("块3在服务期限与付款方式字段之间未找到可编辑插入点")
                    insert_rng.SetRange(safe_between, safe_between)
                    insert_rng.Collapse(wdCollapseStart)
                    insert_items(
                        insert_rng,
                        block3_items,
                        label="块3",
                    )
                else:
                    insertion_log_parts.append("    块3为空，跳过")

                insert_prefix_before_keyword(PAYMENT_METHOD_MARKER, payment_prefix)
                protected_fields[PAYMENT_METHOD_MARKER] = (
                    refind_field(PAYMENT_METHOD_MARKER)
                    or protected_fields[PAYMENT_METHOD_MARKER]
                )
                update_protected_field(PAYMENT_METHOD_MARKER, payment_value)

                block4_items = _convert_lines_to_items(block4)
                insertion_log_parts.append(f"  插入块4（{len(block4_items)} 条）...")
                if len(block4_items) == 0:
                    insertion_log_parts.append("    提示：块4为空，无需插入")
                else:
                    insertion_log_parts.append(
                        "    块4内容: "
                        f"{[item['line'][:30] + '...' if item['type'] == 'text' and len(item['line']) > 30 else item['line'] if item['type'] == 'text' else '<表格>' for item in block4_items]}"
                    )

                protected_fields[PAYMENT_METHOD_MARKER] = (
                    refind_field(PAYMENT_METHOD_MARKER)
                    or protected_fields[PAYMENT_METHOD_MARKER]
                )
                payment_method_rng = protected_fields[PAYMENT_METHOD_MARKER]
                bound_end_now = int(get_insertion_bound_end())
                start_after_payment = _resolve_block4_insert_start(
                    int(payment_method_rng.End),
                    bound_end_now,
                )
                safe_pos = None
                use_inline = False
                if block4_items:
                    safe_pos = find_next_editable_pos_bounded(
                        start_after_payment,
                        bound_end_now,
                        max_lookahead=20000,
                    )
                    if safe_pos is None:
                        use_inline = True
                        insertion_log_parts.append(
                            "    块4在付款方式字段后未找到独立可编辑插入点，改用段落末尾内联插入"
                        )
                    else:
                        insert_rng.Start = min(max(0, safe_pos), doc.Content.End)
                        insert_rng.End = insert_rng.Start
                        insert_rng.Collapse(wdCollapseStart)
                        insertion_log_parts.append(
                            f"    在付款方式字段后插入，位置 {insert_rng.Start}"
                        )
                        try:
                            if is_range_locked(
                                doc.Range(int(insert_rng.Start), int(insert_rng.Start))
                            ):
                                use_inline = True
                        except Exception:
                            pass
                else:
                    insertion_log_parts.append("    块4为空，跳过")

                inserted_count = 0
                if block4_items and use_inline and PAYMENT_METHOD_MARKER in protected_fields:
                    insertion_log_parts.append(
                        "    块4将以内联换行追加到付款方式段落末尾"
                    )
                    inserted_count = insert_items_inline_at_end_of_paragraph(
                        protected_fields[PAYMENT_METHOD_MARKER], block4_items
                    )
                elif block4_items:
                    for item in block4_items:
                        attempts = 0
                        while attempts < 80:
                            attempts += 1
                            try:
                                ensure_editable_insert_range(insert_rng)
                                if item["type"] == "text":
                                    insert_content_with_formatting(insert_rng, item["line"])
                                    inserted_count += 1
                                    insertion_log_parts.append(
                                        f"    [{inserted_count}/{len(block4_items)}] 已插入: {item['line'][:50]}..."
                                    )
                                    break
                                if item["type"] == "table":
                                    insert_table_with_formatting(insert_rng, item["rows"])
                                    inserted_count += 1
                                    insertion_log_parts.append(
                                        f"    [{inserted_count}/{len(block4_items)}] 已插入表格，行数 {len(item['rows'])}。"
                                    )
                                    break
                            except Exception as error:
                                if is_locked_exception(error):
                                    try:
                                        current_pos = int(insert_rng.Start)
                                    except Exception:
                                        current_pos = 0
                                    next_pos = find_next_editable_pos_bounded(
                                        current_pos + 1,
                                        int(get_insertion_bound_end()),
                                        max_lookahead=20000,
                                    )
                                    if next_pos is None or next_pos <= current_pos:
                                        insertion_log_parts.append(f"    插入项出错: {error}")
                                        break
                                    try:
                                        insert_rng.SetRange(next_pos, next_pos)
                                        insert_rng.Collapse(wdCollapseStart)
                                        continue
                                    except Exception:
                                        insertion_log_parts.append(f"    插入项出错: {error}")
                                        break
                                insertion_log_parts.append(f"    插入项出错: {error}")
                                break

                insertion_log_parts.append(
                    f"  块4插入完成: {inserted_count}/{len(block4_items)} 条。"
                )

                insertion_log_parts.append("步骤4：清理空段落与换行...")

                def build_cleanup_range():
                    return doc.Range(
                        int(insertion_bound_start),
                        int(get_insertion_bound_end()),
                    )

                max_passes = 5
                total_empty_deleted = 0

                for pass_num in range(1, max_passes + 1):
                    insertion_log_parts.append(
                        f"  步骤4.1 第 {pass_num} 轮：删除空段落..."
                    )

                    empty_deleted = 0
                    final_paragraphs = list(build_cleanup_range().Paragraphs)
                    for index in range(len(final_paragraphs) - 1, -1, -1):
                        try:
                            paragraph = final_paragraphs[index]
                            if paragraph.Range.Information(wdWithInTable):
                                continue

                            if is_protected_range(paragraph.Range):
                                continue

                            if is_effectively_empty_text(paragraph.Range.Text):
                                paragraph.Range.Delete()
                                empty_deleted += 1
                                insertion_log_parts.append(f"    删除空段落，索引 {index}")
                        except Exception as error:
                            insertion_log_parts.append(f"    处理第 {index} 段出错: {error}")

                    total_empty_deleted += empty_deleted
                    insertion_log_parts.append(
                        f"  第 {pass_num} 轮完成：删除空段 {empty_deleted} 个。"
                    )

                    if empty_deleted == 0:
                        insertion_log_parts.append(
                            f"  未再发现空段，第 {pass_num} 轮后停止。"
                        )
                        break

                    insertion_log_parts.append("  步骤4.2：清理可编辑段落中的换行...")

                    cleaned_count = 0
                    paragraphs_to_delete = []

                    for paragraph in build_cleanup_range().Paragraphs:
                        if paragraph.Range.Information(wdWithInTable):
                            continue

                        paragraph_text = paragraph.Range.Text
                        if is_effectively_empty_text(paragraph_text):
                            continue

                        if is_protected_range(paragraph.Range):
                            continue

                        try:
                            paragraph_range = paragraph.Range
                            full_text = paragraph_range.Text
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
                                r"[\t\u00a0\u2000-\u200b\u3000]+",
                                " ",
                                cleaned_text,
                            )
                            cleaned_text = re.sub(r" {2,}", " ", cleaned_text).strip()

                            if cleaned_text and cleaned_text != text_without_mark:
                                paragraph_range.Text = cleaned_text + "\r"
                                cleaned_count += 1
                                insertion_log_parts.append(
                                    f"    已清理: {cleaned_text[:50]}..."
                                )
                            elif not cleaned_text:
                                paragraphs_to_delete.append(paragraph_range)
                                insertion_log_parts.append(
                                    f"    标记删除（清理后为空）: '{paragraph_text[:50]}...'"
                                )
                        except Exception as error:
                            insertion_log_parts.append(
                                f"    警告: 无法清理段落 '{paragraph_text[:50]}...': {error}"
                            )

                    if paragraphs_to_delete:
                        insertion_log_parts.append(
                            f"  删除清理后变空的段落 {len(paragraphs_to_delete)} 个..."
                        )
                        for paragraph_range in reversed(paragraphs_to_delete):
                            try:
                                paragraph_range.Delete()
                            except Exception as error:
                                insertion_log_parts.append(f"    警告: 无法删除段落: {error}")

                    insertion_log_parts.append(
                        f"  步骤4.2完成：清理 {cleaned_count} 段，删除 {len(paragraphs_to_delete)} 个空段。"
                    )

                    insertion_log_parts.append("  步骤4.3：最终检查剩余空段落...")

                    final_empty_deleted = 0
                    final_paragraphs = list(build_cleanup_range().Paragraphs)
                    for paragraph in reversed(final_paragraphs):
                        try:
                            if paragraph.Range.Information(wdWithInTable):
                                continue
                            if is_protected_range(paragraph.Range):
                                continue

                            if is_effectively_empty_text(paragraph.Range.Text):
                                paragraph.Range.Delete()
                                final_empty_deleted += 1
                        except Exception:
                            pass

                    if final_empty_deleted > 0:
                        insertion_log_parts.append(
                            f"  步骤4.3完成：删除剩余空段 {final_empty_deleted} 个。"
                        )
                    else:
                        insertion_log_parts.append("  步骤4.3完成：未发现剩余空段。")

                try:
                    def visible_text(text: str) -> str:
                        if not text:
                            return ""
                        return (
                            text.replace("\r", "")
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

                    def row_is_empty(row) -> bool:
                        try:
                            cells = row.Cells
                            for cell_index in range(1, cells.Count + 1):
                                try:
                                    text = cells(cell_index).Range.Text
                                except Exception:
                                    text = ""
                                if visible_text(text):
                                    return False
                            return True
                        except Exception:
                            return False

                    def trim_table_trailing_empty_rows(table) -> int:
                        removed = 0
                        try:
                            for row_index in range(table.Rows.Count, 0, -1):
                                try:
                                    row = table.Rows(row_index)
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

                    table_range = doc.Range(
                        int(insertion_bound_start),
                        int(get_insertion_bound_end()),
                    )
                    tables = table_range.Tables
                    trimmed_tables = 0
                    trimmed_rows_total = 0
                    deleted_empty_tables = 0

                    for table_index in range(tables.Count, 0, -1):
                        try:
                            table = tables(table_index)
                            removed_rows = trim_table_trailing_empty_rows(table)
                            if removed_rows > 0:
                                trimmed_tables += 1
                                trimmed_rows_total += removed_rows

                            cleaned_text = visible_text(table.Range.Text)
                            if not cleaned_text:
                                table.Range.Delete()
                                deleted_empty_tables += 1
                        except Exception:
                            continue

                    if trimmed_tables > 0 or deleted_empty_tables > 0:
                        insertion_log_parts.append(
                            f"  步骤4.4完成：修剪表格 {trimmed_tables} 个，删除尾部空行 {trimmed_rows_total} 行，删除空表格 {deleted_empty_tables} 个。"
                        )
                except Exception:
                    pass

                insertion_log_parts.append(
                    "步骤4完成：已清理可编辑内容中的空段落与多余换行。"
                )
                insertion_log_parts.append("内容处理成功。")

                comment_step_label = "步骤5"
                if "inline_style_fragments" in state:
                    style_writeback_result = apply_inline_style_fragments(
                        doc=doc,
                        inline_style_fragments=state.get("inline_style_fragments"),
                        bound_start=int(insertion_bound_start),
                        bound_end=int(get_insertion_bound_end()),
                        log_parts=insertion_log_parts,
                        step_label="步骤5",
                    )
                    style_writeback_summary = summarize_style_writeback_result(
                        style_writeback_result
                    )
                    comment_step_label = "步骤6"

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

                added = comment_writeback_result.get("added", 0)
                failed = comment_writeback_result.get("failed", 0)
                skipped = comment_writeback_result.get("skipped", 0)
                issues = comment_writeback_result.get("issues", [])

                summary = (
                    f"AI批注写入: 生成={generated_count}, 成功={added}, "
                    f"失败={failed}, 跳过={skipped}"
                )
                progress_log.info(summary)

                if generated_count > 0 and added == 0:
                    error_msg = (
                        f"批注生成成功但写入失败: 生成{generated_count}条, 成功写入0条"
                    )
                    progress_log.error(error_msg)
                    raise ValueError(error_msg)

                comment_writeback_summary = summary
                comment_writeback_added = added
                comment_writeback_failed = failed
                comment_writeback_skipped = skipped
                comment_writeback_errors = [
                    {
                        "reference_text": issue.get("reference_text", ""),
                        "reason": issue.get("reason", ""),
                        "error": issue.get("error", ""),
                    }
                    for issue in issues
                ]

            doc.Save()
            insertion_log_parts.append("文档已保存。")

        except Exception as error:
            insertion_log_parts.append(f"Word 处理过程中出错: {error}")
            raise
        finally:
            close_word_application(
                word_app=word,
                doc=doc,
                com_initialized=com_initialized,
                wait_time=0.0,
                node_name="update_word",
            )

    except Exception as error:
        insertion_log_parts.append(f"初始化 Word COM 时出错: {error}")
        raise

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


def _build_manual_test_output_path(source_doc_path: pathlib.Path) -> pathlib.Path:
    return source_doc_path.with_name(
        f"{source_doc_path.stem}{DEFAULT_MANUAL_TEST_SUFFIX}{source_doc_path.suffix}"
    )


def _prepare_manual_test_copy(
    source_doc_path: pathlib.Path, output_path: pathlib.Path
) -> None:
    if output_path.exists():
        output_path.chmod(output_path.stat().st_mode | stat.S_IWUSR)
        output_path.unlink()
    shutil.copy2(source_doc_path, output_path)
    output_path.chmod(output_path.stat().st_mode | stat.S_IWUSR)


def _print_manual_state(state: TenderGraphStateBase) -> None:
    print("测试状态:")
    for key, value in state.items():
        if key == "polished_text":
            print(f"  {key}: {value[:120]}...")
        else:
            print(f"  {key}: {value}")


def _run_manual_delete_then_update_scenario(
    source_doc_path: pathlib.Path,
) -> pathlib.Path:
    """先执行 delete 节点再执行 update_word，模拟 e2e graph 流程。"""
    from backend.nodes.gngk_word_nodes.gngk_fw_zc_delete_tender_param import (
        gngk_fw_zc_delete_tender_param,
    )

    if not source_doc_path.exists():
        raise FileNotFoundError(f"更新测试源文件不存在: {source_doc_path}")

    output_path = _build_manual_test_output_path(source_doc_path)
    _prepare_manual_test_copy(source_doc_path, output_path)

    insertion_before_text, insertion_after_text = get_default_anchor_texts("gngk_fw_zc")

    # ---- 步骤1: 执行 delete 节点 ----
    delete_state = TenderGraphStateBase(
        tender_type="gngk_fw_zc",
        prepared_doc_path=str(output_path),
        insertion_before_text=insertion_before_text,
        insertion_after_text=insertion_after_text,
    )

    print("[场景] 国内公开-服务自筹三字段回填（delete → update_word）")
    print(f"源文件: {source_doc_path}")
    print(f"测试副本: {output_path}")
    print("执行模式: 先执行 gngk_fw_zc_delete_tender_param，再执行 gngk_fw_zc_update_word")
    print()
    print("=" * 40 + " 步骤1: delete_tender_param " + "=" * 40)
    _print_manual_state(delete_state)
    print("-" * 80)

    delete_result = gngk_fw_zc_delete_tender_param(delete_state, config=None)
    print("✅ gngk_fw_zc_delete_tender_param 执行完成")
    print()

    # ---- 步骤2: 执行 update_word 节点 ----
    update_state = TenderGraphStateBase(
        tender_type="gngk_fw_zc",
        prepared_doc_path=str(output_path),
        polished_text=MANUAL_TEST_INSERT_TEXT,
        insertion_before_text=insertion_before_text,
        insertion_after_text=insertion_after_text,
    )

    print("=" * 40 + " 步骤2: update_word " + "=" * 40)
    _print_manual_state(update_state)
    print("-" * 80)

    update_result = gngk_fw_zc_update_word(update_state, config=None)
    print("✅ gngk_fw_zc_update_word 执行完成")
    print(f"回填产物: {output_path}")
    print("插入日志:")
    for part in str(update_result.get("insertion_log", "")).split("; "):
        print(f"  - {part}")
    return output_path


def main() -> None:
    print("=" * 80)
    print("开始测试国内公开-服务自筹三字段回填场景（delete → update_word）")
    print("=" * 80)

    output_path: Optional[pathlib.Path] = None
    try:
        output_path = _run_manual_delete_then_update_scenario(
            DEFAULT_MANUAL_TEST_SOURCE_DOC
        )
    except Exception as exc:
        print("❌ 执行失败")
        print(f"错误信息: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print()
    print("=" * 80)
    print("诊断完成")
    if output_path is not None:
        print(f"回填产物文件: {output_path}")
    print("国内公开-服务自筹三字段回填场景执行成功")
    print("=" * 80)


__all__ = [
    "GNGK_THREE_FIELD_PROFILE",
    "gngk_fw_zc_update_word",
    "split_polished_text_into_blocks",
    "_convert_lines_to_items",
    "_resolve_block4_insert_start",
    "_validate_block_window",
]


if __name__ == "__main__":
    main()
