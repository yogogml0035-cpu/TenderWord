"""文件上传 API 路由.

提供单文件和多文件上传功能，支持文件类型验证和大小限制.
"""

from datetime import datetime
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from backend.models.common import ErrorResponse
from backend.util.common_util.upload_storage import persist_file_bytes

router = APIRouter(prefix="/upload", tags=["File Upload"])


# ========================================
# Pydantic 响应模型
# ========================================
class FileUploadResponse(BaseModel):
    """单文件上传响应模型."""

    success: bool = Field(..., description="是否上传成功")
    file_path: str = Field(..., description="文件保存路径")
    file_name: str = Field(..., description="保存的文件名")
    original_name: str = Field(..., description="原始文件名")
    file_size: int = Field(..., description="文件大小（字节）")
    content_type: str = Field(..., description="文件 MIME 类型")
    upload_time: str = Field(..., description="上传时间（ISO 格式）")


class FileInfo(BaseModel):
    """单个文件信息."""

    file_path: str = Field(..., description="文件保存路径")
    file_name: str = Field(..., description="保存的文件名")
    original_name: str = Field(..., description="原始文件名")
    size: int = Field(..., description="文件大小（字节）")
    content_type: str = Field(..., description="文件 MIME 类型")


class MultiFileUploadResponse(BaseModel):
    """多文件上传响应模型."""

    success: bool = Field(..., description="是否上传成功")
    files: List[FileInfo] = Field(
        default_factory=list, description="上传成功的文件列表"
    )
    total_count: int = Field(..., description="总文件数")
    success_count: int = Field(..., description="成功上传数")
    failed_count: int = Field(..., description="失败数")
    upload_time: str = Field(..., description="上传时间（ISO 格式）")


async def save_upload_file(upload_file: UploadFile) -> dict:
    """保存单个上传文件.

    Args:
        upload_file: FastAPI UploadFile 对象

    Returns:
        包含文件信息的字典

    Raises:
        HTTPException: 文件验证失败时抛出
    """
    original_name = upload_file.filename

    # 读取文件内容
    content = await upload_file.read()
    return persist_file_bytes(
        original_name=original_name,
        content=content,
        content_type=upload_file.content_type or "application/octet-stream",
    )


# ========================================
# API 端点
# ========================================
@router.post(
    "",
    response_model=FileUploadResponse,
    summary="上传单个文件",
    description="上传单个 Word 文档文件（.doc/.docx/.pdf/.txt 格式）",
    responses={
        415: {"model": ErrorResponse, "description": "无效的文件类型"},
        413: {"model": ErrorResponse, "description": "文件过大"},
        500: {"model": ErrorResponse, "description": "上传失败"},
    },
)
async def upload_single_file(
    file: UploadFile = File(..., description="要上传的文件"),
    file_type: str = None,
) -> FileUploadResponse:
    """上传单个文件.

    Args:
        file: 上传的文件
        file_type: 文件类型标记（可选）

    Returns:
        文件上传成功响应
    """
    file_info = await save_upload_file(file)

    return FileUploadResponse(
        success=True,
        file_path=file_info["file_path"],
        file_name=file_info["file_name"],
        original_name=file_info["original_name"],
        file_size=file_info["file_size"],
        content_type=file_info["content_type"],
        upload_time=datetime.utcnow().isoformat() + "Z",
    )


@router.post(
    "/multiple",
    response_model=MultiFileUploadResponse,
    summary="批量上传文件",
    description="批量上传多个 Word 文档文件",
    responses={
        415: {"model": ErrorResponse, "description": "包含无效的文件类型"},
        413: {"model": ErrorResponse, "description": "文件过大"},
        500: {"model": ErrorResponse, "description": "部分文件上传失败"},
    },
)
async def upload_multiple_files(
    files: List[UploadFile] = File(..., description="要上传的文件列表"),
    file_type: str = None,
) -> MultiFileUploadResponse:
    """批量上传多个文件.

    Args:
        files: 上传的文件列表
        file_type: 文件类型标记（可选）

    Returns:
        批量上传响应，包含成功和失败的统计
    """
    uploaded_files: List[FileInfo] = []
    failed_files: List[dict] = []

    for upload_file in files:
        try:
            file_info = await save_upload_file(upload_file)
            uploaded_files.append(
                FileInfo(
                    file_path=file_info["file_path"],
                    file_name=file_info["file_name"],
                    original_name=file_info["original_name"],
                    size=file_info["file_size"],
                    content_type=file_info["content_type"],
                )
            )
        except HTTPException as e:
            failed_files.append(
                {
                    "filename": upload_file.filename,
                    "error": e.detail,
                }
            )

    total_count = len(files)
    success_count = len(uploaded_files)
    failed_count = len(failed_files)

    # 如果全部失败，返回错误
    if success_count == 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "FILE_UPLOAD_FAILED",
                "message": "所有文件上传失败",
                "details": failed_files,
            },
        )

    return MultiFileUploadResponse(
        success=True,
        files=uploaded_files,
        total_count=total_count,
        success_count=success_count,
        failed_count=failed_count,
        upload_time=datetime.utcnow().isoformat() + "Z",
    )
