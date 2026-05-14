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


def test_read_template_response_content_returns_joined_chunks() -> None:
    response = FakeResponse([b"hello", b"", b"world"])

    assert read_template_response_content(response, max_bytes=16) == b"helloworld"


def test_read_template_response_content_rejects_oversized_stream() -> None:
    response = FakeResponse([b"hello", b"world"])

    with pytest.raises(TemplateDownloadTooLargeError, match="模板文件大小超过限制"):
        read_template_response_content(response, max_bytes=8)


def test_fetch_template_file_rejects_oversized_content_length(monkeypatch) -> None:
    class FakeDownloadResponse:
        headers = {"Content-Length": "9"}

        def raise_for_status(self) -> None:
            return None

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
        lambda *args, **kwargs: FakeDownloadResponse(),
    )

    with pytest.raises(TemplateDownloadTooLargeError):
        template_candidates.fetch_template_file("https://example.com/template.docx")
