"""Agent run streaming API."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.models import AgentRunStreamRequest
from backend.services.agent_run_service import get_agent_run_service

router = APIRouter(prefix="/agent/runs", tags=["Agent Runs"])


@router.post(
    "/stream",
    summary="任务上下文助手流式入口",
    description="返回 NDJSON 流，由任务上下文助手理解上下文并调度受控 skill。",
)
async def stream_agent_run(
    request: Request,
    payload: AgentRunStreamRequest,
) -> StreamingResponse:
    service = get_agent_run_service()
    return StreamingResponse(
        service.stream(request, payload),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
