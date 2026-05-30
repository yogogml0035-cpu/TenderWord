from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.api import comment_supplement as comment_supplement_api
from backend.models import CommentSupplementRequest, GenerateResponse, LLMModel, TaskKind

@pytest.mark.asyncio
async def test_create_comment_supplement_task_returns_created_response(monkeypatch) -> None:
    class FakeDocumentService:
        async def create_comment_supplement_task(self, request):
            assert request.conversation_id == "conv-1"
            return GenerateResponse(
                success=True,
                task_id="task-1",
                task_kind=TaskKind.COMMENT_SUPPLEMENT,
                message="任务已创建",
            )

    monkeypatch.setattr(
        comment_supplement_api,
        "get_document_service",
        lambda: FakeDocumentService(),
    )

    response = await comment_supplement_api.create_comment_supplement_task(
        CommentSupplementRequest(
            conversation_id="conv-1",
            source_file="/tmp/generated.docx",
            model=LLMModel.DEEPSEEK,
        )
    )

    assert response.success is True
    assert response.task_kind == TaskKind.COMMENT_SUPPLEMENT

@pytest.mark.asyncio
async def test_create_comment_supplement_task_failure_returns_400(monkeypatch) -> None:
    class FakeDocumentService:
        async def create_comment_supplement_task(self, request):
            return GenerateResponse(
                success=False,
                task_id="task-1",
                message="当前会话没有可补充批注的文档，请先完成一次生成",
                error="COMMENT_SUPPLEMENT_NO_DOCUMENT",
            )

    monkeypatch.setattr(
        comment_supplement_api,
        "get_document_service",
        lambda: FakeDocumentService(),
    )

    with pytest.raises(HTTPException) as exc_info:
        await comment_supplement_api.create_comment_supplement_task(
            CommentSupplementRequest(conversation_id="conv-1", source_file="/tmp/missing.docx")
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error"]["code"] == "COMMENT_SUPPLEMENT_NO_DOCUMENT"
