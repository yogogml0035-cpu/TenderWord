"""Execution log module for generate-task success auditing.

This module writes a single kind of audit record:
- generate task completed successfully
- required fields are complete
- fixed output format with the final node name `update_word`
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

# 主日志记录器（模块内部使用）
_execution_logger = logging.getLogger("TenderWord")
_execution_logger.addHandler(_queue_handler)
_execution_logger.setLevel(logging.INFO)
_execution_logger.propagate = False  # 阻止日志传播到根 logger，避免输出到控制台


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


def _normalize_required_field(state: Mapping[str, Any], key: str) -> str:
    return str(state.get(key, "") or "").strip()


def _build_generate_success_message(state: Mapping[str, Any]) -> str | None:
    project_zbr_xbr = _normalize_required_field(state, "project_zbr_xbr")
    project_number = _normalize_required_field(state, "project_number")
    project_name = _normalize_required_field(state, "project_name")

    if not (project_zbr_xbr and project_number and project_name):
        return None

    return f"{project_zbr_xbr}-{project_number}-{project_name}结束生成，当前进入update_word"


def log_generate_task_success(state: Mapping[str, Any]) -> None:
    """记录正式生成任务成功完成的审计日志。"""
    message = _build_generate_success_message(state)
    if message is None:
        return
    _execution_logger.info(message)

# 任务执行日志文件路径（向后兼容）
TASK_EXECUTION_LOG_FILE = str(_file_handler.baseFilename)


__all__ = [
    "log_generate_task_success",
    "TASK_EXECUTION_LOG_FILE",
    "start_execution_log_listener",
    "stop_execution_log_listener",
]
