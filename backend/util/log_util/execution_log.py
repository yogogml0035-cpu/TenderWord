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
import os
import queue
from datetime import datetime
from pathlib import Path
from typing import Mapping, Any

# 日志目录: backend/logs/
LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 动态生成按日期命名的日志文件
_today = datetime.now().strftime("%Y%m%d")
TASK_EXECUTION_LOG_FILE = str(LOG_DIR / f"execution-{_today}.log")

# 有界队列，防止内存溢出
_log_queue: queue.Queue[logging.LogRecord] = queue.Queue(maxsize=10000)

# 日志文件路径
_log_file = LOG_DIR / f"execution-{datetime.now().strftime('%Y%m%d')}.log"

# 文件 handler - 使用 TimedRotatingFileHandler 支持按天轮转
_file_handler = logging.handlers.TimedRotatingFileHandler(
    filename=str(_log_file),
    when="midnight",
    backupCount=30,  # 保留 30 天
    encoding="utf-8",
    delay=True,
)
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s：%(message)s", "%Y-%m-%d %H:%M:%S")
)

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


__all__ = [
    "logger",
    "log_task_start",
    "log_task_end",
    "TASK_EXECUTION_LOG_FILE",
    "start_execution_log_listener",
    "stop_execution_log_listener",
]
