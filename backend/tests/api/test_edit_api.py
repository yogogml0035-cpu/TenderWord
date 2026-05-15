from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.api import edit
from backend.models.generate import GenerateResponse


@pytest.mark.asyncio
async def test_create_edit_task_returns_400_for_invalid_upload_path(monkeypatch) -> None:
    class FakeDocumentService:
        async def create_edit_task(self, request):
            return GenerateResponse(
                success=False,
                task_id="task-invalid-edit-path",
                message="file_path 文件路径无效：文件路径必须位于上传目录",
                error="UPLOAD_PATH_OUT_OF_SCOPE",
            )

    monkeypatch.setattr(edit, "get_document_service", lambda: FakeDocumentService())

    with pytest.raises(HTTPException) as exc_info:
        await edit.create_edit_task(
            SimpleNamespace(
                form_type="xjcg_tender",
                model="deepseek",
                conversation_id="conv-1",
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["success"] is False
    assert exc_info.value.detail["error"]["code"] == "UPLOAD_PATH_OUT_OF_SCOPE"
    assert "file_path" in exc_info.value.detail["error"]["message"]
