from __future__ import annotations

from urllib.parse import quote

import pytest
from fastapi import HTTPException

from backend.api.download import validate_file_path
from backend.config.settings import settings


def test_validate_file_path_accepts_file_inside_upload_dir(tmp_path, monkeypatch) -> None:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    document = upload_dir / "result.docx"
    document.write_bytes(b"doc")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_dir))

    assert validate_file_path(quote(str(document), safe="")) == document.resolve()


def test_validate_file_path_rejects_file_outside_upload_dir(tmp_path, monkeypatch) -> None:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    outside = tmp_path / "outside.docx"
    outside.write_bytes(b"doc")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_dir))

    with pytest.raises(HTTPException) as exc_info:
        validate_file_path(quote(str(outside), safe=""))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error"]["code"] == "ACCESS_DENIED"
