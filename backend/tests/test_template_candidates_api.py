from __future__ import annotations

from dataclasses import dataclass

import pytest
import requests
from fastapi import HTTPException

import backend.api.template_candidates as template_candidates_api
import backend.util.common_util.template_candidates as template_candidate_util
from backend.models.template_candidates import (
    TemplateCandidateSelectPayload,
    TemplateCandidateSelectRequest,
)


def run_async_endpoint(coro):
    try:
        coro.send(None)
    except StopIteration as exc:
        return exc.value
    raise AssertionError("Endpoint coroutine yielded unexpectedly during test execution")


@dataclass
class DummyResponse:
    json_payload: object | None = None
    content: bytes = b"template"
    headers: dict[str, str] | None = None
    should_raise: Exception | None = None

    def json(self):
        return self.json_payload

    def raise_for_status(self):
        if self.should_raise:
            raise self.should_raise


def test_fetch_template_candidates_normalizes_external_json_array(monkeypatch):
    def mock_get(url, params=None, timeout=None, stream=False):
        assert params == {
            "tenderno": "0811-TEST",
        }
        assert stream is False
        return DummyResponse(
            json_payload=[
                {
                    "tenderno": " 0811-NEW ",
                    "tendername": " 最新项目 ",
                    "tname": " 上海市中医医院 ",
                    "bm": " 采购处 ",
                    "hytype": " 医疗行业 ",
                    "tendertype": " 国内公开 ",
                    "hwlx": " 货物 ",
                    "yxj": 1,
                    "zbr": " 张三 ",
                    "xbr": " 李四 ",
                    "year": "2026",
                    "fsg": "http://10.11.1.224/file-a",
                    "shener": "http://10.11.1.224/file-b",
                },
                {
                    "tenderno": "0811-OLD",
                    "tendername": "旧项目",
                    "tname": "上海市第一人民医院",
                    "bm": "设备科",
                    "hytype": "医疗行业",
                    "tendertype": "国内公开",
                    "hwlx": "货物",
                    "yxj": "3",
                    "zbr": "王五",
                    "xbr": "赵六",
                    "year": "2024",
                    "fsg": "http://10.11.1.224/file-c",
                    "shener": "http://10.11.1.224/file-d",
                },
            ]
        )

    monkeypatch.setattr(template_candidate_util.requests, "get", mock_get)

    result = template_candidate_util.fetch_template_candidates(
        tenderno="0811-TEST",
    )

    assert [candidate["tendername"] for candidate in result] == ["最新项目", "旧项目"]
    assert result[0]["tenderno"] == "0811-NEW"
    assert result[0]["tname"] == "上海市中医医院"
    assert result[0]["bm"] == "采购处"
    assert result[0]["hytype"] == "医疗行业"
    assert result[0]["tendertype"] == "国内公开"
    assert result[0]["hwlx"] == "货物"
    assert result[0]["yxj"] == "1"
    assert result[0]["year"] == 2026
    assert result[0]["selectable"] is True
    assert result[1]["year"] == 2024
    assert result[1]["selectable"] is False
    assert result[1]["blocked_reason"] == template_candidate_util.OLD_TEMPLATE_MESSAGE


def test_get_template_candidates_route_returns_wrapped_candidates(monkeypatch):
    monkeypatch.setattr(
        template_candidates_api,
        "fetch_template_candidates",
        lambda **_: [
            {
                "tenderno": "0811-TEST",
                "tendername": "项目A",
                "tname": "采购人A",
                "bm": "采购部",
                "hytype": "医疗行业",
                "tendertype": "国内公开",
                "hwlx": "货物",
                "yxj": "2",
                "zbr": "张三",
                "xbr": "李四",
                "year": 2026,
                "fsg": "http://10.11.1.224/fsg",
                "shener": "http://10.11.1.224/shener",
                "selectable": True,
                "blocked_reason": None,
            }
        ],
    )

    result = run_async_endpoint(
        template_candidates_api.get_template_candidates(
            tenderno="0811-TEST",
        )
    )

    assert result.success is True
    assert result.data.candidates[0].tenderno == "0811-TEST"
    assert result.data.candidates[0].tendername == "项目A"
    assert result.data.candidates[0].tname == "采购人A"
    assert result.data.candidates[0].bm == "采购部"
    assert result.data.candidates[0].hytype == "医疗行业"
    assert result.data.candidates[0].tendertype == "国内公开"
    assert result.data.candidates[0].hwlx == "货物"
    assert result.data.candidates[0].yxj == "2"


def test_download_template_candidate_rejects_disallowed_host(monkeypatch):
    monkeypatch.setattr(
        template_candidates_api,
        "fetch_template_file",
        lambda _url: (_ for _ in ()).throw(ValueError("模板文件链接主机不在允许列表中")),
    )

    with pytest.raises(HTTPException) as exc_info:
        run_async_endpoint(
            template_candidates_api.download_template_candidate(
                file_url="http://evil.example.com/file.docx",
                download_name="项目A-发售稿.docx",
            )
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error"]["code"] == "TEMPLATE_SOURCE_DENIED"


def test_download_template_candidate_infers_previewable_media_type_from_filename(monkeypatch):
    monkeypatch.setattr(
        template_candidates_api,
        "fetch_template_file",
        lambda _url: DummyResponse(
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Disposition": 'attachment; filename="remote.docx"',
            },
            content=b"word-content",
        ),
    )

    response = run_async_endpoint(
        template_candidates_api.download_template_candidate(
            file_url="http://10.11.1.224/file.docx",
            download_name="项目A-送审稿",
        )
    )

    assert response.media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert (
        response.headers["Content-Disposition"]
        == "inline; filename*=UTF-8''%E9%A1%B9%E7%9B%AEA-%E9%80%81%E5%AE%A1%E7%A8%BF.docx"
    )


def test_select_template_candidate_blocks_old_year_before_download():
    request = TemplateCandidateSelectRequest(
        candidate=TemplateCandidateSelectPayload(
            tendername="旧模板",
            year=2024,
            fsg="http://10.11.1.224/fsg",
            shener="http://10.11.1.224/shener",
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        run_async_endpoint(template_candidates_api.select_template_candidate(request))

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error"]["code"] == "TEMPLATE_TOO_OLD"
    assert exc_info.value.detail["error"]["message"] == template_candidate_util.OLD_TEMPLATE_MESSAGE


def test_select_template_candidate_returns_full_success(monkeypatch):
    fetched_urls: list[str] = []

    monkeypatch.setattr(
        template_candidates_api,
        "fetch_template_file",
        lambda url: fetched_urls.append(url)
        or DummyResponse(
            headers={
                "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "Content-Disposition": 'attachment; filename="remote.docx"',
            },
            content=b"word-content",
        ),
    )

    persisted_names: list[str] = []

    def persist_side_effect(*, original_name, content, content_type):
        persisted_names.append(original_name)
        return {
            "file_path": f"D:/UploadFiles/{original_name}",
            "file_name": original_name,
            "original_name": original_name,
            "file_size": len(content),
            "content_type": content_type,
        }

    monkeypatch.setattr(template_candidates_api, "persist_file_bytes", persist_side_effect)

    request = TemplateCandidateSelectRequest(
        candidate=TemplateCandidateSelectPayload(
            tendername="项目模板",
            year=2026,
            fsg="http://10.11.1.224/fsg",
            shener="http://10.11.1.224/shener",
        )
    )

    result = run_async_endpoint(template_candidates_api.select_template_candidate(request))

    assert result.success is True
    assert result.data.partial_success is False
    assert result.data.selected_files.clean_draft is not None
    assert result.data.selected_files.origin_tender is not None
    assert result.data.selected_files.clean_draft.original_name == "项目模板-送审稿.docx"
    assert result.data.selected_files.origin_tender.original_name == "项目模板-送审稿.docx"
    assert result.data.failed_slots == []
    assert fetched_urls == ["http://10.11.1.224/shener"]
    assert persisted_names == ["项目模板-送审稿.docx", "项目模板-送审稿.docx"]


def test_select_template_candidate_returns_partial_success(monkeypatch):
    def fetch_side_effect(url):
        return DummyResponse(
            headers={
                "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "Content-Disposition": 'attachment; filename="remote.docx"',
            },
            content=url.encode("utf-8"),
        )

    persist_calls = 0

    def persist_side_effect(*, original_name, content, content_type):
        nonlocal persist_calls
        persist_calls += 1
        if persist_calls == 2:
            raise HTTPException(
                status_code=500,
                detail={"message": "文件保存失败", "details": "disk full"},
            )
        return {
            "file_path": f"D:/UploadFiles/{original_name}",
            "file_name": original_name,
            "original_name": original_name,
            "file_size": len(content),
            "content_type": content_type,
        }

    monkeypatch.setattr(template_candidates_api, "fetch_template_file", fetch_side_effect)
    monkeypatch.setattr(template_candidates_api, "persist_file_bytes", persist_side_effect)

    request = TemplateCandidateSelectRequest(
        candidate=TemplateCandidateSelectPayload(
            tendername="项目模板",
            year=2026,
            fsg="http://10.11.1.224/fsg",
            shener="http://10.11.1.224/shener",
        )
    )

    result = run_async_endpoint(template_candidates_api.select_template_candidate(request))

    assert result.success is True
    assert result.data.partial_success is True
    assert result.data.selected_files.clean_draft is not None
    assert result.data.selected_files.origin_tender is None
    assert [failure.slot for failure in result.data.failed_slots] == ["origin_tender"]
    assert result.data.selected_files.clean_draft.original_name == "项目模板-送审稿.docx"


def test_select_template_candidate_raises_when_all_slots_fail(monkeypatch):
    monkeypatch.setattr(
        template_candidates_api,
        "fetch_template_file",
        lambda _url: (_ for _ in ()).throw(
            requests.exceptions.RequestException("download failed")
        ),
    )

    request = TemplateCandidateSelectRequest(
        candidate=TemplateCandidateSelectPayload(
            tendername="项目模板",
            year=2026,
            fsg="http://10.11.1.224/fsg",
            shener="http://10.11.1.224/shener",
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        run_async_endpoint(template_candidates_api.select_template_candidate(request))

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail["error"]["code"] == "TEMPLATE_SELECT_FAILED"
