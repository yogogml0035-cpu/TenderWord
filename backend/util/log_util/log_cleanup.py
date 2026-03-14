"""Log cleanup utility for managing log file sizes.

This module provides functionality to clean up log files when the total
size exceeds a specified threshold. It protects the current day's log
files from deletion.

Usage:
    from backend.util.log_util.log_cleanup import cleanup_logs

    # Clean up logs when total size exceeds 200MB
    deleted_count = cleanup_logs('backend/logs', max_total_mb=200)
"""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional


def get_log_files(log_dir: Path) -> List[Path]:
    """获取目录下所有的日志文件。

    Args:
        log_dir: 日志目录路径

    Returns:
        日志文件列表
    """
    patterns = [
        "execution-*.log",
        "execution-*.log.*",
        "progress-*.log",
        "progress-*.log.*",
    ]
    log_files = []
    for pattern in patterns:
        log_files.extend(log_dir.glob(pattern))
    return list({path.resolve(): path for path in log_files}.values())


def get_total_size(files: List[Path]) -> int:
    """计算文件总大小。

    Args:
        files: 文件列表

    Returns:
        总大小（字节）
    """
    return sum(f.stat().st_size for f in files if f.exists())


def cleanup_logs(log_dir: str, max_total_mb: int = None) -> int:
    """清理日志文件，保持总大小在阈值以下。

    当日志文件总大小超过阈值时，按修改时间排序，删除最旧的文件，
    直到总大小低于阈值。当天的日志文件会被保护，不会被删除。

    Args:
        log_dir: 日志目录路径
        max_total_mb: 最大总大小（MB），默认使用 settings.LOG_CLEANUP_MAX_MB

    Returns:
        删除的文件数量

    Example:
        >>> deleted = cleanup_logs('backend/logs')
        >>> print(f"Deleted {deleted} files")
    """
    # 延迟导入 settings 以避免循环依赖
    from backend.config.settings import settings
    
    if max_total_mb is None:
        max_total_mb = settings.LOG_CLEANUP_MAX_MB
    """清理日志文件，保持总大小在阈值以下。

    当日志文件总大小超过阈值时，按修改时间排序，删除最旧的文件，
    直到总大小低于阈值。当天的日志文件会被保护，不会被删除。

    Args:
        log_dir: 日志目录路径
        max_total_mb: 最大总大小（MB），默认200MB

    Returns:
        删除的文件数量

    Example:
        >>> deleted = cleanup_logs('backend/logs', max_total_mb=200)
        >>> print(f"Deleted {deleted} files")
    """
    log_path = Path(log_dir)
    if not log_path.exists():
        return 0

    # 获取当天日期字符串（用于保护当天的文件）
    today = datetime.now().strftime("%Y%m%d")

    # 获取所有日志文件
    log_files = get_log_files(log_path)

    if not log_files:
        return 0

    # 计算总大小
    max_bytes = max_total_mb * 1024 * 1024
    total_size = get_total_size(log_files)

    if total_size <= max_bytes:
        return 0

    # 按修改时间排序（最旧的在前）
    log_files.sort(key=lambda f: f.stat().st_mtime)

    deleted_count = 0
    for log_file in log_files:
        # 保护当天的文件
        if today in log_file.name:
            continue

        try:
            file_size = log_file.stat().st_size
            log_file.unlink()
            total_size -= file_size
            deleted_count += 1

            if total_size <= max_bytes:
                break
        except Exception as e:
            # 使用 stderr 输出避免循环依赖（logging 模块可能会调用 cleanup）
            import sys
            print(f"[log_cleanup] Warning: Failed to delete {log_file}: {e}",
                  file=sys.stderr, flush=True)
            # 使用 stderr 输出避免循环依赖（logging 模块可能会调用 cleanup）
            import sys
            print(f"[log_cleanup] Warning: Failed to delete {log_file}: {e}",
                  file=sys.stderr, flush=True)

    return deleted_count


def get_log_stats(log_dir: str) -> dict:
    """获取日志目录的统计信息。

    Args:
        log_dir: 日志目录路径

    Returns:
        包含统计信息的字典：
        - total_files: 文件总数
        - total_size_mb: 总大小（MB）
        - execution_files: execution日志文件数
        - progress_files: progress日志文件数
    """
    log_path = Path(log_dir)
    if not log_path.exists():
        return {
            "total_files": 0,
            "total_size_mb": 0,
            "execution_files": 0,
            "progress_files": 0,
        }

    log_files = get_log_files(log_path)
    total_size = get_total_size(log_files)

    execution_files = [f for f in log_files if f.name.startswith("execution-")]
    progress_files = [f for f in log_files if f.name.startswith("progress-")]

    return {
        "total_files": len(log_files),
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "execution_files": len(execution_files),
        "progress_files": len(progress_files),
    }


__all__ = ["cleanup_logs", "get_log_stats", "get_log_files", "get_total_size"]
