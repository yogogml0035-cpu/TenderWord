from __future__ import annotations

import re
from typing import Optional
import time
import pathlib
import sys

# 添加项目根目录到 sys.path
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from states import XjcgTenderGraphState
from util.word_application_util import (
    create_word_application,
    close_word_application,
    open_document_with_retry,
    unprotect_document,
)
from util.word_constants import (
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


def split_polished_text_into_blocks(polished_text: str):
    polished_text_norm = polished_text.replace("\r\n", "\n").replace("\r", "\n")
    raw_lines = polished_text_norm.split("\n")
    content_list = [line.rstrip() for line in raw_lines if line.strip() != ""]

    def parse_keyword_line(line: Optional[str], keyword: str):
        if not line or keyword not in line:
            return "", None
        m = re.search(rf"^(?P<prefix>.*?){re.escape(keyword)}\s*([：:])(?P<value>.*)$", line)
        if m:
            return m.group("prefix"), m.group("value")
        idx = line.find(keyword)
        prefix = line[:idx]
        rest = line[idx + len(keyword):]
        rest = rest.lstrip()
        if rest.startswith("：") or rest.startswith(":"):
            rest = rest[1:]
        return prefix, rest

    delivery_date_idx = next((i for i, line in enumerate(content_list) if "交付日期" in line), None)
    payment_method_idx = next((i for i, line in enumerate(content_list) if "付款方式" in line), None)

    delivery_date_line = content_list[delivery_date_idx] if delivery_date_idx is not None else None
    payment_method_line = content_list[payment_method_idx] if payment_method_idx is not None else None

    delivery_prefix, delivery_value = parse_keyword_line(delivery_date_line, "交付日期")
    payment_prefix, payment_value = parse_keyword_line(payment_method_line, "付款方式")

    block1 = content_list[:delivery_date_idx] if delivery_date_idx is not None else (content_list[:] if content_list else [])
    block2 = (
        content_list[delivery_date_idx + 1:payment_method_idx]
        if delivery_date_idx is not None and payment_method_idx is not None
        else (content_list[delivery_date_idx + 1:] if delivery_date_idx is not None else [])
    )
    block3 = content_list[payment_method_idx + 1:] if payment_method_idx is not None else []

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


def update_word(state: XjcgTenderGraphState, config) -> XjcgTenderGraphState:
    start_time = time.perf_counter()
    

    from util.logging_utils import log_task_end
    log_task_end(state, "update_word")
    
    print("[update_word] 开始执行...")
    
    """在指定锚点位置将润色后的文本插入到 Word 文档中。"""
    prepared_doc_path = state.get("prepared_doc_path")
    polished_text = state.get("polished_text")
    insertion_before_text = state.get("insertion_before_text")
    insertion_after_text = state.get("insertion_after_text")
    
    if not prepared_doc_path:
        raise ValueError("需要 prepared_doc_path 来插入内容到 Word 文档")
    if not polished_text:
        raise ValueError("需要 polished_text 来插入内容到 Word 文档")
    if not insertion_before_text or not insertion_after_text:
        raise ValueError("insertion_before_text 和 insertion_after_text 必须提供，用于定位插入范围")
    
    split_result = split_polished_text_into_blocks(polished_text)
    content_list = split_result["content_list"]
    
    insertion_log_parts = []
    word = None
    doc = None
    com_initialized = False
    
    try:
        # 使用统一的工具函数创建 Word 应用程序
        # 独立实例，避免与其他节点共享同一 Word 进程导致句柄失效
        word, com_initialized = create_word_application(
            initial_delay=0.0,  # 不需要等待
            post_init_delay=1.0,  # 等待上一个节点关闭文档/进程
            use_existing=False,  # 使用独立实例
            verify=False,  # 验证步骤在工具函数中已包含
            node_name="update_word"
        )
        
        try:
            # 使用统一的工具函数打开文档（带重试机制）
            doc = open_document_with_retry(
                word_app=word,
                file_path=prepared_doc_path,
                read_only=False,
                node_name="update_word"
            )
            insertion_log_parts.append(f"已打开文档: {prepared_doc_path}")
            
            # 使用统一的工具函数取消文档保护
            if unprotect_document(doc, node_name="update_word"):
                insertion_log_parts.append("已取消文档保护")

            def _norm(s: str) -> str:
                """归一化文本：去掉首尾空白、把多空格/全角空格归一"""
                if s is None:
                    return ""
                s = s.replace("\u3000", " ")  # 全角空格
                s = re.sub(r"\s+", " ", s)    # 多空白 -> 单空格
                return s.strip()
            
            def _iter_paragraph_hits(doc, text: str, target_size: float):
                """扫描所有段落，找到文本匹配且字号/字体符合的候选。"""
                want = _norm(text)
                hits = []
                for para in doc.Paragraphs:
                    try:
                        raw = para.Range.Text
                        stripped = _norm(raw.replace("\r", "").replace("\a", ""))
                        if stripped != want:
                            continue
                        
                        font_name = str(para.Range.Font.Name)
                        font_size = float(para.Range.Font.Size)
                        is_font = font_name in ("宋体", "SimSun")
                        is_size = abs(font_size - float(target_size)) < 0.5
                        
                        # 页码信息只在命中时取一次，避免频繁触发重分页
                        page = int(para.Range.Information(wdActiveEndPageNumber))
                        
                        hits.append({
                            "page": page,
                            "start": int(para.Range.Start),
                            "end": int(para.Range.End),
                            "font": font_name,
                            "size": font_size,
                            "is_font": is_font,
                            "is_size": is_size,
                        })
                    except Exception:
                        continue
                return hits
            
            def _pick_before_anchor(hits):
                """
                选前置锚点：默认选"页码最大"的（避开目录/前言重复标题）。
                """
                if not hits:
                    return None
                strict = [h for h in hits if h["is_font"] and h["is_size"]]
                pool = strict if strict else hits
                pool.sort(key=lambda x: (x["page"], x["start"]))
                return pool[-1]
            
            def _pick_after_anchor(hits, min_start: int):
                """
                选后置锚点：取"在 min_start 之后最早出现"的那一个。
                """
                if not hits:
                    return None
                hits2 = [h for h in hits if h["start"] >= int(min_start)]
                if not hits2:
                    return None
                strict = [h for h in hits2 if h["is_font"] and h["is_size"]]
                pool = strict if strict else hits2
                pool.sort(key=lambda x: (x["start"], x["page"]))
                return pool[0]

            # gngk 模块固定使用 22.0（二号）
            target_size = 22.0
            
            # 一次扫描拿到候选（非常稳）
            before_hits = _iter_paragraph_hits(doc, insertion_before_text, target_size)
            after_hits  = _iter_paragraph_hits(doc, insertion_after_text, target_size)
            
            if not before_hits:
                raise ValueError(f"未找到前置锚点段落: {insertion_before_text}")
            before_hit = _pick_before_anchor(before_hits)
            before_anchor_start = before_hit["start"]
            before_anchor_end   = before_hit["end"]
            before_anchor_page  = before_hit["page"]
            
            # 对齐到下一页起始（可选，跟原来逻辑一致）
            selection = word.Selection
            try:
                selection.GoTo(wdGoToPage, wdGoToAbsolute, before_anchor_page + 1)
                insertion_bound_start = int(selection.Start)
                if insertion_bound_start < before_anchor_end:
                    insertion_bound_start = before_anchor_end
            except Exception:
                insertion_bound_start = before_anchor_end
            
            after_hit = _pick_after_anchor(after_hits, insertion_bound_start)
            if not after_hit:
                raise ValueError(f"未找到后置锚点段落: {insertion_after_text}")
            
            after_anchor_start = after_hit["start"]
            after_anchor_end   = after_hit["end"]
            after_anchor_page  = after_hit["page"]
            insertion_bound_end = after_anchor_start
            
            if insertion_bound_end <= insertion_bound_start:
                raise ValueError(
                    f"锚点范围非法: start={insertion_bound_start}, end={insertion_bound_end}"
                )
            
            # 这个 marker 继续保留（后面 get_insertion_bound_end 会用）
            after_anchor_marker = doc.Range(int(after_anchor_start), int(after_anchor_start))
            
            def get_insertion_bound_end() -> int:
                try:
                    return int(after_anchor_marker.Start)
                except Exception:
                    return int(insertion_bound_end)
            
            insertion_log_parts.append(
                f"✅ 前置锚点: 页={before_anchor_page}, {before_anchor_start}-{before_anchor_end}, 字体={before_hit['font']}, 字号={before_hit['size']}"
            )
            insertion_log_parts.append(
                f"✅ 后置锚点: 页={after_anchor_page}, {after_anchor_start}-{after_anchor_end}, 字体={after_hit['font']}, 字号={after_hit['size']}"
            )
            insertion_log_parts.append(
                f"锚点范围(字符位置): {insertion_bound_start} - {insertion_bound_end}"
            )
            
            # 优先使用 extract_tender_params 已计算好的页范围，避免重复查找
            start_page = state.get("start_page")
            end_page = state.get("end_page")

            if start_page is None or end_page is None:
                # 回退到自身计算
                start_page = before_anchor_page + 1
                end_page = after_anchor_page - 1
                insertion_log_parts.append(f"回退计算页范围: {start_page} - {end_page}")
            else:
                insertion_log_parts.append(f"使用预计算页范围: {start_page} - {end_page}")

            if start_page is None or end_page is None:
                raise ValueError("无法确定插入页范围")
            if end_page < start_page:
                raise ValueError(f"插入页范围非法: {start_page} - {end_page}")

            try:
                region_text = doc.Range(insertion_bound_start, insertion_bound_end).Text
                if re.search(r"第[一二三四五六七八九十0-9]+章", region_text):
                    raise ValueError("锚点之间检测到章节标题，停止插入以避免侵入其他章节")
            except Exception as _region_e:
                if isinstance(_region_e, ValueError):
                    raise

            selection = word.Selection

            # 继续在 start_page 插入内容
            target_page = start_page
            insertion_log_parts.append(f"处理目标页 {target_page}")
            
            selection = word.Selection
            
            # 导航到目标页起始位置
            selection.GoTo(wdGoToPage, wdGoToAbsolute, target_page)
            page_start = selection.Start
            page_start_page = selection.Information(wdActiveEndPageNumber)
            
            # 查找目标页的结束位置（下一页的起始位置或文档末尾）
            next_page = target_page + 1
            selection.GoTo(wdGoToPage, wdGoToAbsolute, next_page)
            page_end = selection.Start
            page_end_page = selection.Information(wdActiveEndPageNumber)
            
            # 如果目标页不存在或已到达文档末尾，使用文档末尾
            if page_start_page != target_page or page_end == page_start:
                page_end = doc.Content.End
            elif page_end_page == next_page:
                # 下一页存在，使用其起始位置作为结束位置
                pass
            else:
                # 已到达文档末尾
                page_end = doc.Content.End
            
            # 为目标页创建范围
            if page_end > page_start:
                page_rng = doc.Range(page_start, page_end)
                
                # 步骤1：在页面中查找不可编辑字段
                insertion_log_parts.append(f"步骤1：在第 {target_page} 页查找不可编辑字段...")
                
                protected_keywords = ["交付日期", "付款方式"]
                protected_fields = {}  # {keyword: paragraph_range}
                
                # 在页面中查找受保护字段
                for para in page_rng.Paragraphs:
                    para_text = para.Range.Text.strip()
                    for keyword in protected_keywords:
                        if keyword in para_text and "：" in para_text:
                            if keyword not in protected_fields:
                                protected_fields[keyword] = para.Range
                                insertion_log_parts.append(f"  找到受保护字段: {keyword}")
                
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
                    insertion_log_parts.append(f"  交付日期前缀: {delivery_prefix.strip()}")
                if payment_prefix.strip():
                    insertion_log_parts.append(f"  付款方式前缀: {payment_prefix.strip()}")
                
                # 步骤3：删除所有可编辑内容
                insertion_log_parts.append(f"步骤3：删除第 {target_page} 页可编辑内容...")
                
                paras = list(page_rng.Paragraphs)
                deleted_count = 0
                
                # 从末尾向起始位置迭代
                for i in range(len(paras) - 1, -1, -1):
                    try:
                        para = paras[i]
                        para_text = para.Range.Text.strip()
                        
                        # 跳过空段落
                        if not para_text or para_text == "\r" or para_text == "\n" or len(para_text) == 0:
                            continue
                        
                        # 检查段落是否包含受保护关键字
                        is_protected = False
                        for keyword in protected_keywords:
                            if keyword in para_text:
                                is_protected = True
                                break
                        
                        # 如果未受保护，尝试删除
                        if not is_protected:
                            try:
                                para_rng = para.Range
                                para_rng.Delete()
                                deleted_count += 1
                                insertion_log_parts.append(f"  已删除可编辑段落: {para_text[:50]}...")
                            except Exception as e:
                                insertion_log_parts.append(f"  跳过（受保护或不可编辑）: {para_text[:50]}... (错误: {e})")
                    except Exception as e:
                        insertion_log_parts.append(f"  处理第 {i} 段出错: {e}")
                
                insertion_log_parts.append(f"步骤3完成：已删除 {deleted_count} 个可编辑段落。")
                
                # 步骤4：按块插入内容
                insertion_log_parts.append("步骤4：按块插入内容...")
                
                # 删除后重新获取页面范围
                selection.GoTo(wdGoToPage, wdGoToAbsolute, target_page)
                page_start_after = selection.Start
                selection.GoTo(wdGoToPage, wdGoToAbsolute, next_page)
                page_end_after = (
                    selection.Start if selection.Information(wdActiveEndPageNumber) == next_page else doc.Content.End
                )
                bound_end_for_search = int(get_insertion_bound_end())
                if int(page_end_after) < bound_end_for_search:
                    page_end_after = bound_end_for_search
                page_rng_after = doc.Range(page_start_after, page_end_after)

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
                            if keyword in para_text and ("：" in para_text or ":" in para_text):
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
                        marker = "\u200B"
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

                def find_editable_insertion_pos(start_pos: int, max_lookahead: int = 400) -> int:
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

                def find_next_editable_pos(after_pos: int, max_paragraphs: int = 250) -> int:
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

                def find_next_editable_pos_bounded(start_pos: int, bound_end: int, max_lookahead: int = 4000) -> Optional[int]:
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

                def find_prev_editable_pos(before_pos: int, max_lookback: int = 4000) -> Optional[int]:
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
                    return ("锁定" in err) or ("locked" in err) or ("-2146823683" in err)

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
                            pos2 = find_next_editable_pos_bounded(pos + 1, bound_end, max_lookahead=20000)
                            if pos2 is not None and pos2 > pos:
                                insert_range.SetRange(pos2, pos2)
                                insert_range.Collapse(wdCollapseStart)
                    except Exception:
                        pass
                
                # 格式设置
                insert_font_name = "宋体"
                insert_font_size = 12

                # 检测 Markdown 风格的表格（支持两种格式）
                # 1) 标准：行以 '|' 开头，第二行为 | --- | --- |；2) 简写：多行用 | 分隔列，无分隔符行
                def is_table_separator_line(line: str) -> bool:
                    return bool(re.match(r"^\s*\|\s*:?-{3,}.*\|\s*$", line))

                def _parse_table_row(line: str):
                    """按 '|' 分割一行得到单元格列表，去除首尾空串。"""
                    cells = [cell.strip() for cell in line.split("|")]
                    if cells and cells[0] == "":
                        cells = cells[1:]
                    if cells and cells[-1] == "":
                        cells = cells[:-1]
                    return cells

                def looks_like_table_row(line: str) -> bool:
                    """是否像表格行：包含 | 且能解析出至少 2 列。"""
                    s = (line or "").strip()
                    if "|" not in s:
                        return False
                    cells = _parse_table_row(s)
                    return len(cells) >= 2

                def parse_table_block(lines, start_idx):
                    """解析连续的 Markdown 表格行为行，并返回行和下一个索引。"""
                    table_lines = []
                    i = start_idx
                    while i < len(lines) and lines[i].strip().startswith("|"):
                        table_lines.append(lines[i].strip())
                        i += 1

                    # 标准 Markdown 表格：至少 2 行且第二行为分隔符
                    if len(table_lines) >= 2 and is_table_separator_line(table_lines[1]):
                        header = table_lines[0]
                        data_lines = table_lines[2:] if len(table_lines) > 2 else []
                        all_lines = [header] + data_lines
                        rows = [_parse_table_row(ln) for ln in all_lines]
                        return rows, i

                    # 否则尝试“简写表格”：从 start_idx 起连续多行均为 | 分隔的多列（可不以 | 开头）
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
                    """将普通行转换为项目列表（文本或表格）。"""
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
                
                # 辅助函数：插入带格式的内容
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
                    """在当前范围插入一个 Markdown 解析的表格。"""
                    if not rows:
                        return None

                    cols = max(len(r) for r in rows)
                    start_pos = insert_range.End
                    table_range = doc.Range(start_pos, start_pos)
                    table = doc.Tables.Add(table_range, len(rows), cols)
                    # 应用边框，使表格符合"有边框"的预期
                    try:
                        table.Borders.Enable = True
                    except Exception:
                        pass

                    # 填充所有行的所有单元格
                    for r_idx, row in enumerate(rows):
                        for c_idx, val in enumerate(row):
                            try:
                                cell = table.Cell(r_idx + 1, c_idx + 1)
                                # 先清空单元格内容（删除除末尾标记外的所有内容）
                                cell_range = cell.Range
                                # 单元格末尾有特殊字符（\r\x07），需要保留
                                if cell_range.End > cell_range.Start + 1:
                                    delete_range = doc.Range(cell_range.Start, cell_range.End - 1)
                                    delete_range.Delete()
                                
                                # 在单元格开始位置插入文本
                                cell_range = cell.Range
                                cell_range.InsertBefore(val)
                                
                                # 设置格式
                                cell_range = cell.Range
                                cell_range.Font.Name = insert_font_name
                                cell_range.Font.Size = insert_font_size
                                cell_range.Font.Bold = False
                                cell_range.ParagraphFormat.LineSpacingRule = wdLineSpace1pt5
                                cell_range.ParagraphFormat.LeftIndent = 0
                                cell_range.ParagraphFormat.FirstLineIndent = 0
                                cell_range.ParagraphFormat.OutlineLevel = wdOutlineLevelBodyText
                                # 设置单元格内容居中对齐
                                cell_range.ParagraphFormat.Alignment = 1  # wdAlignParagraphCenter = 1
                                # 设置单元格垂直居中
                                cell.VerticalAlignment = 1  # wdCellAlignVerticalCenter = 1
                            except Exception as cell_e:
                                # 处理合并单元格等异常情况
                                pass

                    # 所有行填充完成后，移动插入范围到表格之后
                    try:
                        insert_range.SetRange(table.Range.End, table.Range.End)
                    except Exception:
                        insert_range.Collapse(wdCollapseEnd)
                        insert_range.Start = table.Range.End
                        insert_range.End = table.Range.End
                    insert_range.Collapse(wdCollapseEnd)
                    return table
                    
                # 辅助函数：更新受保护字段的值
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
                        insertion_log_parts.append(f"  警告: 插入前缀失败 '{keyword}': {e}")
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
                        insertion_log_parts.append(f"  已更新受保护字段 '{keyword}': {new_value_clean[:50]}...")
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
                                insertion_log_parts.append(f"    警告: 内联插入表格失败，改为文本: {e}")
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
                
                # 如果交付日期字段存在，在其之前插入
                if "交付日期" in protected_fields:
                    delivery_date_rng = protected_fields["交付日期"]
                    before_pos = int(delivery_date_rng.Start)
                    safe_before = find_prev_editable_pos(before_pos, max_lookback=20000)
                    if safe_before is None:
                        safe_before = find_editable_insertion_pos(int(page_start_after), max_lookahead=20000)
                    insert_rng.SetRange(safe_before, safe_before)
                    insert_rng.Collapse(wdCollapseStart)
                
                block1_items = convert_lines_to_items(block1)
                for item in block1_items:
                    try:
                        if item["type"] == "text":
                            inserted_rng = insert_content_with_formatting(insert_rng, item["line"])
                            insertion_log_parts.append(f"    已插入: {item['line'][:50]}...")
                        elif item["type"] == "table":
                            insert_table_with_formatting(insert_rng, item["rows"])
                            insertion_log_parts.append(f"    已插入表格，行数 {len(item['rows'])}。")
                    except Exception as e:
                        insertion_log_parts.append(f"    插入项出错: {e}")
                
                if "交付日期" in protected_fields:
                    insert_prefix_before_keyword("交付日期", delivery_prefix)
                    protected_fields["交付日期"] = refind_protected_paragraph("交付日期") or protected_fields["交付日期"]
                    update_protected_field("交付日期", delivery_value)
                    
                    # 插入块2（在交付日期和付款方式之间）
                    insertion_log_parts.append("  插入块2...")
                    if "交付日期" in protected_fields and "付款方式" in protected_fields:
                        delivery_date_rng = protected_fields["交付日期"]
                        protected_fields["付款方式"] = refind_protected_paragraph("付款方式") or protected_fields["付款方式"]
                        payment_method_rng = protected_fields["付款方式"]
                        
                        # 在交付日期字段之后、付款方式字段之前插入
                        start_between = int(delivery_date_rng.End)
                        end_between = int(payment_method_rng.Start)
                        safe_between = find_next_editable_pos_bounded(start_between, end_between, max_lookahead=20000)
                        if safe_between is None:
                            safe_between = find_next_editable_pos(start_between)
                        insert_rng.SetRange(safe_between, safe_between)
                        insert_rng.Collapse(wdCollapseStart)
                        
                        block2_items = convert_lines_to_items(block2)
                        for item in block2_items:
                            try:
                                if item["type"] == "text":
                                    inserted_rng = insert_content_with_formatting(insert_rng, item["line"])
                                    insertion_log_parts.append(f"    已插入: {item['line'][:50]}...")
                                elif item["type"] == "table":
                                    insert_table_with_formatting(insert_rng, item["rows"])
                                    insertion_log_parts.append(f"    已插入表格，行数 {len(item['rows'])}。")
                            except Exception as e:
                                insertion_log_parts.append(f"    插入项出错: {e}")
                    elif "交付日期" in protected_fields:
                        # 仅存在交付日期，在其后插入
                        delivery_date_rng = protected_fields["交付日期"]
                        start_after = int(delivery_date_rng.End)
                        safe_after = find_next_editable_pos(start_after)
                        insert_rng.SetRange(safe_after, safe_after)
                        insert_rng.Collapse(wdCollapseStart)
                        
                        block2_items = convert_lines_to_items(block2)
                        for item in block2_items:
                            try:
                                if item["type"] == "text":
                                    inserted_rng = insert_content_with_formatting(insert_rng, item["line"])
                                    insertion_log_parts.append(f"    已插入: {item['line'][:50]}...")
                                elif item["type"] == "table":
                                    insert_table_with_formatting(insert_rng, item["rows"])
                                    insertion_log_parts.append(f"    已插入表格，行数 {len(item['rows'])}。")
                            except Exception as e:
                                insertion_log_parts.append(f"    插入项出错: {e}")
                    
                    if "付款方式" in protected_fields:
                        insert_prefix_before_keyword("付款方式", payment_prefix)
                        protected_fields["付款方式"] = refind_protected_paragraph("付款方式") or protected_fields["付款方式"]
                        update_protected_field("付款方式", payment_value)
                    
                    # 插入块3（在付款方式之后）
                    block3_items = convert_lines_to_items(block3)
                    insertion_log_parts.append(f"  插入块3（{len(block3_items)} 条）...")
                    if len(block3_items) == 0:
                        insertion_log_parts.append("    警告：块3为空，无需插入")
                    else:
                        insertion_log_parts.append(
                            f"    块3内容: "
                            f"{[item['line'][:30] + '...' if item['type']=='text' and len(item['line'])>30 else item['line'] if item['type']=='text' else '<表格>' for item in block3_items]}"
                        )
                    
                    if "付款方式" in protected_fields:
                        protected_fields["付款方式"] = refind_protected_paragraph("付款方式") or protected_fields["付款方式"]
                        payment_method_rng = protected_fields["付款方式"]
                        bound_end_now = int(get_insertion_bound_end())
                        if int(payment_method_rng.End) > bound_end_now:
                            raise ValueError("付款方式字段位置超出插入边界，停止以避免侵入后置章节")
                        payment_end = int(payment_method_rng.End)
                        start_after_payment = min(payment_end + 1, bound_end_now)
                        safe_pos = None
                        if start_after_payment < bound_end_now:
                            safe_pos = find_next_editable_pos_bounded(
                                start_after_payment, bound_end_now, max_lookahead=20000
                            )
                        if safe_pos is None or safe_pos >= bound_end_now:
                            if bound_end_now > payment_end:
                                back = find_prev_editable_pos(bound_end_now - 1, max_lookback=20000)
                                if back is not None and back >= payment_end:
                                    safe_pos = back
                        if safe_pos is None:
                            safe_pos = start_after_payment
                        insert_rng.Start = min(max(0, safe_pos), doc.Content.End)
                        insert_rng.End = insert_rng.Start
                        insert_rng.Collapse(wdCollapseStart)
                        insertion_log_parts.append(f"    在付款方式字段后插入，位置 {insert_rng.Start}")
                    else:
                        safe_pos = int(get_insertion_bound_end())
                        insert_rng.SetRange(safe_pos, safe_pos)
                        insert_rng.Collapse(wdCollapseStart)
                        insertion_log_parts.append(f"    未找到付款方式字段，插入到后置锚点前，位置 {insert_rng.Start}")

                    use_inline = False
                    try:
                        if is_range_locked(doc.Range(int(insert_rng.Start), int(insert_rng.Start))):
                            use_inline = True
                    except Exception:
                        pass

                    inserted_count = 0
                    if use_inline and "付款方式" in protected_fields:
                        insertion_log_parts.append("    块3将以内联换行追加到付款方式段落末尾")
                        inserted_count = insert_items_inline_at_end_of_paragraph(protected_fields["付款方式"], block3_items)
                    else:
                        for item in block3_items:
                            attempts = 0
                            while attempts < 80:
                                attempts += 1
                                try:
                                    ensure_editable_insert_range(insert_rng)
                                    if item["type"] == "text":
                                        inserted_rng = insert_content_with_formatting(insert_rng, item["line"])
                                        inserted_count += 1
                                        insertion_log_parts.append(f"    [{inserted_count}/{len(block3_items)}] 已插入: {item['line'][:50]}...")
                                        break
                                    elif item["type"] == "table":
                                        insert_table_with_formatting(insert_rng, item["rows"])
                                        inserted_count += 1
                                        insertion_log_parts.append(f"    [{inserted_count}/{len(block3_items)}] 已插入表格，行数 {len(item['rows'])}。")
                                        break
                                except Exception as e:
                                    if is_locked_exception(e):
                                        try:
                                            cur = int(insert_rng.Start)
                                        except Exception:
                                            cur = 0
                                        bound_end_retry = int(get_insertion_bound_end())
                                        nxt = find_next_editable_pos_bounded(cur + 1, bound_end_retry, max_lookahead=20000)
                                        if nxt is None or nxt <= cur:
                                            insertion_log_parts.append(f"    插入项出错: {e}")
                                            break
                                        try:
                                            insert_rng.SetRange(nxt, nxt)
                                            insert_rng.Collapse(wdCollapseStart)
                                            continue
                                        except Exception:
                                            insertion_log_parts.append(f"    插入项出错: {e}")
                                            break
                                    insertion_log_parts.append(f"    插入项出错: {e}")
                                    break
                    
                    insertion_log_parts.append(f"  块3插入完成: {inserted_count}/{len(block3_items)} 条。")
                    
                    # 步骤5：从所有可编辑内容中移除空段落和换行符
                    insertion_log_parts.append("步骤5：清理空段落与换行...")
                    
                    # 多次遍历以确保所有空段落都被删除
                    max_passes = 5
                    total_empty_deleted = 0
                    
                    for pass_num in range(1, max_passes + 1):
                        insertion_log_parts.append(f"  步骤5.1 第 {pass_num} 轮：删除空段落...")
                        
                        # 重新获取页面范围（删除后会发生变化）
                        selection.GoTo(wdGoToPage, wdGoToAbsolute, target_page)
                        page_start_final = selection.Start
                        selection.GoTo(wdGoToPage, wdGoToAbsolute, next_page)
                        page_end_final = selection.Start if selection.Information(wdActiveEndPageNumber) == next_page else doc.Content.End
                        page_rng_final = doc.Range(page_start_final, page_end_final)
                        
                        paras_final = list(page_rng_final.Paragraphs)
                        empty_deleted = 0
                        
                        # 从末尾向起始位置迭代，避免索引问题
                        for i in range(len(paras_final) - 1, -1, -1):
                            try:
                                para = paras_final[i]
                                
                                # 跳过表格中的段落，防止损坏
                                if para.Range.Information(wdWithInTable):
                                    continue
                                
                                para_text = para.Range.Text.strip()
                                
                                # Check if paragraph is protected
                                is_protected = False
                                for keyword in protected_keywords:
                                    if keyword in para_text:
                                        is_protected = True
                                        break
                                
                                # Only process editable paragraphs
                                if not is_protected:
                                    # 获取原始文本以便彻底检查
                                    raw_text = para.Range.Text
                                    # 移除段落标记以便检查
                                    raw_text_no_mark = raw_text.rstrip("\r\n")
                                    
                                    # 移除所有可能的空白字符
                                    raw_cleaned = raw_text_no_mark.replace("\r", "").replace("\n", "").replace(" ", "").replace("\t", "").replace("\u00A0", "").replace("\u2000", "").replace("\u2001", "").replace("\u2002", "").replace("\u2003", "").replace("\u2004", "").replace("\u2005", "").replace("\u2006", "").replace("\u2007", "").replace("\u2008", "").replace("\u2009", "").replace("\u200A", "").replace("\u200B", "").strip()
                                    
                                    # 仅在完全为空时删除（没有任何可见字符）
                                    if len(raw_cleaned) == 0:
                                        try:
                                            para.Range.Delete()
                                            empty_deleted += 1
                                            insertion_log_parts.append(f"    删除空段落，索引 {i}")
                                        except Exception as e:
                                            insertion_log_parts.append(f"    警告: 无法删除索引 {i} 的段落: {e}")
                            except Exception as e:
                                insertion_log_parts.append(f"    处理第 {i} 段出错: {e}")
                        
                        total_empty_deleted += empty_deleted
                        insertion_log_parts.append(f"  第 {pass_num} 轮完成：删除空段 {empty_deleted} 个。")
                        
                        # 如果本轮没有删除空段落，则完成
                        if empty_deleted == 0:
                            insertion_log_parts.append(f"  未再发现空段，第 {pass_num} 轮后停止。")
                            break
                    
                    insertion_log_parts.append(f"  步骤5.1完成：共删除空段 {total_empty_deleted} 个，用时 {pass_num} 轮。")
                    
                    # 第二轮：从可编辑段落中移除换行符
                    insertion_log_parts.append("  步骤5.2：清理可编辑段落中的换行...")
                    
                    # 删除空段落后重新获取页面范围
                    selection.GoTo(wdGoToPage, wdGoToAbsolute, target_page)
                    page_start_clean = selection.Start
                    selection.GoTo(wdGoToPage, wdGoToAbsolute, next_page)
                    page_end_clean = selection.Start if selection.Information(wdActiveEndPageNumber) == next_page else doc.Content.End
                    page_rng_clean = doc.Range(page_start_clean, page_end_clean)
                    
                    cleaned_count = 0
                    paras_to_delete = []  # 收集清理后变为空的段落
                    
                    for para in page_rng_clean.Paragraphs:
                        # 跳过表格中的段落，防止损坏
                        if para.Range.Information(wdWithInTable):
                            continue

                        para_text = para.Range.Text.strip()
                        
                        # 跳过空段落（它们应该在步骤5.1中已被删除）
                        if not para_text or para_text == "\r" or para_text == "\n":
                            continue
                        
                        # 检查段落是否受保护
                        is_protected = False
                        for keyword in protected_keywords:
                            if keyword in para_text:
                                is_protected = True
                                break
                        
                        # 从可编辑段落中移除换行符
                        if not is_protected:
                            try:
                                para_rng = para.Range
                                # 获取包括段落标记的完整文本
                                full_text = para_rng.Text
                                
                                # 临时移除段落标记以便处理
                                text_without_mark = full_text.rstrip("\r\n")
                                
                                # 在处理前检查是否有实际内容
                                if not text_without_mark or len(text_without_mark.strip()) == 0:
                                    continue
                                
                                # 移除所有换行符和回车符
                                cleaned_text = text_without_mark.replace("\r", "").replace("\n", "").replace("\r\n", "")
                                
                                # 同时移除多个空格（可选，但有助于清理）
                                cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
                                
                                # 仅在以下情况下替换：
                                # 1. cleaned_text 不为空（有内容）
                                # 2. cleaned_text 与原始文本不同（实际已更改）
                                if cleaned_text and len(cleaned_text) > 0 and cleaned_text != text_without_mark:
                                    # 用清理后的文本替换（添加回段落标记）
                                    para_rng.Text = cleaned_text + "\r"
                                    cleaned_count += 1
                                    insertion_log_parts.append(f"    已清理: {cleaned_text[:50]}...")
                                elif cleaned_text and len(cleaned_text) > 0:
                                    # 文本已经清理，无需更改
                                    pass
                                else:
                                    # 清理后 cleaned_text 为空，标记为删除
                                    if len(cleaned_text) == 0:
                                        paras_to_delete.append(para_rng)
                                        insertion_log_parts.append(f"    标记删除（清理后为空）: '{para_text[:50]}...'")
                            except Exception as e:
                                insertion_log_parts.append(f"    警告: 无法清理段落 '{para_text[:50]}...': {e}")
                    
                    # 删除清理后变为空的段落
                    if paras_to_delete:
                        insertion_log_parts.append(f"  删除清理后变空的段落 {len(paras_to_delete)} 个...")
                        for para_rng in reversed(paras_to_delete):  # 从末尾向起始位置删除
                            try:
                                para_rng.Delete()
                            except Exception as e:
                                insertion_log_parts.append(f"    警告: 无法删除段落: {e}")
                    
                    insertion_log_parts.append(f"  步骤5.2完成：清理 {cleaned_count} 段，删除 {len(paras_to_delete)} 个空段。")
                    
                    # 最终轮：再次检查是否有剩余的空段落
                    insertion_log_parts.append("  步骤5.3：最终检查剩余空段落...")
                    selection.GoTo(wdGoToPage, wdGoToAbsolute, target_page)
                    page_start_final = selection.Start
                    selection.GoTo(wdGoToPage, wdGoToAbsolute, next_page)
                    page_end_final = selection.Start if selection.Information(wdActiveEndPageNumber) == next_page else doc.Content.End
                    page_rng_final = doc.Range(page_start_final, page_end_final)
                    
                    final_empty_deleted = 0
                    paras_final = list(page_rng_final.Paragraphs)
                    for i in range(len(paras_final) - 1, -1, -1):
                        try:
                            para = paras_final[i]
                            
                            # 跳过表格中的段落
                            if para.Range.Information(wdWithInTable):
                                continue

                            para_text = para.Range.Text.strip()
                            
                            # Check if paragraph is protected
                            is_protected = False
                            for keyword in protected_keywords:
                                if keyword in para_text:
                                    is_protected = True
                                    break
                            
                            if not is_protected:
                                raw_text = para.Range.Text
                                raw_text_no_mark = raw_text.rstrip("\r\n")
                                raw_cleaned = raw_text_no_mark.replace("\r", "").replace("\n", "").replace(" ", "").replace("\t", "").replace("\u00A0", "").strip()
                                
                                if len(raw_cleaned) == 0:
                                    try:
                                        para.Range.Delete()
                                        final_empty_deleted += 1
                                    except:
                                        pass
                        except:
                            pass
                    
                    if final_empty_deleted > 0:
                        insertion_log_parts.append(f"  步骤5.3完成：删除剩余空段 {final_empty_deleted} 个。")
                    else:
                        insertion_log_parts.append("  步骤5.3完成：未发现剩余空段。")
                    
                    insertion_log_parts.append("步骤5完成：已清理可编辑内容中的空段落与多余换行。")
                    insertion_log_parts.append("内容处理成功。")
            
            doc.Save()
            insertion_log_parts.append("文档已保存。")

        except Exception as e:
            error_msg = f"Word 处理过程中出错: {e}"
            insertion_log_parts.append(error_msg)
            raise
        finally:
            # 使用统一的工具函数关闭 Word 应用程序
            close_word_application(
                word_app=word,
                doc=doc,
                com_initialized=com_initialized,
                wait_time=0.0,  # 不需要额外等待
                node_name="update_word"
            )
    
    except Exception as e:
        error_msg = f"初始化 Word COM 时出错: {e}"
        insertion_log_parts.append(error_msg)
        raise
    
    # 使用插入日志更新状态
    new_state_dict = dict(state)
    insertion_log = "; ".join(insertion_log_parts)
    new_state_dict["insertion_log"] = insertion_log
    new_state = XjcgTenderGraphState(**new_state_dict)
    
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
