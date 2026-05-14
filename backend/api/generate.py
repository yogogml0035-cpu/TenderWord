"""文档生成 API 路由.

提供文档生成的 REST API 端点。
"""

import logging

from fastapi import APIRouter, HTTPException, Path, status

from backend.models import (
    FormType,
    GenerateRequest,
    GenerateResponse,
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
2. 使用 GET /api/stream/{task_id} 订阅 SSE 事件流

**表单类型**：
- `xjcg_tender`: 询价采购
- `gngk_hw_zc_tender`: 国内公开（货物 / 自筹）
- `gngk_hw_cz_tender`: 国内公开（货物 / 财政）
- `gngk_fw_zc_tender`: 国内公开（服务 / 自筹）
- `gngk_fw_cz_tender`: 国内公开（服务 / 财政）
- `gjgk_tender`: 国际公开

**模型选择**：
- `deepseek`: DeepSeek 模型（默认）
- `qwen`: 通义千问模型
- `doubao`: 豆包模型
"""
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
    from backend.services.task_service import get_task_service

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
