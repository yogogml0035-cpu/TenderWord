"""
Word 文档提取工具函数
提供统一的 Word 文档内容提取功能，包括上标/下标识别、表格提取、自动编号保留等
"""

import re
import pathlib
import time

from util.word_application_util import (
    create_word_application,
    close_word_application,
    open_document_with_retry,
)


# Unicode 上标和下标字符映射表
SUPERSCRIPT_MAP = {
    '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
    '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
    '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾',
    'n': 'ⁿ', 'i': 'ⁱ',
}

SUBSCRIPT_MAP = {
    '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
    '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
    '+': '₊', '-': '₋', '=': '₌', '(': '₍', ')': '₎',
    'a': 'ₐ', 'e': 'ₑ', 'o': 'ₒ', 'x': 'ₓ',
}


def extract_text_from_xml(xml_content, preserve_structure=False):
    """
    从 WordOpenXML 解析文本，识别上标/下标（支持 vertAlign 和 position）
    
    Args:
        xml_content: Word XML 内容字符串
        preserve_structure: 是否保留文档结构（段落换行、表格等）
                          True: 保留段落边界的换行符，适用于提取整个文档
                          False: 不保留换行，适用于提取单个单元格或段落内的文本
    
    Returns:
        str: 提取的文本，上标/下标字符已转换为Unicode上标/下标字符
    """
    try:
        # 简单的 XML 实体解码
        def _xml_unescape(text):
            return text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("&quot;", '"').replace("&apos;", "'")
        
        def _process_run(run_content, align_pattern, position_pattern, text_pattern):
            """处理单个 run，返回处理后的文本"""
            # --- 判别上标/下标 ---
            is_superscript = False
            is_subscript = False
            
            # 检查 vertAlign
            align_match = align_pattern.search(run_content)
            if align_match:
                val = align_match.group(1)
                if val == 'superscript':
                    is_superscript = True
                elif val == 'subscript':
                    is_subscript = True
            
            # 如果没有 vertAlign，检查 position
            if not is_superscript and not is_subscript:
                pos_match = position_pattern.search(run_content)
                if pos_match:
                    try:
                        # 单位是半磅 (1/144 英寸)
                        val = int(pos_match.group(1))
                        if val >= 4:  # 偏移 >= 2磅 视为上标
                            is_superscript = True
                        elif val <= -4: # 偏移 <= -2磅 视为下标
                            is_subscript = True
                    except:
                        pass
            
            # --- 提取文本并转换 ---
            run_texts = []
            text_matches = text_pattern.finditer(run_content)
            for tm in text_matches:
                raw_text = tm.group(1)
                text = _xml_unescape(raw_text)
                
                if is_superscript:
                    converted = []
                    for char in text:
                        converted.append(SUPERSCRIPT_MAP.get(char, char))
                    run_texts.append("".join(converted))
                elif is_subscript:
                    converted = []
                    for char in text:
                        converted.append(SUBSCRIPT_MAP.get(char, char))
                    run_texts.append("".join(converted))
                else:
                    run_texts.append(text)
            
            return "".join(run_texts)

        # 查找所有的 run (<w:r>...</w:r>)
        # 使用 DOTALL 模式让 . 匹配换行符
        run_pattern = re.compile(r'<w:r\b[^>]*>(.*?)</w:r>', re.DOTALL)
        
        # 1. 查找标准上标/下标属性 <w:vertAlign w:val="superscript"/>
        align_pattern = re.compile(r'<w:vertAlign\s+w:val=["\'](superscript|subscript)["\']\s*/>')
        
        # 2. 查找位置偏移 <w:position w:val="6"/> (val 单位是半磅)
        # 阈值设为 3 (1.5磅)，通常上标偏移量会大于这个值
        position_pattern = re.compile(r'<w:position\s+w:val=["\'](-?\d+)["\']\s*/>')
        
        # 查找文本 <w:t>...</w:t>
        text_pattern = re.compile(r'<w:t\b[^>]*>(.*?)</w:t>', re.DOTALL)

        if not preserve_structure:
            # 原始逻辑：不保留结构，适用于单个段落或单元格
            result = []
            pos = 0
            while True:
                match = run_pattern.search(xml_content, pos)
                if not match:
                    break
                
                run_content = match.group(1)
                pos = match.end()
                
                run_text = _process_run(run_content, align_pattern, position_pattern, text_pattern)
                if run_text:
                    result.append(run_text)
                        
            return "".join(result)
        
        else:
            # 保留结构模式：识别段落边界，保留换行和表格
            # 段落模式 <w:p>...</w:p>
            para_pattern = re.compile(r'<w:p\b[^>]*>(.*?)</w:p>', re.DOTALL)
            # 表格模式 <w:tbl>...</w:tbl>
            table_pattern = re.compile(r'<w:tbl\b[^>]*>(.*?)</w:tbl>', re.DOTALL)
            # 表格行 <w:tr>...</w:tr>
            row_pattern = re.compile(r'<w:tr\b[^>]*>(.*?)</w:tr>', re.DOTALL)
            # 表格单元格 <w:tc>...</w:tc>
            cell_pattern = re.compile(r'<w:tc\b[^>]*>(.*?)</w:tc>', re.DOTALL)
            
            result_parts = []
            
            # 按顺序处理内容：找到所有段落和表格，按位置排序处理
            # 先找出所有段落和表格的位置
            elements = []
            
            for match in para_pattern.finditer(xml_content):
                # 检查这个段落是否在表格内（如果在 <w:tbl> 和 </w:tbl> 之间则跳过）
                para_start = match.start()
                # 简单检查：往前找最近的 <w:tbl 和 </w:tbl>
                before_content = xml_content[:para_start]
                last_tbl_open = before_content.rfind('<w:tbl')
                last_tbl_close = before_content.rfind('</w:tbl>')
                # 如果最近的 <w:tbl 比 </w:tbl> 更靠后，说明在表格内
                if last_tbl_open > last_tbl_close:
                    continue  # 跳过表格内的段落，由表格处理
                elements.append(('para', match.start(), match.group(1)))
            
            for match in table_pattern.finditer(xml_content):
                elements.append(('table', match.start(), match.group(1)))
            
            # 按位置排序
            elements.sort(key=lambda x: x[1])
            
            for elem_type, _, content in elements:
                if elem_type == 'para':
                    # 处理段落：提取所有 run 中的文本
                    para_texts = []
                    for run_match in run_pattern.finditer(content):
                        run_content = run_match.group(1)
                        run_text = _process_run(run_content, align_pattern, position_pattern, text_pattern)
                        if run_text:
                            para_texts.append(run_text)
                    
                    para_text = "".join(para_texts)
                    if para_text.strip():  # 只添加非空段落
                        result_parts.append(para_text)
                
                elif elem_type == 'table':
                    # 处理表格：转换为 Markdown 格式
                    table_rows = []
                    for row_match in row_pattern.finditer(content):
                        row_content = row_match.group(1)
                        row_cells = []
                        for cell_match in cell_pattern.finditer(row_content):
                            cell_content = cell_match.group(1)
                            # 提取单元格中所有段落的文本
                            cell_texts = []
                            for para_match in para_pattern.finditer(cell_content):
                                para_content = para_match.group(1)
                                para_texts = []
                                for run_match in run_pattern.finditer(para_content):
                                    run_content = run_match.group(1)
                                    run_text = _process_run(run_content, align_pattern, position_pattern, text_pattern)
                                    if run_text:
                                        para_texts.append(run_text)
                                if para_texts:
                                    cell_texts.append("".join(para_texts))
                            
                            # 单元格内多个段落用空格连接，避免破坏 Markdown 表格
                            cell_text = " ".join(cell_texts).strip()
                            # 转义管道符号
                            cell_text = cell_text.replace('|', '\\|')
                            row_cells.append(cell_text)
                        
                        if row_cells:
                            table_rows.append(row_cells)
                    
                    # 生成 Markdown 表格
                    if table_rows:
                        md_lines = []
                        # 表头
                        header = table_rows[0]
                        md_lines.append("| " + " | ".join(header) + " |")
                        # 分隔行
                        md_lines.append("| " + " | ".join(["---"] * len(header)) + " |")
                        # 数据行
                        for row in table_rows[1:]:
                            # 确保列数一致
                            while len(row) < len(header):
                                row.append("")
                            row = row[:len(header)]
                            md_lines.append("| " + " | ".join(row) + " |")
                        
                        result_parts.append("\n".join(md_lines))
            
            # 用换行符连接所有部分
            return "\n".join(result_parts)
    
    except Exception as e:
        print(f"    XML 解析失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def extract_text_with_superscript_subscript(range_obj):
    """
    提取WPS/Word范围中的文本，保留上标和下标格式
    
    优先使用 WordOpenXML 提取（支持 vertAlign 和 position 偏移），
    如果 XML 提取失败则回退到逐字符遍历方式。
    
    Args:
        range_obj: WPS/Word Range对象
        
    Returns:
        str: 提取的文本，上标/下标字符已转换为Unicode上标/下标字符
    """
    # 策略1: 优先尝试通过 WordOpenXML 提取
    try:
        xml_content = None
        try:
            # 尝试获取 XML，如果 COM 不支持会报错
            xml_content = range_obj.WordOpenXML
        except:
            pass
            
        if xml_content and isinstance(xml_content, str) and len(xml_content) > 0:
            xml_text = extract_text_from_xml(xml_content)
            if xml_text is not None:
                return xml_text
    except Exception as e:
        print(f"    WordOpenXML 提取异常，回退到逐字符遍历: {e}")

    # 策略2: 回退到逐字符遍历 (增强版，支持位置偏移检测)
    try:
        result = []
        characters = range_obj.Characters
        char_count = characters.Count
        
        # 遍历每个字符
        for i in range(1, char_count + 1):
            try:
                char = characters(i)
                char_text = char.Text
                font = char.Font
                
                # 检查是否是上标
                is_superscript = False
                is_subscript = False
                
                # 检查上标 (包括标准上标属性和位置偏移)
                try:
                    sup_val = font.Superscript
                    # Word COM 返回 -1 或 True 表示上标，0 或 False 表示否
                    # 9999999 (wdUndefined) 表示混合状态，不应视为上标
                    if sup_val == -1 or sup_val == True:
                        is_superscript = True
                    else:
                        # 检查位置偏移 (单位：磅)
                        # 如果没有开启 Superscript，但位置提升了 > 1.5 磅，也视为上标
                        try:
                            pos_val = font.Position
                            if pos_val > 1.5:
                                is_superscript = True
                        except:
                            pass
                except:
                    pass
                
                # 检查下标
                try:
                    sub_val = font.Subscript
                    if sub_val == -1 or sub_val == True:
                        is_subscript = True
                    elif not is_superscript:
                        # 检查位置偏移 (负值表示下移)
                        try:
                            pos_val = font.Position
                            if pos_val < -1.5:
                                is_subscript = True
                        except:
                            pass
                except:
                    pass
                
                # 根据上标/下标状态转换字符
                if is_superscript and char_text in SUPERSCRIPT_MAP:
                    result.append(SUPERSCRIPT_MAP[char_text])
                elif is_subscript and char_text in SUBSCRIPT_MAP:
                    result.append(SUBSCRIPT_MAP[char_text])
                else:
                    result.append(char_text)
                    
            except Exception as char_e:
                # 如果处理某个字符失败，尝试获取原始文本
                try:
                    result.append(characters(i).Text)
                except:
                    pass
        
        return ''.join(result)
        
    except Exception as e:
        # 最终回退
        print(f"    提取带上标/下标文本时出错: {e}")
        try:
            return range_obj.Text
        except:
            return ""


def extract_table_as_text(table):
    """
    提取WPS/Word表格，转换为Markdown表格格式，便于大模型理解表格结构
    
    Args:
        table: WPS/Word表格对象
        
    Returns:
        str: Markdown格式的表格文本
    """
    try:
        rows_count = table.Rows.Count
        cols_count = table.Columns.Count
        
        if rows_count == 0 or cols_count == 0:
            return table.Range.Text
        
        # 提取所有单元格内容
        table_data = []
        for row_idx in range(1, rows_count + 1):
            row_data = []
            for col_idx in range(1, cols_count + 1):
                try:
                    cell = table.Cell(row_idx, col_idx)
                    # 使用上标/下标提取函数保留科学计数法等格式
                    cell_text = extract_text_with_superscript_subscript(cell.Range)
                    # 清理单元格文本：移除末尾的特殊字符（\r\x07）并清理空白
                    cell_text = cell_text.rstrip('\r\x07\n').strip()
                    # 将换行符替换为空格，避免破坏Markdown表格格式
                    cell_text = cell_text.replace('\r', ' ').replace('\n', ' ')
                    # 转义管道符号，避免破坏表格结构
                    cell_text = cell_text.replace('|', '\\|')
                    row_data.append(cell_text)
                except Exception as cell_e:
                    # 某些合并单元格可能无法访问，填充空字符串
                    row_data.append("")
            table_data.append(row_data)
        
        if not table_data:
            return extract_text_with_superscript_subscript(table.Range)
        
        # 构建Markdown表格
        markdown_lines = []
        
        # 表头行
        header_row = table_data[0]
        markdown_lines.append("| " + " | ".join(header_row) + " |")
        
        # 分隔行
        separator = "| " + " | ".join(["---"] * len(header_row)) + " |"
        markdown_lines.append(separator)
        
        # 数据行
        for row_data in table_data[1:]:
            # 确保每行列数与表头一致
            while len(row_data) < len(header_row):
                row_data.append("")
            row_data = row_data[:len(header_row)]  # 截断多余的列
            markdown_lines.append("| " + " | ".join(row_data) + " |")
        
        return "\n".join(markdown_lines)
        
    except Exception as e:
        print(f"    提取表格时出错: {e}")
        import traceback
        traceback.print_exc()
        # 如果出错，回退到原始文本提取
        try:
            return extract_text_with_superscript_subscript(table.Range)
        except:
            return ""


def extract_text_with_list_numbers(range_obj):
    """
    提取WPS/Word范围中的文本，保留自动编号
    
    Args:
        range_obj: WPS/Word Range对象
        
    Returns:
        str: 提取的文本，包含自动编号
    """
    try:
        result_lines = []
        paragraphs = []
        
        # 尝试多种方法获取段落列表（增强的错误处理）
        try:
            # 方法1: 直接转换为列表（适用于某些 Range 对象）
            paragraphs = list(range_obj.Paragraphs)
        except Exception as e1:
            # 方法2: 使用索引访问（适用于不支持枚举的 Range 对象）
            try:
                para_count = range_obj.Paragraphs.Count
                for i in range(1, para_count + 1):
                    try:
                        para = range_obj.Paragraphs(i)
                        paragraphs.append(para)
                    except:
                        pass
            except Exception as e2:
                # 方法3: 尝试直接迭代（某些情况下可能有效）
                try:
                    for para in range_obj.Paragraphs:
                        paragraphs.append(para)
                except Exception as e3:
                    # 所有方法都失败，使用直接文本提取
                    # 检查是否是对象删除错误
                    error_msgs = [str(e1), str(e2), str(e3)]
                    has_deleted_error = any("对象已被删除" in str(e) or "无效指针" in str(e) or "-2147467261" in str(e) or "-2147352567" in str(e) for e in error_msgs)
                    
                    if has_deleted_error:
                        print(f"    检测到对象失效，使用直接文本提取")
                    else:
                        print(f"    无法获取段落列表，使用直接文本提取: {e1}, {e2}, {e3}")
                    
                    try:
                        # 尝试使用上标/下标提取
                        text = extract_text_with_superscript_subscript(range_obj)
                        if text:
                            return text
                    except Exception as text_e:
                        print(f"    直接文本提取也失败: {text_e}")
                        return ""
                    return ""
        
        for para in paragraphs:
            try:
                # 检查段落对象是否有效
                try:
                    para_range = para.Range
                except Exception as para_check:
                    # 如果段落对象已失效，跳过
                    if "对象已被删除" in str(para_check) or "无效指针" in str(para_check):
                        continue
                    raise
                
                # 检查是否有自动编号
                list_format = para_range.ListFormat
                has_list = False
                list_string = ""
                
                try:
                    # 尝试获取列表类型（如果ListType > 0，说明有自动编号）
                    list_type = list_format.ListType
                    if list_type > 0:
                        has_list = True
                        # 获取编号文本（如"1."、"1.1"等）
                        try:
                            list_string = list_format.ListString
                        except:
                            # 如果获取ListString失败，尝试其他方法
                            try:
                                # 某些版本可能使用ListValue
                                list_string = str(list_format.ListValue) + "."
                            except:
                                list_string = ""
                except:
                    # 如果无法获取ListType，尝试直接获取ListString
                    try:
                        list_string = list_format.ListString
                        if list_string:
                            has_list = True
                    except:
                        pass
                
                # 获取段落文本，保留原始内容和上标/下标格式
                para_text = extract_text_with_superscript_subscript(para_range)
                
                if para_text:
                    # 获取原文档中段落的实际文本，以保留换行格式
                    try:
                        original_para_text = para_range.Text
                        # 检查原文档段落末尾是否有换行符（通常是 \r）
                        has_trailing_newline = original_para_text.endswith('\r') or original_para_text.endswith('\n')
                        # 清理特殊控制字符
                        para_text_clean = para_text.replace('\x07', '')
                        # 如果原文档有换行符，但提取的文本没有，则添加
                        if has_trailing_newline and not (para_text_clean.endswith('\r') or para_text_clean.endswith('\n')):
                            # 使用原文档的换行符格式
                            if original_para_text.endswith('\r\n'):
                                para_text_clean += '\r\n'
                            elif original_para_text.endswith('\r'):
                                para_text_clean += '\r'
                            elif original_para_text.endswith('\n'):
                                para_text_clean += '\n'
                    except:
                        # 如果无法获取原文档文本，只清理特殊字符
                        para_text_clean = para_text.replace('\x07', '')
                    
                    if has_list and list_string:
                        # 如果有自动编号，将编号添加到文本前
                        # 检查文本开头是否已经包含编号（避免重复）
                        # 去除编号字符串两端的空格（编号本身不应该有前后空格）
                        list_string_clean = list_string.strip()
                        # 检查去除前导空白后的文本是否以编号开头
                        para_text_stripped = para_text_clean.lstrip()
                        if para_text_stripped and para_text_stripped.startswith(list_string_clean):
                            # 文本已经包含编号，直接使用原始文本（保留所有格式包括换行）
                            result_lines.append(para_text_clean)
                        else:
                            # 文本不包含编号，添加编号
                            result_lines.append(list_string_clean + " " + para_text_clean)
                    else:
                        # 没有自动编号，直接添加原始文本（保留所有格式包括换行）
                        result_lines.append(para_text_clean)
                        
            except Exception as para_e:
                # 如果处理某个段落失败，回退到直接提取文本（带上标/下标）
                # 检查是否是对象删除错误
                if "对象已被删除" in str(para_e) or "无效指针" in str(para_e):
                    # 对象已失效，跳过这个段落
                    continue
                try:
                    para_text = extract_text_with_superscript_subscript(para.Range)
                    if para_text:
                        result_lines.append(para_text)
                except:
                    # 如果连文本都无法获取，跳过这个段落
                    pass
        
        # 如果没有提取到任何内容，回退到直接提取文本（带上标/下标）
        if not result_lines:
            return extract_text_with_superscript_subscript(range_obj)
        
        # 直接连接所有段落文本，保留原文档的实际格式（包括换行符）
        # 不统一添加换行，让原文档的格式自然保留
        return ''.join(result_lines)
        
    except Exception as e:
        print(f"    提取带编号文本时出错: {e}")
        import traceback
        traceback.print_exc()
        # 如果出错，回退到带上标/下标的文本提取
        try:
            return extract_text_with_superscript_subscript(range_obj)
        except:
            # 如果连文本都无法获取，返回空字符串
            print("    警告: 无法提取任何文本内容")
            return ""


def extract_content_with_tables(range_obj):
    """
    提取WPS/Word范围中的内容，包括表格，保留表格格式和自动编号
    
    Args:
        range_obj: WPS/Word Range对象
        
    Returns:
        str: 提取的内容，表格已格式化，自动编号已保留
    """
    try:
        # 获取范围内的所有表格（增强的错误处理）
        tables = []
        try:
            # 方法1: 直接转换为列表
            tables = list(range_obj.Tables)
        except Exception as e1:
            # 方法2: 使用索引访问
            try:
                table_count = range_obj.Tables.Count
                for i in range(1, table_count + 1):
                    try:
                        table = range_obj.Tables(i)
                        tables.append(table)
                    except:
                        pass
            except Exception as e2:
                # 方法3: 尝试直接迭代
                try:
                    for table in range_obj.Tables:
                        tables.append(table)
                except Exception as e3:
                    # 所有方法都失败，回退到文本提取
                    print(f"    无法获取表格列表，使用文本提取: {e1}, {e2}, {e3}")
                    try:
                        return extract_text_with_list_numbers(range_obj)
                    except:
                        try:
                            return range_obj.Text
                        except:
                            return ""
        
        if not tables:
            # 没有表格，使用带自动编号的文本提取
            return extract_text_with_list_numbers(range_obj)
        
        # 获取范围的起始和结束位置
        start_pos = range_obj.Start
        end_pos = range_obj.End
        
        # 按位置排序表格
        sorted_tables = sorted(tables, key=lambda t: t.Range.Start)
        
        result_parts = []
        current_pos = start_pos
        
        # 遍历所有表格和文本内容
        for table in sorted_tables:
            table_start = table.Range.Start
            table_end = table.Range.End
            
            # 检查表格是否与范围有交集（表格可能部分在范围内）
            if table_end > start_pos and table_start < end_pos:
                # 提取表格前的文本（只提取在当前范围内且表格之前的部分）
                text_start = max(current_pos, start_pos)
                text_end = min(table_start, end_pos)
                
                if text_end > text_start:
                    text_before = range_obj.Document.Range(text_start, text_end)
                    # 使用带自动编号的文本提取函数
                    text_content = extract_text_with_list_numbers(text_before)
                    if text_content:
                        result_parts.append(text_content)
                
                # 提取表格（只提取在范围内的部分）
                if table_start >= start_pos and table_end <= end_pos:
                    # 表格完全在范围内
                    table_text = extract_table_as_text(table)
                    if table_text:
                        result_parts.append(table_text)
                else:
                    # 表格部分在范围内，提取表格的格式化文本
                    table_text = extract_table_as_text(table)
                    if table_text:
                        result_parts.append(table_text)
                
                current_pos = max(current_pos, table_end)
        
        # 提取最后一个表格后的文本
        text_start = max(current_pos, start_pos)
        text_end = end_pos
        if text_end > text_start:
            text_after = range_obj.Document.Range(text_start, text_end)
            # 使用带自动编号的文本提取函数
            text_content = extract_text_with_list_numbers(text_after)
            if text_content:
                result_parts.append(text_content)
        
        # 如果没有提取到任何内容，回退到带编号的文本提取
        if not result_parts:
            return extract_text_with_list_numbers(range_obj)
        
        # 直接连接各部分，保留原文档的实际格式
        # 不添加额外的换行符，让原文档的格式自然保留
        return ''.join(result_parts)
        
    except Exception as e:
        print(f"    提取内容（含表格）时出错: {e}")
        import traceback
        traceback.print_exc()
        # 如果出错，回退到带编号的文本提取
        try:
            return extract_text_with_list_numbers(range_obj)
        except:
            # 如果带编号提取也失败，使用带上标/下标的文本作为最后回退
            try:
                return extract_text_with_superscript_subscript(range_obj)
            except:
                # 如果连文本都无法获取，返回空字符串
                print("    警告: 无法提取任何内容")
                return ""


def extract_text_from_word_file(file_path: str) -> str:
    """从 Word 文件中提取所有文本内容，包括表格和自动编号"""
    file_path_obj = pathlib.Path(file_path)
    
    # 检查文件是否存在
    if not file_path_obj.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    # 根据文件扩展名选择不同的读取方式
    # 注意：.docx 和 .doc 都使用 win32com 读取，以便正确提取自动编号
    if file_path_obj.suffix.lower() in (".docx", ".doc"):
        # 对于 .docx 和 .doc 文件，使用 win32com（需要 Windows 环境）
        # 使用 extract_content_with_tables 来提取内容，保留表格格式和自动编号
        word = None
        doc = None
        com_initialized = False
        
        try:
            # 使用统一的工具函数创建 Word 应用程序
            word, com_initialized = create_word_application(
                initial_delay=2.0,  # 首次尝试前等待，确保上一个节点完全关闭
                post_init_delay=0.5,  # 给 Word 时间初始化
                use_existing=False,  # 并发环境下必须使用独立实例
                verify=False,
                node_name="word_extraction"
            )
            
            # 使用统一的工具函数打开文档（带重试机制）
            doc = open_document_with_retry(
                word_app=word,
                file_path=str(file_path_obj.resolve()),
                read_only=True,
                node_name="word_extraction"
            )
            
            # 使用 extract_content_with_tables 提取内容，保留表格格式和自动编号
            content_range = doc.Content
            document_text = extract_content_with_tables(content_range)
            return document_text
            
        except ImportError:
            raise ValueError("读取 Word 文件需要 pywin32 库，且只能在 Windows 环境下运行")
        except Exception as e:
            raise ValueError(f"读取 Word 文件失败: {e}")
        finally:
            # 使用统一的工具函数关闭 Word 应用程序
            close_word_application(
                word_app=word,
                doc=doc,
                com_initialized=com_initialized,
                wait_time=0.0,
                node_name="word_extraction"
            )
    else:
        raise ValueError(f"不支持的文件格式: {file_path_obj.suffix}")

