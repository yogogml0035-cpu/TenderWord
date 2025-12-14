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
from state import TenderGraphState
from util.word_application_util import create_word_application, close_word_application

# WPS/Word constants (WPS 兼容 Word 的常量)
wdFindStop = 0
wdCollapseEnd = 0
wdGoToPage = 1
wdGoToAbsolute = 1
wdActiveEndPageNumber = 3


def delete_tender_param(state: TenderGraphState, config) -> TenderGraphState:
    """
    根据前后内容定位插入位置，删除该位置的 WPS/Word 内容。
    
    从 state 中读取：
    - insertion_before_text: 插入位置的前置文本
    - insertion_after_text: 插入位置的后置文本
    - prepared_doc_path: WPS/Word 文档路径
    
    删除锚点之间的内容并保存文档。
    """
    start_time = time.time()
    print(f"[delete_tender_param] 开始执行...")
    
    prepared_doc_path = state.get("prepared_doc_path")
    before_text = state.get("insertion_before_text")
    after_text = state.get("insertion_after_text")
    
    if not prepared_doc_path:
        raise ValueError("需要 prepared_doc_path 来删除 WPS/Word 文档中的内容")
    
    if not before_text or not after_text:
        # 如果没有提供前后文本，跳过删除
        print(f"[delete_tender_param] 警告: 未提供 insertion_before_text 或 insertion_after_text，跳过删除")
        new_state_dict = dict(state)
        new_state = TenderGraphState(**new_state_dict)
        log_state("delete_tender_param", new_state)
        return new_state
    
    # 确保路径是绝对路径（WPS/Word COM 对象需要绝对路径）
    if not os.path.isabs(prepared_doc_path):
        prepared_doc_path = os.path.abspath(prepared_doc_path)
    
    # 检查文件是否存在
    if not os.path.exists(prepared_doc_path):
        raise FileNotFoundError(f"未找到准备好的文档: {prepared_doc_path}")
    
    # 检查文件是否可写
    if not os.access(prepared_doc_path, os.W_OK):
        raise PermissionError(f"无法写入准备好的文档: {prepared_doc_path}")
    
    wps = None
    doc = None
    com_initialized = False
    
    try:
        # 使用统一的工具函数创建 Word 应用程序
        # 独立实例 + 预留时间，避免前序节点关闭未完成导致句柄失效
        wps, com_initialized = create_word_application(
            initial_delay=2.0,  # 创建前等待 2 秒，让之前的实例有时间完全关闭
            post_init_delay=1.0,  # 给 Word 初始化的时间
            use_existing=False,  # 不使用已运行的实例，创建新的独立实例
            verify=True,
            node_name="delete_tender_param"
        )

        open_attempts = 3
        last_error = None
        for attempt in range(1, open_attempts + 1):
            try:
                doc = wps.Documents.Open(
                    FileName=prepared_doc_path,
                    ConfirmConversions=False,
                    ReadOnly=False,  # 需要写入以删除内容
                    AddToRecentFiles=False,
                    NoEncodingDialog=True
                )
                print(f"已打开文档: {prepared_doc_path}")
                break
            except Exception as open_error:
                last_error = open_error
                print(f"[delete_tender_param] 打开文档失败（第 {attempt} 次）: {open_error}")
                if attempt < open_attempts:
                    time.sleep(1.0)
                else:
                    raise RuntimeError(f"无法打开文档进行删除操作: {open_error}")
        
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
            elif after_page <= before_page:
                print(f"错误: 后置文本页码 ({after_page}) 小于等于前置文本页码 ({before_page})")
            elif after_start_pos is None or after_end_pos is None:
                print("错误: 未能获取后置文本位置，无法删除内容")
            else:
                # === 直接基于锚点字符范围删除（比按页更稳定） ===
                if before_end_pos is None:
                    print("错误: 未能获取前置文本结束位置，无法删除内容")
                else:
                    print("开始删除锚点之间的内容（不再按页删除，避免误删第四章之后部分）")
                    
                    def refind_after_anchor():
                        """在删除前重新定位后置锚点，避免因内容移动导致范围偏移"""
                        refind_rng = doc_content.Duplicate
                        refind_rng.Start = before_end_pos
                        refind_rng.End = doc_content.End
                        refind = refind_rng.Find
                        refind.ClearFormatting()
                        refind.Text = after_text
                        refind.Forward = True
                        refind.Wrap = wdFindStop
                        refind.MatchCase = False
                        refind.MatchWholeWord = False
                        while refind.Execute():
                            font_name = refind_rng.Font.Name
                            font_size = refind_rng.Font.Size
                            is_font = (font_name == "宋体" or font_name == "SimSun")
                            is_size = abs(font_size - 18.0) < 0.5
                            if is_font and is_size:
                                return refind_rng.Start, refind_rng.End
                            refind_rng.Collapse(wdCollapseEnd)
                            refind_rng.End = doc_content.End
                        return None, None
                    
                    def is_range_locked(rng):
                        """检测范围是否被保护"""
                        try:
                            if hasattr(rng, "Locked") and rng.Locked:
                                return True
                        except Exception:
                            pass
                        
                        # 检查字段锁定
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
                        
                        # 通过尝试写入检测保护
                        try:
                            marker = "\u200B"
                            test_pos = rng.End
                            probe_rng = doc.Range(test_pos, test_pos)
                            probe_rng.InsertAfter(marker)
                            inserted = doc.Range(test_pos, test_pos + 1)
                            if inserted.Text == marker:
                                inserted.Delete()
                                return False
                        except Exception as probe_e:
                            err = str(probe_e).lower()
                            if "锁定" in err or "locked" in err or "-2146823683" in err:
                                return True
                        return False
                    
                    # 删除前再次确认后置锚点，避免锚点位移导致范围越界
                    refreshed_after_start, refreshed_after_end = refind_after_anchor()
                    if refreshed_after_start is not None and refreshed_after_end is not None:
                        after_start_pos = refreshed_after_start
                        after_end_pos = refreshed_after_end
                        print(f"删除前重新定位后置锚点成功，起始: {after_start_pos}，结束: {after_end_pos}")
                    else:
                        print("警告: 删除前未能重新定位后置锚点，将使用旧位置，可能存在风险")
                    
                    # 合法性校验，避免 Range 越界
                    doc_end = doc.Content.End
                    if (
                        after_start_pos is None
                        or before_end_pos is None
                        or after_start_pos <= before_end_pos
                        or after_start_pos > doc_end
                        or before_end_pos < 0
                        or before_end_pos > doc_end
                    ):
                        print(f"错误: 锚点位置异常，放弃删除。before_end_pos={before_end_pos}, after_start_pos={after_start_pos}, doc_end={doc_end}")
                    else:
                        print("开始逐步删除（逐段/表格），每次删除前重新定位后置锚点以避免越界")
                        max_steps = 2000  # 防止极端情况下无限循环
                        step_idx = 0
                        while step_idx < max_steps:
                            step_idx += 1
                            # 每步重新定位后置锚点，保证范围不越界
                            refreshed_after_start, refreshed_after_end = refind_after_anchor()
                            if refreshed_after_start is not None and refreshed_after_end is not None:
                                after_start_pos = refreshed_after_start
                                after_end_pos = refreshed_after_end
                            else:
                                print("逐步删除时未能重新定位后置锚点，停止删除以避免误删")
                                break
                            
                            if (
                                after_start_pos is None
                                or before_end_pos is None
                                or after_start_pos <= before_end_pos
                                or after_start_pos > doc_end
                                or before_end_pos < 0
                                or before_end_pos > doc_end
                            ):
                                print(f"逐步删除结束：范围异常。before_end_pos={before_end_pos}, after_start_pos={after_start_pos}, doc_end={doc_end}")
                                break
                            
                            delete_rng = doc.Range(before_end_pos, after_start_pos)
                            
                            # 优先删除范围内的第一张表
                            try:
                                tables = list(delete_rng.Tables)
                            except Exception:
                                tables = []
                            if tables:
                                tbl = tables[0]
                                tbl_rng = tbl.Range
                                
                                # === 关键修复：检查表格是否超出删除范围（包含后置锚点）===
                                if tbl_rng.End > after_start_pos:
                                    print("  提示: 表格超出删除范围（可能包含后置锚点），启用安全截断删除")
                                    try:
                                        # 只删除到锚点之前
                                        safe_del_rng = doc.Range(tbl_rng.Start, after_start_pos)
                                        if is_range_locked(safe_del_rng):
                                            before_end_pos = after_start_pos
                                        else:
                                            safe_del_rng.Delete()
                                        continue
                                    except Exception as safe_tbl_e:
                                        print(f"  安全删除表格部分失败: {safe_tbl_e}")
                                        before_end_pos = after_start_pos
                                        continue
                                
                                if is_range_locked(tbl_rng):
                                    # 跳过被保护表格，移动指针到表格末尾继续
                                    before_end_pos = tbl_rng.End
                                    # 防御性检查：确保不跳过锚点
                                    if before_end_pos > after_start_pos:
                                        before_end_pos = after_start_pos
                                    continue
                                try:
                                    tbl.Delete()
                                    continue
                                except Exception:
                                    try:
                                        safe_start = max(delete_rng.Start, tbl_rng.Start - 1)
                                        safe_end = min(delete_rng.End, tbl_rng.End + 1)
                                        # 再次确保不超过 after_start_pos
                                        if safe_end > after_start_pos:
                                            safe_end = after_start_pos
                                        doc.Range(safe_start, safe_end).Delete()
                                        continue
                                    except Exception as del_tbl_e:
                                        err = str(del_tbl_e)
                                        if "锁定" not in err and "locked" not in err.lower() and "-2146823683" not in err:
                                            print(f"  删除表格失败: {del_tbl_e}")
                                        # 即使失败，移动指针以避免卡死
                                        before_end_pos = min(doc_end, tbl_rng.End)
                                        # 确保不跳过锚点
                                        if before_end_pos > after_start_pos:
                                            before_end_pos = after_start_pos
                                        continue
                            
                            # 其次删除范围内的第一段
                            try:
                                paras = list(delete_rng.Paragraphs)
                            except Exception:
                                paras = []
                            if paras:
                                para_rng = paras[0].Range
                                
                                # === 关键修复：检查段落是否超出删除范围（包含后置锚点）===
                                if para_rng.End > after_start_pos:
                                    # 这种情况通常发生在锚点位于段落中间或段落末尾（如软回车）
                                    # 我们必须确保不删除锚点
                                    try:
                                        # 只删除到锚点之前
                                        safe_del_rng = doc.Range(para_rng.Start, after_start_pos)
                                        if is_range_locked(safe_del_rng):
                                            before_end_pos = after_start_pos
                                        else:
                                            safe_del_rng.Delete()
                                        continue
                                    except Exception as safe_para_e:
                                        print(f"  安全删除段落部分失败: {safe_para_e}")
                                        before_end_pos = after_start_pos
                                        continue

                                if is_range_locked(para_rng):
                                    # 跳过受保护段落，移动指针到段末
                                    before_end_pos = para_rng.End
                                    # 防御性检查：确保不跳过锚点
                                    if before_end_pos > after_start_pos:
                                        before_end_pos = after_start_pos
                                    continue
                                try:
                                    para_rng.Delete()
                                    continue
                                except Exception as para_del_e:
                                    err = str(para_del_e)
                                    if "锁定" not in err and "locked" not in err.lower() and "-2146823683" not in err:
                                        print(f"  删除段落失败: {para_del_e}")
                                    before_end_pos = min(doc_end, para_rng.End)
                                    # 确保不跳过锚点
                                    if before_end_pos > after_start_pos:
                                        before_end_pos = after_start_pos
                                    continue
                            
                            # 若无段落/表格可删，尝试按字符删除一个小块
                            try:
                                chunk_end = min(after_start_pos, delete_rng.Start + 50)
                                if chunk_end > delete_rng.Start:
                                    small_rng = doc.Range(delete_rng.Start, chunk_end)
                                    if is_range_locked(small_rng):
                                        before_end_pos = chunk_end
                                        continue
                                    small_rng.Delete()
                                    continue
                            except Exception as char_del_e:
                                err = str(char_del_e)
                                if "锁定" not in err and "locked" not in err.lower() and "-2146823683" not in err:
                                    print(f"  删除字符块失败: {char_del_e}")
                                before_end_pos = min(doc_end, delete_rng.End)
                                continue
                            
                            # 没有可删除内容，结束
                            print("逐步删除结束：无更多可删除内容或均受保护")
                            break
                    
                        # 记录页码范围供后续节点参考（不再参与删除）
                        start_page = before_page + 1
                        end_page = after_page - 1
        
                        # 在"交付日期"所在行行首插入换行（确保锚点在前置锚后）
                        try:
                            def refind_before_anchor():
                                """重新查找前置锚点，获取新的结束位置"""
                                rng = doc.Content.Duplicate
                                finder = rng.Find
                                finder.ClearFormatting()
                                finder.Text = before_text
                                finder.Forward = True
                                finder.Wrap = wdFindStop
                                finder.MatchCase = False
                                finder.MatchWholeWord = False
                                while finder.Execute():
                                    font_name = rng.Font.Name
                                    font_size = rng.Font.Size
                                    is_font = (font_name == "宋体" or font_name == "SimSun")
                                    is_size = abs(font_size - 18.0) < 0.5
                                    if is_font and is_size:
                                        return rng.End
                                    rng.Collapse(wdCollapseEnd)
                                    rng.End = doc.Content.End
                                return None
                            
                            def find_anchor_after(start_pos, texts):
                                search_rng = doc.Content.Duplicate
                                search_rng.Start = start_pos
                                search_rng.End = doc.Content.End
                                finder = search_rng.Find
                                finder.ClearFormatting()
                                finder.Forward = True
                                finder.Wrap = wdFindStop
                                finder.MatchCase = False
                                finder.MatchWholeWord = False
                                for anchor_text in texts:
                                    search_rng.Start = start_pos
                                    search_rng.End = doc.Content.End
                                    finder.Text = anchor_text
                                    if finder.Execute():
                                        return search_rng.Start
                                return None
                            
                            def insert_newline_at(pos):
                                safe_pos = min(max(0, pos), doc.Content.End)
                                try:
                                    rng = doc.Range(safe_pos, safe_pos)
                                    rng.InsertBefore("\r")
                                    print(f"已在位置 {safe_pos} 强制插入换行")
                                    return True
                                except Exception as ins_e:
                                    print(f"警告: 在位置 {safe_pos} 插入换行失败: {ins_e}")
                                    return False
                            
                            inserted = False
                            refreshed_before_end = refind_before_anchor()
                            anchor_search_start = refreshed_before_end if refreshed_before_end is not None else (before_end_pos or 0)
                            anchor_pos = find_anchor_after(anchor_search_start, ["交付日期：", "交付日期:"])
                            if anchor_pos is not None:
                                try:
                                    para = doc.Range(anchor_pos, anchor_pos).Paragraphs(1)
                                    para_text = para.Range.Text.replace("\r", "\\r").replace("\n", "\\n").replace("\a", "")
                                    print(f"调试: refreshed_before_end={refreshed_before_end}, 交付日期所在段落: {para_text}")
                                except Exception as dbg_e:
                                    print(f"调试: refreshed_before_end={refreshed_before_end}, 获取段落文本失败: {dbg_e}")
                            if anchor_pos is not None:
                                try:
                                    para = doc.Range(anchor_pos, anchor_pos).Paragraphs(1)
                                    para_range = para.Range
                                    para_text_raw = para_range.Text
                                    # 尝试在段落文本中找到开头的可编辑字符（优先寻找数字"2"）
                                    insert_offset = 0
                                    try:
                                        idx_digit = para_text_raw.find("2")
                                        if idx_digit >= 0:
                                            insert_offset = idx_digit
                                        else:
                                            # 回退到第一个非空白字符
                                            for i, ch in enumerate(para_text_raw):
                                                if not ch.isspace() and ch not in ("\r", "\n", "\a"):
                                                    insert_offset = i
                                                    break
                                    except Exception:
                                        pass
                                    insert_pos = para_range.Start + insert_offset
                                    print(f"调试: 段落起始={para_range.Start}, 选择插入位置={insert_pos} (相对偏移={insert_offset})")
                                    inserted = insert_newline_at(insert_pos)
                                except Exception as para_e:
                                    print(f'警告: 获取"交付日期"所在段落失败: {para_e}')
                            else:
                                print('提示: 未找到"交付日期"锚点，使用原始插入策略')
                            
                            # 如果未能插入，再退回到原始位置尝试
                            if not inserted and before_end_pos is not None:
                                insert_pos = min(max(0, before_end_pos), doc.Content.End)
                                rng = doc.Range(insert_pos, insert_pos)
                                rng.InsertParagraphAfter()
                                print(f"已在位置 {insert_pos} 插入回车换行（回退方案）")
                        except Exception as newline_e:
                            print(f"警告: 插入回车换行处理失败: {newline_e}")
        
                        # 保存清理后的文档
                        try:
                            print("  开始保存文档...")
                            try:
                                wps.ScreenUpdating = False
                            except Exception:
                                pass
                            
                            print("  正在保存文档（这可能需要几秒钟）...")
                            doc.Save()
                            print("  文档已保存（删除完成）")
                            
                            try:
                                wps.ScreenUpdating = True
                            except Exception:
                                pass
                        except Exception as save_e:
                            print(f"  警告: 保存文档失败: {save_e}")
        
                    # 记录一个逻辑上的页范围供后续节点参考（不再参与删除）
                    start_page = before_page + 1
                    end_page = after_page - 1
                    print(f"[delete_tender_param] 内容删除完成，页码范围: {start_page} - {end_page}")
        
    except Exception as e:
        error_msg = f"删除内容时发生错误: {e}"
        print(f"[delete_tender_param] {error_msg}")
        # 打印详细的错误堆栈信息
        import traceback
        print(f"[delete_tender_param] 详细错误堆栈:")
        traceback.print_exc()
        # 终止图运行：抛出异常而不是吞掉错误
        raise RuntimeError(error_msg) from e
        
    finally:
        print("[delete_tender_param] 开始清理资源...")
        # 使用统一的工具函数关闭 Word 应用程序
        close_word_application(
            word_app=wps,
            doc=doc,
            com_initialized=com_initialized,
            wait_time=1.5,
            node_name="delete_tender_param"
        )
    
    # 更新状态
    new_state_dict = dict(state)
    new_state = TenderGraphState(**new_state_dict)
    log_state("delete_tender_param", new_state)
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"[delete_tender_param] 执行完成，耗时: {elapsed_time:.2f} 秒 ({elapsed_time*1000:.0f} 毫秒)")
    
    return new_state

