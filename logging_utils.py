import json
import logging
import os
from typing import Mapping, Any

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
TASK_EXECUTION_LOG_FILE = os.path.join(LOG_DIR, "task_execution.log")

# 主日志记录器（使用任务执行日志文件）
logger = logging.getLogger("TenderWord")
if not logger.handlers:
    handler = logging.FileHandler(TASK_EXECUTION_LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s：%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # 阻止日志传播到根 logger，避免输出到控制台


def log_task_start(state: Mapping[str, Any], task_name: str) -> None:
    """记录任务开始执行"""
    project_number = state.get("project_number", "")
    project_name = state.get("project_name", "")
    project_info = f"{project_number}-{project_name}" if project_number or project_name else ""
    logger.info(f"{project_info}开始生成，当前进入{task_name}")

def log_task_end(state: Mapping[str, Any], task_name: str) -> None:
    """记录任务结束执行"""
    project_number = state.get("project_number", "")
    project_name = state.get("project_name", "")
    project_info = f"{project_number}-{project_name}" if project_number or project_name else ""
    logger.info(f"{project_info}结束生成，当前进入{task_name}")
