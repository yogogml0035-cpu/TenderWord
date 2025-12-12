from __future__ import annotations

import datetime
from typing import Callable, Optional
import os
import pathlib
import re
import time

from langchain_deepseek import ChatDeepSeek

# 处理相对导入和直接运行的情况
try:
    from ...config import AgentConfig
    from ...logging_utils import log_state
    from ...state import TenderGraphState
except ImportError:
    # 直接运行时使用绝对导入
    import sys
    
    # 先尝试直接导入（假设 TenderWord/ 目录已在 sys.path 中）
    try:
        from config import AgentConfig
        from logging_utils import log_state
        from state import TenderGraphState
    except ImportError:
        # 如果失败，添加父目录并使用 TenderWord 前缀
        import pathlib
        ROOT = pathlib.Path(__file__).resolve().parents[2]
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from TenderWord.config import AgentConfig
        from TenderWord.logging_utils import log_state
        from TenderWord.state import TenderGraphState

POLISH_PROMPT = """
# Role
你是一台**智能招标文件生成机器**。你的核心能力是**“结构复刻”**和**“动态填充”**。

# The Prime Directives (最高禁令)
1.  **严禁加戏：** 严禁自动补充【参考内容】中没有的章节（如商务、评标、合同等）。
2.  **严禁Markdown装饰：** 输出纯文本，不要使用 `**` (加粗) 或 `---` (分隔符)。
3.  **严格镜像：** 输出文档的**一级大标题（序号及名称）**必须与【参考内容】**完全一致**。如果参考内容是“二、技术要求”，你就不能写成“三、技术需求”。
4.  **条款完整：** 【参考内容】中的法律条款（付款方式、售后通用语），必须**逐字照抄**。

# Logic Rules (核心逻辑分支)

请先扫描【技术参数】的内容特征，然后按顺序匹配以下逻辑：

## 1. 动态定位规则 (首先执行)
* **识别技术章节：** 在开始写入数据前，请先在【参考内容】中找到**描述设备具体指标的那一章**（可能是“二、技术要求”，也可能是“三、技术规格”等）。
* **锁定目标：** 下面的所有“写入技术参数”的操作，都必须发生在你识别出的**这一个章节**内，保持该章节原有的序号和标题不变。

## 2. 结构分支判断 (按顺序匹配)

### 分支 A：多包件项目 (Multi-Package)
* **触发条件：** 【技术参数】中明确出现了“第1包”、“包1”、“包件A”等分包描述。
* **执行动作：**
    * 必须为每个包件生成独立的大标题（格式如“**第X包：[包件名称]**”）。
    * **在每个包件的大标题下**，完整克隆【参考内容】的所有章节结构（包括项目概述、付款方式、以及你定位到的**技术章节**）。
    * *注意：* 保持“第X包”作为最高层级，不要将其降级为设备。

### 分支 B：单包多设备项目 (Single Package, Multi-Device)
* **触发条件：** 无分包描述，但【技术参数】包含多个独立设备（如：荧光细胞计数仪、冰箱、PCR仪）。
* **执行动作：**
    * 只生成一次【参考内容】的完整结构。
    * 在你定位到的**技术章节**内部，必须对设备进行分层，使用“**设备一：[名称]**”、“**设备二：[名称]**”的格式分别列出参数。

### 分支 C：单一设备项目 (Single Device)
* **触发条件：** 无分包描述，且只有一种设备。
* **执行动作：**
    * 只生成一次【参考内容】的完整结构。
    * 在你定位到的**技术章节**内部，直接列出该设备的参数，**不需要**添加“设备一”这样的前缀。

---
# Input Data

【参考内容】(这是唯一的结构模版，请严格复刻其目录结构)：
[{origin_tender_params}]

【技术参数】(这是内容源，请根据上述分支判断结构)：
[{tender_params}]"""


def _sanitize_filename(name: str) -> str:
    """Remove characters invalid in Windows file names."""
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip()


# Unicode 上标和下标字符映射表
_SUPERSCRIPT_MAP = {
    '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
    '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
    '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾',
    'n': 'ⁿ', 'i': 'ⁱ',
}

_SUBSCRIPT_MAP = {
    '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
    '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
    '+': '₊', '-': '₋', '=': '₌', '(': '₍', ')': '₎',
    'a': 'ₐ', 'e': 'ₑ', 'o': 'ₒ', 'x': 'ₓ',
}


def _extract_text_with_superscript_subscript(range_obj):
    """
    提取WPS/Word范围中的文本，保留上标和下标格式
    
    Args:
        range_obj: WPS/Word Range对象
        
    Returns:
        str: 提取的文本，上标/下标字符已转换为Unicode上标/下标字符
    """
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
                
                try:
                    superscript_val = font.Superscript
                    # Word COM 返回 -1 或 True 表示上标，0 或 False 表示否
                    # 9999999 (wdUndefined) 表示混合状态，不应视为上标
                    # 显式检查以处理各种可能的返回值类型
                    is_superscript = (superscript_val == True) or (superscript_val == -1)
                except:
                    pass
                
                try:
                    subscript_val = font.Subscript
                    # 同样的逻辑处理下标
                    is_subscript = (subscript_val == True) or (subscript_val == -1)
                except:
                    pass
                
                # 根据上标/下标状态转换字符
                if is_superscript and char_text in _SUPERSCRIPT_MAP:
                    result.append(_SUPERSCRIPT_MAP[char_text])
                elif is_subscript and char_text in _SUBSCRIPT_MAP:
                    result.append(_SUBSCRIPT_MAP[char_text])
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
        # 如果出错，回退到普通文本提取
        print(f"    提取带上标/下标文本时出错: {e}")
        try:
            return range_obj.Text
        except:
            return ""


def _extract_table_as_text(table):
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
                    cell_text = _extract_text_with_superscript_subscript(cell.Range)
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
            return _extract_text_with_superscript_subscript(table.Range)
        
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
        # 如果出错，回退到带上标/下标的文本提取
        try:
            return _extract_text_with_superscript_subscript(table.Range)
        except:
            return ""


def _extract_text_with_list_numbers(range_obj):
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
        
        # 尝试多种方法获取段落列表
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
                        text = _extract_text_with_superscript_subscript(range_obj)
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
                para_text = _extract_text_with_superscript_subscript(para_range)
                
                if para_text:
                    if has_list and list_string:
                        # 如果有自动编号，将编号添加到文本前
                        # 检查文本开头是否已经包含编号（避免重复）
                        # 去除编号字符串两端的空格（编号本身不应该有前后空格）
                        list_string_clean = list_string.strip()
                        # 检查去除前导空白后的文本是否以编号开头
                        para_text_stripped = para_text.lstrip()
                        if para_text_stripped and para_text_stripped.startswith(list_string_clean):
                            # 文本已经包含编号，直接使用原始文本（保留所有格式）
                            result_lines.append(para_text)
                        else:
                            # 文本不包含编号，添加编号
                            # 保留原始文本的所有格式（包括前导空格、换行符等）
                            # 在文本最前面添加编号和空格
                            result_lines.append(list_string_clean + " " + para_text)
                    else:
                        # 没有自动编号，直接添加原始文本
                        result_lines.append(para_text)
                        
            except Exception as para_e:
                # 如果处理某个段落失败，回退到直接提取文本（带上标/下标）
                # 检查是否是对象删除错误
                if "对象已被删除" in str(para_e) or "无效指针" in str(para_e):
                    # 对象已失效，跳过这个段落
                    continue
                try:
                    para_text = _extract_text_with_superscript_subscript(para.Range)
                    if para_text:
                        result_lines.append(para_text)
                except:
                    # 如果连文本都无法获取，跳过这个段落
                    pass
        
        # 如果没有提取到任何内容，回退到直接提取文本（带上标/下标）
        if not result_lines:
            return _extract_text_with_superscript_subscript(range_obj)
        
        # 直接连接所有段落文本，保留所有原始格式和符号
        return ''.join(result_lines)
        
    except Exception as e:
        print(f"    提取带编号文本时出错: {e}")
        import traceback
        traceback.print_exc()
        # 如果出错，回退到带上标/下标的文本提取
        try:
            return _extract_text_with_superscript_subscript(range_obj)
        except:
            # 如果连文本都无法获取，返回空字符串
            print("    警告: 无法提取任何文本内容")
            return ""


def _extract_content_with_tables(range_obj):
    """
    提取WPS/Word范围中的内容，包括表格，保留表格格式和自动编号
    
    Args:
        range_obj: WPS/Word Range对象
        
    Returns:
        str: 提取的内容，表格已格式化，自动编号已保留
    """
    try:
        # 获取范围内的所有表格
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
                        return _extract_text_with_list_numbers(range_obj)
                    except:
                        try:
                            return range_obj.Text
                        except:
                            return ""
        
        if not tables:
            # 没有表格，使用带自动编号的文本提取
            return _extract_text_with_list_numbers(range_obj)
        
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
                    text_content = _extract_text_with_list_numbers(text_before)
                    if text_content:
                        result_parts.append(text_content)
                
                # 提取表格（只提取在范围内的部分）
                if table_start >= start_pos and table_end <= end_pos:
                    # 表格完全在范围内
                    table_text = _extract_table_as_text(table)
                    if table_text:
                        result_parts.append(table_text)
                else:
                    # 表格部分在范围内，提取表格的格式化文本
                    table_text = _extract_table_as_text(table)
                    if table_text:
                        result_parts.append(table_text)
                
                current_pos = max(current_pos, table_end)
        
        # 提取最后一个表格后的文本
        text_start = max(current_pos, start_pos)
        text_end = end_pos
        if text_end > text_start:
            text_after = range_obj.Document.Range(text_start, text_end)
            # 使用带自动编号的文本提取函数
            text_content = _extract_text_with_list_numbers(text_after)
            if text_content:
                result_parts.append(text_content)
        
        # 如果没有提取到任何内容，回退到带编号的文本提取
        if not result_parts:
            return _extract_text_with_list_numbers(range_obj)
        
        # 直接连接各部分，保留原始格式，不添加额外的分隔符
        return ''.join(result_parts)
        
    except Exception as e:
        print(f"    提取内容（含表格）时出错: {e}")
        import traceback
        traceback.print_exc()
        # 如果出错，回退到带编号的文本提取
        try:
            return _extract_text_with_list_numbers(range_obj)
        except:
            # 如果带编号提取也失败，使用带上标/下标的文本作为最后回退
            try:
                return _extract_text_with_superscript_subscript(range_obj)
            except:
                # 如果连文本都无法获取，返回空字符串
                print("    警告: 无法提取任何内容")
                return ""


def _extract_text_from_word_file(file_path: str) -> str:
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
        try:
            import pythoncom
            import win32com.client as win32
            from pywintypes import com_error
            
            def _create_word():
                """
                创建 Microsoft Word 应用程序实例
                增加重试机制和休眠时间，处理上次实例未完全关闭的情况
                """
                max_retries = 3
                retry_delay = 2.0  # 每次重试前等待 2 秒
                initial_delay = 2.0  # 首次尝试前等待 2 秒，确保上一个节点完全关闭
                
                # 首次尝试前等待，让之前的实例有时间完全关闭
                print(f"    等待 {initial_delay} 秒，确保上一个节点完全关闭...")
                time.sleep(initial_delay)
                
                for retry in range(max_retries):
                    if retry > 0:
                        print(f"    第 {retry + 1} 次重试创建 Word 应用程序实例（等待 {retry_delay} 秒后重试）...")
                        time.sleep(retry_delay)
                    
                    errors = []
                    app_name = "Word"
                    
                    # 直接使用 Word.Application
                    print("    尝试创建 Word.Application 实例...")
                    try:
                        app = win32.gencache.EnsureDispatch("Word.Application")
                        print("    成功创建 Word.Application 实例")
                        return app, app_name
                    except Exception as e:
                        error_str = str(e)
                        errors.append(f"Word EnsureDispatch: {e}")
                        # 如果是 RPC 错误，记录以便重试
                        if "RPC" in error_str or "-2147023174" in error_str:
                            print(f"    检测到 RPC 错误，将在重试时处理: {e}")
                    
                    try:
                        app = win32.DispatchEx("Word.Application")
                        print("    成功创建 Word.Application 实例 (DispatchEx)")
                        return app, app_name
                    except Exception as e:
                        error_str = str(e)
                        errors.append(f"Word DispatchEx: {e}")
                        if "RPC" in error_str or "-2147023174" in error_str:
                            print(f"    检测到 RPC 错误，将在重试时处理: {e}")
                    
                    try:
                        app = win32.Dispatch("Word.Application")
                        print("    成功创建 Word.Application 实例 (Dispatch)")
                        return app, app_name
                    except Exception as e:
                        error_str = str(e)
                        errors.append(f"Word Dispatch: {e}")
                        if "RPC" in error_str or "-2147023174" in error_str:
                            print(f"    检测到 RPC 错误，将在重试时处理: {e}")
                    
                    # 如果所有方法都失败，检查是否是 RPC 错误，如果是则继续重试
                    has_rpc_error = any("RPC" in str(e) or "-2147023174" in str(e) for e in errors)
                    if has_rpc_error and retry < max_retries - 1:
                        print(f"    检测到 RPC 服务器不可用错误，将在 {retry_delay} 秒后重试...")
                        continue
                
                # 所有重试都失败
                raise RuntimeError(f"经过 {max_retries} 次尝试后仍无法创建 Word 应用程序实例; " + "; ".join(errors))
            
            def _safe_close(doc_obj, word_obj):
                try:
                    if doc_obj:
                        try:
                            doc_obj.Close()
                        except Exception:
                            pass
                    if word_obj:
                        try:
                            word_obj.Quit()
                        except Exception:
                            pass
                finally:
                    try:
                        pythoncom.CoUninitialize()
                    except Exception:
                        pass
            
            pythoncom.CoInitialize()
            word = None
            doc = None
            try:
                word, app_name = _create_word()
                word.Visible = False
                word.DisplayAlerts = 0
                
                # 允许一次重试，缓解 COM 断开
                for attempt in (1, 2):
                    try:
                        doc = word.Documents.Open(str(file_path_obj.resolve()), ReadOnly=True)
                        # 立即获取 Content 对象，避免后续对象失效
                        content_range = doc.Content
                        # 使用 extract_content_with_tables 提取内容，保留表格格式和自动编号
                        document_text = _extract_content_with_tables(content_range)
                        return document_text
                    except com_error as ce:
                        # -2147417848: RPC/COM 断开，等待后重试
                        # -2147467261: 无效指针
                        # -2147352567: 对象已被删除
                        hresult = getattr(ce, "hresult", None)
                        if attempt == 1 and hresult in (-2147417848, -2147467261, -2147352567):
                            print(f"    检测到 COM 错误 (hresult={hresult})，等待后重试...")
                            time.sleep(1.5)
                            continue
                        # 如果是对象删除错误，尝试直接提取文本
                        if hresult in (-2147467261, -2147352567):
                            print(f"    检测到对象失效，尝试直接提取文本...")
                            try:
                                if doc:
                                    try:
                                        # 尝试保留上标格式
                                        return _extract_text_with_superscript_subscript(doc.Content)
                                    except:
                                        return doc.Content.Text
                            except:
                                pass
                        raise
            finally:
                _safe_close(doc, word)
        except ImportError:
            raise ValueError("读取 Word 文件需要 pywin32 库，且只能在 Windows 环境下运行")
        except Exception as e:
            raise ValueError(f"读取 Word 文件失败: {e}")
    else:
        raise ValueError(f"不支持的文件格式: {file_path_obj.suffix}")


async def generate_polished_text(state: TenderGraphState, config) -> TenderGraphState:
    start_time = time.perf_counter()
    print("[generate_polished_text] 开始执行...")
    
    # 优先使用文件路径，如果没有则使用文本内容
    origin_tender_path = state.get("origin_tender_path")
    origin_tender_params = state.get("origin_tender_params")
    tender_param_path = state.get("tender_param_path")
    
    
    # 获取参考内容（tender_param）
    tender_params = state.get("tender_params", "")  
    if not tender_params:
        if not tender_param_path:
            raise ValueError("需要提供 tender_param（参考内容）或 tender_param_path 来生成润色文本")
        file_path_obj = pathlib.Path(tender_param_path)
        if not file_path_obj.exists():
            raise ValueError(f"tender_params_path 不存在: {tender_param_path}")
        if not file_path_obj.is_file():
            raise ValueError(f"tender_params_path 不是文件: {tender_param_path}")

        tender_params = _extract_text_from_word_file(str(file_path_obj))
        print(f"[generate_polished_text] 从文件提取技术参数完成，长度: {len(tender_params)}")
        # 简单检查是否有上标字符
        superscript_chars = set(_SUPERSCRIPT_MAP.values())
        has_superscript = any(c in superscript_chars for c in tender_params)
        print(f"[generate_polished_text] 提取内容是否包含上标: {has_superscript}")
    

    agent_config = AgentConfig.from_runnable_config(config)
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY is not set")

    llm = ChatDeepSeek(
        model=agent_config.llm_model,
        temperature=agent_config.llm_temperature,
        api_key=api_key,
        max_tokens=8192
    )

    prompt = POLISH_PROMPT.format(
        tender_params=tender_params,
        origin_tender_params=origin_tender_params,
    )
    
    # 保存提示词到文件
    prompts_dir = pathlib.Path(__file__).resolve().parents[2] / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    prompt_file = prompts_dir / f"prompt_{timestamp}.txt"
    try:
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt)
    except Exception as e:
        print(f"警告: 保存提示词文件失败: {e}")
    
    stream_callback: Optional[Callable[[str], None]] = None
    suppress_llm_stdout = False
    if config:
        try:
            configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
            if isinstance(configurable, dict):
                stream_callback = configurable.get("llm_stream_callback")
                suppress_llm_stdout = bool(configurable.get("suppress_llm_stdout", False))
            if not stream_callback and isinstance(config, dict):
                stream_callback = config.get("llm_stream_callback")
        except Exception:
            stream_callback = None

    def _push_stream_update(text: str) -> None:
        if callable(stream_callback) and text is not None:
            try:
                stream_callback(str(text))
            except Exception as cb_exc:
                print(f"警告: LLM 流式回调失败: {cb_exc}")

    def _log_chunk(text: str) -> None:
        if suppress_llm_stdout:
            return
        print(text, end="", flush=True)

    def _chunk_to_text(chunk) -> str:
        if chunk is None:
            return ""
        text = getattr(chunk, "content", None)
        if isinstance(text, list):
            text = "".join([str(t) for t in text if t is not None])
        if not text and hasattr(chunk, "message"):
            text = getattr(chunk.message, "content", "")  # type: ignore[attr-defined]
        return str(text) if text else ""

    content_parts = []
    stream_method = getattr(llm, "astream", None)
    invoke_method = getattr(llm, "ainvoke", None)
    if callable(stream_method):
        try:
            async for chunk in stream_method(prompt):
                chunk_text = _chunk_to_text(chunk)
                if not chunk_text:
                    continue
                content_parts.append(chunk_text)
                _log_chunk(chunk_text)
                _push_stream_update("".join(content_parts))
            print()  # 换行，避免日志粘连
            content = "".join(content_parts)
        except Exception as stream_exc:
            print(f"流式获取失败，回退到非流式: {stream_exc}")
            if callable(invoke_method):
                response = await invoke_method(prompt)
                content = getattr(response, "content", response)
            else:
                response = llm.invoke(prompt)
                content = getattr(response, "content", response)
            _push_stream_update(str(content))
    else:
        if callable(invoke_method):
            response = await invoke_method(prompt)
            content = getattr(response, "content", response)
        else:
            response = llm.invoke(prompt)
            content = getattr(response, "content", response)
        _push_stream_update(str(content))
    # content = """"""

    # 将大模型生成的内容写入 txt 文件，命名：项目编号-项目名称-初稿.txt
    project_number = str(state.get("project_number", "") or "").strip()
    project_name = str(state.get("project_name", "") or "").strip()
    filename_parts = [_sanitize_filename(part) for part in (project_number, project_name) if part]
    filename = "-".join(filename_parts + ["初稿"]) if filename_parts else "初稿"
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    filename = f"{filename}-{timestamp}.txt"
    # 优先使用 origin_tender_path 所在目录，其次 tender_param_path，再次 prompts 目录
    output_dir = None
    try:
        if origin_tender_path:
            output_dir = pathlib.Path(origin_tender_path).resolve().parent
        elif tender_param_path:
            output_dir = pathlib.Path(tender_param_path).resolve().parent
    except Exception:
        output_dir = None
    if not output_dir:
        output_dir = prompts_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    polished_txt_path = output_dir / filename
    try:
        with open(polished_txt_path, "w", encoding="utf-8") as f:
            f.write(str(content))
    except Exception as e:
        print(f"警告: 保存润色文本到文件失败: {e}")

    # 只返回需要更新的键，避免并行执行时的状态冲突
    # 在 LangGraph 中，并行节点应该只返回部分状态更新
    new_state = TenderGraphState(polished_text=content, generate_polished_done=True)
    # 为了日志记录，创建完整状态（仅用于日志）
    full_state_for_log = dict(state)
    full_state_for_log.update({"polished_text": content, "generate_polished_done": True})
    log_state("generate_polished_text", TenderGraphState(**full_state_for_log))
    
    duration = time.perf_counter() - start_time
    duration_ms = duration * 1000
    print(f"[generate_polished_text] 执行完成，耗时: {duration:.2f} 秒 ({duration_ms:.0f} 毫秒)")
    return new_state


if __name__ == "__main__":
    """
    测试模块：测试 extract_tender_params 和 generate_polished_text 两个节点
    """
    import pathlib
    import sys
    import time
    
    # 添加项目根目录到路径，以便导入模块
    ROOT = pathlib.Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    
    # 重新导入必要的模块（使用绝对导入）
    from TenderWord.state import TenderGraphState
    from TenderWord.nodes.xjcg_word_nodes.extract_tender_params import extract_tender_params
    
    # 测试配置：参考文档路径和技术参数路径
    # 可以根据需要修改这两个路径
    reference_doc_path_str = "TenderFile/251918-询价文件-初稿.doc"  # 参考文档路径
    tech_spec_path_str = "TenderFile/恒温暖柜等设备招标参数.docx"  # 技术参数路径
    
    # 基于项目根目录解析路径
    reference_doc_path = (ROOT / reference_doc_path_str).resolve()
    tech_spec_path = (ROOT / tech_spec_path_str).resolve()
    
    print("\n" + "=" * 80)
    print("测试 extract_tender_params 和 generate_polished_text 节点")
    print("=" * 80)
    print(f"参考文档路径: {reference_doc_path}")
    print(f"参考文档是否存在: {reference_doc_path.exists()}")
    print(f"技术参数路径: {tech_spec_path}")
    print(f"技术参数文档是否存在: {tech_spec_path.exists()}")
    print()
    
    if not reference_doc_path.exists():
        print(f"错误: 参考文档不存在: {reference_doc_path}")
        sys.exit(1)
    
    if not tech_spec_path.exists():
        print(f"错误: 技术参数文档不存在: {tech_spec_path}")
        sys.exit(1)
    
    try:
        # 第一步：从参考文档中提取参数（调用 extract_tender_params）
        print("\n" + "-" * 80)
        print("第一步: 从参考文档中提取参数")
        print("-" * 80)
        
        extract_state: TenderGraphState = {
            "prepared_doc_path": str(reference_doc_path),
            "insertion_before_text": "第三章  采购需求",
            "insertion_after_text": "第四章  响应文件有关格式",
        }
        
        result_state = extract_tender_params(extract_state, config=None)
        tender_params = result_state.get("tender_params", "")
        
        if not tender_params:
            print("错误: 未能从参考文档中提取到内容")
            sys.exit(1)
        
        # 等待 Word 实例完全关闭
        print("等待 Word 实例完全关闭...")
        time.sleep(1.0)
        
        # 第二步：读取技术参数文档内容
        print("\n" + "-" * 80)
        print("第二步: 读取技术参数文档内容")
        print("-" * 80)
        
        origin_tender_params = _extract_text_from_word_file(str(tech_spec_path))
        
        # 第三步：调用 generate_polished_text 生成润色后的文本
        print("\n" + "-" * 80)
        print("第三步: 生成润色后的文本")
        print("-" * 80)
        
        polish_state: TenderGraphState = {
            "tender_params": tender_params,
            "origin_tender_params": origin_tender_params,
        }
        
        polished_result_state = generate_polished_text(polish_state, config=None)
        polished_text = polished_result_state.get("polished_text", "")
        
        if polished_text:
            print(f"\n成功生成润色文本，长度: {len(polished_text)} 字符")
            
            # 保存完整内容到文件
            output_file = tech_spec_path.parent / f"{tech_spec_path.stem}_polished.txt"
            try:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(polished_text)
                print(f"润色文本已保存到文件: {output_file}")
            except Exception as save_e:
                print(f"警告: 保存文件时出错: {save_e}")
            
            print("\n" + "=" * 80)
            print("生成的润色文本（完整内容）:")
            print("=" * 80)
            print(polished_text)
            print("=" * 80)
            print(f"\n内容总长度: {len(polished_text)} 字符")
            print(f"内容行数: {len(polished_text.splitlines())} 行")
        else:
            print("\n未生成任何内容")
        
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
