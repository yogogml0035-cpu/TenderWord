"""Plain chat streaming API routes."""

from __future__ import annotations

import logging
from typing import List, Literal

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.services.chat_stream_service import (
    build_error_detail,
    extract_latest_user_message,
    normalize_chat_messages,
    stream_chat_response,
)
from backend.services.user_routing_service import (
    CHAT_REWRITE_SWITCH_HINT_TEXT,
    DOC_CONTEXT_HINT_TEXT,
    looks_like_doc_context_query,
    looks_like_rewrite_intent,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"] = Field(..., description="消息角色")
    content: str = Field(..., min_length=1, description="消息文本")


class ChatStreamRequest(BaseModel):
    conversation_id: str = Field(..., min_length=1, description="会话ID")
    model: Literal["deepseek", "qwen", "doubao"] = Field(
        default="deepseek", description="模型类型"
    )
    messages: List[ChatMessage] = Field(default_factory=list, description="聊天历史消息")


@router.post(
    "/stream",
    summary="普通聊天流式接口",
    description="已废弃，建议改用 /user/stream。返回 NDJSON 流，事件类型至少包含 chunk / done / error。",
    deprecated=True,
)
async def stream_chat(request: Request, payload: ChatStreamRequest) -> StreamingResponse:
    normalized_messages = normalize_chat_messages(payload.messages)

    if not normalized_messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=build_error_detail("REQ_MISSING_FIELD", "messages 不能为空"),
        )

    latest_user_message = extract_latest_user_message(normalized_messages)

    if looks_like_doc_context_query(latest_user_message):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=build_error_detail("CHAT_DOC_CONTEXT_REQUIRED", DOC_CONTEXT_HINT_TEXT),
        )
    if looks_like_rewrite_intent(latest_user_message):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=build_error_detail("CHAT_MODE_REQUIRES_REWRITE", CHAT_REWRITE_SWITCH_HINT_TEXT),
        )

    return StreamingResponse(
        stream_chat_response(
            request,
            conversation_id=payload.conversation_id,
            model_provider=payload.model,
            normalized_messages=normalized_messages,
        ),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
