"""Unified user message routing API."""

from __future__ import annotations

import logging
from typing import List, Literal

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.graphs.user_graph import UserGraph
from backend.services.chat_stream_service import build_error_detail, extract_latest_user_message, normalize_chat_messages
from backend.services.document_service import get_document_service
from backend.services.user_routing_service import get_user_routing_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user", tags=["User"])


class UserChatMessage(BaseModel):
    role: Literal["user", "assistant"] = Field(..., description="消息角色")
    content: str = Field(..., min_length=1, description="消息文本")


class UserStreamRequest(BaseModel):
    conversation_id: str = Field(..., min_length=1, description="会话ID")
    model: Literal["deepseek", "qwen", "doubao"] = Field(
        default="deepseek", description="模型类型"
    )
    messages: List[UserChatMessage] = Field(default_factory=list, description="聊天历史消息")


@router.post(
    "/stream",
    summary="统一用户消息入口",
    description="返回 NDJSON 流，先路由再分发到普通聊天或 rewrite 任务创建。",
)
async def stream_user_message(request: Request, payload: UserStreamRequest) -> StreamingResponse:
    normalized_messages = normalize_chat_messages(payload.messages)
    if not normalized_messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=build_error_detail("REQ_MISSING_FIELD", "messages 不能为空"),
        )

    latest_user_message = extract_latest_user_message(normalized_messages)
    if not latest_user_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=build_error_detail("REQ_MISSING_FIELD", "messages 不能为空"),
        )

    user_graph = UserGraph(
        document_service=get_document_service(),
        routing_service=get_user_routing_service(),
    )

    initial_state = {
        "conversation_id": payload.conversation_id,
        "model_provider": payload.model,
        "messages": normalized_messages,
        "latest_user_message": latest_user_message,
    }

    return StreamingResponse(
        user_graph.stream(request, initial_state),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
