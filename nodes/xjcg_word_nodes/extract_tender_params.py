from __future__ import annotations

import os
import time
import pythoncom
import win32com.client as win32

# 处理相对导入和直接运行的情况
try:
    from ...logging_utils import log_state
    from ...state import TenderGraphState
except ImportError:
    # 直接运行时使用绝对导入
    import pathlib
    import sys

    # 先尝试直接导入（假设 TenderWord/ 目录已在 sys.path 中）
    try:
        from logging_utils import log_state
        from state import TenderGraphState
    except ImportError:
        # 如果失败，添加项目根目录到 sys.path
        ROOT = pathlib.Path(__file__).resolve().parents[2]
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        # 从项目根目录直接导入
        from logging_utils import log_state
        from state import TenderGraphState

# WPS/Word constants (WPS 兼容 Word 的常量)
wdFindStop = 0
wdCollapseEnd = 0
wdGoToPage = 1
wdGoToAbsolute = 1
wdActiveEndPageNumber = 3


def find_wps_progids():
    """
    尝试查找系统中已注册的 WPS COM 对象 ProgID
    
    Returns:
        list: 可能的 WPS ProgID 列表
    """
    # 常见的 WPS ProgID 列表（按优先级排序）
    common_progids = [
        "KWPS.Application",  # WPS 文字的标准 ProgID（最常见）
        "wps.Application",   # 小写版本
        "WPS.Application",   # 大写版本
        "Kingsoft.Application",  # 金山软件
        "ksoapi.Application",  # WPS API
        "Ket.Application",  # WPS 文字（某些版本）
        "Word.Application",  # 兼容 Word（某些 WPS 版本）
    ]
    
    # 尝试通过注册表查找 WPS 相关的 COM 对象
    # 只检查常见的已知路径，避免全表扫描
    try:
        import winreg
        found_progids = []
        
        # 直接检查常见的 WPS ProgID 是否在注册表中
        test_progids = [
            "KWPS.Application",
            "wps.Application", 
            "WPS.Application",
            "Kingsoft.Application",
            "Ket.Application",
            "ksoapi.Application",
            "Word.Application",  # 某些 WPS 版本可能注册为 Word
        ]
        
        for progid in test_progids:
            try:
                # 检查 ProgID 是否存在
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, progid) as key:
                    # 检查是否有 CLSID 子键
                    try:
                        with winreg.OpenKey(key, "CLSID") as clsid_key:
                            clsid_value, _ = winreg.QueryValueEx(clsid_key, "")
                            # 如果 CLSID 存在，说明这个 ProgID 已注册
                            found_progids.append(progid)
                            print(f"[find_wps_progids] 在注册表中找到 ProgID: {progid} (CLSID: {clsid_value})")
                    except Exception:
                        pass
            except FileNotFoundError:
                # ProgID 不存在，跳过
                pass
            except Exception:
                pass
        
        # 尝试扫描注册表查找所有包含 "WPS" 或 "Kingsoft" 的 Application ProgID
        try:
            # 扫描 HKEY_CLASSES_ROOT 下的所有键
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "") as root_key:
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(root_key, i)
                        i += 1
                        
                        # 检查是否是 Application 类型的 ProgID，且包含 WPS 或 Kingsoft
                        if subkey_name.endswith(".Application") and (
                            "wps" in subkey_name.lower() or 
                            "kingsoft" in subkey_name.lower() or
                            "ket" in subkey_name.lower()
                        ):
                            try:
                                # 验证这个 ProgID 是否有效
                                with winreg.OpenKey(root_key, subkey_name) as test_key:
                                    try:
                                        with winreg.OpenKey(test_key, "CLSID") as clsid_key:
                                            clsid_value, _ = winreg.QueryValueEx(clsid_key, "")
                                            if subkey_name not in found_progids:
                                                found_progids.append(subkey_name)
                                                print(f"[find_wps_progids] 扫描注册表发现新的 ProgID: {subkey_name} (CLSID: {clsid_value})")
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                    except OSError:
                        # 枚举结束
                        break
                    except Exception:
                        continue
        except Exception as scan_e:
            print(f"[find_wps_progids] 扫描注册表时出错: {scan_e}")
        
        # 如果找到了已注册的 ProgID，将它们放在列表前面
        if found_progids:
            # 去重并合并：先放找到的，再放其他的
            all_progids = list(dict.fromkeys(found_progids + common_progids))
            print(f"[find_wps_progids] 最终 ProgID 列表: {all_progids}")
            return all_progids
    except Exception as e:
        # 注册表访问失败，使用默认列表
        print(f"[find_wps_progids] 注册表访问失败: {e}")
    
    print(f"[find_wps_progids] 使用默认 ProgID 列表: {common_progids}")
    return common_progids


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


def _extract_text_from_xml(xml_content, preserve_structure=False):
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
        import re
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
            xml_text = _extract_text_from_xml(xml_content)
            if xml_text is not None:
                return xml_text
    except Exception as e:
        print(f"    WordOpenXML 提取异常，回退到逐字符遍历: {e}")

    # 策略2: 回退到逐字符遍历 (增强版)
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
                
                is_superscript = False
                is_subscript = False
                
                # 检查上标 (包括标准上标属性和位置偏移)
                try:
                    sup_val = font.Superscript
                    # 检查是否开启了上标属性 (-1=True, 9999999=Undefined)
                    if sup_val == -1 or sup_val == True:
                        is_superscript = True
                    else:
                        # 检查位置偏移 (单位：磅)
                        # 如果没有开启 Superscript，但位置提升了 > 1.5 磅，也视为上标
                        pos_val = font.Position
                        if pos_val > 1.5:
                            is_superscript = True
                except:
                    pass
                
                # 检查下标
                try:
                    sub_val = font.Subscript
                    if sub_val == -1 or sub_val == True:
                        is_subscript = True
                    else:
                        # 检查位置下沉
                        pos_val = font.Position
                        if pos_val < -1.5:
                            is_subscript = True
                except:
                    pass
                
                # 转换字符
                if is_superscript and char_text in SUPERSCRIPT_MAP:
                    result.append(SUPERSCRIPT_MAP[char_text])
                elif is_subscript and char_text in SUBSCRIPT_MAP:
                    result.append(SUBSCRIPT_MAP[char_text])
                else:
                    result.append(char_text)
                    
            except Exception as char_e:
                # 容错处理
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
            return table.Range.Text
        
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
            return table.Range.Text
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
        paragraphs = list(range_obj.Paragraphs)
        
        for para in paragraphs:
            try:
                # 检查是否有自动编号
                list_format = para.Range.ListFormat
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
                para_text = extract_text_with_superscript_subscript(para.Range)
                
                if para_text:
                    # 获取原文档中段落的实际文本，以保留换行格式
                    try:
                        original_para_text = para.Range.Text
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
                try:
                    para_text = extract_text_with_superscript_subscript(para.Range)
                    if para_text:
                        result_lines.append(para_text)
                except:
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
        return extract_text_with_superscript_subscript(range_obj)


def extract_content_with_tables(range_obj):
    """
    提取WPS/Word范围中的内容，包括表格，保留表格格式和自动编号
    
    Args:
        range_obj: WPS/Word Range对象
        
    Returns:
        str: 提取的内容，表格已格式化，自动编号已保留
    """
    try:
        # 获取范围内的所有表格
        tables = list(range_obj.Tables)
        
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
            return extract_text_with_superscript_subscript(range_obj)


def extract_tender_params(state: TenderGraphState, config) -> TenderGraphState:
    """
    根据前后内容定位插入位置，提取该位置的 WPS/Word 内容并存储到 tender_params 状态中。
    
    从 state 中读取：
    - insertion_before_text: 插入位置的前置文本
    - insertion_after_text: 插入位置的后置文本
    - prepared_doc_path: WPS/Word 文档路径
    
    提取的内容将存储到 state 的 tender_params 字段中。
    """
    start_time = time.time()
    print(f"[extract_tender_params] 开始执行...")
    
    prepared_doc_path = state.get("prepared_doc_path")
    before_text = state.get("insertion_before_text")
    after_text = state.get("insertion_after_text")
    
    if not prepared_doc_path:
        raise ValueError("需要 prepared_doc_path 来提取 WPS/Word 文档中的内容")
    
    if not before_text or not after_text:
        # 如果没有提供前后文本，返回空内容
        print(f"[extract_tender_params] 警告: 未提供 insertion_before_text 或 insertion_after_text，跳过提取")
        new_state_dict = dict(state)
        new_state_dict["tender_params"] = ""
        new_state = TenderGraphState(**new_state_dict)
        log_state("extract_tender_params", new_state)
        return new_state
    
    # 确保路径是绝对路径（WPS/Word COM 对象需要绝对路径）
    if not os.path.isabs(prepared_doc_path):
        prepared_doc_path = os.path.abspath(prepared_doc_path)
    
    # 检查文件是否存在
    if not os.path.exists(prepared_doc_path):
        raise FileNotFoundError(f"未找到准备好的文档: {prepared_doc_path}")
    
    # 检查文件是否可读
    if not os.access(prepared_doc_path, os.R_OK):
        raise PermissionError(f"无法读取准备好的文档: {prepared_doc_path}")
    
    extracted_content = ""
    wps = None
    doc = None
    
    try:
        pythoncom.CoInitialize()

        # 直接使用 Microsoft Word，休眠一定时间让之前的实例完全关闭
        initial_delay = 0.2  # 创建前等待 0.2 秒，让之前的实例有时间完全关闭
        print(f"[extract_tender_params] 等待 {initial_delay} 秒后创建 Microsoft Word 实例...")
        time.sleep(initial_delay)
        
        wps = None
        try:
            import win32com.client as win32client
            
            # 方法1: 尝试获取已运行的 Word 实例
            try:
                wps = win32client.GetActiveObject("Word.Application")
                wps.Visible = False
                wps.DisplayAlerts = 0
                print("[extract_tender_params] 成功获取已运行的 Word 实例")
            except Exception:
                # 方法2: 创建新的 Word 实例
                try:
                    wps = win32client.DispatchEx("Word.Application")
                    wps.Visible = False
                    wps.DisplayAlerts = 0
                    # 给 Word 一点时间完成初始化
                    time.sleep(0.5)
                    print("[extract_tender_params] 成功创建新的 Word 实例 (DispatchEx)")
                except Exception:
                    # 方法3: 使用 EnsureDispatch 作为备选
                    try:
                        wps = win32client.gencache.EnsureDispatch("Word.Application")
                        wps.Visible = False
                        wps.DisplayAlerts = 0
                        time.sleep(0.5)
                        print("[extract_tender_params] 成功创建新的 Word 实例 (EnsureDispatch)")
                    except Exception as e:
                        raise RuntimeError(f"无法创建 Microsoft Word 应用程序实例: {e}")
        except ImportError:
            raise RuntimeError("无法导入 win32com.client，请确保已安装 pywin32")
        
        # 验证 Word 对象是否可用
        try:
            app_name = wps.Name
            print(f"[extract_tender_params] 使用 Microsoft Word (名称: {app_name})")
        except Exception as word_name_e:
            raise RuntimeError(f"Word 实例创建但验证失败: {word_name_e}")

        try:
            # 第一次尝试打开文档（只读模式，因为只需要提取内容）
            doc = wps.Documents.Open(
                FileName=prepared_doc_path,
                ConfirmConversions=False,
                ReadOnly=True,  # 只读模式，只需要提取内容
                AddToRecentFiles=False,
                NoEncodingDialog=True
            )
            print(f"已打开文档: {prepared_doc_path}")
        except Exception as open_error:
            # 参考 get_replacements 的逻辑，针对 COM/RPC 错误做一次重试
            error_code = (
                open_error.args[0]
                if hasattr(open_error, "args") and open_error.args
                else None
            )
            # -2147023174: RPC 服务器不可用
            # -2147023179: 接口未知
            is_com_rpc_error = (
                error_code in (-2147023174, -2147023179)
                or "RPC" in str(open_error)
                or "接口未知" in str(open_error)
            )
            if is_com_rpc_error:
                print("[extract_tender_params] 检测到 COM/RPC 错误，尝试重新创建 Word 应用程序并重试...")
                try:
                    # 关闭旧的 WPS 对象
                    try:
                        if wps is not None:
                            wps.Quit(SaveChanges=False)
                    except Exception:
                        pass

                    # 等待一下，确保进程退出
                    time.sleep(1.0)

                    # 重新创建 Word 应用程序对象
                    try:
                        import win32com.client as win32client
                        try:
                            wps = win32client.GetActiveObject("Word.Application")
                        except Exception:
                            wps = win32client.DispatchEx("Word.Application")
                        wps.Visible = False
                        wps.DisplayAlerts = 0
                        time.sleep(0.5)
                        print("[extract_tender_params] Word 应用程序对象已重新创建，正在重试打开文档...")
                    except Exception as recreate_e:
                        raise RuntimeError(f"无法重新创建 Word 应用程序实例: {recreate_e}")

                    # 重试打开文档（只读模式）
                    doc = wps.Documents.Open(
                        FileName=prepared_doc_path,
                        ConfirmConversions=False,
                        ReadOnly=True,
                        AddToRecentFiles=False,
                        NoEncodingDialog=True
                    )
                    print(f"重试后已打开文档: {prepared_doc_path}")
                    time.sleep(0.2)
                except Exception as retry_error:
                    error_msg = f"重新创建 Word 应用程序后打开文档失败: {retry_error}"
                    print(f"[extract_tender_params] {error_msg}")
                    # 尝试获取更详细的错误信息
                    import traceback
                    print(f"[extract_tender_params] 详细错误信息:")
                    traceback.print_exc()
                    # 确保关闭 Word
                    try:
                        if wps is not None:
                            wps.Quit(SaveChanges=False)
                    except Exception:
                        pass
                    raise
            else:
                # 非 COM 错误，按原逻辑处理
                print(f"[extract_tender_params] 首次打开失败，等待 1 秒重试: {open_error}")
                time.sleep(1.0)
                try:
                    doc = wps.Documents.Open(
                        FileName=prepared_doc_path,
                        ConfirmConversions=False,
                        ReadOnly=True,
                        AddToRecentFiles=False,
                        NoEncodingDialog=True
                    )
                    print(f"重试后已打开文档: {prepared_doc_path}")
                except Exception as retry_error:
                    error_msg = f"打开文档失败: {retry_error}"
                    print(f"[extract_tender_params] {error_msg}")
                    # 尝试获取更详细的错误信息
                    import traceback
                    print(f"[extract_tender_params] 详细错误信息:")
                    traceback.print_exc()
                    raise
        
        # 尝试取消保护（如果需要）
        try:
            protection_type = doc.ProtectionType
            print(f"文档保护类型: {protection_type} (-1 表示无保护)")
            if protection_type != -1:  # -1 表示 wdNoProtection
                try:
                    # 尝试获取密码（如果有的话，这里传空字符串）
                    doc.Unprotect("")
                    print("已取消文档保护")
                except Exception as unprotect_e:
                    print(f"警告: 取消文档保护失败: {unprotect_e}")
                    # 尝试强制取消保护
                    try:
                        doc.ProtectionType = -1
                        print("已强制设置文档为无保护状态")
                    except Exception:
                        pass
        except Exception as prot_e:
            print(f"警告: 检查文档保护时出错: {prot_e}")
        
        # 确保文档可编辑
        try:
            if doc.ProtectContent:
                print("警告: 文档内容仍受保护，尝试强制取消...")
                doc.ProtectContent = False
        except Exception:
            pass
        
        # 在文档正文中查找前后文本，使用字体和字号匹配
        doc_content = doc.Content
        
        # 查找前置文本（使用字体和字号匹配）
        before_page = None
        before_end_pos = None
        find_before_rng = doc_content.Duplicate
        find_before = find_before_rng.Find
        find_before.ClearFormatting()
        find_before.Text = before_text
        find_before.Forward = True
        find_before.Wrap = wdFindStop
        find_before.MatchCase = False
        find_before.MatchWholeWord = False
        
        print(f"正在查找前置文本 '{before_text}'（要求格式：宋体 小二/18pt）...")
        while find_before.Execute():
            # 检查字体和字号
            font_name = find_before_rng.Font.Name
            font_size = find_before_rng.Font.Size
            is_font = (font_name == "宋体" or font_name == "SimSun")
            is_size = abs(font_size - 18.0) < 0.5
            
            if is_font and is_size:
                before_page = find_before_rng.Information(wdActiveEndPageNumber)
                before_end_pos = find_before_rng.End
                print(f"找到前置文本 '{before_text}'，页码: {before_page}，字体: {font_name}，字号: {font_size}pt，位置: {before_end_pos}")
                break
            else:
                # 继续搜索下一个匹配项
                find_before_rng.Collapse(wdCollapseEnd)
                find_before_rng.End = doc_content.End
        
        if before_page is None:
            print(f"警告: 未找到符合格式要求的前置文本 '{before_text}'（宋体 小二/18pt）")
            extracted_content = ""
        else:
            # 将 before_end_pos 调整到前置锚点所在页的下一页起始处，避免第三章内容残留
            try:
                selection = wps.Selection
                selection.GoTo(wdGoToPage, wdGoToAbsolute, before_page + 1)
                next_page_start = selection.Start
                if next_page_start > before_end_pos:
                    before_end_pos = next_page_start
                    print(f"将 before_end_pos 对齐到下一页起始: {before_end_pos}")
            except Exception as adj_e:
                print(f"警告: 无法对齐 before_end_pos 到下一页起始: {adj_e}")
            
            # 查找后置文本（从前置文本之后开始搜索，也使用字体和字号匹配）
            after_page = None
            after_start_pos = None  # 保存后置锚点的起始位置
            # 从前置文本之后开始搜索
            find_after_rng = doc_content.Duplicate
            find_after_rng.Start = before_end_pos
            find_after_rng.End = doc_content.End
            
            find_after = find_after_rng.Find
            find_after.ClearFormatting()
            find_after.Text = after_text
            find_after.Forward = True
            find_after.Wrap = wdFindStop
            find_after.MatchCase = False
            find_after.MatchWholeWord = False
            
            print(f"正在查找后置文本 '{after_text}'（要求格式：宋体 小二/18pt）...")
            while find_after.Execute():
                # 检查字体和字号
                font_name = find_after_rng.Font.Name
                font_size = find_after_rng.Font.Size
                is_font = (font_name == "宋体" or font_name == "SimSun")
                is_size = abs(font_size - 18.0) < 0.5
                
                if is_font and is_size:
                    after_page = find_after_rng.Information(wdActiveEndPageNumber)
                    after_start_pos = find_after_rng.Start  # 保存后置锚点的起始位置
                    after_end_pos = find_after_rng.End  # 保存后置锚点的结束位置（第四章标题的结束位置）
                    print(f"找到后置文本 '{after_text}'，页码: {after_page}，字体: {font_name}，字号: {font_size}pt，起始位置: {after_start_pos}，结束位置: {after_end_pos}")
                    break
                else:
                    # 继续搜索下一个匹配项
                    find_after_rng.Collapse(wdCollapseEnd)
                    find_after_rng.End = doc_content.End
            
            if after_page is None:
                print(f"警告: 未找到符合格式要求的后置文本 '{after_text}'（宋体 小二/18pt）")
                extracted_content = ""
            elif after_page <= before_page:
                print(f"错误: 后置文本页码 ({after_page}) 小于等于前置文本页码 ({before_page})")
                extracted_content = ""
            elif after_start_pos is None or after_end_pos is None:
                print("错误: 未能获取后置文本位置，无法提取/清理内容")
                extracted_content = ""
            else:
                # === 直接基于锚点字符范围提取内容 ===
                if before_end_pos is None:
                    print("错误: 未能获取前置文本结束位置，无法提取内容")
                    extracted_content = ""
                else:
                    # 提取两个锚点之间的全部原始内容，作为 tender_params（保留表格格式）
                    # 注意：提取时使用 after_start_pos，这样不会包含第四章标题
                    between_rng = doc.Range(before_end_pos, after_start_pos)
                    # 使用新函数提取内容，保留表格格式
                    extracted_content = extract_content_with_tables(between_rng)
                    total_chars = len(extracted_content)
                    non_whitespace_chars = len([c for c in extracted_content if not c.isspace()])
                    line_count = len(extracted_content.splitlines())
                    table_count = len(list(between_rng.Tables))
                    print(f"成功提取锚点之间内容，总长度: {total_chars} 字符，非空白字符: {non_whitespace_chars} 字符，行数: {line_count} 行，表格数量: {table_count} 个")

                    # 记录页码范围供后续节点参考
                    start_page = before_page + 1
                    end_page = after_page - 1
                    print(f"[extract_tender_params] 内容提取完成，页码范围: {start_page} - {end_page}")
        
    except Exception as e:
        error_msg = f"提取内容时发生错误: {e}"
        print(f"[extract_tender_params] {error_msg}")
        # 打印详细的错误堆栈信息
        import traceback
        print(f"[extract_tender_params] 详细错误堆栈:")
        traceback.print_exc()
        # 终止图运行：抛出异常而不是吞掉错误
        raise RuntimeError(error_msg) from e
        
    finally:
        print("[extract_tender_params] 开始清理资源...")
        # 安全关闭文档
        if doc:
            try:
                print("[extract_tender_params] 正在关闭文档...")
                # 检查文档是否仍然有效
                try:
                    _ = doc.Name  # 尝试访问属性来检查对象是否有效
                    doc.Close(SaveChanges=False)
                    print("[extract_tender_params] 文档已关闭")
                except AttributeError:
                    # 对象已断开，说明已经关闭了
                    print("[extract_tender_params] 文档对象已断开，无需关闭")
                    pass
                except Exception as close_doc_e:
                    print(f"[extract_tender_params] 关闭文档时出错: {close_doc_e}")
            except Exception as e:
                print(f"[extract_tender_params] 关闭文档时发生异常: {e}")
                pass
        
        # 安全关闭 Word 应用程序
        if wps:
            try:
                print("[extract_tender_params] 正在关闭 Word 应用程序...")
                # 检查 wps 对象是否仍然有效
                try:
                    _ = wps.Name  # 尝试访问属性来检查对象是否有效
                    wps.Quit(SaveChanges=False)
                    print("[extract_tender_params] Word 应用程序已关闭")
                except AttributeError:
                    # 对象已断开，说明已经关闭了
                    print("[extract_tender_params] Word 对象已断开，无需关闭")
                    pass
                except Exception as quit_wps_e:
                    print(f"[extract_tender_params] 关闭 Word 应用程序时出错: {quit_wps_e}")
            except Exception as e:
                print(f"[extract_tender_params] 关闭 Word 时发生异常: {e}")
                pass
        
        # 添加延迟，确保 Word 进程完全退出
        print("[extract_tender_params] 等待 Word 进程完全退出...")
        time.sleep(1.0)  # 增加等待时间，确保进程完全退出
        
        # 清理残留的 Word 进程（如果正常关闭失败）
        try:
            import psutil
            word_processes = []
            current_pid = None
            if wps:
                try:
                    # 尝试获取当前 Word 进程的 PID
                    import win32process
                    handle = wps.Hwnd
                    _, current_pid = win32process.GetWindowThreadProcessId(handle)
                except Exception:
                    pass
            
            for proc in psutil.process_iter(['pid', 'name', 'create_time']):
                try:
                    proc_name = proc.info['name'].lower()
                    if proc_name == 'winword.exe':
                        pid = proc.info['pid']
                        # 排除当前进程（如果已知）
                        if current_pid and pid == current_pid:
                            continue
                        # 检查进程创建时间，只清理最近10分钟内创建的进程（可能是我们创建的）
                        create_time = proc.info.get('create_time', 0)
                        if create_time > 0:
                            age_seconds = time.time() - create_time
                            if age_seconds < 600:  # 10分钟内创建的
                                word_processes.append(pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            if word_processes:
                print(f"[extract_tender_params] 检测到 {len(word_processes)} 个可能的残留 Word 进程: {word_processes}")
                # 尝试终止这些进程
                for pid in word_processes:
                    try:
                        proc = psutil.Process(pid)
                        proc.terminate()
                        print(f"[extract_tender_params] 已终止残留进程 (PID: {pid})")
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        print(f"[extract_tender_params] 无法终止进程 {pid}: {e}")
                    except Exception as e:
                        print(f"[extract_tender_params] 终止进程 {pid} 时出错: {e}")
        except ImportError:
            print("[extract_tender_params] 未安装 psutil，无法检查残留进程")
        except Exception as cleanup_e:
            print(f"[extract_tender_params] 检查残留进程时出错: {cleanup_e}")
        
        # 安全清理 COM
        try:
            print("[extract_tender_params] 清理 COM 资源...")
            pythoncom.CoUninitialize()
            print("[extract_tender_params] COM 资源已清理")
        except Exception as com_e:
            print(f"[extract_tender_params] 清理 COM 时出错: {com_e}")
    
    # 更新状态
    new_state_dict = dict(state)
    new_state_dict["origin_tender_params"] = extracted_content
    # 保存页码范围供后续节点复用
    new_state_dict["start_page"] = locals().get("start_page")
    new_state_dict["end_page"] = locals().get("end_page")
    new_state = TenderGraphState(**new_state_dict)
    log_state("extract_tender_params", new_state)
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"[extract_tender_params] 执行完成，耗时: {elapsed_time:.2f} 秒 ({elapsed_time*1000:.0f} 毫秒)")
    
    return new_state


def diagnose_wps_installation():
    """
    诊断 WPS 安装和 COM 注册状态
    打印详细的诊断信息，帮助用户排查问题
    """
    print("=" * 60)
    print("WPS Office 安装诊断工具")
    print("=" * 60)
    
    # 1. 检查注册表中的 ProgID
    print("\n1. 检查注册表中的 WPS ProgID...")
    try:
        import winreg
        wps_progids = find_wps_progids()
        print(f"   找到的 ProgID 列表: {wps_progids}")
        
        # 检查每个 ProgID 是否真的存在
        valid_progids = []
        for progid in wps_progids:
            try:
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, progid) as key:
                    try:
                        with winreg.OpenKey(key, "CLSID") as clsid_key:
                            clsid_value, _ = winreg.QueryValueEx(clsid_key, "")
                            valid_progids.append((progid, clsid_value))
                            print(f"   ✓ {progid} - 已注册 (CLSID: {clsid_value})")
                    except Exception:
                        print(f"   ✗ {progid} - 未找到 CLSID")
            except FileNotFoundError:
                print(f"   ✗ {progid} - 未在注册表中找到")
            except Exception as e:
                print(f"   ✗ {progid} - 检查失败: {e}")
        
        if not valid_progids:
            print("   ⚠ 警告: 未找到任何有效的 WPS ProgID！")
    except Exception as e:
        print(f"   注册表检查失败: {e}")
    
    # 2. 检查 WPS 进程
    print("\n2. 检查正在运行的 WPS 进程...")
    try:
        import psutil
        wps_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                proc_name = proc.info['name'].lower()
                if 'wps' in proc_name or 'kingsoft' in proc_name or 'ket' in proc_name:
                    exe_path = proc.info.get('exe', 'N/A')
                    wps_processes.append({
                        'name': proc.info['name'],
                        'pid': proc.info['pid'],
                        'exe': exe_path
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if wps_processes:
            print(f"   找到 {len(wps_processes)} 个 WPS 相关进程:")
            for proc in wps_processes:
                print(f"   - {proc['name']} (PID: {proc['pid']}, 路径: {proc['exe']})")
        else:
            print("   ⚠ 未找到正在运行的 WPS 进程")
            print("   提示: 尝试手动打开 WPS Office，然后重新运行诊断")
    except ImportError:
        print("   ⚠ 未安装 psutil 包，无法检查进程")
        print("   提示: 运行 'pip install psutil' 安装")
    except Exception as e:
        print(f"   进程检查失败: {e}")
    
    # 3. 尝试创建 WPS 实例
    print("\n3. 尝试创建 WPS COM 实例...")
    wps_progids = find_wps_progids()
    success = False
    for progid in wps_progids:
        try:
            print(f"   尝试 ProgID: {progid}...")
            wps = win32.Dispatch(progid)
            wps.Visible = False
            wps.DisplayAlerts = 0
            time.sleep(0.2)
            name = wps.Name
            print(f"   ✓ 成功！WPS 应用程序名称: {name}")
            try:
                wps.Quit(SaveChanges=False)
            except:
                pass
            success = True
            break
        except Exception as e:
            print(f"   ✗ 失败: {e}")
    
    if not success:
        print("   ⚠ 所有 ProgID 都失败了")
    
    # 4. 提供建议
    print("\n4. 建议:")
    if not success:
        print("   如果无法创建 WPS 实例，请尝试以下方法：")
        print("   1. 确保已安装 WPS Office（建议安装最新版本）")
        print("   2. 尝试以管理员权限运行程序")
        print("   3. 手动打开 WPS Office，然后关闭，这可能会注册 COM 组件")
        print("   4. 检查 WPS 安装目录是否存在（通常在 C:\\Program Files\\Kingsoft\\WPS Office）")
        print("   5. 尝试重新安装 WPS Office")
        print("   6. 检查是否有杀毒软件或防火墙阻止了 COM 接口")
    else:
        print("   ✓ WPS COM 接口工作正常！")
    
    print("=" * 60)


if __name__ == "__main__":
    """
    测试模块：测试从指定文档中提取参数的功能
    """
    import pathlib
    import sys
    
    # 添加项目根目录到路径，以便导入模块
    ROOT = pathlib.Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    
    # 检查命令行参数，如果提供了 --diagnose，则运行诊断
    if len(sys.argv) > 1 and sys.argv[1] == "--diagnose":
        diagnose_wps_installation()
        sys.exit(0)
    
    # 重新导入必要的模块（从项目根目录直接导入）
    from state import TenderGraphState
    
    # 测试文档路径列表
    test_doc_paths = [
        "TenderFile/252699-原位杂交仪-询价文件-初稿1 - 副本.doc"
    ]
    
    # 循环测试每个文件
    for doc_idx, test_doc_path_str in enumerate(test_doc_paths, 1):
        # 基于项目根目录解析路径
        test_doc_path = (ROOT / test_doc_path_str).resolve()
        
        print("\n" + "=" * 80)
        print(f"测试 {doc_idx}/{len(test_doc_paths)}: extract_tender_params 节点")
        print("=" * 80)
        print(f"测试文档路径: {test_doc_path}")
        print(f"文档是否存在: {test_doc_path.exists()}")
        print()
        
        if not test_doc_path.exists():
            print(f"警告: 文档不存在: {test_doc_path}，跳过此文件")
            print()
            continue
        
        # 在处理下一个文档前，确保之前的 WPS 实例已完全关闭
        if doc_idx > 1:
            import time
            print("等待之前的 WPS 实例完全关闭...")
            time.sleep(1.0)  # 增加等待时间，确保 WPS 完全关闭
        
        # 创建测试状态
        test_state: TenderGraphState = {
            "prepared_doc_path": str(test_doc_path),
            "insertion_before_text": "第三章  采购需求",
            "insertion_after_text": "第四章  响应文件有关格式",
        }
        
        try:
            # 调用 extract_tender_params 函数
            result_state = extract_tender_params(test_state, config=None)
            
            tender_params = result_state.get("origin_tender_params", "") 
            if tender_params:
                print(f"\n成功提取内容，长度: {len(tender_params)} 字符")
                
                # 保存完整内容到文件
                output_file = test_doc_path.parent / f"{test_doc_path.stem}_extracted_params.txt"
                try:
                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write(tender_params)
                    print(f"完整内容已保存到文件: {output_file}")
                except Exception as save_e:
                    print(f"警告: 保存文件时出错: {save_e}")
            else:
                print("\n未提取到任何内容（可能未找到前后文本或内容为空）")
            
        except Exception as e:
            print(f"\n错误: {e}")
            import traceback
            traceback.print_exc()
            print(f"\n继续测试下一个文件...")
            print()
            continue

