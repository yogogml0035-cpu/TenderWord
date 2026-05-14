from __future__ import annotations

import pytest

from backend.util.common_util import template_candidates
from backend.util.common_util.template_candidates import (
    TemplateDownloadTooLargeError,
    read_template_response_content,
)


class FakeResponse:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    def iter_content(self, chunk_size: int):
        del chunk_size
        yield from self._chunks


class FakeDownloadResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {}

    @property
    def is_redirect(self) -> bool:
        return 300 <= self.status_code < 400

    def raise_for_status(self) -> None:
        return None


def test_read_template_response_content_returns_joined_chunks() -> None:
    response = FakeResponse([b"hello", b"", b"world"])

    assert read_template_response_content(response, max_bytes=16) == b"helloworld"


def test_read_template_response_content_rejects_oversized_stream() -> None:
    response = FakeResponse([b"hello", b"world"])

    with pytest.raises(TemplateDownloadTooLargeError, match="模板文件大小超过限制"):
        read_template_response_content(response, max_bytes=8)


def test_fetch_template_file_rejects_oversized_content_length(monkeypatch) -> None:
    monkeypatch.setattr(
        template_candidates.settings,
        "TEMPLATE_CANDIDATE_ALLOWED_HOSTS",
        ["example.com"],
    )
    monkeypatch.setattr(
        template_candidates.settings,
        "TEMPLATE_CANDIDATE_MAX_DOWNLOAD_SIZE",
        8,
    )
    monkeypatch.setattr(
        template_candidates.requests,
        "get",
        lambda *args, **kwargs: FakeDownloadResponse(headers={"Content-Length": "9"}),
    )

    with pytest.raises(TemplateDownloadTooLargeError):
        template_candidates.fetch_template_file("https://example.com/template.docx")


def test_fetch_template_file_rejects_redirect_to_disallowed_host(monkeypatch) -> None:
    requested_urls: list[str] = []

    def fake_get(url: str, **kwargs):
        assert kwargs["allow_redirects"] is False
        requested_urls.append(url)
        return FakeDownloadResponse(
            status_code=302,
            headers={"Location": "https://evil.example/template.docx"},
        )

    monkeypatch.setattr(
        template_candidates.settings,
        "TEMPLATE_CANDIDATE_ALLOWED_HOSTS",
        ["example.com"],
    )
    monkeypatch.setattr(template_candidates.requests, "get", fake_get)

    with pytest.raises(ValueError, match="主机不在允许列表"):
        template_candidates.fetch_template_file("https://example.com/template.docx")

    assert requested_urls == ["https://example.com/template.docx"]


def test_fetch_template_file_follows_allowed_redirect(monkeypatch) -> None:
    responses = [
        FakeDownloadResponse(
            status_code=302,
            headers={"Location": "/redirected-template.docx"},
        ),
        FakeDownloadResponse(status_code=200, headers={"Content-Length": "4"}),
    ]
    requested_urls: list[str] = []

    def fake_get(url: str, **kwargs):
        assert kwargs["allow_redirects"] is False
        requested_urls.append(url)
        return responses.pop(0)

    monkeypatch.setattr(
        template_candidates.settings,
        "TEMPLATE_CANDIDATE_ALLOWED_HOSTS",
        ["example.com"],
    )
    monkeypatch.setattr(
        template_candidates.settings,
        "TEMPLATE_CANDIDATE_MAX_DOWNLOAD_SIZE",
        8,
    )
    monkeypatch.setattr(template_candidates.requests, "get", fake_get)

    response = template_candidates.fetch_template_file("https://example.com/template.docx")

    assert response.status_code == 200
    assert requested_urls == [
        "https://example.com/template.docx",
        "https://example.com/redirected-template.docx",
    ]


def test_fetch_template_file_rejects_too_many_redirects(monkeypatch) -> None:
    def fake_get(url: str, **kwargs):
        assert kwargs["allow_redirects"] is False
        return FakeDownloadResponse(status_code=302, headers={"Location": url})

    monkeypatch.setattr(
        template_candidates.settings,
        "TEMPLATE_CANDIDATE_ALLOWED_HOSTS",
        ["example.com"],
    )
    monkeypatch.setattr(template_candidates.requests, "get", fake_get)

    with pytest.raises(ValueError, match="重定向次数过多"):
        template_candidates.fetch_template_file("https://example.com/template.docx")
