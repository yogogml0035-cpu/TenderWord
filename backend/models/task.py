"""
任务相关模型

定义任务状态、进度和响应相关的 Pydantic 模型。
基于 task/task_queue_manager.py 中的定义。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """
    任务状态枚举

    对应 task/task_queue_manager.py 中的 TaskStatus 枚举
    """

    QUEUED = "queued"  # 排队中
    RUNNING = "running"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消


class TaskKind(str, Enum):
    """任务类别"""

    GENERATE = "generate"
    REWRITE = "rewrite"
    EDIT = "edit"


class NodeStatus(str, Enum):
    """
    节点状态枚举
    """

    PENDING = "pending"  # 待执行
    RUNNING = "running"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败


class TaskProgress(BaseModel):
    """
    任务进度模型

    基于 task/task_queue_manager.py 中的 TaskProgress dataclass

    Attributes:
        task_id: 任务ID
        status: 当前状态
        completed_count: 已完成节点数
        total_nodes: 总节点数
        current_node: 当前正在执行的节点名称
        progress_text: 进度文本（如 "3/7"）
        progress_percent: 进度百分比
    """

    task_id: str = Field(..., description="任务ID")
    status: TaskStatus = Field(..., description="任务当前状态")
    completed_count: int = Field(default=0, description="已完成节点数", ge=0)
    total_nodes: int = Field(default=7, description="总节点数", ge=1)
    progress_text: str = Field(default="0/7", description="进度文本")
    progress_percent: float = Field(default=0.0, description="进度百分比")
    current_node: Optional[str] = Field(
        default=None, description="当前正在执行的节点名称"
    )
    current_node_display: Optional[str] = Field(
        default=None, description="当前节点显示名称（中文）"
    )
    completed_nodes: List[str] = Field(
        default_factory=list, description="已完成的节点名称列表"
    )

    def to_progress_dict(self) -> Dict[str, Any]:
        """转换为进度字典，用于 SSE 推送"""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "completed_count": self.completed_count,
            "total_nodes": self.total_nodes,
            "progress_text": self.progress_text,
            "progress_percent": round(self.progress_percent, 1),
            "current_node": self.current_node,
            "current_node_display": self.current_node_display,
        }


class TaskInfo(BaseModel):
    """
    任务信息模型

    基于 task/task_queue_manager.py 中的 Task dataclass
    用于返回任务的完整信息
    """

    task_id: str = Field(..., description="任务ID")
    user_session_id: str = Field(..., description="用户会话ID")
    task_kind: TaskKind = Field(default=TaskKind.GENERATE, description="任务类别")
    status: TaskStatus = Field(..., description="任务状态")
    created_at: datetime = Field(..., description="创建时间")
    started_at: Optional[datetime] = Field(default=None, description="开始执行时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")
    elapsed_time: Optional[float] = Field(default=None, description="已用时间（秒）")
    queue_position: int = Field(
        default=0, description="队列位置（0=正在执行, -1=不在队列中）"
    )
    waiting_count: int = Field(default=0, description="前面等待的任务数")
    result: Optional[Any] = Field(default=None, description="执行结果")
    error: Optional[str] = Field(default=None, description="错误信息")
    progress: TaskProgress = Field(
        default_factory=lambda: TaskProgress(task_id="", status=TaskStatus.QUEUED),
        description="任务进度",
    )
    current_running_progress: Optional[TaskProgress] = Field(
        default=None,
        description="当前正在执行任务的进度快照（仅排队任务需要）",
    )


class TaskResponse(BaseModel):
    """
    任务响应模型

    用于 API 返回任务操作结果
    """

    success: bool = Field(..., description="是否成功")
    task_id: Optional[str] = Field(default=None, description="任务ID")
    message: str = Field(default="", description="消息说明")
    data: Optional[TaskInfo] = Field(default=None, description="任务详细信息")


class TaskListResponse(BaseModel):
    """
    任务列表响应模型
    """

    success: bool = Field(..., description="是否成功")
    total: int = Field(default=0, description="任务总数")
    tasks: List[TaskInfo] = Field(default_factory=list, description="任务列表")
    message: str = Field(default="", description="消息说明")


class TaskCancelResponse(BaseModel):
    """
    任务取消响应模型
    """

    success: bool = Field(..., description="是否成功取消")
    task_id: str = Field(..., description="任务ID")
    message: str = Field(default="", description="消息说明")
    was_running: bool = Field(default=False, description="取消时任务是否正在执行")


class TaskHeartbeatResponse(BaseModel):
    """
    任务心跳响应模型
    """

    success: bool = Field(..., description="是否成功接收心跳")
    task_id: str = Field(..., description="任务ID")
    alive: bool = Field(..., description="任务是否仍处于活跃状态")
    task_kind: TaskKind = Field(default=TaskKind.GENERATE, description="任务类别")
    status: Optional[TaskStatus] = Field(default=None, description="任务当前状态")
