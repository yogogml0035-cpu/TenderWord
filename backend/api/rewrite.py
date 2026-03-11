"""Rewrite task API routes."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.models import GenerateResponse, LLMModel
from backend.services.document_service import get_document_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rewrite", tags=["Rewrite"])


class RewriteRequest(BaseModel):
    conversation_id: str = Field(..., min_length=1, description="会话ID")
    user_prompt: str = Field(..., min_length=1, description="修改指令")
    model: LLMModel = Field(default=LLMModel.DEEPSEEK, description="使用的模型")


def _error_status(code: str) -> int:
    if code in {"REWRITE_NO_DOCUMENT", "REWRITE_HISTORY_NOT_FOUND"}:
        return status.HTTP_404_NOT_FOUND
    if code in {"REWRITE_PROMPT_INVALID", "REWRITE_TARGET_NOT_RESOLVED"}:
        return status.HTTP_400_BAD_REQUEST
    if code == "LLM_TIMEOUT":
        return status.HTTP_504_GATEWAY_TIMEOUT
    if code == "LLM_SERVICE_ERROR":
        return status.HTTP_503_SERVICE_UNAVAILABLE
    return status.HTTP_400_BAD_REQUEST


@router.post(
    "",
    response_model=GenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="创建修改任务",
)
async def create_rewrite_task(request: RewriteRequest) -> GenerateResponse:
    logger.info(
        "收到修改请求: conversation_id=%s, model=%s",
        request.conversation_id,
        request.model.value,
    )
    document_service = get_document_service()
    response = await document_service.create_rewrite_task(
        conversation_id=request.conversation_id,
        user_prompt=request.user_prompt,
        model_provider=request.model.value,
    )

    if response.success:
        return response

    error_code = response.error or "REWRITE_FAILED"
    raise HTTPException(
        status_code=_error_status(error_code),
        detail={
            "success": False,
            "error": {
                "code": error_code,
                "message": response.message or "修改任务创建失败",
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
