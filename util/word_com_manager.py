"""
Word COM 并发访问管理器

解决多用户并发访问 Word COM 对象时的冲突问题。
提供全局锁和重试机制，确保 COM 操作的线程安全。

主要功能：
1. 全局锁：确保同一时间只有一个线程可以访问 COM 对象
2. 重试机制：当遇到 RPC 错误时自动等待并重试
3. 上下文管理器：简化 COM 操作的资源管理
"""

from __future__ import annotations

import functools
import threading
import time
import random
from contextlib import contextmanager
from typing import Any, Callable, Optional, Tuple, TypeVar

import pythoncom

try:
    import win32com.client as win32
except ImportError:
    win32 = None


# 全局锁，用于串行化所有 COM 操作
_com_lock = threading.RLock()

# 配置常量
MAX_RETRIES = 5  # 最大重试次数
BASE_RETRY_DELAY = 1.0  # 基础重试延迟（秒）
MAX_RETRY_DELAY = 10.0  # 最大重试延迟（秒）
LOCK_TIMEOUT = 300.0  # 锁超时时间（秒），5分钟

# RPC 错误代码
RPC_ERROR_CODES = (
    -2147023174,  # RPC 服务器不可用
    -2147023179,  # 接口未知
    -2147417848,  # RPC 断开
    -2147467261,  # 无效指针
    -2147352567,  # 对象已被删除
    -2146959355,  # COM 错误
)

T = TypeVar('T')


def is_rpc_error(exception: Exception) -> bool:
    """
    检查异常是否是 RPC/COM 相关错误
    
    Args:
        exception: 要检查的异常
        
    Returns:
        bool: 是否是 RPC 错误
    """
    error_str = str(exception).lower()
    
    # 检查错误代码
    if hasattr(exception, 'args') and exception.args:
        error_code = exception.args[0]
        if isinstance(error_code, int) and error_code in RPC_ERROR_CODES:
            return True
    
    # 检查 hresult
    if hasattr(exception, 'hresult'):
        if exception.hresult in RPC_ERROR_CODES:
            return True
    
    # 检查错误消息
    rpc_keywords = ['rpc', '服务器不可用', '接口未知', '无效指针', '对象已被删除', 'disconnected']
    return any(keyword in error_str for keyword in rpc_keywords)


def calculate_retry_delay(attempt: int) -> float:
    """
    计算重试延迟（指数退避 + 随机抖动）
    
    Args:
        attempt: 当前尝试次数（从0开始）
        
    Returns:
        float: 延迟时间（秒）
    """
    # 指数退避
    delay = BASE_RETRY_DELAY * (2 ** attempt)
    # 限制最大延迟
    delay = min(delay, MAX_RETRY_DELAY)
    # 添加随机抖动（±20%）
    jitter = delay * 0.2 * (random.random() * 2 - 1)
    return delay + jitter


def with_com_retry(
    max_retries: int = MAX_RETRIES,
    retry_on_rpc_error: bool = True,
    operation_name: str = ""
) -> Callable:
    """
    装饰器：为函数添加 COM 操作重试机制
    
    Args:
        max_retries: 最大重试次数
        retry_on_rpc_error: 是否在 RPC 错误时重试
        operation_name: 操作名称，用于日志
        
    Returns:
        装饰后的函数
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            op_name = operation_name or func.__name__
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # 检查是否应该重试
                    should_retry = retry_on_rpc_error and is_rpc_error(e)
                    
                    if should_retry and attempt < max_retries:
                        delay = calculate_retry_delay(attempt)
                        print(f"[COM Manager] {op_name} 操作失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                        print(f"[COM Manager] 等待 {delay:.1f} 秒后重试...")
                        time.sleep(delay)
                    else:
                        # 不重试或已达最大重试次数
                        if attempt > 0:
                            print(f"[COM Manager] {op_name} 操作在 {attempt + 1} 次尝试后仍然失败")
                        raise
            
            # 不应该到达这里，但为了类型安全
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected error in retry logic")
        
        return wrapper
    return decorator


class ComLockAcquisitionError(Exception):
    """无法获取 COM 锁时抛出的异常"""
    pass


@contextmanager
def com_lock(timeout: float = LOCK_TIMEOUT, operation_name: str = ""):
    """
    上下文管理器：获取 COM 全局锁
    
    使用方式：
        with com_lock(operation_name="打开文档"):
            # 执行 COM 操作
            doc = word.Documents.Open(...)
    
    Args:
        timeout: 锁超时时间（秒）
        operation_name: 操作名称，用于日志
        
    Yields:
        None
        
    Raises:
        ComLockAcquisitionError: 无法在超时时间内获取锁
    """
    op_name = operation_name or "COM操作"
    acquired = _com_lock.acquire(timeout=timeout)
    
    if not acquired:
        raise ComLockAcquisitionError(
            f"无法获取 COM 锁 (超时 {timeout} 秒)，操作: {op_name}"
        )
    
    try:
        yield
    finally:
        _com_lock.release()


@contextmanager
def com_session(
    initial_delay: float = 0.0,
    operation_name: str = "",
    use_existing: bool = False,
) -> Tuple[Any, bool]:
    """
    上下文管理器：创建一个完整的 COM 会话
    
    自动处理：
    1. 获取全局锁
    2. 初始化 COM
    3. 创建 Word 应用程序实例
    4. 在退出时清理资源
    
    使用方式：
        with com_session(operation_name="处理文档") as (word_app, com_initialized):
            doc = word_app.Documents.Open(...)
            # 处理文档
            doc.Close()
    
    Args:
        initial_delay: 创建前等待时间
        operation_name: 操作名称
        use_existing: 是否尝试使用已存在的 Word 实例
        
    Yields:
        Tuple[word_app, com_initialized]: Word 应用程序对象和 COM 初始化标志
    """
    op_name = operation_name or "COM会话"
    word_app = None
    com_initialized = False
    
    # 获取全局锁
    with com_lock(operation_name=op_name):
        try:
            # 初始等待
            if initial_delay > 0:
                print(f"[COM Manager] [{op_name}] 等待 {initial_delay} 秒...")
                time.sleep(initial_delay)
            
            # 初始化 COM
            try:
                pythoncom.CoInitialize()
                com_initialized = True
            except Exception as e:
                raise RuntimeError(f"初始化 COM 失败: {e}")
            
            # 创建 Word 应用程序
            word_app = _create_word_app_internal(use_existing, op_name)
            
            yield word_app, com_initialized
            
        finally:
            # 清理资源
            _cleanup_word_app(word_app, com_initialized, op_name)


def _create_word_app_internal(use_existing: bool, node_name: str) -> Any:
    """
    内部函数：创建 Word 应用程序实例
    
    Args:
        use_existing: 是否使用已存在的实例
        node_name: 节点名称
        
    Returns:
        Word.Application 对象
    """
    if win32 is None:
        raise RuntimeError("无法导入 win32com.client，请确保已安装 pywin32")
    
    word_app = None
    creation_method = None
    
    # 方法1: 尝试获取已运行的 Word 实例（如果启用）
    if use_existing:
        try:
            word_app = win32.GetActiveObject("Word.Application")
            word_app.Visible = False
            word_app.DisplayAlerts = 0
            creation_method = "GetActiveObject"
            print(f"[COM Manager] [{node_name}] 成功获取已运行的 Word 实例")
        except Exception:
            pass
    
    # 方法2: 创建新的独立实例（DispatchEx）
    if word_app is None:
        try:
            word_app = win32.DispatchEx("Word.Application")
            word_app.Visible = False
            word_app.DisplayAlerts = 0
            creation_method = "DispatchEx"
            print(f"[COM Manager] [{node_name}] 成功创建新的 Word 实例 (DispatchEx)")
        except Exception:
            pass
    
    # 方法3: 使用 EnsureDispatch 作为备选
    if word_app is None:
        try:
            word_app = win32.gencache.EnsureDispatch("Word.Application")
            word_app.Visible = False
            word_app.DisplayAlerts = 0
            creation_method = "EnsureDispatch"
            print(f"[COM Manager] [{node_name}] 成功创建新的 Word 实例 (EnsureDispatch)")
        except Exception as e:
            raise RuntimeError(f"无法创建 Microsoft Word 应用程序实例: {e}")
    
    # 验证 Word 对象
    try:
        app_name = word_app.Name
        print(f"[COM Manager] [{node_name}] 使用 Microsoft Word (名称: {app_name}, 方法: {creation_method})")
    except Exception as e:
        raise RuntimeError(f"Word 实例创建但验证失败: {e}")
    
    return word_app


def _cleanup_word_app(word_app: Any, com_initialized: bool, node_name: str) -> None:
    """
    内部函数：清理 Word 应用程序资源
    
    Args:
        word_app: Word 应用程序对象
        com_initialized: 是否已初始化 COM
        node_name: 节点名称
    """
    # 关闭 Word 应用程序
    if word_app is not None:
        try:
            word_app.Quit(SaveChanges=False)
            print(f"[COM Manager] [{node_name}] Word 应用程序已关闭")
        except Exception as e:
            print(f"[COM Manager] [{node_name}] 关闭 Word 时出错: {e}")
    
    # 等待进程退出
    time.sleep(0.5)
    
    # 清理 COM
    if com_initialized:
        try:
            pythoncom.CoUninitialize()
            print(f"[COM Manager] [{node_name}] COM 资源已清理")
        except Exception as e:
            print(f"[COM Manager] [{node_name}] 清理 COM 时出错: {e}")


class WordComOperation:
    """
    Word COM 操作封装类
    
    提供线程安全的 Word 文档操作，自动处理锁和重试。
    
    使用方式：
        op = WordComOperation(node_name="my_node")
        with op.open_document(doc_path) as doc:
            # 处理文档
            content = doc.Content.Text
    """
    
    def __init__(self, node_name: str = "", max_retries: int = MAX_RETRIES):
        """
        初始化操作对象
        
        Args:
            node_name: 节点名称，用于日志
            max_retries: 最大重试次数
        """
        self.node_name = node_name
        self.max_retries = max_retries
        self._word_app = None
        self._com_initialized = False
        self._doc = None
    
    @contextmanager
    def open_document(
        self,
        file_path: str,
        read_only: bool = True,
        initial_delay: float = 1.0,
    ):
        """
        打开 Word 文档（带锁和重试）
        
        Args:
            file_path: 文档路径（绝对路径）
            read_only: 是否只读打开
            initial_delay: 初始等待时间
            
        Yields:
            Word Document 对象
        """
        with com_lock(operation_name=f"{self.node_name}-打开文档"):
            try:
                # 初始等待
                if initial_delay > 0:
                    print(f"[{self.node_name}] 等待 {initial_delay} 秒后打开文档...")
                    time.sleep(initial_delay)
                
                # 初始化 COM
                try:
                    pythoncom.CoInitialize()
                    self._com_initialized = True
                except Exception as e:
                    raise RuntimeError(f"初始化 COM 失败: {e}")
                
                # 创建 Word 应用程序（带重试）
                self._word_app = self._create_word_app_with_retry()
                
                # 打开文档（带重试）
                self._doc = self._open_document_with_retry(file_path, read_only)
                
                yield self._doc
                
            finally:
                self._cleanup()
    
    def _create_word_app_with_retry(self) -> Any:
        """创建 Word 应用程序（带重试）"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return _create_word_app_internal(
                    use_existing=False,  # 并发环境下不共享实例
                    node_name=self.node_name
                )
            except Exception as e:
                last_exception = e
                
                if is_rpc_error(e) and attempt < self.max_retries:
                    delay = calculate_retry_delay(attempt)
                    print(f"[{self.node_name}] 创建 Word 失败 (尝试 {attempt + 1}): {e}")
                    print(f"[{self.node_name}] 等待 {delay:.1f} 秒后重试...")
                    time.sleep(delay)
                else:
                    raise
        
        if last_exception:
            raise last_exception
        raise RuntimeError("创建 Word 应用程序时发生未知错误")
    
    def _open_document_with_retry(self, file_path: str, read_only: bool) -> Any:
        """打开文档（带重试）"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                doc = self._word_app.Documents.Open(
                    FileName=file_path,
                    ConfirmConversions=False,
                    ReadOnly=read_only,
                    AddToRecentFiles=False,
                    NoEncodingDialog=True
                )
                print(f"[{self.node_name}] 已打开文档: {file_path}")
                return doc
            except Exception as e:
                last_exception = e
                
                if is_rpc_error(e) and attempt < self.max_retries:
                    delay = calculate_retry_delay(attempt)
                    print(f"[{self.node_name}] 打开文档失败 (尝试 {attempt + 1}): {e}")
                    print(f"[{self.node_name}] 等待 {delay:.1f} 秒后重试...")
                    time.sleep(delay)
                    
                    # 尝试重新创建 Word 应用程序
                    try:
                        if self._word_app:
                            try:
                                self._word_app.Quit(SaveChanges=False)
                            except:
                                pass
                        self._word_app = _create_word_app_internal(
                            use_existing=False,
                            node_name=self.node_name
                        )
                    except:
                        pass
                else:
                    raise
        
        if last_exception:
            raise last_exception
        raise RuntimeError("打开文档时发生未知错误")
    
    def _cleanup(self) -> None:
        """清理资源"""
        # 关闭文档
        if self._doc is not None:
            try:
                self._doc.Close(SaveChanges=False)
                print(f"[{self.node_name}] 文档已关闭")
            except Exception as e:
                print(f"[{self.node_name}] 关闭文档时出错: {e}")
            self._doc = None
        
        # 关闭 Word
        if self._word_app is not None:
            try:
                self._word_app.Quit(SaveChanges=False)
                print(f"[{self.node_name}] Word 应用程序已关闭")
            except Exception as e:
                print(f"[{self.node_name}] 关闭 Word 时出错: {e}")
            self._word_app = None
        
        # 等待进程退出
        time.sleep(0.5)
        
        # 清理 COM
        if self._com_initialized:
            try:
                pythoncom.CoUninitialize()
                print(f"[{self.node_name}] COM 资源已清理")
            except Exception as e:
                print(f"[{self.node_name}] 清理 COM 时出错: {e}")
            self._com_initialized = False


# 便捷函数
def create_word_application_safe(
    initial_delay: float = 2.0,
    post_init_delay: float = 0.5,
    use_existing: bool = False,
    verify: bool = True,
    node_name: str = "",
) -> Tuple[Any, bool]:
    """
    线程安全地创建 Word 应用程序实例（带锁和重试）
    
    这是对原有 create_word_application 的线程安全封装。
    
    Args:
        initial_delay: 创建前等待时间（秒）
        post_init_delay: 创建后等待时间（秒）
        use_existing: 是否尝试使用已存在的实例
        verify: 是否验证 Word 对象
        node_name: 节点名称
        
    Returns:
        Tuple[word_app, com_initialized]
    """
    with com_lock(operation_name=f"{node_name}-创建Word"):
        if win32 is None:
            raise RuntimeError("无法导入 win32com.client，请确保已安装 pywin32")
        
        # 初始等待
        if initial_delay > 0:
            log_prefix = f"[{node_name}] " if node_name else ""
            print(f"{log_prefix}等待 {initial_delay} 秒后创建 Microsoft Word 实例...")
            time.sleep(initial_delay)
        
        # 初始化 COM
        com_initialized = False
        try:
            pythoncom.CoInitialize()
            com_initialized = True
        except Exception as e:
            raise RuntimeError(f"初始化 COM 失败: {e}")
        
        try:
            # 带重试地创建 Word
            word_app = None
            last_exception = None
            
            for attempt in range(MAX_RETRIES + 1):
                try:
                    word_app = _create_word_app_internal(use_existing, node_name)
                    break
                except Exception as e:
                    last_exception = e
                    
                    if is_rpc_error(e) and attempt < MAX_RETRIES:
                        delay = calculate_retry_delay(attempt)
                        print(f"[{node_name}] 创建 Word 失败 (尝试 {attempt + 1}): {e}")
                        print(f"[{node_name}] 等待 {delay:.1f} 秒后重试...")
                        time.sleep(delay)
                    else:
                        raise
            
            if word_app is None and last_exception:
                raise last_exception
            
            # 创建后等待
            if post_init_delay > 0:
                time.sleep(post_init_delay)
            
            # 验证
            if verify:
                try:
                    app_name = word_app.Name
                    log_prefix = f"[{node_name}] " if node_name else ""
                    print(f"{log_prefix}Word 实例验证成功 (名称: {app_name})")
                except Exception as e:
                    raise RuntimeError(f"Word 实例验证失败: {e}")
            
            return word_app, com_initialized
            
        except Exception as e:
            # 创建失败，清理 COM
            if com_initialized:
                try:
                    pythoncom.CoUninitialize()
                except:
                    pass
            raise


def close_word_application_safe(
    word_app: Optional[Any],
    doc: Optional[Any] = None,
    com_initialized: bool = False,
    wait_time: float = 1.5,
    node_name: str = "",
) -> None:
    """
    线程安全地关闭 Word 应用程序（带锁）
    
    Args:
        word_app: Word 应用程序对象
        doc: Word 文档对象
        com_initialized: 是否已初始化 COM
        wait_time: 关闭后等待时间
        node_name: 节点名称
    """
    with com_lock(operation_name=f"{node_name}-关闭Word"):
        log_prefix = f"[{node_name}] " if node_name else ""
        
        # 关闭文档
        if doc is not None:
            try:
                doc.Close(SaveChanges=False)
                print(f"{log_prefix}文档已关闭")
            except Exception as e:
                print(f"{log_prefix}关闭文档时出错: {e}")
        
        # 关闭 Word
        if word_app is not None:
            try:
                word_app.Quit(SaveChanges=False)
                print(f"{log_prefix}Word 应用程序已关闭")
            except Exception as e:
                print(f"{log_prefix}关闭 Word 时出错: {e}")
        
        # 等待
        if wait_time > 0:
            time.sleep(wait_time)
        
        # 清理 COM
        if com_initialized:
            try:
                pythoncom.CoUninitialize()
                print(f"{log_prefix}COM 资源已清理")
            except Exception as e:
                print(f"{log_prefix}清理 COM 时出错: {e}")

