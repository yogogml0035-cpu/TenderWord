from __future__ import annotations

import pathlib
import re
import time
import uuid
from typing import Any, Dict

from fastapi import HTTPException, status

from backend.config.settings import settings


def sanitize_filename(filename: str, fallback_stem: str = "file") -> str:
    """Sanitize a potentially unsafe filename for local persistence."""

    raw_name = pathlib.Path(filename or "").name.strip()
    if not raw_name:
        raw_name = fallback_stem

    suffix = pathlib.Path(raw_name).suffix
    stem = pathlib.Path(raw_name).stem or fallback_stem
    safe_stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", stem).strip(" .")
    if not safe_stem:
        safe_stem = fallback_stem
    safe_suffix = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "", suffix)
    return f"{safe_stem}{safe_suffix}"


def validate_file_extension(filename: str) -> bool:
    """Check whether the filename extension is allowed."""

    suffix = pathlib.Path(filename).suffix.lower()
    return suffix in settings.ALLOWED_EXTENSIONS


def validate_file_size(file_size: int) -> bool:
    """Check whether the file size is within the configured limit."""

    return file_size <= settings.MAX_UPLOAD_SIZE


def ensure_upload_dir() -> pathlib.Path:
    """Ensure the upload directory exists and return it."""

    upload_dir = pathlib.Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def generate_unique_filename(original_name: str) -> str:
    """Generate a unique filename inside the upload directory."""

    upload_dir = ensure_upload_dir()
    safe_name = sanitize_filename(original_name)
    file_path = upload_dir / safe_name

    if file_path.exists():
        timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
        stem = file_path.stem
        suffix = file_path.suffix
        unique_suffix = uuid.uuid4().hex[:8]
        file_path = upload_dir / f"{stem}_{timestamp}_{unique_suffix}{suffix}"

    return str(file_path)


def persist_file_bytes(
    *,
    original_name: str,
    content: bytes,
    content_type: str | None = None,
) -> Dict[str, Any]:
    """Validate and persist file bytes into the configured upload directory."""

    safe_original_name = sanitize_filename(original_name)

    if not validate_file_extension(safe_original_name):
        allowed = ", ".join(settings.ALLOWED_EXTENSIONS)
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "code": "FILE_INVALID_TYPE",
                "message": f"不支持的文件类型。允许的类型: {allowed}",
                "details": f"文件名: {safe_original_name}",
            },
        )

    file_size = len(content)
    if not validate_file_size(file_size):
        max_size_mb = settings.MAX_UPLOAD_SIZE / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "code": "FILE_TOO_LARGE",
                "message": f"文件大小超过限制（最大 {max_size_mb}MB）",
                "details": f"文件大小: {file_size / (1024 * 1024):.2f}MB",
            },
        )

    save_path = generate_unique_filename(safe_original_name)

    try:
        with open(save_path, "wb") as file_obj:
            file_obj.write(content)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "FILE_UPLOAD_FAILED",
                "message": "文件保存失败",
                "details": str(exc),
            },
        ) from exc

    return {
        "file_path": str(pathlib.Path(save_path).resolve()),
        "file_name": pathlib.Path(save_path).name,
        "original_name": safe_original_name,
        "file_size": file_size,
        "content_type": content_type or "application/octet-stream",
    }
