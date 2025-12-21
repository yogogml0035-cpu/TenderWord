"""
Word COM 并发访问管理器

解决多用户并发访问 Word COM 对象时的冲突问题。
提供全局锁和重试机制，确保 COM 操作的线程安全。

主要功能：
1. 全局锁：确保同一时间只有一个线程可以访问 COM 对象
2. 重试机制：当遇到 RPC 错误时自动等待并重试
"""

from __future__ import annotations

import threading
import random
from contextlib import contextmanager


# 全局锁，用于串行化所有 COM 操作
_com_lock = threading.RLock()

# 配置常量
MAX_RETRIES = 5  # 最大重试次数
BASE_RETRY_DELAY = 1.0  # 基础重试延迟（秒）
MAX_RETRY_DELAY = 10.0  # 最大重试延迟（秒）
LOCK_TIMEOUT = 1800.0  # 锁超时时间（秒）

# RPC 错误代码
RPC_ERROR_CODES = (
    -2147023174,  # RPC 服务器不可用
    -2147023179,  # 接口未知
    -2147417848,  # RPC 断开
    -2147467261,  # 无效指针
    -2147352567,  # 对象已被删除
    -2146959355,  # COM 错误
)


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
