"""文档生成 API 路由.

提供文档生成的 REST API 端点，支持 SSE 流式输出。
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Path, status
from fastapi.responses import StreamingResponse

from backend.models import (
    DoneEventData,
    ErrorEventData,
    FormType,
    GenerateRequest,
    GenerateResponse,
    HeartbeatEventData,
    SSEEvent,
    SSEEventType,
)
from backend.services.document_service import get_document_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generate", tags=["Generate"])


# ========================================
# API 端点
# ========================================
@router.post(
    "",
    response_model=GenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="创建文档生成任务",
    description="""
创建文档生成任务，返回任务ID。

任务在后台异步执行，可通过以下方式获取进度：
1. 使用 GET /api/tasks/{task_id} 查询任务状态
2. 使用 GET /api/generate/{task_id}/stream 订阅 SSE 事件流

**表单类型**：
- `xjcg_tender`: 询价采购
- `gngk_tender`: 国内公开招标

**模型选择**：
- `deepseek`: DeepSeek 模型（默认）
- `qwen`: 通义千问模型
- `doubao`: 豆包模型
""",
)
async def create_generate_task(
    request: GenerateRequest,
) -> GenerateResponse:
    """创建文档生成任务.

    Args:
        request: 生成请求

    Returns:
        GenerateResponse: 包含 task_id 的响应
    """
    logger.info(
        f"收到文档生成请求: form_type={request.form_type}, model={request.model}"
    )

    document_service = get_document_service()
    response = document_service.create_task(request)

    if not response.success:
        logger.warning(f"创建任务失败: {response.message}")
        # 对于已知错误，返回 400
        if "未知的表单类型" in (response.error or ""):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error": response.error,
                    "message": response.message,
                },
            )

    return response


@router.get(
    "/{task_id}/stream",
    summary="订阅任务 SSE 事件流",
    description="""
订阅文档生成任务的 SSE 事件流。

**事件类型**：
- `log`: 普通日志消息
- `llm`: LLM 流式输出
- `progress`: 进度更新
- `node_start`: 节点开始执行
- `node_complete`: 节点执行完成
- `done`: 任务完成
- `error`: 错误
- `heartbeat`: 心跳（每 15 秒）
""",
)
async def stream_generate_events(
    task_id: str = Path(
        ...,
        description="任务ID",
        min_length=1,
        examples=["task-abc12345-1234"],
    ),
):
    """订阅任务 SSE 事件流.

    Args:
        task_id: 任务ID

    Returns:
        StreamingResponse: SSE 事件流
    """
    document_service = get_document_service()
    callback = document_service.get_callback(task_id)

    if not callback:
        # 任务不存在
        async def error_generator():
            event = SSEEvent(
                event=SSEEventType.ERROR,
                data=ErrorEventData(
                    task_id=task_id,
                    error="任务不存在",
                    is_fatal=True,
                ).model_dump(),
            )
            yield event.to_sse_format()

        return StreamingResponse(
            error_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    async def event_generator():
        """SSE 事件生成器."""
        last_event_count = 0
        heartbeat_counter = 0
        max_heartbeats = 120  # 最多 30 分钟（15秒 * 120）

        while True:
            # 获取新事件
            events = callback.get_events()
            new_events = events[last_event_count:]

            # 发送新事件
            for event in new_events:
                yield event.to_sse_format()
                last_event_count += 1

                # 如果是完成或错误事件，结束流
                if event.event in (SSEEventType.DONE, SSEEventType.ERROR):
                    logger.info(f"SSE 流结束: task_id={task_id}, event={event.event}")
                    return

            # 检查是否完成
            if callback.is_done():
                logger.info(f"SSE 流结束（任务完成）: task_id={task_id}")
                return

            # 发送心跳
            heartbeat_counter += 1
            if heartbeat_counter % 15 == 0:  # 每 15 次循环发送一次心跳
                heartbeat_event = SSEEvent(
                    event=SSEEventType.HEARTBEAT,
                    data=HeartbeatEventData(task_id=task_id).model_dump(),
                )
                yield heartbeat_event.to_sse_format()

                # 检查心跳超时
                if heartbeat_counter > max_heartbeats * 15:
                    logger.warning(f"SSE 流超时: task_id={task_id}")
                    timeout_event = SSEEvent(
                        event=SSEEventType.ERROR,
                        data=ErrorEventData(
                            task_id=task_id,
                            error="连接超时",
                            is_fatal=True,
                        ).model_dump(),
                    )
                    yield timeout_event.to_sse_format()
                    return

            # 等待
            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )


@router.get(
    "/{task_id}",
    response_model=GenerateResponse,
    summary="获取生成任务状态",
    description="获取文档生成任务的当前状态和结果。",
)
async def get_generate_task(
    task_id: str = Path(
        ...,
        description="任务ID",
        min_length=1,
        examples=["task-abc12345-1234"],
    ),
) -> GenerateResponse:
    """获取生成任务状态.

    Args:
        task_id: 任务ID

    Returns:
        GenerateResponse: 任务状态响应
    """
    from services.task_service import get_task_service

    task_service = get_task_service()
    task_response = task_service.get_task(task_id)

    if not task_response or not task_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error": {
                    "code": "TASK_NOT_FOUND",
                    "message": "任务不存在",
                    "task_id": task_id,
                },
            },
        )

    task_info = task_response.data

    # 构建响应
    return GenerateResponse(
        success=True,
        task_id=task_id,
        message="获取任务状态成功",
        output_file=task_info.result if task_info.status.value == "completed" else None,
        progress=task_info.progress,
        error=task_info.error,
    )
