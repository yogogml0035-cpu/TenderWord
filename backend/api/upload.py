"""文件上传 API 路由.

提供单文件和多文件上传功能，支持文件类型验证和大小限制.
"""

import pathlib
import time
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.models.common import ErrorResponse

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


# ========================================
# 文件上传工具函数
# ========================================
def validate_file_extension(filename: str) -> bool:
    """验证文件扩展名是否在允许列表中.

    Args:
        filename: 原始文件名

    Returns:
        是否允许上传
    """
    suffix = pathlib.Path(filename).suffix.lower()
    return suffix in settings.ALLOWED_EXTENSIONS


def validate_file_size(file_size: int) -> bool:
    """验证文件大小是否超过限制.

    Args:
        file_size: 文件大小（字节）

    Returns:
        是否在允许范围内
    """
    return file_size <= settings.MAX_UPLOAD_SIZE


def generate_unique_filename(original_name: str) -> str:
    """生成唯一文件名，处理重名情况.

    如果文件已存在，在文件名后添加时间戳和随机后缀.

    Args:
        original_name: 原始文件名

    Returns:
        唯一文件名
    """
    upload_dir = pathlib.Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_path = upload_dir / original_name

    if file_path.exists():
        # 添加时间戳和随机后缀
        timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
        stem = file_path.stem
        suffix = file_path.suffix
        unique_suffix = uuid.uuid4().hex[:8]
        file_path = upload_dir / f"{stem}_{timestamp}_{unique_suffix}{suffix}"

    return str(file_path)


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

    # 验证文件扩展名
    if not validate_file_extension(original_name):
        allowed = ", ".join(settings.ALLOWED_EXTENSIONS)
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "code": "FILE_INVALID_TYPE",
                "message": f"不支持的文件类型。允许的类型: {allowed}",
                "details": f"文件名: {original_name}",
            },
        )

    # 读取文件内容
    content = await upload_file.read()
    file_size = len(content)

    # 验证文件大小
    if not validate_file_size(file_size):
        max_size_mb = settings.MAX_UPLOAD_SIZE / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "code": "FILE_TOO_LARGE",
                "message": f"文件大小超过限制（最大 {max_size_mb}MB）",
                "details": f"文件大小: {file_size / (1024 * 1024):.2f}MB",
            },
        )

    # 生成唯一文件名并保存
    save_path = generate_unique_filename(original_name)

    try:
        with open(save_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "FILE_UPLOAD_FAILED",
                "message": "文件保存失败",
                "details": str(e),
            },
        )

    return {
        "file_path": str(pathlib.Path(save_path).resolve()),
        "file_name": pathlib.Path(save_path).name,
        "original_name": original_name,
        "file_size": file_size,
        "content_type": upload_file.content_type or "application/octet-stream",
    }


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
