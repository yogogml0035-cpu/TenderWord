from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.models import (
    EditTaskRequest,
    FormType,
    GenerateResponse,
    InsertionConfig,
    LLMModel,
    TenderData,
)

from .logging import AgentRunAuditLogger, scrub_sensitive_text

if TYPE_CHECKING:
    from backend.services.conversation_service import ConversationService
    from backend.services.document_service import DocumentService
    from backend.services.task_service import TaskService

CREATE_EDIT_TASK_TOOL = "create_edit_task_tool"
CREATE_REWRITE_TASK_TOOL = "create_rewrite_task_tool"
READ_CURRENT_CONVERSATION_SUMMARY_TOOL = "read_current_conversation_summary_tool"
READ_CURRENT_TASK_PUBLIC_SUMMARY_TOOL = "read_current_task_public_summary_tool"


class CreateRewriteTaskToolInput(BaseModel):
    """受控 rewrite task tool 入参。"""

    conversation_id: str = Field(..., min_length=1, description="当前会话 ID")
    user_prompt: str = Field(..., min_length=1, description="rewrite 指令正文")
    model: LLMModel = Field(
        default=LLMModel.DEEPSEEK,
        description="任务使用的模型提供方",
    )
    rewrite_log_path: str | None = Field(
        default=None,
        description="可选的审计日志路径，由后端受控写入",
    )

    @field_validator("conversation_id", "user_prompt")
    @classmethod
    def _normalize_required_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized

    @field_validator("rewrite_log_path")
    @classmethod
    def _normalize_optional_path(cls, value: str | None) -> str | None:
        normalized = str(value or "").strip()
        return normalized or None

class CreateEditTaskToolInput(BaseModel):
    """受控 edit task tool 入参。"""

    conversation_id: str = Field(..., min_length=1, description="当前会话 ID")
    form_type: FormType = Field(..., description="当前页面 form type")
    model: LLMModel = Field(
        default=LLMModel.DEEPSEEK,
        description="任务使用的模型提供方",
    )
    edit_prompt: str = Field(..., min_length=1, description="edit 指令正文")
    file_path: str = Field(..., min_length=1, description="待修改 Word 文件路径")
    insertion_config: InsertionConfig = Field(..., description="插入锚点配置")
    tender_lx: int = Field(..., description="标的类型编码（0=货物, 1=工程, 2=服务）")
    fund_source_lx: int = Field(..., description="资金性质编码（0=自筹, 1=财政）")
    tender_data_snapshot: TenderData | None = Field(
        default=None,
        description="可选的招标数据快照",
    )

    @field_validator("conversation_id", "edit_prompt", "file_path")
    @classmethod
    def _normalize_required_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized

    @field_validator("fund_source_lx")
    @classmethod
    def _validate_binary_flag(cls, value: int) -> int:
        if value not in (0, 1):
            raise ValueError("字段必须是 0 或 1")
        return int(value)

    @field_validator("tender_lx")
    @classmethod
    def _validate_tender_lx(cls, value: int) -> int:
        if value not in (0, 1, 2):
            raise ValueError("tender_lx 必须是 0、1 或 2")
        return int(value)

    @model_validator(mode="after")
    def _validate_anchor_texts(self) -> "CreateEditTaskToolInput":
        before_text = str(self.insertion_config.before_text or "").strip()
        after_text = str(self.insertion_config.after_text or "").strip()
        if not before_text or not after_text:
            raise ValueError("插入锚点不能为空")
        return self


class ReadCurrentConversationSummaryToolInput(BaseModel):
    conversation_id: str = Field(..., min_length=1, description="当前会话 ID")
    limit: int = Field(default=3, ge=1, le=5, description="返回最近 run 摘要数量")

    @field_validator("conversation_id")
    @classmethod
    def _normalize_conversation_id(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("conversation_id 不能为空")
        return normalized


class ReadCurrentTaskPublicSummaryToolInput(BaseModel):
    conversation_id: str = Field(..., min_length=1, description="当前会话 ID")
    task_id: str = Field(..., min_length=1, description="当前会话内任务 ID")

    @field_validator("conversation_id", "task_id")
    @classmethod
    def _normalize_required_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized


@dataclass(slots=True)
class TaskContextAssistantToolContext:
    document_service: DocumentService | None = None
    conversation_service: ConversationService | None = None
    task_service: TaskService | None = None
    agent_run_audit_logger: AgentRunAuditLogger | None = None


RewriteTaskExecutor = Callable[..., Awaitable[GenerateResponse]]
EditTaskExecutor = Callable[..., Awaitable[GenerateResponse]]
ConversationSummaryExecutor = Callable[..., Awaitable[dict[str, object]]]
TaskPublicSummaryExecutor = Callable[..., Awaitable[dict[str, object]]]


def make_create_rewrite_task_executor(
    context: TaskContextAssistantToolContext | None = None,
) -> RewriteTaskExecutor:
    if context is not None and context.document_service is not None:
        document_service = context.document_service
    else:
        from backend.services.document_service import get_document_service

        document_service = get_document_service()

    async def _execute(
        *,
        conversation_id: str,
        user_prompt: str,
        model: LLMModel = LLMModel.DEEPSEEK,
        rewrite_log_path: str | None = None,
    ) -> GenerateResponse:
        return await document_service.create_rewrite_task(
            conversation_id=conversation_id,
            user_prompt=user_prompt,
            model_provider=model.value,
            rewrite_log_path=rewrite_log_path,
        )

    return _execute


def create_rewrite_task_tool(
    context: TaskContextAssistantToolContext | None = None,
) -> StructuredTool:
    executor = make_create_rewrite_task_executor(context)

    async def _create_rewrite_task(
        conversation_id: str,
        user_prompt: str,
        model: LLMModel = LLMModel.DEEPSEEK,
        rewrite_log_path: str | None = None,
    ) -> dict[str, object]:
        response = await executor(
            conversation_id=conversation_id,
            user_prompt=user_prompt,
            model=model,
            rewrite_log_path=rewrite_log_path,
        )
        return response.model_dump(mode="json")

    return StructuredTool.from_function(
        coroutine=_create_rewrite_task,
        name=CREATE_REWRITE_TASK_TOOL,
        description=(
            "在已有 rewrite history 的当前会话里创建 rewrite 队列任务。"
            "缺少会话上下文时不要调用这个工具，应先追问用户补齐条件。"
        ),
        args_schema=CreateRewriteTaskToolInput,
    )

def make_create_edit_task_executor(
    context: TaskContextAssistantToolContext | None = None,
) -> EditTaskExecutor:
    if context is not None and context.document_service is not None:
        document_service = context.document_service
    else:
        from backend.services.document_service import get_document_service

        document_service = get_document_service()

    async def _execute(
        *,
        conversation_id: str,
        form_type: FormType,
        model: LLMModel = LLMModel.DEEPSEEK,
        edit_prompt: str,
        file_path: str,
        insertion_config: InsertionConfig,
        tender_lx: int,
        fund_source_lx: int,
        tender_data_snapshot: TenderData | None = None,
    ) -> GenerateResponse:
        request = EditTaskRequest(
            conversation_id=conversation_id,
            form_type=form_type,
            model=model,
            edit_prompt=edit_prompt,
            file_path=file_path,
            insertion_config=insertion_config,
            tender_lx=tender_lx,
            fund_source_lx=fund_source_lx,
            tender_data_snapshot=tender_data_snapshot,
        )
        return await document_service.create_edit_task(request)

    return _execute

def create_edit_task_tool(
    context: TaskContextAssistantToolContext | None = None,
) -> StructuredTool:
    executor = make_create_edit_task_executor(context)

    async def _create_edit_task(
        conversation_id: str,
        form_type: FormType,
        model: LLMModel = LLMModel.DEEPSEEK,
        edit_prompt: str = "",
        file_path: str = "",
        insertion_config: InsertionConfig | None = None,
        tender_lx: int = 0,
        fund_source_lx: int = 0,
        tender_data_snapshot: TenderData | None = None,
    ) -> dict[str, object]:
        if insertion_config is None:
            raise ValueError("insertion_config 不能为空")

        response = await executor(
            conversation_id=conversation_id,
            form_type=form_type,
            model=model,
            edit_prompt=edit_prompt,
            file_path=file_path,
            insertion_config=insertion_config,
            tender_lx=tender_lx,
            fund_source_lx=fund_source_lx,
            tender_data_snapshot=tender_data_snapshot,
        )
        return response.model_dump(mode="json")

    return StructuredTool.from_function(
        coroutine=_create_edit_task,
        name=CREATE_EDIT_TASK_TOOL,
        description=(
            "在已有上传 Word 文件、完整锚点和当前页面 edit 上下文时创建 edit 队列任务。"
            "缺少上传文件、锚点或表单上下文时不要调用这个工具，应先追问用户补齐条件。"
        ),
        args_schema=CreateEditTaskToolInput,
    )


def make_read_current_conversation_summary_executor(
    context: TaskContextAssistantToolContext | None = None,
) -> ConversationSummaryExecutor:
    if context is not None and context.conversation_service is not None:
        conversation_service = context.conversation_service
    else:
        from backend.services.conversation_service import get_conversation_service

        conversation_service = get_conversation_service()

    audit_logger = (
        context.agent_run_audit_logger
        if context is not None and context.agent_run_audit_logger is not None
        else AgentRunAuditLogger()
    )

    async def _execute(
        *,
        conversation_id: str,
        limit: int = 3,
    ) -> dict[str, object]:
        latest_rewrite_state = conversation_service.get_latest_rewrite_state(conversation_id)
        return {
            "conversation_id": conversation_id,
            "rewrite_available": conversation_service.has_rewrite_history(conversation_id),
            "latest_rewrite_context": _summarize_rewrite_state(latest_rewrite_state),
            "recent_agent_runs": audit_logger.read_conversation_summaries(
                conversation_id,
                limit=limit,
            ),
        }

    return _execute


def create_read_current_conversation_summary_tool(
    context: TaskContextAssistantToolContext | None = None,
) -> StructuredTool:
    executor = make_read_current_conversation_summary_executor(context)

    async def _read_current_conversation_summary(
        conversation_id: str,
        limit: int = 3,
    ) -> dict[str, object]:
        return await executor(conversation_id=conversation_id, limit=limit)

    return StructuredTool.from_function(
        coroutine=_read_current_conversation_summary,
        name=READ_CURRENT_CONVERSATION_SUMMARY_TOOL,
        description=(
            "读取当前 conversation_id 的受控摘要。"
            "只返回 rewrite 可用性、受控 rewrite 上下文摘要和最近 agent run 结构化摘要，"
            "不会暴露原文、下载路径或隐藏推理。"
        ),
        args_schema=ReadCurrentConversationSummaryToolInput,
    )


def make_read_current_task_public_summary_executor(
    context: TaskContextAssistantToolContext | None = None,
) -> TaskPublicSummaryExecutor:
    if context is not None and context.task_service is not None:
        task_service = context.task_service
    else:
        from backend.services.task_service import get_task_service

        task_service = get_task_service()

    async def _execute(
        *,
        conversation_id: str,
        task_id: str,
    ) -> dict[str, object]:
        response = task_service.get_task(task_id)
        if response is None or response.data is None:
            return {
                "task_id": task_id,
                "available": False,
                "message": "当前任务不存在。",
            }

        task_info = response.data
        if str(task_info.user_session_id or "").strip() != conversation_id:
            return {
                "task_id": task_id,
                "available": False,
                "message": "当前任务不属于该会话。",
            }

        result_payload = task_info.result if isinstance(task_info.result, dict) else {}
        summary: dict[str, Any] = {
            "task_id": task_info.task_id,
            "available": True,
            "task_kind": task_info.task_kind.value,
            "status": task_info.status.value,
            "queue_position": task_info.queue_position,
            "waiting_count": task_info.waiting_count,
            "progress": {
                "progress_text": task_info.progress.progress_text,
                "progress_percent": task_info.progress.progress_percent,
                "current_node_display": task_info.progress.current_node_display,
            },
            "has_result": task_info.result is not None,
            "download_ready": bool(result_payload.get("download_url")),
        }

        if task_info.current_running_progress is not None:
            summary["current_running_progress"] = {
                "progress_text": task_info.current_running_progress.progress_text,
                "progress_percent": task_info.current_running_progress.progress_percent,
                "current_node_display": task_info.current_running_progress.current_node_display,
            }

        sanitized_error = scrub_sensitive_text(task_info.error)
        if sanitized_error:
            summary["error"] = sanitized_error

        return summary

    return _execute


def create_read_current_task_public_summary_tool(
    context: TaskContextAssistantToolContext | None = None,
) -> StructuredTool:
    executor = make_read_current_task_public_summary_executor(context)

    async def _read_current_task_public_summary(
        conversation_id: str,
        task_id: str,
    ) -> dict[str, object]:
        return await executor(conversation_id=conversation_id, task_id=task_id)

    return StructuredTool.from_function(
        coroutine=_read_current_task_public_summary,
        name=READ_CURRENT_TASK_PUBLIC_SUMMARY_TOOL,
        description=(
            "读取当前 conversation_id 内某个任务的公共状态摘要。"
            "只返回 task 状态、排队信息和进度概览，不返回输出文件路径或完整结果。"
        ),
        args_schema=ReadCurrentTaskPublicSummaryToolInput,
    )


def _summarize_rewrite_state(
    rewrite_state: dict[str, Any] | None,
) -> dict[str, object] | None:
    if not isinstance(rewrite_state, dict):
        return None

    return {
        "has_prepared_doc": bool(str(rewrite_state.get("prepared_doc_path") or "").strip()),
        "has_polished_text": bool(str(rewrite_state.get("polished_text") or "").strip()),
        "has_comment_metadata": bool(
            rewrite_state.get("generated_comments_path")
            or rewrite_state.get("comment_writeback_summary")
        ),
        "has_style_writeback_summary": bool(
            str(rewrite_state.get("style_writeback_summary") or "").strip()
        ),
    }


__all__ = [
    "CREATE_EDIT_TASK_TOOL",
    "CREATE_REWRITE_TASK_TOOL",
    "CreateEditTaskToolInput",
    "CreateRewriteTaskToolInput",
    "ConversationSummaryExecutor",
    "EditTaskExecutor",
    "READ_CURRENT_CONVERSATION_SUMMARY_TOOL",
    "READ_CURRENT_TASK_PUBLIC_SUMMARY_TOOL",
    "ReadCurrentConversationSummaryToolInput",
    "ReadCurrentTaskPublicSummaryToolInput",
    "RewriteTaskExecutor",
    "TaskContextAssistantToolContext",
    "TaskPublicSummaryExecutor",
    "create_edit_task_tool",
    "create_read_current_conversation_summary_tool",
    "create_read_current_task_public_summary_tool",
    "create_rewrite_task_tool",
    "make_create_edit_task_executor",
    "make_create_rewrite_task_executor",
    "make_read_current_conversation_summary_executor",
    "make_read_current_task_public_summary_executor",
]
