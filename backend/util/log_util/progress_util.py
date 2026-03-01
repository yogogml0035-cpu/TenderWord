"""
线程安全的进度日志工具模块

使用 QueueHandler + QueueListener 模式确保 async FastAPI 环境下的线程安全。
适用于高并发场景下的进度追踪和日志记录。

使用方法:
    from backend.util.log_util.progress_util import (
        progress_logger,
        start_progress_log_listener,
        stop_progress_log_listener,
    )

    # 应用启动时
    start_progress_log_listener()

    # 记录日志
    progress_logger.info("进度信息")
    progress_logger.debug("调试信息")

    # 应用关闭时
    stop_progress_log_listener()
"""

import logging
import logging.handlers
import queue
from datetime import datetime
from pathlib import Path

# 日志目录: backend/logs/
LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 有界队列，防止内存溢出
_log_queue: queue.Queue[logging.LogRecord] = queue.Queue(maxsize=10000)

# 日志文件路径: backend/logs/progress-YYYYMMDD.log
_log_file = LOG_DIR / f"progress-{datetime.now().strftime('%Y%m%d')}.log"

# 文件 handler - 使用 TimedRotatingFileHandler 支持按天轮转
_file_handler = logging.handlers.TimedRotatingFileHandler(
    filename=str(_log_file),
    when="midnight",
    backupCount=7,
    encoding="utf-8",
    delay=True,
)
_file_handler.setFormatter(
    logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%H:%M:%S")
)

# QueueHandler - 线程安全的日志处理
_queue_handler = logging.handlers.QueueHandler(_log_queue)

# QueueListener - 后台线程处理日志写入
_listener = logging.handlers.QueueListener(
    _log_queue,
    _file_handler,
    respect_handler_level=True,
)

# 全局 logger 实例
progress_logger = logging.getLogger("progress")
progress_logger.addHandler(_queue_handler)
progress_logger.setLevel(logging.DEBUG)
progress_logger.propagate = False  # 阻止日志传播到根 logger


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
