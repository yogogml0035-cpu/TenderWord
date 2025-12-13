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
    ROOT = pathlib.Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from logging_utils import log_state
    from state import TenderGraphState

# Word constants
wdFindStop = 0
wdCollapseEnd = 0
wdActiveEndPageNumber = 7  # Information property constant for page number


def _get_page_number(rng) -> int:
    """
    获取 Word Range 所在的页数。
    
    返回页数，如果无法获取则返回 -1。
    """
    try:
        page_num = rng.Information(wdActiveEndPageNumber)
        return int(page_num) if page_num else -1
    except Exception:
        return -1


def replace_content(state: TenderGraphState, config) -> TenderGraphState:
    """
    在 Word 文档中替换指定的内容，包括页眉页脚等所有部分。
    
    从 state 中读取 replacements 列表（由 get_replacements 节点生成）。
    替换前会检查内容是否处于保护状态，受保护的内容不会被替换。
    
    Word 文档的页眉页脚类型说明：
    - 首页页眉/页脚：文档第一页的页眉页脚（如果启用了"首页不同"选项）
    - 奇数页页眉/页脚（Primary）：第1、3、5...页的页眉页脚
    - 偶数页页眉/页脚（Even Pages）：第2、4、6...页的页眉页脚
    这种设计主要用于双面打印，使左右页面的页眉页脚可以不同。
    
    日志会记录：
    - 找到了多少条替换的内容
    - 多少条已被成功替换
    - 多少条因为保护状态替换失败
    - 失败的内容和所在页数
    """
    start_time = time.time()
    print(f"[replace_content] 开始执行...")
    
    prepared_doc_path = state.get("prepared_doc_path")
    
    if not prepared_doc_path:
        raise ValueError("需要 prepared_doc_path 来替换 Word 文档中的内容")
    
    # 确保路径是绝对路径（Word COM 对象需要绝对路径）
    if not os.path.isabs(prepared_doc_path):
        prepared_doc_path = os.path.abspath(prepared_doc_path)
    
    # 检查文件是否存在
    if not os.path.exists(prepared_doc_path):
        raise FileNotFoundError(f"未找到准备好的文档: {prepared_doc_path}")
    
    # 检查文件是否可读
    if not os.access(prepared_doc_path, os.R_OK):
        raise PermissionError(f"无法读取准备好的文档: {prepared_doc_path}")
    
    # 获取替换列表
    replacements = state.get("replacements")
    
    # 如果没有需要替换的内容，直接返回
    if not replacements:
        replacement_log = "未指定替换内容，跳过内容替换。"
        new_state_dict = dict(state)
        new_state_dict["replacement_log"] = replacement_log
        new_state = TenderGraphState(**new_state_dict)
        log_state("replace_content", new_state)
        return new_state
    
    replacement_log_parts = []
    word = None
    doc = None
    
    # 统计信息
    total_stats = {
        "total_found": 0,
        "total_replaced": 0,
        "total_error": 0,
    }
    
    # 记录失败的替换详情
    failed_replacements = []
    
    try:
        pythoncom.CoInitialize()
        
        # 独立实例 + 预留时间，避免前序节点关闭未完成导致句柄失效
        initial_delay = 1.0  # 创建前等待 1 秒，让之前的实例有时间完全关闭
        print(f"[replace_content] 等待 {initial_delay} 秒后创建 Microsoft Word 实例...")
        time.sleep(initial_delay)
        
        # 使用 DispatchEx 独立实例
        word = win32.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        time.sleep(1)
        print("[replace_content] 成功创建新的 Word 实例 (DispatchEx)")
        
        # 打开文档时增加重试以避免 COM 接口尚未就绪
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
        if doc is None and last_error:
            # 理论上上面的 raise 已经抛出，但为了保险保留提示
            raise last_error
        replacement_log_parts.append(f"已打开: {prepared_doc_path}")
        
        # 尝试取消保护
        try:
            if doc.ProtectionType != -1:  # -1 表示 wdNoProtection
                doc.Unprotect()
        except Exception:
            pass
        
        print(f"开始替换 {len(replacements)} 对替换内容...")
        
        # 判断哪些替换是项目内容、项目名称和项目编号
        # 通过 placeholder_mapping 来判断
        placeholder_mapping = state.get("placeholder_mapping", {})
        project_content_placeholder = placeholder_mapping.get("project_content")
        project_number_placeholder = placeholder_mapping.get("project_number")
        project_name_placeholder = placeholder_mapping.get("project_name")
        
        # 将替换对分为三类：
        # 1. project_content_replacements - 项目内容（最先处理，只在正文中）
        # 2. header_replacements - 项目名称和项目编号（在页眉和正文中）
        # 3. body_replacements - 其他内容（只在正文中）
        project_content_replacements = []  # 项目内容替换（最先处理）
        header_replacements = []  # 需要遍历页眉和正文的替换
        body_replacements = []    # 只需要遍历正文的替换
        
        for search_text, replace_text in replacements:
            if search_text == project_content_placeholder:
                project_content_replacements.append((search_text, replace_text))
            elif search_text == project_number_placeholder or search_text == project_name_placeholder:
                header_replacements.append((search_text, replace_text))
            else:
                body_replacements.append((search_text, replace_text))
        
        story_type_names = {
            1: "正文",
            6: "偶数页页眉",
            7: "奇数页页眉",
            10: "首页页眉",
        }
        
        # 定义需要处理的 StoryType
        # 项目内容：只处理正文(1) - 最先处理
        # 项目名称和项目编号：正文(1) + 页眉(6, 7, 10)
        # 其他内容：只处理正文(1)
        project_content_story_types = {1}  # 只处理正文
        header_story_types = {1, 6, 7, 10}  # 正文和所有页眉
        body_story_types = {1}  # 只处理正文
        
        def process_replacements_in_range(rng, replacements_to_process, story_type_name, doc):
            """在指定的 Range 中处理替换"""
            comment_text = "ERP系统数据"  # 统一的批注内容
            
            for rep_idx, (search_text, replace_text) in enumerate(replacements_to_process, 1):
                print(f"  [{rep_idx}/{len(replacements_to_process)}] 正在在 [{story_type_name}] 中搜索 '{search_text}'...")
                
                # 创建搜索范围的副本，避免丢失原始引用
                search_rng = rng.Duplicate
                find = search_rng.Find
                find.ClearFormatting()
                find.Text = search_text
                find.Forward = True
                find.Wrap = wdFindStop
                find.MatchCase = False
                find.MatchWholeWord = False
                
                count = 0
                # Execute 返回 True 如果找到
                while find.Execute():
                    count += 1
                    total_stats["total_found"] += 1
                    
                    # 获取页数
                    page_num = _get_page_number(search_rng)
                    page_info = f"第 {page_num} 页" if page_num > 0 else "未知页码"
                    
                    try:
                        search_rng.Text = replace_text
                        total_stats["total_replaced"] += 1
                        print(f"    [已替换] '{search_text}' -> '{replace_text}' 在 {page_info}")
                        
                        # 在替换后的文本上添加批注
                        try:
                            # 获取替换后的文本范围（search_rng 现在包含替换后的文本）
                            comment_range = search_rng.Duplicate
                            doc.Comments.Add(Range=comment_range, Text=comment_text)
                            print(f"    [批注] 已为替换后的文本添加批注 '{comment_text}'")
                        except Exception as comment_e:
                            # 如果添加批注失败，记录但不影响替换操作
                            print(f"    [警告] 添加批注失败: {comment_e}")
                        
                        search_rng.Collapse(wdCollapseEnd)
                    except Exception as e:
                        total_stats["total_error"] += 1
                        failed_replacements.append((search_text, page_num, str(e)))
                        print(f"    [错误] 在 {page_info} 找到 '{search_text}' 但编辑失败: {e}")
                        search_rng.Collapse(wdCollapseEnd)
                
                if count > 0:
                    print(f"  摘要: 在 [{story_type_name}] 中将 '{search_text}' 替换为 '{replace_text}' 共 {count} 处")
        
        # 一次遍历处理所有替换，按优先级顺序：project_content -> header -> body
        if project_content_replacements:
            print(f"正在处理项目内容替换 ({len(project_content_replacements)} 对) 在正文中（优先处理）...")
        if header_replacements:
            print(f"正在处理项目编号/项目名称替换 ({len(header_replacements)} 对) 在页眉和正文中...")
        if body_replacements:
            print(f"正在处理其他替换 ({len(body_replacements)} 对) 仅在正文中...")
        
        # 遍历所有 StoryRanges，根据类型决定处理哪些替换
        # 处理顺序：1. project_content（正文） 2. header（页眉和正文） 3. body（正文）
        for story_range in doc.StoryRanges:
            rng = story_range
            while rng:
                story_type = rng.StoryType
                story_type_name = story_type_names.get(story_type, f"未知类型 {story_type}")
                
                # 1. 优先处理项目内容（只在正文中）
                if project_content_replacements and story_type in project_content_story_types:
                    print(f"正在处理 [{story_type_name}]...")
                    process_replacements_in_range(rng, project_content_replacements, story_type_name, doc)
                
                # 2. 处理项目名称和项目编号（在正文和页眉中）
                if header_replacements and story_type in header_story_types:
                    # 如果已经在处理 project_content 时打印过，这里不再重复打印
                    if not (project_content_replacements and story_type in project_content_story_types):
                        print(f"正在处理 [{story_type_name}]...")
                    process_replacements_in_range(rng, header_replacements, story_type_name, doc)
                
                # 3. 处理其他内容（只在正文中）
                if body_replacements and story_type in body_story_types:
                    # 如果已经在处理 project_content 或 header 时打印过，这里不再重复打印
                    if not (project_content_replacements and story_type in project_content_story_types) and \
                       not (header_replacements and story_type in header_story_types):
                        print(f"正在处理 [{story_type_name}]...")
                    process_replacements_in_range(rng, body_replacements, story_type_name, doc)
                
                try:
                    rng = rng.NextStoryRange
                except:
                    break
        
        # 生成最终统计报告
        replacement_log_parts.append("=" * 60)
        replacement_log_parts.append("替换摘要:")
        replacement_log_parts.append(f"  总计找到: {total_stats['total_found']}")
        replacement_log_parts.append(f"  成功替换: {total_stats['total_replaced']}")
        replacement_log_parts.append(f"  失败 (错误): {total_stats['total_error']}")
        
        if failed_replacements:
            replacement_log_parts.append("")
            replacement_log_parts.append("失败的替换:")
            for search_text, page_num, reason in failed_replacements:
                page_info = f"第 {page_num} 页" if page_num > 0 else "未知页码"
                replacement_log_parts.append(f"  - '{search_text}' 在 {page_info}: {reason}")
        
        replacement_log_parts.append("=" * 60)
        replacement_log_parts.append("内容替换完成。")
        
        doc.Save()
        replacement_log_parts.append("文档已保存。")
            
    finally:
        print("[replace_content] 开始清理资源...")
        # 安全关闭文档
        if doc:
            try:
                print("[replace_content] 正在关闭文档...")
                try:
                    _ = doc.Name  # 尝试访问属性来检查对象是否有效
                    doc.Close(SaveChanges=False)
                    print("[replace_content] 文档已关闭")
                except AttributeError:
                    print("[replace_content] 文档对象已断开，无需关闭")
                except Exception as close_doc_e:
                    print(f"[replace_content] 关闭文档时出错: {close_doc_e}")
            except Exception:
                pass
        
        # 安全关闭 Word 应用程序
        if word:
            try:
                print("[replace_content] 正在关闭 Word 应用程序...")
                try:
                    _ = word.Name  # 尝试访问属性来检查对象是否有效
                    word.Quit(SaveChanges=False)
                    print("[replace_content] Word 应用程序已关闭")
                except AttributeError:
                    print("[replace_content] Word 对象已断开，无需关闭")
                except Exception as quit_word_e:
                    print(f"[replace_content] 关闭 Word 应用程序时出错: {quit_word_e}")
            except Exception:
                pass
        
        # 添加延迟，确保 Word 进程完全退出
        print("[replace_content] 等待 Word 进程完全退出...")
        time.sleep(1.5)  # 增加等待时间
        
        # 清理残留的 Word 进程
        try:
            import psutil
            word_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'create_time']):
                try:
                    proc_name = proc.info['name'].lower()
                    if proc_name == 'winword.exe':
                        pid = proc.info['pid']
                        create_time = proc.info.get('create_time', 0)
                        if create_time > 0:
                            age_seconds = time.time() - create_time
                            if age_seconds < 600:  # 10分钟内创建的
                                word_processes.append(pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            if word_processes:
                print(f"[replace_content] 检测到 {len(word_processes)} 个可能的残留 Word 进程: {word_processes}")
                for pid in word_processes:
                    try:
                        proc = psutil.Process(pid)
                        proc.terminate()
                        print(f"[replace_content] 已终止残留进程 (PID: {pid})")
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        print(f"[replace_content] 无法终止进程 {pid}: {e}")
                    except Exception as e:
                        print(f"[replace_content] 终止进程 {pid} 时出错: {e}")
        except ImportError:
            print("[replace_content] 未安装 psutil，无法检查残留进程")
        except Exception as cleanup_e:
            print(f"[replace_content] 检查残留进程时出错: {cleanup_e}")
        
        # 安全清理 COM
        try:
            print("[replace_content] 清理 COM 资源...")
            pythoncom.CoUninitialize()
            print("[replace_content] COM 资源已清理")
        except Exception as com_e:
            print(f"[replace_content] 清理 COM 时出错: {com_e}")
    
    # Update state with replacement log
    new_state_dict = dict(state)
    # 使用换行符连接日志，使输出更易读
    replacement_log = "\n".join(replacement_log_parts)
    new_state_dict["replacement_log"] = replacement_log
    new_state_dict["replace_content_done"] = True
    new_state = TenderGraphState(**new_state_dict)
    log_state("replace_content", new_state)
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"[replace_content] 执行完成，耗时: {elapsed_time:.2f} 秒 ({elapsed_time*1000:.0f} 毫秒)")
    
    return new_state

