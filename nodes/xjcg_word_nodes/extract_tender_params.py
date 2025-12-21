from __future__ import annotations

import os
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
)
from util.word_com_manager import com_lock, is_rpc_error, calculate_retry_delay, MAX_RETRIES
from util.word_extraction_utils import (
    extract_content_with_tables,
    extract_text_from_word_file,
)

# WPS/Word constants (WPS 兼容 Word 的常量)
wdFindStop = 0
wdCollapseEnd = 0
wdGoToPage = 1
wdGoToAbsolute = 1
wdActiveEndPageNumber = 3
    


def extract_tender_params(state: XjcgTenderGraphState, config) -> XjcgTenderGraphState:
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
        new_state = XjcgTenderGraphState(**new_state_dict)
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
    com_initialized = False
    
    try:
        # 使用统一的工具函数创建 Word 应用程序
        # 在并发环境下使用独立实例，避免多用户冲突
        wps, com_initialized = create_word_application(
            initial_delay=0.5,  # 创建前等待，让之前的实例有时间完全关闭
            post_init_delay=0.5,  # 给 Word 一点时间完成初始化
            use_existing=False,  # 并发环境下必须使用独立实例
            verify=True,
            node_name="extract_tender_params"
        )

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
                    # 使用统一的工具函数关闭旧的 Word 应用程序
                    close_word_application(
                        word_app=wps,
                        doc=None,
                        com_initialized=com_initialized,
                        wait_time=1.0,
                        node_name="extract_tender_params"
                    )
                    wps = None
                    com_initialized = False

                    # 使用统一的工具函数重新创建 Word 应用程序对象
                    wps, com_initialized = create_word_application(
                        initial_delay=1.0,  # 等待 1 秒，确保之前的实例完全关闭
                        post_init_delay=0.5,  # 给 Word 一点时间完成初始化
                        use_existing=False,  # 并发环境下必须使用独立实例
                        verify=True,
                        node_name="extract_tender_params"
                    )
                    print("[extract_tender_params] Word 应用程序对象已重新创建，正在重试打开文档...")

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
                    # 使用统一的工具函数确保关闭 Word
                    close_word_application(
                        word_app=wps,
                        doc=None,
                        com_initialized=com_initialized,
                        wait_time=0.5,
                        node_name="extract_tender_params"
                    )
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
        # 使用统一的工具函数关闭 Word 应用程序
        close_word_application(
            word_app=wps,
            doc=doc,
            com_initialized=com_initialized,
            wait_time=1.0,
            node_name="extract_tender_params"
        )
    
    # 更新状态
    new_state_dict = dict(state)
    new_state_dict["origin_tender_params"] = extracted_content
    # 保存页码范围供后续节点复用
    new_state_dict["start_page"] = locals().get("start_page")
    new_state_dict["end_page"] = locals().get("end_page")
    
    # 如果提供了 tender_param_path，从文件中提取 tender_params 并更新状态
    tender_param_path = state.get("tender_param_path")
    if tender_param_path:
        print(f"[extract_tender_params] 检测到 tender_param_path，开始提取技术参数...")
        file_path_obj = pathlib.Path(tender_param_path)
        if not file_path_obj.exists():
            raise ValueError(f"tender_param_path 不存在: {tender_param_path}")
        if not file_path_obj.is_file():
            raise ValueError(f"tender_param_path 不是文件: {tender_param_path}")
        
        tender_params = extract_text_from_word_file(str(file_path_obj))
        print(f"[extract_tender_params] 从文件提取技术参数完成，长度: {len(tender_params)}")
        new_state_dict["tender_params"] = tender_params
    
    new_state = XjcgTenderGraphState(**new_state_dict)
    log_state("extract_tender_params", new_state)
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"[extract_tender_params] 执行完成，耗时: {elapsed_time:.2f} 秒 ({elapsed_time*1000:.0f} 毫秒)")
    
    return new_state


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
    
    
    # 重新导入必要的模块（从项目根目录直接导入）
    from state import XjcgTenderGraphState
    
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
        test_state: XjcgTenderGraphState = {
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

