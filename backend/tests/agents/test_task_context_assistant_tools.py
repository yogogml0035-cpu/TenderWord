from __future__ import annotations

import pytest

from backend.agents.task_context_assistant import (
    TaskContextAssistantToolContext,
    create_rewrite_task_tool,
)
from backend.models import GenerateResponse, TaskKind, TaskStatus


@pytest.mark.asyncio
async def test_create_rewrite_task_tool_reuses_document_service() -> None:
    captured: dict[str, object] = {}

    class FakeDocumentService:
        async def create_rewrite_task(self, **kwargs) -> GenerateResponse:
            captured.update(kwargs)
            return GenerateResponse(
                success=True,
                task_id="rewrite-task-42",
                message="queued",
                task_kind=TaskKind.REWRITE,
                status=TaskStatus.QUEUED,
                queue_position=0,
                waiting_count=0,
            )

    tool = create_rewrite_task_tool(
        TaskContextAssistantToolContext(document_service=FakeDocumentService())
    )

    result = await tool.ainvoke(
        {
            "conversation_id": "conv-42",
            "user_prompt": "改写第三包技术参数",
            "model": "deepseek",
            "rewrite_log_path": "backend/logs/rewrite-task-42.jsonl",
        }
    )

    assert tool.name == "create_rewrite_task_tool"
    assert captured == {
        "conversation_id": "conv-42",
        "user_prompt": "改写第三包技术参数",
        "model_provider": "deepseek",
        "rewrite_log_path": "backend/logs/rewrite-task-42.jsonl",
    }
    assert result["task_id"] == "rewrite-task-42"
    assert result["task_kind"] == "rewrite"
