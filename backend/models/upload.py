"""
文件上传响应模型

定义文件上传相关的 Pydantic 模型，用于 API 请求和响应。
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class UploadedFileInfo(BaseModel):
    """
    已上传文件信息模型
    """

    original_filename: str = Field(..., description="原始文件名")
    saved_filename: str = Field(..., description="保存后的文件名")
    file_path: str = Field(..., description="文件保存路径")
    file_size: int = Field(..., description="文件大小（字节）")
    file_type: str = Field(..., description="文件 MIME 类型")
    uploaded_at: datetime = Field(default_factory=datetime.now, description="上传时间")


class UploadResponse(BaseModel):
    """
    文件上传响应模型

    Attributes:
        success: 是否上传成功
        message: 消息说明
        files: 上传成功的文件列表
        failed_files: 上传失败的文件列表
    """

    success: bool = Field(..., description="是否上传成功")
    message: str = Field(default="", description="消息说明")
    files: List[UploadedFileInfo] = Field(
        default_factory=list, description="上传成功的文件列表"
    )
    failed_files: List[dict] = Field(
        default_factory=list, description="上传失败的文件列表"
    )


class UploadSingleResponse(BaseModel):
    """
    单文件上传响应模型

    用于单次单文件上传的响应
    """

    success: bool = Field(..., description="是否上传成功")
    message: str = Field(default="", description="消息说明")
    file: Optional[UploadedFileInfo] = Field(
        default=None, description="上传成功的文件信息"
    )
    error: Optional[str] = Field(default=None, description="错误信息（失败时）")


class FileDeleteResponse(BaseModel):
    """
    文件删除响应模型
    """

    success: bool = Field(..., description="是否删除成功")
    file_path: str = Field(..., description="被删除的文件路径")
    message: str = Field(default="", description="消息说明")


class FileListResponse(BaseModel):
    """
    文件列表响应模型
    """

    success: bool = Field(..., description="是否成功")
    total: int = Field(default=0, description="文件总数")
    files: List[UploadedFileInfo] = Field(default_factory=list, description="文件列表")
