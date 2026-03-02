"""
统一的 Word 文档更新节点

将润色后的文本插入到 Word 文档中，支持多种招标类型。
使用 anchor_utils.find_anchor_range() 进行锚点定位。
"""

from __future__ import annotations

import re
from typing import Optional, Dict, Any
import time
import pathlib
import sys

# 添加项目根目录到 sys.path
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.states import TenderGraphStateBase
from backend.config.tender_config import TARGET_SIZES
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
from backend.util.word_util.anchor_utils import find_anchor_range




def split_polished_text_into_blocks(polished_text: str) -> Dict[str, Any]:
    """
    将润色文本按关键字（交付日期、付款方式）拆分为三个块。

    Args:
        polished_text: 润色后的文本内容

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


def update_word(state: TenderGraphStateBase, config) -> TenderGraphStateBase:
    """
    在指定锚点位置将润色后的文本插入到 Word 文档中。

    统一支持 xjcg（询价采购）和 gngk（公开招标）两种招标类型，
    根据状态中的 tender_type 自动选择对应的字体大小进行锚点定位。

    Args:
        state: 图状态，包含 prepared_doc_path、polished_text、
               insertion_before_text、insertion_after_text 等字段
        config: LangGraph 配置

    Returns:
        更新后的状态，包含 insertion_log
    """
    start_time = time.perf_counter()

    from backend.util.log_util import log_task_start, log_task_end

    logged_end = False
    log_task_start(state, "update_word")

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

    # 根据招标类型获取目标字体大小
    target_size = TARGET_SIZES.get(tender_type, 18.0)

    split_result = split_polished_text_into_blocks(polished_text)
    content_list = split_result["content_list"]

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
            insertion_log_parts.append(f"查找锚点（目标字号: {target_size}）...")
            before_hit, after_hit = find_anchor_range(
                doc,
                insertion_before_text,
                insertion_after_text,
                target_size,
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

            selection = word.Selection
            try:
                selection.GoTo(wdGoToPage, wdGoToAbsolute, before_anchor_page + 1)
                insertion_bound_start = int(selection.Start)
                if insertion_bound_start < before_anchor_end:
                    insertion_bound_start = before_anchor_end
            except Exception:
                insertion_bound_start = before_anchor_end

            insertion_bound_end = after_anchor_start

            if insertion_bound_end <= insertion_bound_start:
                raise ValueError(
                    f"锚点范围非法: start={insertion_bound_start}, end={insertion_bound_end}"
                )

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
                start_page = before_anchor_page + 1
                end_page = after_anchor_page - 1
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

            # 为目标页创建范围
            if page_end > page_start:
                page_rng = doc.Range(page_start, page_end)

                # 步骤1：在页面中查找不可编辑字段
                insertion_log_parts.append(
                    f"步骤1：在第 {target_page} 页查找不可编辑字段..."
                )

                protected_keywords = ["交付日期", "付款方式"]
                protected_fields = {}

                # 在页面中查找受保护字段
                for para in page_rng.Paragraphs:
                    para_text = para.Range.Text.strip()
                    for keyword in protected_keywords:
                        if keyword in para_text and "：" in para_text:
                            if keyword not in protected_fields:
                                protected_fields[keyword] = para.Range
                                insertion_log_parts.append(
                                    f"  找到受保护字段: {keyword}"
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

                protected_fields = {}
                for keyword in protected_keywords:
                    try:
                        para_rng = refind_protected_paragraph(keyword)
                        if para_rng is not None:
                            protected_fields[keyword] = para_rng
                    except Exception:
                        pass

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

                # 检测 Markdown 风格的表格
                def is_table_separator_line(line: str) -> bool:
                    return bool(re.match(r"^\s*\|\s*:?-{3,}.*\|\s*$", line))

                def _parse_table_row(line: str):
                    cells = [cell.strip() for cell in line.split("|")]
                    if cells and cells[0] == "":
                        cells = cells[1:]
                    if cells and cells[-1] == "":
                        cells = cells[:-1]
                    return cells

                def looks_like_table_row(line: str) -> bool:
                    s = (line or "").strip()
                    if "|" not in s:
                        return False
                    cells = _parse_table_row(s)
                    return len(cells) >= 2

                def parse_table_block(lines, start_idx):
                    table_lines = []
                    i = start_idx
                    while i < len(lines) and lines[i].strip().startswith("|"):
                        table_lines.append(lines[i].strip())
                        i += 1

                    if len(table_lines) >= 2 and is_table_separator_line(
                        table_lines[1]
                    ):
                        header = table_lines[0]
                        data_lines = table_lines[2:] if len(table_lines) > 2 else []
                        all_lines = [header] + data_lines
                        rows = [_parse_table_row(ln) for ln in all_lines]
                        return rows, i

                    table_lines_alt = []
                    j = start_idx
                    while j < len(lines) and looks_like_table_row(lines[j]):
                        table_lines_alt.append(lines[j].strip())
                        j += 1
                    if len(table_lines_alt) >= 2:
                        rows = [_parse_table_row(ln) for ln in table_lines_alt]
                        return rows, j

                    return None, start_idx

                def convert_lines_to_items(lines):
                    items = []
                    idx = 0
                    while idx < len(lines):
                        line = lines[idx]
                        maybe_table, next_idx = parse_table_block(lines, idx)
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
                    insert_range.InsertAfter(line + "\r")
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
                                cell_text = re.sub(r"(?i)<br\s*/?>", "\r", cell_text)
                                cell_range.InsertBefore(cell_text)

                                cell_range = cell.Range
                                cell_range.Font.Name = insert_font_name
                                cell_range.Font.Size = insert_font_size
                                cell_range.Font.Bold = False
                                cell_range.ParagraphFormat.LineSpacingRule = (
                                    wdLineSpace1pt5
                                )
                                cell_range.ParagraphFormat.LeftIndent = 0
                                cell_range.ParagraphFormat.FirstLineIndent = 0
                                cell_range.ParagraphFormat.OutlineLevel = (
                                    wdOutlineLevelBodyText
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

                # 插入块1（在交付日期之前）
                insertion_log_parts.append("  正在插入块1...")
                selection.GoTo(wdGoToPage, wdGoToAbsolute, target_page)
                insert_rng = selection.Range
                insert_rng.Collapse(wdCollapseStart)

                if "交付日期" in protected_fields:
                    delivery_date_rng = protected_fields["交付日期"]
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

                if "交付日期" in protected_fields:
                    insert_prefix_before_keyword("交付日期", delivery_prefix)
                    protected_fields["交付日期"] = (
                        refind_protected_paragraph("交付日期")
                        or protected_fields["交付日期"]
                    )
                    update_protected_field("交付日期", delivery_value)

                    # 插入块2（在交付日期和付款方式之间）
                    insertion_log_parts.append("  插入块2...")
                    if (
                        "交付日期" in protected_fields
                        and "付款方式" in protected_fields
                    ):
                        delivery_date_rng = protected_fields["交付日期"]
                        protected_fields["付款方式"] = (
                            refind_protected_paragraph("付款方式")
                            or protected_fields["付款方式"]
                        )
                        payment_method_rng = protected_fields["付款方式"]

                        start_between = int(delivery_date_rng.End)
                        end_between = int(payment_method_rng.Start)
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
                                    insert_table_with_formatting(
                                        insert_rng, item["rows"]
                                    )
                                    insertion_log_parts.append(
                                        f"    已插入表格，行数 {len(item['rows'])}。"
                                    )
                            except Exception as e:
                                insertion_log_parts.append(f"    插入项出错: {e}")
                    elif "交付日期" in protected_fields:
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
                                    insert_table_with_formatting(
                                        insert_rng, item["rows"]
                                    )
                                    insertion_log_parts.append(
                                        f"    已插入表格，行数 {len(item['rows'])}。"
                                    )
                            except Exception as e:
                                insertion_log_parts.append(f"    插入项出错: {e}")

                    if "付款方式" in protected_fields:
                        insert_prefix_before_keyword("付款方式", payment_prefix)
                        protected_fields["付款方式"] = (
                            refind_protected_paragraph("付款方式")
                            or protected_fields["付款方式"]
                        )
                        update_protected_field("付款方式", payment_value)

                    # 插入块3（在付款方式之后）
                    block3_items = convert_lines_to_items(block3)
                    insertion_log_parts.append(
                        f"  插入块3（{len(block3_items)} 条）..."
                    )
                    if len(block3_items) == 0:
                        insertion_log_parts.append("    警告：块3为空，无需插入")
                    else:
                        insertion_log_parts.append(
                            f"    块3内容: "
                            f"{[item['line'][:30] + '...' if item['type'] == 'text' and len(item['line']) > 30 else item['line'] if item['type'] == 'text' else '<表格>' for item in block3_items]}"
                        )

                    if "付款方式" in protected_fields:
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
                                        inserted_rng = insert_content_with_formatting(
                                            insert_rng, item["line"]
                                        )
                                        inserted_count += 1
                                        insertion_log_parts.append(
                                            f"    [{inserted_count}/{len(block3_items)}] 已插入: {item['line'][:50]}..."
                                        )
                                        break
                                    elif item["type"] == "table":
                                        insert_table_with_formatting(
                                            insert_rng, item["rows"]
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

                                para_text = para.Range.Text.strip()

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

                            para_text = para.Range.Text.strip()

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
            if not logged_end:
                log_task_end(state, "update_word")
                logged_end = True

    except Exception as e:
        error_msg = f"初始化 Word COM 时出错: {e}"
        insertion_log_parts.append(error_msg)
        if not logged_end:
            log_task_end(state, "update_word")
            logged_end = True
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
