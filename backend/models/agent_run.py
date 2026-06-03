"""Agent run 流式协议模型。"""

from __future__ import annotations

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .generate import FormType, InsertionConfig, LLMModel
from .tender import TenderData
from .task import TaskKind, TaskStatus


class AgentSkill(str, Enum):
    """支持的 agent skill。"""

    REWRITE = "rewrite"


class AgentRunUploadedFile(BaseModel):
    """受控上传文件摘要。"""

    model_config = ConfigDict(extra="forbid")

    file_path: str = Field(..., min_length=1, description="上传文件路径")
    file_name: Optional[str] = Field(default=None, description="文件名")

    @field_validator("file_path")
    @classmethod
    def _normalize_file_path(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("file_path 不能为空")
        return normalized


class AgentRunContextSnapshot(BaseModel):
    """agent run 可见的最小上下文快照。"""

    model_config = ConfigDict(extra="forbid")

    rewrite_available: bool = Field(
        default=False,
        description="当前会话是否已有可改写文档上下文",
    )
    uploaded_files: List[AgentRunUploadedFile] = Field(
        default_factory=list,
        description="当前会话可见的上传文件摘要",
    )
    rewrite_context: Optional["AgentRunRewriteContextSnapshot"] = Field(
        default=None,
        description="上传文件 rewrite 任务创建所需的受控上下文摘要",
    )

class AgentRunRewriteContextSnapshot(BaseModel):
    """受控上传文件 rewrite 任务上下文。"""

    model_config = ConfigDict(extra="forbid")

    form_type: Optional[FormType] = Field(default=None, description="当前页面 form type")
    insertion_config: Optional[InsertionConfig] = Field(
        default=None,
        description="当前页面插入锚点配置",
    )
    tender_lx: Optional[int] = Field(default=None, description="标的类型编码")
    fund_source_lx: Optional[int] = Field(default=None, description="资金性质编码")
    tender_data_snapshot: Optional[TenderData] = Field(
        default=None,
        description="当前页面招标数据快照摘要",
    )

    @field_validator("fund_source_lx")
    @classmethod
    def _validate_binary_flag(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return None
        if value not in (0, 1):
            raise ValueError("字段必须是 0 或 1")
        return int(value)

    @field_validator("tender_lx")
    @classmethod
    def _validate_tender_lx(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return None
        if value not in (0, 1, 2):
            raise ValueError("tender_lx 必须是 0、1 或 2")
        return int(value)


class AgentRunStreamRequest(BaseModel):
    """agent run 流式请求。"""

    model_config = ConfigDict(extra="forbid")

    conversation_id: str = Field(..., min_length=1, description="会话 ID")
    message: str = Field(..., min_length=1, description="用户本轮消息")
    model: LLMModel = Field(default=LLMModel.DEEPSEEK, description="模型提供方")
    selected_skills: List[AgentSkill] = Field(
        default_factory=list,
        description="显式选择的 skill，按优先级排序",
    )
    context_snapshot: AgentRunContextSnapshot = Field(..., description="受控上下文快照")

    @field_validator("conversation_id", "message")
    @classmethod
    def _normalize_required_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized

    @field_validator("selected_skills")
    @classmethod
    def _dedupe_selected_skills(cls, value: List[AgentSkill]) -> List[AgentSkill]:
        seen: set[AgentSkill] = set()
        deduped: List[AgentSkill] = []
        for item in value:
            if item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        return deduped


class AgentRunStartedEventData(BaseModel):
    """agent run 启动事件。"""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(..., description="本次 agent run ID")
    conversation_id: str = Field(..., description="会话 ID")
    model: LLMModel = Field(..., description="模型提供方")
    runtime: Literal["fake"] = Field(default="fake", description="当前运行时类型")
    selected_skills: List[AgentSkill] = Field(default_factory=list, description="显式 skill")


class AgentThinkingStageEventData(BaseModel):
    """阶段化思考摘要事件。"""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(..., description="本次 agent run ID")
    stage: Literal["understand", "guard", "tool", "summary"] = Field(
        ...,
        description="阶段键",
    )
    label: str = Field(..., description="阶段展示名")
    status: Literal["in_progress", "completed"] = Field(..., description="阶段状态")
    summary: str = Field(..., description="用户可见摘要")
    selected_skill: Optional[AgentSkill] = Field(default=None, description="关联 skill")
    guard_result: Optional[Literal["passed", "needs_input"]] = Field(
        default=None,
        description="guard 结果",
    )
    tool_name: Optional[str] = Field(default=None, description="关联工具名")


class AgentToolCallEventData(BaseModel):
    """工具调用摘要事件。"""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(..., description="本次 agent run ID")
    tool_name: str = Field(..., description="工具名")
    status: Literal["completed"] = Field(default="completed", description="调用状态")
    summary: str = Field(..., description="调用摘要")
    task_kind: TaskKind = Field(..., description="即将创建的任务类型")


class AgentTaskAcceptedEventData(BaseModel):
    """任务创建成功事件。"""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(..., description="本次 agent run ID")
    task_id: str = Field(..., description="任务 ID")
    task_kind: TaskKind = Field(..., description="任务类型")
    status: TaskStatus = Field(default=TaskStatus.QUEUED, description="任务状态")
    queue_position: int = Field(default=0, description="队列位置")
    waiting_count: int = Field(default=0, description="前方等待任务数")


class AgentNeedsInputEventData(BaseModel):
    """缺条件追问事件。"""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(..., description="本次 agent run ID")
    message: str = Field(..., description="需要用户补充的信息")
    selected_skill: Optional[AgentSkill] = Field(default=None, description="关联 skill")
    missing_requirements: List[str] = Field(
        default_factory=list,
        description="缺失条件键",
    )


class AgentRunDoneEventData(BaseModel):
    """agent run 正常终态事件。"""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(..., description="本次 agent run ID")
    message: str = Field(..., description="终态摘要")
    task_id: Optional[str] = Field(default=None, description="关联任务 ID")
    selected_skill: Optional[AgentSkill] = Field(default=None, description="关联 skill")


class AgentRunErrorEventData(BaseModel):
    """agent run 错误终态事件。"""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(..., description="本次 agent run ID")
    code: str = Field(..., description="错误码")
    message: str = Field(..., description="错误信息")
