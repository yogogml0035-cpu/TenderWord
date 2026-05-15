from __future__ import annotations

import pytest

from backend.util.common_util import upload_storage


def test_resolve_upload_path_accepts_file_inside_posix_upload_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    document = upload_dir / "template.docx"
    document.write_bytes(b"doc")
    monkeypatch.setattr(upload_storage.settings, "UPLOAD_DIR", str(upload_dir))

    assert upload_storage.resolve_upload_file_path(str(document)) == str(document.resolve())


def test_resolve_upload_path_rejects_file_outside_posix_upload_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    outside = tmp_path / "outside.docx"
    outside.write_bytes(b"doc")
    monkeypatch.setattr(upload_storage.settings, "UPLOAD_DIR", str(upload_dir))

    with pytest.raises(ValueError, match="必须位于上传目录"):
        upload_storage.resolve_upload_file_path(str(outside))


def test_resolve_upload_path_rejects_directory_traversal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    outside = tmp_path / "secret.docx"
    outside.write_bytes(b"doc")
    monkeypatch.setattr(upload_storage.settings, "UPLOAD_DIR", str(upload_dir))

    with pytest.raises(ValueError, match="必须位于上传目录"):
        upload_storage.resolve_upload_file_path(str(upload_dir / ".." / "secret.docx"))


def test_resolve_upload_path_rejects_relative_posix_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(upload_storage.settings, "UPLOAD_DIR", str(upload_dir))

    with pytest.raises(ValueError, match="必须位于上传目录"):
        upload_storage.resolve_upload_file_path("uploads/template.docx")


def test_resolve_upload_path_accepts_windows_style_upload_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(upload_storage.settings, "UPLOAD_DIR", "D:/UploadFiles")

    assert (
        upload_storage.resolve_upload_file_path("D:/UploadFiles/template.docx")
        == "D:/UploadFiles/template.docx"
    )


def test_resolve_upload_path_normalizes_windows_dot_segments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(upload_storage.settings, "UPLOAD_DIR", "D:/UploadFiles")

    assert (
        upload_storage.resolve_upload_file_path(
            "D:/UploadFiles/nested/../template.docx"
        )
        == "D:/UploadFiles/template.docx"
    )


def test_resolve_upload_path_rejects_windows_style_outside_upload_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(upload_storage.settings, "UPLOAD_DIR", "D:/UploadFiles")

    with pytest.raises(ValueError, match="必须位于上传目录"):
        upload_storage.resolve_upload_file_path("C:/Windows/win.ini")


def test_resolve_upload_path_rejects_windows_style_prefix_collision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(upload_storage.settings, "UPLOAD_DIR", "D:/UploadFiles")

    with pytest.raises(ValueError, match="必须位于上传目录"):
        upload_storage.resolve_upload_file_path("D:/UploadFiles_evil/template.docx")


def test_resolve_upload_path_rejects_windows_style_directory_traversal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(upload_storage.settings, "UPLOAD_DIR", "D:/UploadFiles")

    with pytest.raises(ValueError, match="必须位于上传目录"):
        upload_storage.resolve_upload_file_path("D:/UploadFiles/../secret.docx")


def test_resolve_upload_path_rejects_posix_path_when_upload_dir_is_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(upload_storage.settings, "UPLOAD_DIR", "D:/UploadFiles")

    with pytest.raises(ValueError, match="必须位于上传目录"):
        upload_storage.resolve_upload_file_path("/mnt/d/UploadFiles/template.docx")
