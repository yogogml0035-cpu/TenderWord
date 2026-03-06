"""
SSE 事件模型

定义 Server-Sent Events (SSE) 相关的 Pydantic 模型，用于实时推送。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field


class SSEEventType(str, Enum):
    """
    SSE 事件类型枚举
    """

    LOG = "log"  # 普通日志
    LLM = "llm"  # LLM 输出
    PROGRESS = "progress"  # 进度更新
    NODE_START = "node_start"  # 节点开始
    NODE_COMPLETE = "node_complete"  # 节点完成
    DONE = "done"  # 任务完成
    ERROR = "error"  # 错误
    HEARTBEAT = "heartbeat"  # 心跳


class SSEEvent(BaseModel):
    """
    SSE 事件模型

    用于 Server-Sent Events 推送的标准事件格式

    Attributes:
        event: 事件类型（log | llm | progress | done | error）
        data: 事件数据（字符串或字典）
        id: 事件ID（可选）
        retry: 重试时间（可选，毫秒）
    """

    event: SSEEventType = Field(..., description="事件类型")
    data: Union[str, Dict[str, Any]] = Field(..., description="事件数据")
    id: Optional[str] = Field(default=None, description="事件ID")
    retry: Optional[int] = Field(default=None, description="重试时间（毫秒）")
    timestamp: datetime = Field(default_factory=datetime.now, description="事件时间戳")

    def to_sse_format(self) -> str:
        """
        转换为 SSE 标准格式

        Returns:
            SSE 格式的字符串
        """
        lines = []

        if self.id:
            lines.append(f"id: {self.id}")

        lines.append(f"event: {self.event.value}")

        if isinstance(self.data, dict):
            import json

            data_str = json.dumps(self.data, ensure_ascii=False)
        else:
            data_str = str(self.data)

        # SSE 数据可以有多行，每行以 data: 开头
        for line in data_str.split("\n"):
            lines.append(f"data: {line}")

        if self.retry:
            lines.append(f"retry: {self.retry}")

        lines.append("")  # 空行表示事件结束

        return "\n".join(lines)


class LogEventData(BaseModel):
    """
    日志事件数据模型
    """

    level: str = Field(default="info", description="日志级别")
    message: str = Field(..., description="日志消息")
    node: Optional[str] = Field(default=None, description="当前节点")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(), description="时间戳"
    )


class LLMEventData(BaseModel):
    """
    LLM 输出事件数据模型
    """

    content: str = Field(..., description="LLM 输出内容")
    content_mode: str = Field(default="snapshot", description="内容语义：snapshot | chunk")
    node: Optional[str] = Field(default=None, description="当前节点")
    model: Optional[str] = Field(default=None, description="使用的模型")
    is_complete: bool = Field(default=False, description="是否完成")
    task_id: Optional[str] = Field(default=None, description="任务ID")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(), description="时间戳"
    )


class ProgressEventData(BaseModel):
    """
    进度事件数据模型
    """

    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态")
    completed_count: int = Field(default=0, description="已完成节点数")
    total_nodes: int = Field(default=7, description="总节点数")
    progress_text: str = Field(default="0/7", description="进度文本")
    progress_percent: float = Field(default=0.0, description="进度百分比")
    current_node: Optional[str] = Field(default=None, description="当前节点")
    current_node_display: Optional[str] = Field(
        default=None, description="当前节点显示名"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(), description="时间戳"
    )


class DoneEventData(BaseModel):
    """
    完成事件数据模型
    """

    task_id: str = Field(..., description="任务ID")
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    output_file: Optional[str] = Field(default=None, description="输出文件路径")
    download_url: Optional[str] = Field(default=None, description="下载链接")
    processing_time: Optional[float] = Field(default=None, description="处理时间（秒）")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(), description="时间戳"
    )


class ErrorEventData(BaseModel):
    """
    错误事件数据模型
    """

    task_id: str = Field(..., description="任务ID")
    error: str = Field(..., description="错误信息")
    node: Optional[str] = Field(default=None, description="发生错误的节点")
    is_fatal: bool = Field(default=True, description="是否致命错误")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(), description="时间戳"
    )


class HeartbeatEventData(BaseModel):
    """
    心跳事件数据模型
    """

    task_id: str = Field(..., description="任务ID")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(), description="时间戳"
    )
