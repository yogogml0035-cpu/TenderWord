"""显式 edit 任务 API 路由。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from backend.models import EditTaskRequest, GenerateResponse
from backend.services.document_service import get_document_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/edit", tags=["Edit"])


@router.post(
    "",
    response_model=GenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="创建显式 edit 文档修改任务",
    description="基于用户显式上传的 Word 文件创建 edit 任务，复用现有任务队列、SSE 和下载链路。",
)
async def create_edit_task(request: EditTaskRequest) -> GenerateResponse:
    logger.info(
        "收到显式 edit 请求: form_type=%s, model=%s, conversation_id=%s",
        request.form_type,
        request.model,
        request.conversation_id,
    )

    document_service = get_document_service()
    response = await document_service.create_edit_task(request)
    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": {
                    "code": response.error or "REQ_INVALID_PARAM",
                    "message": response.message or "创建 edit 任务失败",
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    return response
