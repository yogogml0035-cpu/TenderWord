from __future__ import annotations

import builtins
from pathlib import Path
from unittest.mock import mock_open

import pytest
from fastapi import HTTPException

from backend.config.settings import settings
import backend.util.common_util.upload_storage as upload_storage


def test_persist_file_bytes_saves_into_upload_dir_and_sanitizes_filename(monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", "D:/UploadFiles")
    monkeypatch.setattr(
        upload_storage,
        "generate_unique_filename",
        lambda _name: "D:/UploadFiles/示例_模板_.docx",
    )
    mocked_open = mock_open()
    monkeypatch.setattr(builtins, "open", mocked_open)

    result = upload_storage.persist_file_bytes(
        original_name="nested/示例:模板?.docx",
        content=b"template-bytes",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    mocked_open.assert_called_once_with("D:/UploadFiles/示例_模板_.docx", "wb")
    assert Path(result["file_path"]).name == "示例_模板_.docx"
    assert result["original_name"].endswith(".docx")
    assert ":" not in result["original_name"]
    assert "?" not in result["original_name"]


def test_persist_file_bytes_rejects_invalid_extension(monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", "D:/UploadFiles")

    with pytest.raises(HTTPException) as exc_info:
        upload_storage.persist_file_bytes(
            original_name="template.exe",
            content=b"malicious",
            content_type="application/octet-stream",
        )

    assert exc_info.value.status_code == 415
    assert exc_info.value.detail["code"] == "FILE_INVALID_TYPE"
