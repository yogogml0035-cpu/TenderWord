"""SSE 流式输出路由.

提供 Server-Sent Events (SSE) 端点，用于实时推送任务执行进度和输出。
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Path, Request
from fastapi.responses import StreamingResponse

from backend.core.sse_manager import sse_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["SSE"])


@router.get("/stream/{task_id}")
async def stream_task_events(
    request: Request,
    task_id: str = Path(..., description="任务ID"),
    last_event_id: Optional[str] = Header(
        None,
        alias="Last-Event-ID",
        description="最后接收的事件ID，用于断线重连",
    ),
) -> StreamingResponse:
    """SSE 流式输出端点.

    通过 Server-Sent Events (SSE) 实时推送任务执行进度、日志和 LLM 输出。

    **事件类型**:
    - `log`: 普通日志消息
    - `llm`: LLM 生成内容流
    - `progress`: 进度更新
    - `done`: 任务完成
    - `error`: 错误信息

    **断线重连**:
    客户端可以通过发送 `Last-Event-ID` 请求头来恢复断开的连接，
    服务端会从该事件ID之后继续发送事件。

    **心跳机制**:
    服务端每 15 秒发送一次心跳注释（`: heartbeat`）以保持连接活跃。

    **响应头**:
    - `Content-Type: text/event-stream`
    - `Cache-Control: no-cache`
    - `Connection: keep-alive`
    - `X-Accel-Buffering: no` (禁用 Nginx 缓冲)

    Args:
        request: FastAPI 请求对象
        task_id: 任务ID
        last_event_id: 最后接收的事件ID（断线重连）

    Returns:
        StreamingResponse: SSE 事件流

    Raises:
        HTTPException: 400 - 无效的 Last-Event-ID 格式
    """
    # 解析 Last-Event-ID
    parsed_last_event_id = None
    if last_event_id:
        try:
            parsed_last_event_id = int(last_event_id)
            logger.info(
                f"SSE reconnection request",
                extra={
                    "task_id": task_id,
                    "last_event_id": parsed_last_event_id,
                },
            )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid Last-Event-ID format: {last_event_id}",
            )

    # 生成客户端ID
    client_id = f"{task_id}_{uuid.uuid4().hex[:8]}"

    logger.info(
        f"SSE connection request",
        extra={
            "task_id": task_id,
            "client_id": client_id,
            "last_event_id": parsed_last_event_id,
        },
    )

    async def event_generator():
        """生成 SSE 事件的异步生成器."""
        try:
            async for event_str in sse_manager.event_stream(
                task_id=task_id,
                client_id=client_id,
                last_event_id=parsed_last_event_id,
            ):
                # 检查客户端是否断开连接
                if await request.is_disconnected():
                    logger.info(
                        f"Client disconnected",
                        extra={"task_id": task_id, "client_id": client_id},
                    )
                    break
                yield event_str

        except Exception as e:
            logger.error(
                f"SSE stream error: {str(e)}",
                extra={
                    "task_id": task_id,
                    "client_id": client_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 代理缓冲
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.get("/stream/{task_id}/status")
async def get_stream_status(
    task_id: str = Path(..., description="任务ID"),
) -> dict:
    """获取 SSE 流状态.

    返回指定任务的 SSE 连接状态信息。

    Args:
        task_id: 任务ID

    Returns:
        dict: 包含客户端数量等信息的状态对象
    """
    client_count = sse_manager.get_client_count(task_id)

    return {
        "task_id": task_id,
        "connected_clients": client_count,
        "status": "active" if client_count > 0 else "idle",
    }
