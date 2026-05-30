"""补充批注任务 API 路由。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from backend.models import CommentSupplementRequest, GenerateResponse
from backend.services.document_service import get_document_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/comment-supplement", tags=["CommentSupplement"])

@router.post(
    "",
    response_model=GenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="创建补充批注任务",
    description="基于当前会话最新文档创建补充批注任务，复用任务队列、SSE 和下载链路。",
)
async def create_comment_supplement_task(
    request: CommentSupplementRequest,
) -> GenerateResponse:
    logger.info(
        "收到补充批注请求: conversation_id=%s, source_file=%s, model=%s",
        request.conversation_id,
        request.source_file,
        request.model,
    )

    document_service = get_document_service()
    response = await document_service.create_comment_supplement_task(request)
    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": {
                    "code": response.error or "REQ_INVALID_PARAM",
                    "message": response.message or "创建补充批注任务失败",
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    return response
