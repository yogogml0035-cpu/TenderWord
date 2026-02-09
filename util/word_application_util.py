"""
Word 应用程序创建工具函数

提供统一的 Word.Application 创建和初始化逻辑，供各个节点使用。
集成了 COM 并发管理器，支持多线程安全访问。
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from typing import Optional, Tuple

# 获取 logger
logger = logging.getLogger(__name__)

try:
    import pythoncom
except ImportError:
    pythoncom = None

try:
    import win32com.client as win32
    import win32com
except ImportError:
    win32 = None
    win32com = None

# 导入 COM 管理器
from util.word_com_manager import (
    com_lock,
    is_rpc_error,
    calculate_retry_delay,
    MAX_RETRIES,
    RPC_ERROR_CODES,
)

# 导入诊断工具
try:
    from util.word_diagnostics import (
        diagnose_word_com_environment,
        format_diagnosis_report,
        check_word_installation,
    )
    DIAGNOSTICS_AVAILABLE = True
except ImportError:
    DIAGNOSTICS_AVAILABLE = False


def is_gencache_error(exception: Exception) -> bool:
    """
    检测是否为 win32com gen_py 缓存损坏错误
    
    参数:
        exception: 捕获的异常
        
    返回:
        bool: 如果是缓存损坏错误返回 True
    """
    error_msg = str(exception).lower()
    # 检测常见的缓存损坏错误特征
    cache_error_patterns = [
        "clsidtopackagemap",
        "clsidtoclass",
        "gen_py",
        "gencache",
        "no attribute 'clsid",
    ]
    return any(pattern in error_msg for pattern in cache_error_patterns)


def clear_win32com_cache() -> bool:
    """
    清除 win32com 的 gen_py 缓存目录
    
    当 win32com 缓存损坏时调用此函数可以修复问题。
    
    返回:
        bool: 如果成功清除缓存返回 True，否则返回 False
    """
    if win32com is None:
        logger.warning("[win32com缓存] win32com 未安装，无法清除缓存")
        return False
    
    try:
        # 获取 gen_py 缓存目录路径
        gen_py_path = win32com.__gen_path__
        
        if not gen_py_path:
            logger.warning("[win32com缓存] 未找到 gen_py 缓存路径")
            return False
        
        # 获取父目录（gen_py 目录本身，而不是版本子目录）
        # win32com.__gen_path__ 通常返回类似 C:\Users\xxx\AppData\Local\Temp\gen_py\3.11
        # 我们需要删除整个 gen_py 目录
        gen_py_root = os.path.dirname(gen_py_path)
        if os.path.basename(gen_py_root) == "gen_py":
            cache_dir = gen_py_root
        else:
            cache_dir = gen_py_path
        
        if os.path.exists(cache_dir):
            logger.info(f"[win32com缓存] 正在删除缓存目录: {cache_dir}")
            shutil.rmtree(cache_dir, ignore_errors=True)
            logger.info("[win32com缓存] 缓存目录已删除")
            
            # 重置 gencache 的内部状态
            try:
                if hasattr(win32, 'gencache'):
                    # 清除内存中的缓存映射
                    win32.gencache.bForDemandDefault = 0
                    if hasattr(win32.gencache, '_GetGencache'):
                        win32.gencache._GetGencache()
            except Exception as reset_e:
                logger.debug(f"[win32com缓存] 重置 gencache 状态时出错 (可忽略): {reset_e}")
            
            return True
        else:
            logger.debug(f"[win32com缓存] 缓存目录不存在: {cache_dir}")
            return True  # 目录不存在也算成功
            
    except Exception as e:
        logger.error(f"[win32com缓存] 清除缓存时出错: {e}")
        return False


def create_word_application(
    initial_delay: float = 2.0,
    post_init_delay: float = 0.5,
    use_existing: bool = True,
    verify: bool = True,
    node_name: str = "",
) -> Tuple[any, bool]:
    """
    创建或获取 Word.Application 实例（线程安全）。
    
    此函数使用全局锁确保多线程环境下的安全访问。
    
    参数:
        initial_delay: 创建前等待时间（秒），让之前的实例有时间完全关闭。默认 2.0 秒
        post_init_delay: 创建后等待时间（秒），给 Word 完成初始化的时间。默认 0.5 秒
        use_existing: 是否尝试获取已运行的 Word 实例。默认 True
                     注意：在并发环境下建议设为 False 以避免冲突
        verify: 是否验证 Word 对象是否可用。默认 True
        node_name: 节点名称，用于日志输出。默认空字符串
    
    返回:
        Tuple[word_app, com_initialized]:
            - word_app: Word.Application 对象
            - com_initialized: 是否已初始化 COM（True 表示已初始化，需要在 finally 中调用 CoUninitialize）
    
    异常:
        RuntimeError: 如果无法创建 Word 应用程序实例
        ImportError: 如果无法导入 win32com.client
    """
    # 使用全局锁保护整个创建过程
    with com_lock(operation_name=f"{node_name}-创建Word"):
        return _create_word_application_internal(
            initial_delay=initial_delay,
            post_init_delay=post_init_delay,
            use_existing=use_existing,
            verify=verify,
            node_name=node_name,
        )


def _create_word_application_internal(
    initial_delay: float,
    post_init_delay: float,
    use_existing: bool,
    verify: bool,
    node_name: str,
) -> Tuple[any, bool]:
    """
    内部函数：创建 Word 应用程序实例（带重试机制）
    
    调用此函数前应该已经获取了全局锁。
    """
    if pythoncom is None or win32 is None:
        error_msg = "缺少 Word COM 依赖（pywin32/pythoncom），无法执行 Word 自动化。\n"
        error_msg += "请确保使用已安装 pywin32 的 Python 解释器运行。\n"
        error_msg += "安装命令: pip install pywin32\n"
        if DIAGNOSTICS_AVAILABLE:
            try:
                diagnosis = diagnose_word_com_environment()
                error_msg += "\n环境诊断信息:\n"
                error_msg += format_diagnosis_report(diagnosis)
            except Exception:
                pass
        raise RuntimeError(error_msg)
    
    log_prefix = f"[{node_name}] " if node_name else ""
    
    # 创建前等待，让之前的实例有时间完全关闭
    if initial_delay > 0:
        logger.debug(f"{log_prefix}等待 {initial_delay} 秒后创建 Microsoft Word 实例...")
        time.sleep(initial_delay)
    
    # 初始化 COM
    com_initialized = False
    try:
        pythoncom.CoInitialize()
        com_initialized = True
    except Exception as e:
        raise RuntimeError(f"初始化 COM 失败: {e}")
    
    word_app = None
    last_exception = None
    
    # 带重试机制的 Word 应用程序创建
    for attempt in range(MAX_RETRIES + 1):
        try:
            word_app = _try_create_word_app(use_existing, node_name)
            break  # 创建成功
        except Exception as e:
            last_exception = e
            
            if is_rpc_error(e) and attempt < MAX_RETRIES:
                delay = calculate_retry_delay(attempt)
                logger.warning(f"{log_prefix}创建 Word 失败 (尝试 {attempt + 1}/{MAX_RETRIES + 1}): {e}")
                logger.info(f"{log_prefix}等待 {delay:.1f} 秒后重试...")
                time.sleep(delay)
            else:
                # 创建失败，清理 COM
                if com_initialized:
                    try:
                        pythoncom.CoUninitialize()
                    except Exception:
                        pass
                raise
    
    if word_app is None:
        if com_initialized:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
        if last_exception:
            raise last_exception
        raise RuntimeError("无法创建 Microsoft Word 应用程序实例")
    
    # 创建后等待，给 Word 完成初始化的时间
    if post_init_delay > 0:
        time.sleep(post_init_delay)
    
    # 验证 Word 对象是否可用
    if verify:
        try:
            app_name = word_app.Name
            logger.info(f"{log_prefix}使用 Microsoft Word (名称: {app_name})")
        except Exception as verify_e:
            if com_initialized:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass
            raise RuntimeError(f"Word 实例创建但验证失败: {verify_e}")
    
    return word_app, com_initialized


def _try_create_word_app(use_existing: bool, node_name: str, cache_cleared: bool = False) -> any:
    """
    尝试创建 Word 应用程序实例
    
    按优先级尝试三种方法：
    1. GetActiveObject - 获取已运行的实例
    2. DispatchEx - 创建新的独立实例
    3. EnsureDispatch - 备选方法
    
    如果遇到 win32com 缓存损坏错误，会自动清除缓存并重试一次。
    
    参数:
        use_existing: 是否尝试获取已运行的 Word 实例
        node_name: 节点名称，用于日志输出
        cache_cleared: 内部参数，标记是否已经清除过缓存（避免无限递归）
    """
    log_prefix = f"[{node_name}] " if node_name else ""
    word_app = None
    creation_method = None
    last_exception = None
    
    # 方法1: 尝试获取已运行的 Word 实例（如果启用）
    if use_existing:
        try:
            word_app = win32.GetActiveObject("Word.Application")
            word_app.Visible = False
            word_app.DisplayAlerts = 0
            creation_method = "GetActiveObject"
            logger.info(f"{log_prefix}成功获取已运行的 Word 实例")
        except Exception as e:
            last_exception = e
            pass  # 继续尝试其他方法
    
    # 方法2: 创建新的独立实例（DispatchEx）
    if word_app is None:
        try:
            word_app = win32.DispatchEx("Word.Application")
            word_app.Visible = False
            word_app.DisplayAlerts = 0
            creation_method = "DispatchEx"
            logger.info(f"{log_prefix}成功创建新的 Word 实例 (DispatchEx)")
        except Exception as e:
            last_exception = e
            pass  # 继续尝试其他方法
    
    # 方法3: 使用 EnsureDispatch 作为备选
    if word_app is None:
        try:
            word_app = win32.gencache.EnsureDispatch("Word.Application")
            word_app.Visible = False
            word_app.DisplayAlerts = 0
            creation_method = "EnsureDispatch"
            logger.info(f"{log_prefix}成功创建新的 Word 实例 (EnsureDispatch)")
        except Exception as e:
            last_exception = e
            # 所有方法都失败，检查是否为缓存错误
            pass
    
    # 如果创建失败，检查是否为缓存损坏错误
    if word_app is None and last_exception is not None:
        if not cache_cleared and is_gencache_error(last_exception):
            logger.warning(f"{log_prefix}检测到 win32com 缓存损坏，正在自动清除缓存...")
            if clear_win32com_cache():
                logger.info(f"{log_prefix}缓存已清除，正在重试创建 Word 实例...")
                # 递归调用，标记已清除缓存
                return _try_create_word_app(use_existing, node_name, cache_cleared=True)
            else:
                logger.error(f"{log_prefix}清除缓存失败，请手动删除 win32com gen_py 缓存目录")
        
        # 生成详细的错误信息
        error_msg = f"无法创建 Word 应用程序实例\n"
        error_msg += f"错误详情: {last_exception}\n\n"
        
        # 添加诊断信息
        if DIAGNOSTICS_AVAILABLE:
            try:
                word_check = check_word_installation()
                if not word_check.get("installed"):
                    error_msg += "【问题诊断】\n"
                    error_msg += f"  ✗ 未检测到 Word 或 WPS 安装\n"
                    error_msg += f"  错误: {word_check.get('error', 'Unknown')}\n\n"
                    error_msg += "【解决方案】\n"
                    error_msg += "  1. 确保已安装 Microsoft Word 或 WPS Office\n"
                    error_msg += "  2. 如果已安装但检测不到，可能需要:\n"
                    error_msg += "     - 修复 Office 安装\n"
                    error_msg += "     - 重新注册 COM 组件 (以管理员身份运行: regsvr32 /s <Office路径>\\MSO.DLL)\n"
                    error_msg += "     - 检查 Word 版本是否与 pywin32 兼容\n"
                else:
                    word_name = word_check.get("name", "Word")
                    word_version = word_check.get("version", "Unknown")
                    error_msg += "【环境信息】\n"
                    error_msg += f"  检测到: {word_name} (版本: {word_version})\n"
                    error_msg += f"  COM ProgID: {word_check.get('com_progid', 'Unknown')}\n\n"
                    error_msg += "【可能的原因】\n"
                    error_msg += "  1. Word 版本不兼容（建议使用 Office 2016 或更高版本）\n"
                    error_msg += "  2. Word 正在被其他程序占用\n"
                    error_msg += "  3. COM 接口注册问题\n"
                    error_msg += "  4. 权限不足（尝试以管理员身份运行）\n"
            except Exception as diag_e:
                logger.debug(f"{log_prefix}生成诊断信息时出错: {diag_e}")
        
        # 抛出详细的异常
        raise RuntimeError(error_msg)
    
    return word_app


def close_word_application(
    word_app: Optional[any],
    doc: Optional[any] = None,
    com_initialized: bool = False,
    wait_time: float = 1.5,
    node_name: str = "",
) -> None:
    """
    安全关闭 Word 应用程序和文档，并清理 COM 资源（线程安全）。
    
    此函数使用全局锁确保多线程环境下的安全访问。
    
    参数:
        word_app: Word.Application 对象，可以为 None
        doc: Word.Document 对象，可以为 None（会在关闭 Word 前关闭）
        com_initialized: 是否已初始化 COM（如果为 True，会调用 CoUninitialize）
        wait_time: 关闭后等待时间（秒），确保进程完全退出。默认 1.5 秒
        node_name: 节点名称，用于日志输出。默认空字符串
    """
    # 使用全局锁保护整个关闭过程
    with com_lock(operation_name=f"{node_name}-关闭Word"):
        _close_word_application_internal(
            word_app=word_app,
            doc=doc,
            com_initialized=com_initialized,
            wait_time=wait_time,
            node_name=node_name,
        )


def _close_word_application_internal(
    word_app: Optional[any],
    doc: Optional[any],
    com_initialized: bool,
    wait_time: float,
    node_name: str,
) -> None:
    """
    内部函数：关闭 Word 应用程序
    
    调用此函数前应该已经获取了全局锁。
    """
    log_prefix = f"[{node_name}] " if node_name else ""
    
    # 安全关闭文档（必须在关闭 Word 之前）
    if doc is not None:
        try:
            logger.debug(f"{log_prefix}正在关闭文档...")
            try:
                _ = doc.Name  # 尝试访问属性来检查对象是否有效
                doc.Close(SaveChanges=False)
                logger.debug(f"{log_prefix}文档已关闭")
            except AttributeError:
                # 对象已断开，说明已经关闭了
                logger.debug(f"{log_prefix}文档对象已断开，无需关闭")
            except Exception as close_doc_e:
                logger.warning(f"{log_prefix}关闭文档时出错: {close_doc_e}")
        except Exception as e:
            logger.warning(f"{log_prefix}关闭文档时发生异常: {e}")
    
    # 安全关闭 Word 应用程序
    if word_app is not None:
        try:
            logger.debug(f"{log_prefix}正在关闭 Word 应用程序...")
            try:
                _ = word_app.Name  # 尝试访问属性来检查对象是否有效
                word_app.Quit(SaveChanges=False)
                logger.info(f"{log_prefix}Word 应用程序已关闭")
            except AttributeError:
                # 对象已断开，说明已经关闭了
                logger.debug(f"{log_prefix}Word 对象已断开，无需关闭")
            except Exception as quit_word_e:
                logger.warning(f"{log_prefix}关闭 Word 应用程序时出错: {quit_word_e}")
        except Exception as e:
            logger.warning(f"{log_prefix}关闭 Word 时发生异常: {e}")
    
    # 添加延迟，确保 Word 进程完全退出
    if wait_time > 0:
        logger.debug(f"{log_prefix}等待 Word 进程完全退出...")
        time.sleep(wait_time)
    
    # 注意：不再清理残留的 Word 进程
    # 因为在并发环境下，这可能会误杀其他用户正在使用的 Word 进程
    # 现在通过 graph.py 中的全局锁确保同一时间只有一个 graph 在执行
    # 所以不需要这么激进的清理策略
    
    # 安全清理 COM（必须在关闭 Word 之后）
    if com_initialized:
        try:
            logger.debug(f"{log_prefix}清理 COM 资源...")
            pythoncom.CoUninitialize()
            logger.debug(f"{log_prefix}COM 资源已清理")
        except Exception as com_e:
            logger.warning(f"{log_prefix}清理 COM 时出错: {com_e}")


def open_document_with_retry(
    word_app: any,
    file_path: str,
    read_only: bool = True,
    max_retries: int = MAX_RETRIES,
    node_name: str = "",
) -> any:
    """
    带重试机制的文档打开函数（线程安全）
    
    当遇到 RPC 错误时会自动重试。
    
    参数:
        word_app: Word.Application 对象
        file_path: 文档路径（绝对路径）
        read_only: 是否只读打开
        max_retries: 最大重试次数
        node_name: 节点名称
        
    返回:
        Word.Document 对象
    """
    # 使用全局锁保护打开操作
    with com_lock(operation_name=f"{node_name}-打开文档"):
        return _open_document_internal(
            word_app=word_app,
            file_path=file_path,
            read_only=read_only,
            max_retries=max_retries,
            node_name=node_name,
        )


def _open_document_internal(
    word_app: any,
    file_path: str,
    read_only: bool,
    max_retries: int,
    node_name: str,
) -> any:
    """
    内部函数：带重试机制的文档打开
    
    调用此函数前应该已经获取了全局锁。
    """
    log_prefix = f"[{node_name}] " if node_name else ""
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            doc = word_app.Documents.Open(
                FileName=file_path,
                ConfirmConversions=False,
                ReadOnly=read_only,
                AddToRecentFiles=False,
                NoEncodingDialog=True
            )
            logger.info(f"{log_prefix}已打开文档: {file_path}")
            return doc
        except Exception as e:
            last_exception = e
            
            if is_rpc_error(e) and attempt < max_retries:
                delay = calculate_retry_delay(attempt)
                logger.warning(f"{log_prefix}打开文档失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                logger.info(f"{log_prefix}等待 {delay:.1f} 秒后重试...")
                time.sleep(delay)
            else:
                raise
    
    if last_exception:
        raise last_exception
    raise RuntimeError(f"无法打开文档: {file_path}")


def save_document_with_retry(
    doc: any,
    max_retries: int = MAX_RETRIES,
    node_name: str = "",
) -> None:
    """
    带重试机制的文档保存函数（线程安全）
    
    当遇到 RPC 错误时会自动重试。
    
    参数:
        doc: Word.Document 对象
        max_retries: 最大重试次数
        node_name: 节点名称
    """
    # 使用全局锁保护保存操作
    with com_lock(operation_name=f"{node_name}-保存文档"):
        log_prefix = f"[{node_name}] " if node_name else ""
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                doc.Save()
                logger.info(f"{log_prefix}文档已保存")
                return
            except Exception as e:
                last_exception = e
                
                if is_rpc_error(e) and attempt < max_retries:
                    delay = calculate_retry_delay(attempt)
                    logger.warning(f"{log_prefix}保存文档失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                    logger.info(f"{log_prefix}等待 {delay:.1f} 秒后重试...")
                    time.sleep(delay)
                else:
                    raise
        
        if last_exception:
            raise last_exception


def unprotect_document(
    doc: any,
    node_name: str = "",
) -> bool:
    """
    取消文档保护（统一的文档保护处理函数）
    
    尝试多种方法取消文档保护，包括：
    1. 检查保护类型
    2. 使用空密码取消保护
    3. 强制设置保护类型
    4. 禁用内容保护
    
    参数:
        doc: Word.Document 对象
        node_name: 节点名称，用于日志输出
        
    返回:
        bool: 是否成功取消保护（或文档本身无保护）
    """
    log_prefix = f"[{node_name}] " if node_name else ""
    
    # 检查保护类型
    try:
        protection_type = doc.ProtectionType
        logger.debug(f"{log_prefix}文档保护类型: {protection_type} (-1 表示无保护)")
        
        if protection_type == -1:  # wdNoProtection
            return True  # 无保护，无需处理
        
        # 尝试使用空密码取消保护
        try:
            doc.Unprotect("")
            logger.info(f"{log_prefix}已取消文档保护")
            return True
        except Exception as unprotect_e:
            logger.warning(f"{log_prefix}使用空密码取消保护失败: {unprotect_e}")
            
            # 尝试强制设置保护类型为无保护
            try:
                doc.ProtectionType = -1
                logger.info(f"{log_prefix}已强制设置文档为无保护状态")
                return True
            except Exception as force_e:
                logger.warning(f"{log_prefix}强制设置保护类型失败: {force_e}")
                
    except Exception as prot_e:
        logger.warning(f"{log_prefix}检查文档保护时出错: {prot_e}")
    
    # 尝试禁用内容保护
    try:
        if hasattr(doc, 'ProtectContent') and doc.ProtectContent:
            logger.warning(f"{log_prefix}文档内容仍受保护，尝试强制取消...")
            doc.ProtectContent = False
            return True
    except Exception:
        pass
    
    return False
