from __future__ import annotations

import os
import shutil
import time
from typing import Dict, Iterable, Tuple

import pythoncom
import win32com.client as win32

# 处理相对导入和直接运行的情况
try:
    from ...config import AgentConfig
    from ...logging_utils import log_state, log_state_start
    from ...state import TenderGraphState
except ImportError:
    # 直接运行时使用绝对导入
    import pathlib
    import sys
    ROOT = pathlib.Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from config import AgentConfig
    from logging_utils import log_state, log_state_start
    from state import TenderGraphState

WD_FIND_STOP = 0
WD_COLLAPSE_END = 0
WD_NO_PROTECTION = -1


def prepare_template(state: TenderGraphState, config) -> TenderGraphState:
    start_time = time.time()
    print(f"[prepare_template] 开始执行...")
    
    agent_config = AgentConfig.from_runnable_config(config)

    template_override = state.get("origin_tender_path")

    template_path = os.path.abspath(
        template_override or agent_config.resolve_template_path()
    )

    if not os.path.exists(template_path):
        raise FileNotFoundError(f"未找到模板: {template_path}")

    # 创建工作路径（使用 project_number-project_name-初稿 格式）
    template_dir = os.path.dirname(template_path)
    _, ext = os.path.splitext(template_path)
    
    # 从 state 中获取项目编号和项目名称
    project_number = state.get("project_number", "")
    project_name = state.get("project_name", "")
    
    # 构建文件名：project_number-project_name-初稿-YYYYMMDD-HHMMSS.doc
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    if project_number and project_name:
        filename = f"{project_number}-{project_name}-初稿-{timestamp}.doc"
    elif project_number:
        filename = f"{project_number}-初稿-{timestamp}.doc"
    elif project_name:
        filename = f"{project_name}-初稿-{timestamp}.doc"
    else:
        # 如果没有项目信息，使用原来的命名方式
        root, _ = os.path.splitext(os.path.basename(template_path))
        filename = f"{root}_processed-{timestamp}.doc"
    
    working_path = os.path.join(template_dir, filename)

    if os.path.isdir(working_path):
        raise IsADirectoryError(f"输出路径指向一个目录: {working_path}")

    # 如果工作文件已存在，先删除
    # 添加重试机制，因为文件可能被 Word 锁定
    if os.path.exists(working_path) and os.path.isfile(working_path):
        max_retries = 5
        retry_delay = 0.5
        for retry in range(max_retries):
            try:
                os.remove(working_path)
                break  # 成功删除，退出重试循环
            except PermissionError:
                if retry < max_retries - 1:
                    # 等待后重试，可能是 Word 还在使用文件
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                else:
                    # 最后一次重试失败，抛出异常
                    raise PermissionError(
                        f"无法删除现有文件 '{working_path}': "
                        f"文件被其他进程锁定 (可能是 Word)。 "
                        f"请关闭 Word 后重试。"
                    )
            except Exception as e:
                # 其他错误，直接抛出
                raise

    # 确保目录存在
    os.makedirs(os.path.dirname(working_path), exist_ok=True)
    
    # 复制模板文件到工作路径
    shutil.copy2(template_path, working_path)
    
    # 验证复制后的文件是否可以被 Word 正常打开
    # 这可以确保后续节点能够正常处理该文件
    word = None
    doc = None
    com_initialized = False
    try:
        pythoncom.CoInitialize()
        com_initialized = True
        word = win32.Dispatch("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0  # 不显示警告对话框
        
        # 使用与 get_replacements.py 和 replace_content.py 相同的参数打开文档
        doc = word.Documents.Open(
            FileName=working_path,
            ConfirmConversions=False,
            ReadOnly=True,  # 只读模式打开，仅用于验证
            AddToRecentFiles=False,
            NoEncodingDialog=True
        )
        # 如果成功打开，立即关闭（不保存）
        # 这样可以验证文件是否可以被 Word 正常打开，并修复一些格式问题
        doc.Close(SaveChanges=False)
    except Exception as e:
        # 如果打开失败，记录错误但不抛出异常
        # 因为可能是文档本身的问题，后续节点会处理
        import logging
        logging.warning(f"警告: 无法验证复制的文档 '{working_path}': {e}")
        # 即使出错，也要确保关闭 Word
        if 'doc' in locals() and doc:
            try:
                doc.Close(SaveChanges=False)
            except:
                pass
        if 'word' in locals() and word:
            try:
                word.Quit(SaveChanges=False)
            except:
                pass
    finally:
        # 安全地关闭文档（必须在关闭 Word 之前）
        if 'doc' in locals() and doc:
            try:
                # 检查文档是否仍然有效
                try:
                    _ = doc.Name
                    doc.Close(SaveChanges=False)
                except AttributeError:
                    # 如果对象已断开，尝试强制关闭
                    try:
                        doc.Close(SaveChanges=False)
                    except Exception:
                        pass
                except Exception:
                    pass
            except Exception:
                pass
        
        # 安全地关闭 Word 应用程序（必须最后执行）
        if 'word' in locals() and word:
            try:
                # 检查 word 对象是否仍然有效
                try:
                    _ = word.Name
                    word.Quit(SaveChanges=False)
                except AttributeError:
                    # 如果对象已断开，尝试强制退出
                    try:
                        word.Quit(SaveChanges=False)
                    except Exception:
                        pass
                except Exception:
                    pass
            except Exception:
                pass
        
        # 添加短暂延迟，确保 Word 进程完全退出
        time.sleep(0.2)
        
        # 安全地清理 COM（必须在关闭 Word 之后）
        if com_initialized:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
    
    stats = None

    new_state_dict = dict(state)
    new_state_dict.update(
        {
            "origin_tender_path": template_path,
            "prepared_doc_path": working_path,
            "insertion_log": ", ".join(f"{k}x{v}" for k, v in stats.items()) if stats else "无替换",
        }
    )
    new_state = TenderGraphState(**new_state_dict)
    log_state_start("prepare_template", new_state)
    log_state("prepare_template", new_state)
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"[prepare_template] 执行完成，耗时: {elapsed_time:.2f} 秒 ({elapsed_time*1000:.0f} 毫秒)")
    
    return new_state
