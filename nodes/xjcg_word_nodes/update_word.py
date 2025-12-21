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

from logging_utils import log_state
from state import XjcgTenderGraphState
from util.word_application_util import (
    create_word_application,
    close_word_application,
    open_document_with_retry,
    save_document_with_retry,
)
from util.word_com_manager import com_lock, is_rpc_error, calculate_retry_delay, MAX_RETRIES

# Word constants
wdGoToPage = 1
wdGoToAbsolute = 1
wdLineSpace1pt5 = 1
wdOutlineLevelBodyText = 10
wdCollapseStart = 1
wdCollapseEnd = 0
wdActiveEndPageNumber = 3
wdFindStop = 0
wdWithInTable = 12


def update_word(state: XjcgTenderGraphState, config) -> XjcgTenderGraphState:
    start_time = time.perf_counter()
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
    
    # 将 polished_text 拆分为内容列表（按行）
    content_list = [line.strip() for line in polished_text.split("\n") if line.strip()]
    
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
            open_attempts = 3
            last_error = None
            for attempt in range(1, open_attempts + 1):
                try:
                    doc = word.Documents.Open(
                        FileName=prepared_doc_path,
                        ConfirmConversions=False,
                        ReadOnly=False,
                        AddToRecentFiles=False,
                        NoEncodingDialog=True
                    )
                    break
                except Exception as e:
                    last_error = e
                    if attempt < open_attempts:
                        time.sleep(1.0)
                    else:
                        raise
            insertion_log_parts.append(f"已打开文档: {prepared_doc_path}")
            
            # 如果需要，尝试取消保护
            if doc.ProtectionType != -1:
                try:
                    doc.Unprotect()
                    insertion_log_parts.append("已取消文档保护")
                except:
                    pass

            # 优先使用 extract_tender_params 已计算好的页范围，避免重复查找
            start_page = state.get("start_page")
            end_page = state.get("end_page")

            if start_page is None or end_page is None:
                # 回退到自身查找
                def _find_anchor_page(anchor_text: str) -> Optional[int]:
                    search_rng = doc.Content.Duplicate
                    find = search_rng.Find
                    find.ClearFormatting()
                    find.Text = anchor_text
                    find.Forward = True
                    find.Wrap = wdFindStop
                    find.MatchCase = False
                    find.MatchWholeWord = False
                    while find.Execute():
                        font_name = search_rng.Font.Name
                        font_size = search_rng.Font.Size
                        is_font = font_name in ("宋体", "SimSun")
                        is_size = abs(font_size - 18.0) < 0.5
                        if is_font and is_size:
                            return search_rng.Information(wdActiveEndPageNumber)
                        search_rng.Collapse(wdCollapseEnd)
                        search_rng.End = doc.Content.End
                    return None

                before_page = _find_anchor_page(insertion_before_text)
                after_page = _find_anchor_page(insertion_after_text)
                insertion_log_parts.append(f"前置锚点 '{insertion_before_text}' 所在页: {before_page}")
                insertion_log_parts.append(f"后置锚点 '{insertion_after_text}' 所在页: {after_page}")

                if before_page is None or after_page is None:
                    raise ValueError("未找到前后锚点（需宋体/SimSun 且 18pt）")
                if after_page <= before_page:
                    raise ValueError(f"后置锚点页码({after_page}) 不大于前置锚点页码({before_page})")

                start_page = before_page + 1
                end_page = after_page - 1
                insertion_log_parts.append(f"回退计算页范围: {start_page} - {end_page}")
            else:
                insertion_log_parts.append(f"使用预计算页范围: {start_page} - {end_page}")

            if start_page is None or end_page is None:
                raise ValueError("无法确定插入页范围")
            if end_page < start_page:
                raise ValueError(f"插入页范围非法: {start_page} - {end_page}")

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
                
                # Find indices of protected fields in content_list (找最先出现的)
                delivery_date_idx = None
                payment_method_idx = None
                
                for i, line in enumerate(content_list):
                    if delivery_date_idx is None and "交付日期" in line:
                        delivery_date_idx = i
                    if payment_method_idx is None and "付款方式" in line:
                        payment_method_idx = i
                    # 如果两个都找到了，提前退出循环
                    if delivery_date_idx is not None and payment_method_idx is not None:
                        break
                
                # Split into three blocks
                block1 = content_list[:delivery_date_idx] if delivery_date_idx is not None else []
                block2 = content_list[delivery_date_idx:payment_method_idx] if payment_method_idx is not None else content_list[delivery_date_idx:] if delivery_date_idx is not None else []
                block3 = content_list[payment_method_idx+1:] if payment_method_idx is not None else []
                
                delivery_date_line = content_list[delivery_date_idx] if delivery_date_idx is not None else None
                payment_method_line = content_list[payment_method_idx] if payment_method_idx is not None else None
                
                insertion_log_parts.append(f"  块1: {len(block1)} 条（交付日期之前）")
                insertion_log_parts.append(f"  块2: {len(block2)} 条（交付日期区段）")
                insertion_log_parts.append(f"  块3: {len(block3)} 条（付款方式之后）")
                
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
                page_end_after = selection.Start if selection.Information(wdActiveEndPageNumber) == next_page else doc.Content.End
                page_rng_after = doc.Range(page_start_after, page_end_after)
                
                # 格式设置
                insert_font_name = "宋体"
                insert_font_size = 12

                # 检测 Markdown 风格的表格（以 '|' 开头，后跟分隔符行）
                def is_table_separator_line(line: str) -> bool:
                    return bool(re.match(r"^\s*\|\s*:?-{3,}.*\|\s*$", line))

                def parse_table_block(lines, start_idx):
                    """解析连续的 Markdown 表格行为行，并返回行和下一个索引。"""
                    table_lines = []
                    i = start_idx
                    while i < len(lines) and lines[i].strip().startswith("|"):
                        table_lines.append(lines[i].strip())
                        i += 1

                    if len(table_lines) < 2:
                        return None, start_idx

                    header = table_lines[0]
                    separator = table_lines[1]

                    if not is_table_separator_line(separator):
                        return None, start_idx

                    data_lines = table_lines[2:] if len(table_lines) > 2 else []
                    all_lines = [header] + data_lines

                    rows = []
                    for line in all_lines:
                        # 按 '|' 分割并去除空边缘
                        cells = [cell.strip() for cell in line.split("|")]
                        if cells and cells[0] == "":
                            cells = cells[1:]
                        if cells and cells[-1] == "":
                            cells = cells[:-1]
                        rows.append(cells)

                    return rows, i

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
                def update_protected_field(keyword, new_value):
                    if keyword not in protected_fields:
                        return False
                    
                    para_rng = protected_fields[keyword]
                    para_text = para_rng.Text.strip()
                    
                    if "：" in para_text:
                        colon_pos = para_text.find("：")
                        if colon_pos >= 0:
                            try:
                                value_start = para_rng.Start + colon_pos + 1
                                value_end = para_rng.End - 1  # 排除段落标记
                                value_rng = doc.Range(value_start, value_end)
                                
                                # 从值中移除换行符
                                new_value_clean = new_value.replace("\r", "").replace("\n", "").strip()
                                value_rng.Text = new_value_clean
                                value_rng.Font.Name = insert_font_name
                                value_rng.Font.Size = insert_font_size
                                
                                insertion_log_parts.append(f"  已更新受保护字段 '{keyword}': {new_value_clean[:50]}...")
                                return True
                            except Exception as e:
                                insertion_log_parts.append(f"  警告: 无法更新 '{keyword}': {e}")
                                return False
                    return False
                    
                # 插入块1（在交付日期之前）
                insertion_log_parts.append("  正在插入块1...")
                selection.GoTo(wdGoToPage, wdGoToAbsolute, target_page)
                insert_rng = selection.Range
                insert_rng.Collapse(wdCollapseStart)
                
                # 如果交付日期字段存在，在其之前插入
                if "交付日期" in protected_fields:
                    delivery_date_rng = protected_fields["交付日期"]
                    insert_rng.Start = delivery_date_rng.Start
                    insert_rng.End = delivery_date_rng.Start
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
                
                # Update 交付日期 field value
                if delivery_date_line and "交付日期" in protected_fields:
                    if "：" in delivery_date_line:
                        new_value = delivery_date_line.split("：", 1)[1]
                        update_protected_field("交付日期", new_value)
                    
                    # 插入块2（在交付日期和付款方式之间）
                    insertion_log_parts.append("  插入块2...")
                    if "交付日期" in protected_fields and "付款方式" in protected_fields:
                        delivery_date_rng = protected_fields["交付日期"]
                        payment_method_rng = protected_fields["付款方式"]
                        
                        # 在交付日期字段之后、付款方式字段之前插入
                        insert_rng.Start = delivery_date_rng.End
                        insert_rng.End = payment_method_rng.Start
                        insert_rng.Collapse(wdCollapseStart)
                        
                        # 插入块2内容（排除交付日期行本身）
                        block2_items = convert_lines_to_items(block2[1:])  # 跳过第一行（交付日期行）
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
                        insert_rng.Start = delivery_date_rng.End
                        insert_rng.End = delivery_date_rng.End
                        insert_rng.Collapse(wdCollapseStart)
                        
                        block2_items = convert_lines_to_items(block2[1:])
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
                    
                    # Update 付款方式 field value
                    if payment_method_line and "付款方式" in protected_fields:
                        if "：" in payment_method_line:
                            new_value = payment_method_line.split("：", 1)[1]
                            update_protected_field("付款方式", new_value)
                    
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
                        payment_method_rng = protected_fields["付款方式"]
                        insert_rng.Start = payment_method_rng.End
                        insert_rng.End = payment_method_rng.End
                        insert_rng.Collapse(wdCollapseStart)
                        insertion_log_parts.append(f"    在付款方式字段后插入，位置 {insert_rng.Start}")
                    else:
                        # 如果付款方式不存在，在页面末尾插入
                        selection.GoTo(wdGoToPage, wdGoToAbsolute, target_page)
                        insert_rng = selection.Range
                        insert_rng.Collapse(wdCollapseEnd)
                        insertion_log_parts.append(f"    未找到付款方式字段，插入到页面末尾，位置 {insert_rng.Start}")
                    
                    inserted_count = 0
                    for item in block3_items:
                        try:
                            if item["type"] == "text":
                                inserted_rng = insert_content_with_formatting(insert_rng, item["line"])
                                inserted_count += 1
                                insertion_log_parts.append(f"    [{inserted_count}/{len(block3_items)}] 已插入: {item['line'][:50]}...")
                            elif item["type"] == "table":
                                insert_table_with_formatting(insert_rng, item["rows"])
                                inserted_count += 1
                                insertion_log_parts.append(f"    [{inserted_count}/{len(block3_items)}] 已插入表格，行数 {len(item['rows'])}。")
                        except Exception as e:
                            insertion_log_parts.append(f"    插入项出错: {e}")
                    
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
    log_state("update_word", new_state)
    
    duration = time.perf_counter() - start_time
    duration_ms = duration * 1000
    print(f"[update_word] 执行完成，耗时: {duration:.2f} 秒 ({duration_ms:.0f} 毫秒)")
    return new_state
