"""任务管理 API 路由.

提供任务状态查询、取消、列表等端点。
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Path, Query, status

from backend.models.common import ErrorResponse
from backend.models.task import (
    TaskCancelResponse,
    TaskHeartbeatResponse,
    TaskListResponse,
    TaskResponse,
    TaskStatus,
)
from backend.services.task_service import get_task_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["Tasks"])


# ========================================
# API 端点
# ========================================
@router.get(
    "",
    response_model=TaskListResponse,
    summary="获取任务列表",
    description="获取任务列表，支持按用户会话ID和状态过滤。",
)
async def list_tasks(
    user_session_id: Optional[str] = Query(
        None,
        description="用户会话ID（可选，用于过滤特定用户的任务）",
    ),
    status: Optional[List[TaskStatus]] = Query(
        None,
        description="状态过滤（可多选）",
    ),
) -> TaskListResponse:
    """获取任务列表.

    Args:
        user_session_id: 用户会话ID（可选）
        status: 状态过滤列表（可选）

    Returns:
        TaskListResponse: 任务列表响应
    """
    logger.info(f"获取任务列表: user_session_id={user_session_id}, status={status}")

    task_service = get_task_service()
    result = task_service.list_tasks(
        user_session_id=user_session_id,
        status_filter=status,
    )

    return result


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    responses={
        404: {"model": ErrorResponse, "description": "任务不存在"},
    },
    summary="获取任务状态",
    description="获取指定任务的详细状态信息，包括进度、队列位置等。",
)
async def get_task(
    task_id: str = Path(
        ...,
        description="任务ID",
        min_length=1,
        examples=["abc12345"],
    ),
) -> TaskResponse:
    """获取任务状态.

    Args:
        task_id: 任务ID

    Returns:
        TaskResponse: 任务详情响应

    Raises:
        HTTPException: 任务不存在时返回 404
    """
    logger.info(f"获取任务状态: task_id={task_id}")

    task_service = get_task_service()
    result = task_service.get_task(task_id)

    if not result:
        logger.warning(f"任务不存在: task_id={task_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error": {
                    "code": "TASK_NOT_FOUND",
                    "message": "任务不存在",
                    "task_id": task_id,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    return result


@router.delete(
    "/{task_id}",
    response_model=TaskCancelResponse,
    responses={
        404: {"model": ErrorResponse, "description": "任务不存在"},
        409: {"model": ErrorResponse, "description": "任务当前状态不允许取消"},
    },
    summary="取消任务",
    description="取消指定任务。排队中的任务会立即取消，运行中的任务会标记取消请求。",
)
async def cancel_task(
    task_id: str = Path(
        ...,
        description="任务ID",
        min_length=1,
        examples=["abc12345"],
    ),
) -> TaskCancelResponse:
    """取消任务.

    Args:
        task_id: 任务ID

    Returns:
        TaskCancelResponse: 取消结果响应

    Raises:
        HTTPException: 任务不存在时返回 404
    """
    logger.info(f"取消任务: task_id={task_id}")

    task_service = get_task_service()
    task_response = task_service.get_task(task_id)

    if not task_response or not task_response.data:
        logger.warning(f"取消任务失败，任务不存在: task_id={task_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error": {
                    "code": "TASK_NOT_FOUND",
                    "message": "任务不存在",
                    "task_id": task_id,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    task_info = task_response.data
    if task_info.status in {
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    }:
        logger.info(
            f"取消任务跳过: task_id={task_id}, status={task_info.status.value}"
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "success": False,
                "error": {
                    "code": "TASK_CANNOT_CANCEL",
                    "message": f"任务已处于{task_info.status.value}状态，无需取消",
                    "task_id": task_id,
                    "status": task_info.status.value,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    result = task_service.cancel_task(task_id)
    if result.success:
        logger.info(
            f"任务取消成功: task_id={task_id}, was_running={result.was_running}"
        )
        return result

    logger.warning(f"任务取消失败: task_id={task_id}, message={result.message}")
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "success": False,
            "error": {
                "code": "TASK_CANNOT_CANCEL",
                "message": result.message or "任务当前状态不允许取消",
                "task_id": task_id,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@router.post(
    "/{task_id}/heartbeat",
    response_model=TaskHeartbeatResponse,
    responses={
        404: {"model": ErrorResponse, "description": "任务不存在"},
    },
    summary="更新任务心跳",
    description="更新指定任务的页面心跳，用于判断页面是否仍然存活。",
)
async def heartbeat_task(
    task_id: str = Path(
        ...,
        description="任务ID",
        min_length=1,
        examples=["abc12345"],
    ),
) -> TaskHeartbeatResponse:
    """更新任务心跳."""
    logger.info(f"更新任务心跳: task_id={task_id}")

    task_service = get_task_service()
    result = task_service.heartbeat_task(task_id)

    if not result:
        logger.warning(f"心跳更新失败，任务不存在: task_id={task_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error": {
                    "code": "TASK_NOT_FOUND",
                    "message": "任务不存在",
                    "task_id": task_id,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    return result
