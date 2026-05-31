"""
Backend 模型模块

包含 API 请求/响应/状态的所有 Pydantic 模型定义。
使用 Pydantic v2 语法。
"""

# 招标数据模型
from .tender import (
    TenderData,
    TenderFormConfig,
    TenderType,
)

# 任务相关模型
from .task import (
    NodeStatus,
    TaskCancelResponse,
    TaskInfo,
    TaskKind,
    TaskListResponse,
    TaskProgress,
    TaskResponse,
    TaskStatus,
)

# 生成请求/响应模型
from .generate import (
    CommentGenerationMode,
    CommentSupplementRequest,
    EditTaskRequest,
    FileRequirement,
    FormRequirementsResponse,
    FormType,
    GenerateFilePaths,
    GenerationMode,
    GenerationStyle,
    GenerateRequest,
    GenerateResponse,
    GenerateResult,
    LLMModel,
)

# 文件上传模型
from .upload import (
    FileDeleteResponse,
    FileListResponse,
    UploadedFileInfo,
    UploadResponse,
    UploadSingleResponse,
)

# SSE 事件模型
from .sse import (
    AgentStepEventData,
    AgentStepFindingData,
    CommentAgentHighlightData,
    CommentAgentRoundData,
    CommentAgentStepData,
    CommentAgentWritebackData,
    CommentWritebackSummaryData,
    ContentAgentFinalData,
    ContentAgentRoundData,
    ContentAgentStepData,
    DoneEventData,
    ErrorEventData,
    HeartbeatEventData,
    LLMEventData,
    LogEventData,
    ProgressEventData,
    SSEEvent,
    SSEEventType,
)

# 通用响应模型
from .common import (
    ErrorResponse,
    SuccessResponse,
)
from .template_candidates import (
    TemplateCandidate,
    TemplateCandidateListData,
    TemplateCandidateListResponse,
    TemplateCandidateRanking,
    TemplateCandidateSelectPayload,
    TemplateCandidateSelectRequest,
    TemplateSelectedFile,
    TemplateSelectData,
    TemplateSelectResponse,
)

__all__ = [
    # 通用响应
    "ErrorResponse",
    "SuccessResponse",
    "TemplateCandidate",
    "TemplateCandidateListData",
    "TemplateCandidateListResponse",
    "TemplateCandidateRanking",
    "TemplateCandidateSelectPayload",
    "TemplateCandidateSelectRequest",
    "TemplateSelectedFile",
    "TemplateSelectData",
    "TemplateSelectResponse",
    
    # 招标数据
    "TenderData",
    "TenderFormConfig",
    "TenderType",
    
    # 任务相关
    "TaskStatus",
    "TaskKind",
    "NodeStatus",
    "TaskProgress",
    "TaskInfo",
    "TaskResponse",
    "TaskListResponse",
    "TaskCancelResponse",
    
    # 生成相关
    "LLMModel",
    "FormType",
    "CommentGenerationMode",
    "GenerationMode",
    "GenerationStyle",
    "CommentSupplementRequest",
    "EditTaskRequest",
    "GenerateFilePaths",
    "GenerateRequest",
    "GenerateResponse",
    "GenerateResult",
    "FileRequirement",
    "FormRequirementsResponse",
    
    # 文件上传
    "UploadedFileInfo",
    "UploadResponse",
    "UploadSingleResponse",
    "FileDeleteResponse",
    "FileListResponse",
    
    # SSE 事件
    "SSEEventType",
    "SSEEvent",
    "AgentStepEventData",
    "AgentStepFindingData",
    "ContentAgentRoundData",
    "ContentAgentFinalData",
    "ContentAgentStepData",
    "CommentAgentHighlightData",
    "CommentAgentRoundData",
    "CommentAgentStepData",
    "CommentAgentWritebackData",
    "CommentWritebackSummaryData",
    "LogEventData",
    "LLMEventData",
    "ProgressEventData",
    "DoneEventData",
    "ErrorEventData",
    "HeartbeatEventData",
]
