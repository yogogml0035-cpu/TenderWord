"""任务服务模块.

封装任务队列管理器操作，提供任务状态查询、取消、列表等功能。
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from backend.models.task import (
    TaskCancelResponse,
    TaskInfo,
    TaskListResponse,
    TaskProgress,
    TaskResponse,
    TaskStatus,
)
from backend.task.task_queue_manager import (
    NODE_DISPLAY_NAMES,
    NodeName,
    Task as InternalTask,
    TaskQueueManager,
    TaskStatus as InternalTaskStatus,
    get_task_queue,
)


class TaskService:
    """任务服务类.

    封装 TaskQueueManager 的操作，提供 API 层友好的接口。
    """

    def __init__(self, task_queue: Optional[TaskQueueManager] = None):
        """初始化任务服务.

        Args:
            task_queue: 任务队列管理器实例（默认使用全局单例）
        """
        self._task_queue = task_queue or get_task_queue()

    def get_task(self, task_id: str) -> Optional[TaskResponse]:
        """获取任务状态.

        Args:
            task_id: 任务ID

        Returns:
            TaskResponse 或 None（任务不存在时）
        """
        internal_task = self._task_queue.get_task(task_id)
        if not internal_task:
            return None

        task_info = self._convert_to_task_info(internal_task)
        return TaskResponse(
            success=True,
            task_id=task_id,
            message="获取任务成功",
            data=task_info,
        )

    def cancel_task(self, task_id: str) -> TaskCancelResponse:
        """取消任务.

        Args:
            task_id: 任务ID

        Returns:
            TaskCancelResponse: 取消结果
        """
        internal_task = self._task_queue.get_task(task_id)
        if not internal_task:
            return TaskCancelResponse(
                success=False,
                task_id=task_id,
                message="任务不存在",
                was_running=False,
            )

        was_running = internal_task.status == InternalTaskStatus.RUNNING

        success = self._task_queue.cancel_task(task_id)
        if success:
            message = "任务已取消" if was_running else "排队任务已取消"
            return TaskCancelResponse(
                success=True,
                task_id=task_id,
                message=message,
                was_running=was_running,
            )
        else:
            status_text = self._get_status_text(internal_task.status)
            return TaskCancelResponse(
                success=False,
                task_id=task_id,
                message=f"无法取消{status_text}的任务",
                was_running=was_running,
            )

    def list_tasks(
        self,
        user_session_id: Optional[str] = None,
        status_filter: Optional[List[TaskStatus]] = None,
    ) -> TaskListResponse:
        """获取任务列表.

        Args:
            user_session_id: 用户会话ID（可选，用于过滤）
            status_filter: 状态过滤列表（可选）

        Returns:
            TaskListResponse: 任务列表响应
        """
        # 获取所有任务（需要访问内部数据）
        tasks = self._get_all_tasks()

        # 过滤任务
        filtered_tasks = []
        for task in tasks:
            # 按用户会话过滤
            if user_session_id and task.user_session_id != user_session_id:
                continue

            # 按状态过滤
            if status_filter:
                task_status = self._convert_status(task.status)
                if task_status not in status_filter:
                    continue

            filtered_tasks.append(task)

        # 转换为 TaskInfo 列表
        task_infos = [self._convert_to_task_info(t) for t in filtered_tasks]

        # 按创建时间倒序排列
        task_infos.sort(key=lambda x: x.created_at, reverse=True)

        return TaskListResponse(
            success=True,
            total=len(task_infos),
            tasks=task_infos,
            message="获取任务列表成功",
        )

    def _get_all_tasks(self) -> List[InternalTask]:
        """获取所有任务.

        Returns:
            任务列表
        """
        with self._task_queue._data_lock:
            return list(self._task_queue._tasks.values())

    def _convert_status(self, status: InternalTaskStatus) -> TaskStatus:
        """转换内部状态为 API 状态.

        Args:
            status: 内部任务状态

        Returns:
            API 任务状态
        """
        status_map = {
            InternalTaskStatus.QUEUED: TaskStatus.QUEUED,
            InternalTaskStatus.RUNNING: TaskStatus.RUNNING,
            InternalTaskStatus.COMPLETED: TaskStatus.COMPLETED,
            InternalTaskStatus.FAILED: TaskStatus.FAILED,
            InternalTaskStatus.CANCELLED: TaskStatus.CANCELLED,
        }
        return status_map.get(status, TaskStatus.QUEUED)

    def _convert_to_task_info(self, task: InternalTask) -> TaskInfo:
        """将内部任务转换为 TaskInfo.

        Args:
            task: 内部任务对象

        Returns:
            TaskInfo: API 任务信息
        """
        # 获取当前运行的节点
        current_node = None
        current_node_display = None
        if task.progress.running_nodes:
            current_node = task.progress.running_nodes[0]
            current_node_display = self._get_node_display_name(current_node)

        # 构建进度信息
        progress = TaskProgress(
            task_id=task.task_id,
            status=self._convert_status(task.status),
            completed_count=task.progress.completed_count,
            total_nodes=task.progress.total_nodes,
            current_node=current_node,
            current_node_display=current_node_display,
            completed_nodes=task.progress.completed_nodes,
        )

        # 获取队列位置
        queue_position = self._task_queue.get_queue_position(task.task_id)
        waiting_count = self._task_queue.get_waiting_count(task.task_id)

        return TaskInfo(
            task_id=task.task_id,
            user_session_id=task.user_session_id,
            status=self._convert_status(task.status),
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            elapsed_time=task.elapsed_time,
            queue_position=queue_position,
            waiting_count=waiting_count,
            result=task.result,
            error=task.error,
            progress=progress,
        )

    def _get_node_display_name(self, node_name: str) -> str:
        """获取节点的显示名称.

        Args:
            node_name: 节点名称

        Returns:
            节点显示名称（中文）
        """
        try:
            node = NodeName(node_name)
            return NODE_DISPLAY_NAMES.get(node, node_name)
        except ValueError:
            return node_name

    def _get_status_text(self, status: InternalTaskStatus) -> str:
        """获取状态的中文描述.

        Args:
            status: 内部任务状态

        Returns:
            状态中文描述
        """
        status_text_map = {
            InternalTaskStatus.QUEUED: "排队中",
            InternalTaskStatus.RUNNING: "运行中",
            InternalTaskStatus.COMPLETED: "已完成",
            InternalTaskStatus.FAILED: "已失败",
            InternalTaskStatus.CANCELLED: "已取消",
        }
        return status_text_map.get(status, "未知状态")


# 全局服务实例
_task_service: Optional[TaskService] = None


def get_task_service() -> TaskService:
    """获取任务服务实例（单例）."""
    global _task_service
    if _task_service is None:
        _task_service = TaskService()
    return _task_service
