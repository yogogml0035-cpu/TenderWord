from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.api import template_candidates
from backend.api.template_candidates import (
    download_template_candidate,
    select_template_candidate,
)
from backend.models.template_candidates import (
    TemplateCandidateSelectPayload,
    TemplateCandidateSelectRequest,
)
from backend.util.common_util.template_candidates import TemplateDownloadTooLargeError


class FakeTemplateResponse:
    headers = {
        "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "Content-Disposition": "attachment; filename=remote.docx",
    }


@pytest.mark.asyncio
async def test_download_template_candidate_rejects_oversized_content(monkeypatch) -> None:
    monkeypatch.setattr(
        template_candidates,
        "fetch_template_file",
        lambda url: FakeTemplateResponse(),
    )
    monkeypatch.setattr(
        template_candidates,
        "read_template_response_content",
        lambda response: (_ for _ in ()).throw(
            TemplateDownloadTooLargeError("模板文件大小超过限制")
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        await download_template_candidate("https://example.com/template.docx")

    assert exc_info.value.status_code == 413
    assert exc_info.value.detail["error"]["code"] == "TEMPLATE_FILE_TOO_LARGE"


@pytest.mark.asyncio
async def test_select_template_candidate_does_not_persist_oversized_content(
    monkeypatch,
) -> None:
    persisted: list[dict] = []

    monkeypatch.setattr(
        template_candidates,
        "fetch_template_file",
        lambda url: FakeTemplateResponse(),
    )
    monkeypatch.setattr(
        template_candidates,
        "read_template_response_content",
        lambda response: (_ for _ in ()).throw(
            TemplateDownloadTooLargeError("模板文件大小超过限制")
        ),
    )
    monkeypatch.setattr(
        template_candidates,
        "persist_file_bytes",
        lambda **kwargs: persisted.append(kwargs),
    )

    request = TemplateCandidateSelectRequest(
        candidate=TemplateCandidateSelectPayload(
            tendername="测试项目",
            year=2025,
            shener="https://example.com/template.docx",
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        await select_template_candidate(request)

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail["error"]["code"] == "TEMPLATE_SELECT_FAILED"
    assert persisted == []
