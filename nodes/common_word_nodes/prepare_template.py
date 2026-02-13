from __future__ import annotations

import os
import shutil
import time
import pathlib
import sys

# 添加项目根目录到 sys.path
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from states import TenderGraphStateBase
from util.word_application_util import (
    create_word_application,
    close_word_application,
)


def prepare_template(state: TenderGraphStateBase, config) -> TenderGraphStateBase:
    start_time = time.time()
    
    
    from util.logging_utils import log_task_start
    log_task_start(state, "prepare_template")
    tender_type = state.get("tender_type")
    print(f"[Start] 当前类型：{tender_type}")
    print(f"[prepare_template] 开始执行...")
    
    clean_draft_path = state.get("clean_draft_path")
    origin_tender_path = state.get("origin_tender_path")
    template_path = clean_draft_path or origin_tender_path
    if not template_path or (isinstance(template_path, str) and template_path.strip() == ""):
        raise ValueError("未提供可用的模板路径：需要 clean_draft_path（清洁稿）或 origin_tender_path")
    
    template_path = os.path.abspath(template_path)

    if not os.path.exists(template_path):
        raise FileNotFoundError(f"未找到模板: {template_path}")

    # 创建工作路径（使用 project_number-project_name-初稿 格式）
    template_dir = os.path.dirname(template_path)
    _, ext = os.path.splitext(template_path)
    ext = ext.lower()
    
    # 从 state 中获取项目编号和项目名称
    project_number = state.get("project_number", "")
    project_name = state.get("project_name", "")
    
    # 构建文件名：project_number-project_name-初稿-YYYYMMDD-HHMMSS.doc
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    if project_number and project_name:
        filename = f"{project_number}-{project_name}-初稿-{timestamp}{ext}"
    elif project_number:
        filename = f"{project_number}-初稿-{timestamp}{ext}"
    elif project_name:
        filename = f"{project_name}-初稿-{timestamp}{ext}"
    else:
        # 如果没有项目信息，使用原来的命名方式
        root, _ = os.path.splitext(os.path.basename(template_path))
        filename = f"{root}_processed-{timestamp}{ext}"
    
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
        # 使用统一的工具函数创建 Word 应用程序
        word, com_initialized = create_word_application(
            initial_delay=0.0,  # 不需要等待
            post_init_delay=0.0,  # 不需要等待
            use_existing=False,  # 创建新实例
            verify=False,  # 验证步骤在工具函数中已包含
            node_name="prepare_template"
        )
        
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
        doc = None  # 避免将已关闭的 doc 传给 close_word_application 导致 RPC_E_DISCONNECTED
    except Exception as e:
        # 如果打开失败，记录错误但不抛出异常
        # 因为可能是文档本身的问题，后续节点会处理
        import logging
        logging.warning(f"警告: 无法验证复制的文档 '{working_path}': {e}")
    finally:
        # 使用统一的工具函数关闭 Word 应用程序
        close_word_application(
            word_app=word,
            doc=doc,
            com_initialized=com_initialized,
            wait_time=0.2,
            node_name="prepare_template"
        )
    
    stats = None

    new_state_dict = dict(state)
    new_state_dict.update(
        {
            "prepared_doc_path": working_path,
        }
    )
    new_state = TenderGraphStateBase(**new_state_dict)
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"[prepare_template] 执行完成，耗时: {elapsed_time:.2f} 秒 ({elapsed_time*1000:.0f} 毫秒)")
    
    return new_state
