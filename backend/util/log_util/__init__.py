"""
日志工具模块

提供统一的日志记录功能，包括：
- execution_log: 生成成功审计日志（INFO级别）
- progress_log: 详细执行日志（DEBUG/INFO/WARNING/ERROR级别）
- log_cleanup: 日志清理工具
- sse_log_handler: SSE实时日志推送
"""

# 从 execution_log 导出
from backend.util.log_util.execution_log import (
    log_generate_task_success,
    TASK_EXECUTION_LOG_FILE,
    start_execution_log_listener,
    stop_execution_log_listener,
)

# 从 progress_log 导出
from backend.util.log_util.progress_log import (
    progress_log,
    start_progress_log_listener,
    stop_progress_log_listener,
)

# 从 log_cleanup 导出
from backend.util.log_util.log_cleanup import (
    cleanup_logs,
    get_log_stats,
)

# 从 sse_log_handler 导出
from backend.util.log_util.sse_log_handler import (
    SSELogHandler,
    task_log_context,
    get_current_task_id,
    init_sse_log_handler,
    get_sse_log_handler,
)

__all__ = [
    # execution_log
    "log_generate_task_success",
    "TASK_EXECUTION_LOG_FILE",
    "start_execution_log_listener",
    "stop_execution_log_listener",
    # progress_log
    "progress_log",
    "start_progress_log_listener",
    "stop_progress_log_listener",
    # log_cleanup
    "cleanup_logs",
    "get_log_stats",
    # sse_log_handler
    "SSELogHandler",
    "task_log_context",
    "get_current_task_id",
    "init_sse_log_handler",
    "get_sse_log_handler",
]
