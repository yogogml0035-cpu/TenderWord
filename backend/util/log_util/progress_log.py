"""线程安全的进度日志工具模块

使用 QueueHandler + QueueListener 模式确保 async FastAPI 环境下的线程安全。
适用于高并发场景下的进度追踪和日志记录。

使用方法:
    from backend.util.log_util.progress_log import (
        progress_log,
        start_progress_log_listener,
        stop_progress_log_listener,
    )

    # 应用启动时
    start_progress_log_listener()

    # 记录日志
    progress_log.info("进度信息")
    progress_log.debug("调试信息")

    # 应用关闭时
    stop_progress_log_listener()
"""

import logging
import logging.handlers
import queue
from pathlib import Path

from backend.util.log_util.daily_file_handler import DailyFileHandler

# 延迟导入 settings 以避免循环导入
_settings = None


def _get_settings():
    global _settings
    if _settings is None:
        from backend.config.settings import settings as _settings_instance

        _settings = _settings_instance
    return _settings


def _get_log_dir() -> Path:
    """获取日志目录。"""
    settings = _get_settings()
    # 如果是绝对路径，直接使用；否则相对于 backend 目录
    log_dir = Path(settings.LOG_DIR)
    if not log_dir.is_absolute():
        log_dir = Path(__file__).parent.parent.parent / log_dir
    log_dir.mkdir(exist_ok=True)
    return log_dir


def _get_log_queue() -> queue.Queue[logging.LogRecord]:
    """获取日志队列。"""
    settings = _get_settings()
    return queue.Queue(maxsize=settings.LOG_QUEUE_MAXSIZE)


# 日志目录: backend/logs/
LOG_DIR = _get_log_dir()

# 有界队列，防止内存溢出
_log_queue = _get_log_queue()

# 文件 handler - 直接写入 progress-YYYYMMDD.log，避免重复日期后缀
def _create_file_handler():
    """创建文件 handler。"""
    settings = _get_settings()
    handler = DailyFileHandler(
        log_dir=LOG_DIR,
        prefix="progress",
        backup_count=settings.PROGRESS_LOG_BACKUP_COUNT,
        encoding="utf-8",
        delay=True,
    )
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%H:%M:%S")
    )
    return handler


_file_handler = _create_file_handler()

# QueueHandler - 线程安全的日志处理
_queue_handler = logging.handlers.QueueHandler(_log_queue)

# QueueListener - 后台线程处理日志写入
_listener = logging.handlers.QueueListener(
    _log_queue,
    _file_handler,
    respect_handler_level=True,
)

# 全局 logger 实例
progress_log = logging.getLogger("progress")
progress_log.addHandler(_queue_handler)
progress_log.setLevel(logging.DEBUG)
progress_log.propagate = False  # 阻止日志传播到根 logger


def start_progress_log_listener() -> None:
    """
    启动进度日志监听器。

    应在应用启动时调用（如 FastAPI lifespan 或 main.py）。
    监听器在后台线程中运行，不会阻塞主线程。
    """
    if not _listener._thread:  # type: ignore[attr-defined]
        _listener.start()


def stop_progress_log_listener() -> None:
    """
    停止进度日志监听器。

    应在应用关闭时调用，确保所有日志写入文件。
    监听器停止后会等待队列中的日志处理完毕。
    """
    _listener.stop()
