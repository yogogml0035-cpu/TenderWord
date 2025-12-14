"""
Word 应用程序创建工具函数

提供统一的 Word.Application 创建和初始化逻辑，供各个节点使用。
"""

from __future__ import annotations

import time
import pythoncom
from typing import Optional, Tuple

try:
    import win32com.client as win32
except ImportError:
    win32 = None


def create_word_application(
    initial_delay: float = 2.0,
    post_init_delay: float = 0.5,
    use_existing: bool = True,
    verify: bool = True,
    node_name: str = "",
) -> Tuple[any, bool]:
    """
    创建或获取 Word.Application 实例。
    
    参数:
        initial_delay: 创建前等待时间（秒），让之前的实例有时间完全关闭。默认 2.0 秒
        post_init_delay: 创建后等待时间（秒），给 Word 完成初始化的时间。默认 0.5 秒
        use_existing: 是否尝试获取已运行的 Word 实例。默认 True
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
    if win32 is None:
        raise RuntimeError("无法导入 win32com.client，请确保已安装 pywin32")
    
    # 初始化 COM
    com_initialized = False
    try:
        pythoncom.CoInitialize()
        com_initialized = True
    except Exception as e:
        raise RuntimeError(f"初始化 COM 失败: {e}")
    
    # 创建前等待，让之前的实例有时间完全关闭
    if initial_delay > 0:
        log_prefix = f"[{node_name}] " if node_name else ""
        print(f"{log_prefix}等待 {initial_delay} 秒后创建 Microsoft Word 实例...")
        time.sleep(initial_delay)
    
    word_app = None
    creation_method = None
    
    try:
        # 方法1: 尝试获取已运行的 Word 实例（如果启用）
        if use_existing:
            try:
                word_app = win32.GetActiveObject("Word.Application")
                word_app.Visible = False
                word_app.DisplayAlerts = 0
                creation_method = "GetActiveObject"
                log_prefix = f"[{node_name}] " if node_name else ""
                print(f"{log_prefix}成功获取已运行的 Word 实例")
            except Exception:
                pass  # 继续尝试其他方法
        
        # 方法2: 创建新的独立实例（DispatchEx）
        if word_app is None:
            try:
                word_app = win32.DispatchEx("Word.Application")
                word_app.Visible = False
                word_app.DisplayAlerts = 0
                creation_method = "DispatchEx"
                log_prefix = f"[{node_name}] " if node_name else ""
                print(f"{log_prefix}成功创建新的 Word 实例 (DispatchEx)")
            except Exception:
                pass  # 继续尝试其他方法
        
        # 方法3: 使用 EnsureDispatch 作为备选
        if word_app is None:
            try:
                word_app = win32.gencache.EnsureDispatch("Word.Application")
                word_app.Visible = False
                word_app.DisplayAlerts = 0
                creation_method = "EnsureDispatch"
                log_prefix = f"[{node_name}] " if node_name else ""
                print(f"{log_prefix}成功创建新的 Word 实例 (EnsureDispatch)")
            except Exception as e:
                # 所有方法都失败
                raise RuntimeError(f"无法创建 Microsoft Word 应用程序实例: {e}")
        
        # 创建后等待，给 Word 完成初始化的时间
        if post_init_delay > 0:
            time.sleep(post_init_delay)
        
        # 验证 Word 对象是否可用
        if verify:
            try:
                app_name = word_app.Name
                log_prefix = f"[{node_name}] " if node_name else ""
                print(f"{log_prefix}使用 Microsoft Word (名称: {app_name}, 创建方法: {creation_method})")
            except Exception as verify_e:
                raise RuntimeError(f"Word 实例创建但验证失败: {verify_e}")
        
        return word_app, com_initialized
        
    except Exception as e:
        # 如果创建失败，确保清理 COM
        if com_initialized:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
        raise


def close_word_application(
    word_app: Optional[any],
    doc: Optional[any] = None,
    com_initialized: bool = False,
    wait_time: float = 1.5,
    node_name: str = "",
) -> None:
    """
    安全关闭 Word 应用程序和文档，并清理 COM 资源。
    
    参数:
        word_app: Word.Application 对象，可以为 None
        doc: Word.Document 对象，可以为 None（会在关闭 Word 前关闭）
        com_initialized: 是否已初始化 COM（如果为 True，会调用 CoUninitialize）
        wait_time: 关闭后等待时间（秒），确保进程完全退出。默认 1.5 秒
        node_name: 节点名称，用于日志输出。默认空字符串
    """
    log_prefix = f"[{node_name}] " if node_name else ""
    
    # 安全关闭文档（必须在关闭 Word 之前）
    if doc is not None:
        try:
            print(f"{log_prefix}正在关闭文档...")
            try:
                _ = doc.Name  # 尝试访问属性来检查对象是否有效
                doc.Close(SaveChanges=False)
                print(f"{log_prefix}文档已关闭")
            except AttributeError:
                # 对象已断开，说明已经关闭了
                print(f"{log_prefix}文档对象已断开，无需关闭")
            except Exception as close_doc_e:
                print(f"{log_prefix}关闭文档时出错: {close_doc_e}")
        except Exception as e:
            print(f"{log_prefix}关闭文档时发生异常: {e}")
    
    # 安全关闭 Word 应用程序
    if word_app is not None:
        try:
            print(f"{log_prefix}正在关闭 Word 应用程序...")
            try:
                _ = word_app.Name  # 尝试访问属性来检查对象是否有效
                word_app.Quit(SaveChanges=False)
                print(f"{log_prefix}Word 应用程序已关闭")
            except AttributeError:
                # 对象已断开，说明已经关闭了
                print(f"{log_prefix}Word 对象已断开，无需关闭")
            except Exception as quit_word_e:
                print(f"{log_prefix}关闭 Word 应用程序时出错: {quit_word_e}")
        except Exception as e:
            print(f"{log_prefix}关闭 Word 时发生异常: {e}")
    
    # 添加延迟，确保 Word 进程完全退出
    if wait_time > 0:
        print(f"{log_prefix}等待 Word 进程完全退出...")
        time.sleep(wait_time)
    
    # 清理残留的 Word 进程（如果正常关闭失败）
    try:
        import psutil
        word_processes = []
        current_pid = None
        
        if word_app:
            try:
                # 尝试获取当前 Word 进程的 PID
                import win32process
                handle = word_app.Hwnd
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
            print(f"{log_prefix}检测到 {len(word_processes)} 个可能的残留 Word 进程: {word_processes}")
            # 尝试终止这些进程
            for pid in word_processes:
                try:
                    proc = psutil.Process(pid)
                    proc.terminate()
                    print(f"{log_prefix}已终止残留进程 (PID: {pid})")
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    print(f"{log_prefix}无法终止进程 {pid}: {e}")
                except Exception as e:
                    print(f"{log_prefix}终止进程 {pid} 时出错: {e}")
    except ImportError:
        print(f"{log_prefix}未安装 psutil，无法检查残留进程")
    except Exception as cleanup_e:
        print(f"{log_prefix}检查残留进程时出错: {cleanup_e}")
    
    # 安全清理 COM（必须在关闭 Word 之后）
    if com_initialized:
        try:
            print(f"{log_prefix}清理 COM 资源...")
            pythoncom.CoUninitialize()
            print(f"{log_prefix}COM 资源已清理")
        except Exception as com_e:
            print(f"{log_prefix}清理 COM 时出错: {com_e}")

