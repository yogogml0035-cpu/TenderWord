"""
SSE 日志 Handler - 将日志实时推送到前端

使用 contextvars 管理 task_id 上下文，支持 async 环境。
只推送 INFO/WARNING/ERROR 级别，DEBUG 不推送。

使用方法:
    from backend.util.log_util.sse_log_handler import (
        init_sse_log_handler,
        task_log_context,
        get_current_task_id,
    )

    # 应用启动时初始化
    from backend.core.sse_manager import sse_manager
    handler = init_sse_log_handler(sse_manager)
    logging.getLogger().addHandler(handler)

    # 在任务中使用
    with task_log_context("task-123"):
        logger.info("这条日志会推送到前端")
"""

import asyncio
import logging
from contextvars import ContextVar
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from backend.core.sse_manager import SSEManager

# 使用 contextvars 管理 task_id（支持 async）
_current_task_id: ContextVar[Optional[str]] = ContextVar(
    "current_task_id", default=None
)


class SSELogHandler(logging.Handler):
    """将日志推送到 SSE 的 Handler

    只处理 INFO 及以上级别的日志，DEBUG 不推送。
    需要在 task_log_context 上下文中使用，否则日志不会推送。

    Attributes:
        _sse_manager: SSE 管理器实例
    """

    def __init__(self, sse_manager: "SSEManager"):
        """初始化 SSE 日志 Handler

        Args:
            sse_manager: SSE 管理器实例
        """
        super().__init__()
        self._sse_manager = sse_manager
        self.setLevel(logging.INFO)  # 只处理 INFO 及以上

    def emit(self, record: logging.LogRecord) -> None:
        """发送日志到 SSE

        Args:
            record: 日志记录
        """
        try:
            task_id = _current_task_id.get()
            if task_id is None:
                return  # 无 task_id 上下文，不推送

            message = self.format(record)
            level = record.levelname.lower()

            # 获取或创建事件循环
            try:
                loop = asyncio.get_running_loop()
                # 如果有运行中的循环，创建任务
                asyncio.create_task(self._sse_manager.send_log(task_id, message, level))
            except RuntimeError:
                # 没有运行中的事件循环，静默跳过
                # 这种情况通常发生在同步代码中
                pass

        except Exception:
            # 静默处理错误，避免影响主程序
            self.handleError(record)


class task_log_context:
    """设置当前 task_id 的上下文管理器

    支持 sync 和 async 两种上下文管理器协议。

    Example:
        with task_log_context("task-123"):
            logger.info("这条日志会推送到前端")

        async with task_log_context("task-456"):
            logger.info("这条日志也会推送到前端")
    """

    def __init__(self, task_id: str):
        """初始化上下文管理器

        Args:
            task_id: 任务ID
        """
        self.task_id = task_id
        self.token: Optional[object] = None

    def __enter__(self) -> "task_log_context":
        """进入上下文，设置 task_id"""
        self.token = _current_task_id.set(self.task_id)
        return self

    def __exit__(self, *args) -> None:
        """退出上下文，重置 task_id"""
        if self.token is not None:
            _current_task_id.reset(self.token)

    async def __aenter__(self) -> "task_log_context":
        """进入 async 上下文，设置 task_id"""
        self.token = _current_task_id.set(self.task_id)
        return self

    async def __aexit__(self, *args) -> None:
        """退出 async 上下文，重置 task_id"""
        if self.token is not None:
            _current_task_id.reset(self.token)


def get_current_task_id() -> Optional[str]:
    """获取当前 task_id

    Returns:
        当前上下文中的 task_id，如果没有则返回 None
    """
    return _current_task_id.get()


# 全局 handler 实例（需要在应用启动时初始化）
_sse_log_handler: Optional[SSELogHandler] = None


def init_sse_log_handler(sse_manager: "SSEManager") -> SSELogHandler:
    """初始化 SSE 日志 handler

    应在应用启动时调用（如 FastAPI lifespan 或 main.py）。

    Args:
        sse_manager: SSE 管理器实例

    Returns:
        初始化后的 SSELogHandler 实例
    """
    global _sse_log_handler
    _sse_log_handler = SSELogHandler(sse_manager)
    return _sse_log_handler


def get_sse_log_handler() -> Optional[SSELogHandler]:
    """获取 SSE 日志 handler

    Returns:
        SSELogHandler 实例，如果未初始化则返回 None
    """
    return _sse_log_handler
