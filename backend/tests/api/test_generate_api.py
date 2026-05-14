import pytest
from fastapi import HTTPException

from backend.api.generate import get_generate_task


@pytest.mark.asyncio
async def test_get_generate_task_missing_task_returns_404():
    with pytest.raises(HTTPException) as exc_info:
        await get_generate_task("missing-task")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["error"]["code"] == "TASK_NOT_FOUND"
    assert exc_info.value.detail["error"]["task_id"] == "missing-task"
