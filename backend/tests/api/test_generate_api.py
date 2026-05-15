from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.api import generate
from backend.models.generate import GenerateResponse
from backend.api.generate import get_generate_task


@pytest.mark.asyncio
async def test_get_generate_task_missing_task_returns_404():
    with pytest.raises(HTTPException) as exc_info:
        await get_generate_task("missing-task")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["error"]["code"] == "TASK_NOT_FOUND"
    assert exc_info.value.detail["error"]["task_id"] == "missing-task"


@pytest.mark.asyncio
async def test_create_generate_task_returns_400_for_invalid_upload_path(
    monkeypatch,
) -> None:
    class FakeDocumentService:
        def create_task(self, request):
            return GenerateResponse(
                success=False,
                task_id="task-invalid-path",
                message="file_paths.template 文件路径无效：文件路径必须位于上传目录",
                error="UPLOAD_PATH_OUT_OF_SCOPE",
            )

    monkeypatch.setattr(generate, "get_document_service", lambda: FakeDocumentService())

    with pytest.raises(HTTPException) as exc_info:
        await generate.create_generate_task(
            SimpleNamespace(form_type="xjcg_tender", model="deepseek")
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["success"] is False
    assert exc_info.value.detail["error"]["code"] == "UPLOAD_PATH_OUT_OF_SCOPE"
    assert "file_paths.template" in exc_info.value.detail["error"]["message"]
