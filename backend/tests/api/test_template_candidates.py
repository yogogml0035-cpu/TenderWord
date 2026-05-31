from __future__ import annotations

from types import SimpleNamespace

import pytest
import requests
from fastapi import HTTPException

from backend.api import template_candidates as template_candidates_api
from backend.models.template_candidates import (
    TemplateCandidateSelectPayload,
    TemplateCandidateSelectRequest,
)


def build_select_request(shener: str | None = "http://10.11.1.224/template.docx") -> TemplateCandidateSelectRequest:
    return TemplateCandidateSelectRequest(
        candidate=TemplateCandidateSelectPayload(
            tendername="测试模板",
            year=2026,
            fsg=None,
            shener=shener,
        )
    )


@pytest.mark.asyncio
async def test_select_template_candidate_returns_single_selected_file(monkeypatch) -> None:
    fetch_calls: list[str] = []
    persist_calls: list[dict[str, object]] = []

    def fake_fetch_template_file(file_url: str):
        fetch_calls.append(file_url)
        return SimpleNamespace(
            content=b"template-bytes",
            headers={
                "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            },
        )

    def fake_persist_file_bytes(**kwargs):
        persist_calls.append(kwargs)
        return {
            "file_path": "D:/UploadFiles/selected.docx",
            "file_name": "selected.docx",
            "original_name": kwargs["original_name"],
            "file_size": len(kwargs["content"]),
        }

    monkeypatch.setattr(
        template_candidates_api,
        "fetch_template_file",
        fake_fetch_template_file,
    )
    monkeypatch.setattr(
        template_candidates_api,
        "persist_file_bytes",
        fake_persist_file_bytes,
    )

    response = await template_candidates_api.select_template_candidate(build_select_request())

    assert fetch_calls == ["http://10.11.1.224/template.docx"]
    assert len(persist_calls) == 1
    assert persist_calls[0]["original_name"] == "测试模板-模板.docx"
    assert response.success is True
    assert response.data.selected_file.file_path == "D:/UploadFiles/selected.docx"
    assert response.data.selected_file.original_name == "测试模板-模板.docx"
    response_data = response.model_dump()["data"]
    assert "selected_file" in response_data
    assert "selected_files" not in response_data
    assert "failed_slots" not in response_data
    assert "partial_success" not in response_data


@pytest.mark.asyncio
async def test_select_template_candidate_missing_link_fails_whole_selection() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await template_candidates_api.select_template_candidate(build_select_request(shener=None))

    detail = exc_info.value.detail
    assert exc_info.value.status_code == 502
    assert detail["error"]["code"] == "TEMPLATE_SELECT_FAILED"
    assert detail["error"]["message"] == "模板文件选择失败"
    assert detail["error"]["details"] == "推荐模板链接不存在"
    assert "failed_slots" not in detail
    assert "partial_success" not in detail


@pytest.mark.asyncio
async def test_select_template_candidate_download_failure_fails_whole_selection(monkeypatch) -> None:
    def fake_fetch_template_file(_file_url: str):
        raise requests.exceptions.RequestException("下载失败")

    monkeypatch.setattr(
        template_candidates_api,
        "fetch_template_file",
        fake_fetch_template_file,
    )

    with pytest.raises(HTTPException) as exc_info:
        await template_candidates_api.select_template_candidate(build_select_request())

    detail = exc_info.value.detail
    assert exc_info.value.status_code == 502
    assert detail["error"]["code"] == "TEMPLATE_SELECT_FAILED"
    assert detail["error"]["details"] == "下载失败"
    assert "failed_slots" not in detail
    assert "partial_success" not in detail


@pytest.mark.asyncio
async def test_select_template_candidate_save_failure_fails_whole_selection(monkeypatch) -> None:
    def fake_fetch_template_file(_file_url: str):
        return SimpleNamespace(
            content=b"template-bytes",
            headers={"Content-Type": "application/octet-stream"},
        )

    def fake_persist_file_bytes(**_kwargs):
        raise HTTPException(
            status_code=400,
            detail={"message": "模板文件保存失败", "details": "文件类型不支持"},
        )

    monkeypatch.setattr(
        template_candidates_api,
        "fetch_template_file",
        fake_fetch_template_file,
    )
    monkeypatch.setattr(
        template_candidates_api,
        "persist_file_bytes",
        fake_persist_file_bytes,
    )

    with pytest.raises(HTTPException) as exc_info:
        await template_candidates_api.select_template_candidate(build_select_request())

    detail = exc_info.value.detail
    assert exc_info.value.status_code == 502
    assert detail["error"]["code"] == "TEMPLATE_SELECT_FAILED"
    assert detail["error"]["details"] == "模板文件保存失败: 文件类型不支持"
    assert "failed_slots" not in detail
    assert "partial_success" not in detail
