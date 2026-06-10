"""
SSE 事件模型

定义 Server-Sent Events (SSE) 相关的 Pydantic 模型，用于实时推送。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field
from backend.models.task import TaskKind


class SSEEventType(str, Enum):
    """
    SSE 事件类型枚举
    """

    LOG = "log"  # 普通日志
    LLM = "llm"  # LLM 输出
    PROGRESS = "progress"  # 进度更新
    NODE_START = "node_start"  # 节点开始
    NODE_COMPLETE = "node_complete"  # 节点完成
    AGENT_STEP = "agent_step"  # 智能体步骤
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
    task_kind: TaskKind = Field(default=TaskKind.GENERATE, description="任务类别")
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


class AgentStepFindingData(BaseModel):
    """
    智能体审核意见数据模型
    """

    evidence: str = Field(..., description="审核依据")
    fix_hint: str = Field(..., description="修复建议")


class ContentAgentRoundData(BaseModel):
    """参数生成智能体单阶段摘要。"""

    round: int = Field(..., ge=1, description="轮次")
    phase: Literal["draft", "audit", "revision"] = Field(..., description="阶段")
    label: str = Field(default="", description="阶段展示名")
    summary: str = Field(default="", description="阶段摘要")
    issue_count: int = Field(default=0, ge=0, description="问题数")
    fix_count: int = Field(default=0, ge=0, description="修复数")
    content: Optional[str] = Field(default=None, description="原始输出")
    findings: List[AgentStepFindingData] = Field(default_factory=list, description="阶段问题")


class ContentAgentFinalData(BaseModel):
    """参数生成智能体最终结果摘要。"""

    summary: str = Field(default="", description="最终摘要")
    revision_rounds: int = Field(default=0, ge=0, description="修复轮次")
    final_chars: int = Field(default=0, ge=0, description="最终正文字符数")
    issue_count: int = Field(default=0, ge=0, description="最终问题数")
    content: Optional[str] = Field(default=None, description="最终正文原文")


class ContentAgentStepData(BaseModel):
    """参数生成智能体结构化过程数据。"""

    phase: Literal["draft", "audit", "revision", "final"] = Field(..., description="过程阶段")
    summary: str = Field(default="", description="当前阶段摘要")
    rounds: List[ContentAgentRoundData] = Field(default_factory=list, description="阶段摘要列表")
    highlights: List[AgentStepFindingData] = Field(default_factory=list, description="当前阶段问题")
    final_result: Optional[ContentAgentFinalData] = Field(default=None, description="最终结果")


class CommentAgentHighlightData(BaseModel):
    """批注生成智能体用户可见重点项。"""

    index: int = Field(..., ge=1, description="批注序号")
    status: str = Field(..., description="中文业务状态")
    reason: str = Field(default="", description="中文原因")
    original_reference_text: str = Field(default="", description="原始锚点")
    reference_text: str = Field(default="", description="当前锚点")
    candidate_fragments: List[str] = Field(default_factory=list, description="候选片段")


class CommentAgentRoundData(BaseModel):
    """批注生成智能体单轮校验摘要。"""

    round: int = Field(..., ge=0, description="校验轮次；0 表示最终静默复校验")
    label: str = Field(default="", description="轮次展示名")
    passed: int = Field(default=0, ge=0, description="通过数")
    failed: int = Field(default=0, ge=0, description="失败数")
    skipped: int = Field(default=0, ge=0, description="跳过数")
    highlights: List[CommentAgentHighlightData] = Field(default_factory=list, description="重点项")


class CommentAgentWritebackData(BaseModel):
    """批注生成智能体 Word 写入摘要。"""

    attempted: int = Field(default=0, ge=0, description="尝试写入数")
    added: int = Field(default=0, ge=0, description="成功写入数")
    failed: int = Field(default=0, ge=0, description="失败数")
    skipped: int = Field(default=0, ge=0, description="跳过数")
    issues: List[CommentAgentHighlightData] = Field(default_factory=list, description="写入问题")


class CommentAgentStepData(BaseModel):
    """批注生成智能体结构化过程数据。"""

    phase: Literal["validation_round", "final"] = Field(..., description="过程阶段")
    notice: str = Field(default="", description="用户可见提示")
    rounds: List[CommentAgentRoundData] = Field(default_factory=list, description="校验轮次")
    highlights: List[CommentAgentHighlightData] = Field(default_factory=list, description="当前重点项")
    final_validation: Optional[CommentAgentRoundData] = Field(default=None, description="最终静默复校验")
    writeback: Optional[CommentAgentWritebackData] = Field(default=None, description="Word 写入结果")


class AgentStepEventData(BaseModel):
    """
    智能体步骤事件数据模型
    """

    task_id: str = Field(..., description="任务ID")
    task_kind: TaskKind = Field(default=TaskKind.GENERATE, description="任务类别")
    step_type: str = Field(..., description="步骤/流类型")
    round: int = Field(..., ge=1, description="审核/修复轮次")
    node: str = Field(..., description="当前智能体节点")
    is_complete: bool = Field(default=False, description="是否完成")
    content: Optional[str] = Field(default=None, description="正文快照")
    findings: List[AgentStepFindingData] = Field(
        default_factory=list,
        description="审核意见列表",
    )
    content_agent: Optional[ContentAgentStepData] = Field(
        default=None,
        description="参数生成智能体结构化过程数据",
    )
    comment_agent: Optional[CommentAgentStepData] = Field(
        default=None,
        description="批注生成智能体结构化过程数据",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(), description="时间戳"
    )


class StyleWritebackSummaryData(BaseModel):
    """样式回填摘要。"""

    summary: str = Field(default="", description="摘要文本")
    extracted: int = Field(default=0, description="抽取片段数")
    attempted: int = Field(default=0, description="尝试回填数")
    applied: int = Field(default=0, description="成功回填数")
    skipped: int = Field(default=0, description="跳过数")
    failed: int = Field(default=0, description="失败数")
    applied_by_style: Dict[str, int] = Field(default_factory=dict, description="按样式命中数")
    skipped_by_reason: Dict[str, int] = Field(default_factory=dict, description="按原因跳过数")


class CommentWritebackSummaryData(BaseModel):
    """AI 批注写回摘要。"""

    summary: str = Field(default="", description="摘要文本")
    generated: int = Field(default=0, description="生成批注数")
    added: int = Field(default=0, description="成功写入数")
    failed: int = Field(default=0, description="失败数")
    skipped: int = Field(default=0, description="跳过数")
    warning: bool = Field(default=False, description="是否存在降级 warning")


class DoneEventData(BaseModel):
    """
    完成事件数据模型
    """

    task_id: str = Field(..., description="任务ID")
    task_kind: TaskKind = Field(default=TaskKind.GENERATE, description="任务类别")
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    output_file: Optional[str] = Field(default=None, description="输出文件路径")
    file_name: Optional[str] = Field(default=None, description="输出文件名")
    download_url: Optional[str] = Field(default=None, description="下载链接")
    processing_time: Optional[float] = Field(default=None, description="处理时间（秒）")
    style_writeback: Optional[StyleWritebackSummaryData] = Field(
        default=None,
        description="样式回填摘要",
    )
    comment_writeback: Optional[CommentWritebackSummaryData] = Field(
        default=None,
        description="AI 批注写回摘要",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(), description="时间戳"
    )


class ErrorEventData(BaseModel):
    """
    错误事件数据模型
    """

    task_id: str = Field(..., description="任务ID")
    task_kind: TaskKind = Field(default=TaskKind.GENERATE, description="任务类别")
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
