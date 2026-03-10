"""Execution log module for user behavior auditing.

This module provides logging functionality for tracking user actions
and task execution. Logs are stored in daily files with INFO level only.

Uses QueueHandler + QueueListener pattern for thread-safety in async FastAPI environment.

Log file: backend/logs/execution-YYYYMMDD.log

Usage:
    from backend.util.log_util.execution_log import (
        logger,
        log_task_start,
        log_task_end,
        start_execution_log_listener,
        stop_execution_log_listener,
    )

    # At application startup
    start_execution_log_listener()

    # Log task execution
    log_task_start(state, "node_name")

    # At application shutdown
    stop_execution_log_listener()
"""

import logging
import logging.handlers
import queue
from pathlib import Path
from typing import Any, Mapping

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

# 文件 handler - 直接写入 execution-YYYYMMDD.log，避免重复日期后缀
def _create_file_handler():
    """创建文件 handler。"""
    settings = _get_settings()
    handler = DailyFileHandler(
        log_dir=LOG_DIR,
        prefix="execution",
        backup_count=settings.EXECUTION_LOG_BACKUP_COUNT,
        encoding="utf-8",
        delay=True,
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s：%(message)s", "%Y-%m-%d %H:%M:%S")
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

# 主日志记录器
logger = logging.getLogger("TenderWord")
logger.addHandler(_queue_handler)
logger.setLevel(logging.INFO)
logger.propagate = False  # 阻止日志传播到根 logger，避免输出到控制台


def start_execution_log_listener() -> None:
    """启动执行日志监听器。

    应在应用启动时调用（如 FastAPI lifespan 或 main.py）。
    监听器在后台线程中运行，不会阻塞主线程。
    """
    if not _listener._thread:  # type: ignore[attr-defined]
        _listener.start()


def stop_execution_log_listener() -> None:
    """停止执行日志监听器。

    应在应用关闭时调用，确保所有日志写入文件。
    监听器停止后会等待队列中的日志处理完毕。
    """
    _listener.stop()


def log_task_start(state: Mapping[str, Any], task_name: str) -> None:
    """记录任务开始执行"""
    project_zbr_xbr = state.get("project_zbr_xbr", "")
    project_number = state.get("project_number", "")
    project_name = state.get("project_name", "")
    project_info = (
        f"{project_number}-{project_name}" if project_number or project_name else ""
    )
    logger.info(f"{project_zbr_xbr}-{project_info}开始生成，当前进入{task_name}")


def log_task_end(state: Mapping[str, Any], task_name: str) -> None:
    """记录任务结束执行"""
    project_zbr_xbr = state.get("project_zbr_xbr", "")
    project_number = state.get("project_number", "")
    project_name = state.get("project_name", "")
    project_info = (
        f"{project_number}-{project_name}" if project_number or project_name else ""
    )
    logger.info(f"{project_zbr_xbr}-{project_info}结束生成，当前进入{task_name}")

# 任务执行日志文件路径（向后兼容）
TASK_EXECUTION_LOG_FILE = str(_file_handler.baseFilename)


__all__ = [
    "logger",
    "log_task_start",
    "log_task_end",
    "TASK_EXECUTION_LOG_FILE",
    "start_execution_log_listener",
    "stop_execution_log_listener",
]
