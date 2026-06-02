from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Awaitable, Callable

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, field_validator

from backend.models import GenerateResponse, LLMModel

if TYPE_CHECKING:
    from backend.services.document_service import DocumentService

CREATE_REWRITE_TASK_TOOL = "create_rewrite_task_tool"


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


@dataclass(slots=True)
class TaskContextAssistantToolContext:
    document_service: DocumentService


RewriteTaskExecutor = Callable[..., Awaitable[GenerateResponse]]


def make_create_rewrite_task_executor(
    context: TaskContextAssistantToolContext | None = None,
) -> RewriteTaskExecutor:
    if context is not None:
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


__all__ = [
    "CREATE_REWRITE_TASK_TOOL",
    "CreateRewriteTaskToolInput",
    "RewriteTaskExecutor",
    "TaskContextAssistantToolContext",
    "create_rewrite_task_tool",
    "make_create_rewrite_task_executor",
]
