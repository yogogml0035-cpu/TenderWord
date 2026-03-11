"""Conversation heartbeat API routes."""

from __future__ import annotations

from fastapi import APIRouter, Path
from pydantic import BaseModel, Field

from backend.services.conversation_service import get_conversation_service

router = APIRouter(prefix="/conversations", tags=["Conversations"])


class ConversationHeartbeatData(BaseModel):
    conversation_id: str = Field(..., description="会话ID")
    alive: bool = Field(..., description="会话是否活跃")
    instance_id: str = Field(..., description="服务实例标识")
    server_time: str = Field(..., description="服务端时间戳")
    rewrite_available: bool = Field(default=False, description="当前会话是否可进入修改模式")


class ConversationHeartbeatResponse(BaseModel):
    success: bool = True
    data: ConversationHeartbeatData
    message: str = "conversation heartbeat accepted"
    timestamp: str


@router.post(
    "/{conversation_id}/heartbeat",
    response_model=ConversationHeartbeatResponse,
    summary="更新会话心跳并返回实例标识",
)
async def heartbeat_conversation(
    conversation_id: str = Path(..., min_length=1, description="会话ID"),
) -> ConversationHeartbeatResponse:
    service = get_conversation_service()
    result = service.heartbeat(conversation_id)
    return ConversationHeartbeatResponse(
        data=ConversationHeartbeatData(**result),
        timestamp=result["server_time"],
    )
