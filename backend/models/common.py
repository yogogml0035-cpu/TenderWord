"""通用响应模型.

定义跨模块共享的响应模型，避免代码重复。
"""

from datetime import datetime, timezone
from typing import Any, Dict

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """通用错误响应模型.

    用于所有 API 端点的错误响应格式。

    Attributes:
        success: 固定为 False
        error: 错误详情字典，包含 code, message, details 等字段
        timestamp: 响应时间戳（ISO 8601 格式）
    """

    success: bool = Field(default=False, description="请求是否成功")
    error: Dict[str, Any] = Field(..., description="错误详情")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="响应时间戳",
    )


class SuccessResponse(BaseModel):
    """通用成功响应模型.

    用于简单操作的成功响应格式。

    Attributes:
        success: 固定为 True
        message: 操作结果描述
        timestamp: 响应时间戳（ISO 8601 格式）
    """

    success: bool = Field(default=True, description="请求是否成功")
    message: str = Field(default="操作成功", description="操作结果描述")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="响应时间戳",
    )
