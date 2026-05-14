from __future__ import annotations

import json
import mimetypes
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import requests

from backend.config.settings import settings


OLD_TEMPLATE_MESSAGE = "该模板过旧不能选择，仅供下载参考"
INVALID_TEMPLATE_YEAR_MESSAGE = "模板年份缺失或无效，不能自动选择"


class TemplateDownloadTooLargeError(ValueError):
    """Raised when a proxied template response exceeds the configured byte limit."""


def _request_timeout_seconds() -> float:
    return float(settings.EXTERNAL_REQUEST_TIMEOUT_SECONDS)


def _max_template_download_size() -> int:
    configured_limit = int(settings.TEMPLATE_CANDIDATE_MAX_DOWNLOAD_SIZE)
    if configured_limit > 0:
        return configured_limit
    return int(settings.MAX_UPLOAD_SIZE)


def build_template_candidate_params(
    *,
    tenderno: str,
) -> Dict[str, Any]:
    return {
        "tenderno": tenderno,
    }


def extract_template_year(raw_year: Any) -> Optional[int]:
    if raw_year is None:
        return None

    if isinstance(raw_year, bool):
        return None

    if isinstance(raw_year, int):
        return raw_year

    if isinstance(raw_year, float):
        return int(raw_year)

    if isinstance(raw_year, str):
        value = raw_year.strip()
        if not value:
            return None
        if value.isdigit():
            return int(value)

    return None


def derive_template_blocked_reason(year: Optional[int]) -> Optional[str]:
    if year is None:
        return INVALID_TEMPLATE_YEAR_MESSAGE
    if year < 2025:
        return OLD_TEMPLATE_MESSAGE
    return None


def normalize_template_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_template_candidate(item: Dict[str, Any]) -> Dict[str, Any]:
    year = extract_template_year(item.get("year"))
    blocked_reason = derive_template_blocked_reason(year)
    return {
        "tenderno": normalize_template_text(item.get("tenderno")),
        "tendername": normalize_template_text(item.get("tendername")),
        "tname": normalize_template_text(item.get("tname")),
        "bm": normalize_template_text(item.get("bm")),
        "hytype": normalize_template_text(item.get("hytype")),
        "tendertype": normalize_template_text(item.get("tendertype")),
        "hwlx": normalize_template_text(item.get("hwlx")),
        "yxj": normalize_template_text(item.get("yxj")),
        "zbr": normalize_template_text(item.get("zbr")),
        "xbr": normalize_template_text(item.get("xbr")),
        "year": year,
        "fsg": normalize_template_text(item.get("fsg")) or None,
        "shener": normalize_template_text(item.get("shener")) or None,
        "selectable": blocked_reason is None,
        "blocked_reason": blocked_reason,
    }


def fetch_template_candidates(
    *,
    tenderno: str,
) -> list[Dict[str, Any]]:
    params = build_template_candidate_params(
        tenderno=tenderno,
    )

    try:
        response = requests.get(
            settings.TEMPLATE_CANDIDATE_API_URL,
            params=params,
            timeout=_request_timeout_seconds(),
        )
        response.raise_for_status()
        payload = response.json()
    except requests.exceptions.RequestException as exc:
        raise requests.exceptions.RequestException(f"请求模板候选接口失败: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"模板候选接口返回的不是有效 JSON: {exc}") from exc

    if not isinstance(payload, list):
        raise ValueError("模板候选接口返回格式错误，应为 JSON 数组")

    normalized_candidates: list[Dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        normalized_candidates.append(normalize_template_candidate(item))
    return normalized_candidates


def is_allowed_template_download_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    return hostname.lower() in {host.lower() for host in settings.TEMPLATE_CANDIDATE_ALLOWED_HOSTS}


def validate_template_download_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("模板文件链接协议不受支持")
    if not is_allowed_template_download_host(parsed.hostname):
        raise ValueError("模板文件链接主机不在允许列表中")


def fetch_template_file(url: str) -> requests.Response:
    validate_template_download_url(url)

    try:
        response = requests.get(url, stream=True, timeout=_request_timeout_seconds())
        response.raise_for_status()
        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                declared_size = int(content_length)
            except ValueError:
                declared_size = 0
            if declared_size > _max_template_download_size():
                raise TemplateDownloadTooLargeError(
                    "模板文件大小超过限制"
                    f"（最大 {_max_template_download_size()} 字节）"
                )
        return response
    except TemplateDownloadTooLargeError:
        raise
    except requests.exceptions.RequestException as exc:
        raise requests.exceptions.RequestException(f"下载模板文件失败: {exc}") from exc


def _parse_content_disposition_filename(value: str | None) -> Optional[str]:
    if not value:
        return None

    filename_star_match = re.search(r"filename\*=UTF-8''([^;]+)", value, re.IGNORECASE)
    if filename_star_match:
        return urllib.parse.unquote(filename_star_match.group(1))

    filename_match = re.search(r'filename="?([^";]+)"?', value, re.IGNORECASE)
    if filename_match:
        return filename_match.group(1)

    return None


def _guess_extension_from_content_type(content_type: str | None) -> str:
    if not content_type:
        return ".docx"
    mime = content_type.split(";")[0].strip().lower()
    if mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return ".docx"
    if mime == "application/msword":
        return ".doc"
    guessed = mimetypes.guess_extension(mime)
    return guessed or ".docx"


def resolve_template_media_type(content_type: str | None, filename: str) -> str:
    if content_type:
        normalized = content_type.split(";")[0].strip().lower()
        if normalized and normalized not in {
            "application/octet-stream",
            "binary/octet-stream",
        }:
            return normalized

    suffix = Path(filename).suffix.lower()
    if suffix == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if suffix == ".doc":
        return "application/msword"

    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def infer_remote_filename(response: requests.Response, source_url: str, fallback_name: str) -> str:
    content_disposition = response.headers.get("Content-Disposition")
    header_name = _parse_content_disposition_filename(content_disposition)
    if header_name:
        return Path(header_name).name

    path = urllib.parse.urlparse(source_url).path
    if path:
        candidate_name = Path(path).name
        if candidate_name and "." in candidate_name:
            return candidate_name

    extension = _guess_extension_from_content_type(response.headers.get("Content-Type"))
    return f"{fallback_name}{extension}"


def build_template_download_name(tendername: str, label: str, remote_filename: str) -> str:
    remote_extension = Path(remote_filename).suffix.lower()
    extension = remote_extension or ".docx"
    return f"{tendername}-{label}{extension}"


def iter_response_content(response: requests.Response, chunk_size: int = 64 * 1024) -> Iterable[bytes]:
    for chunk in response.iter_content(chunk_size=chunk_size):
        if chunk:
            yield chunk


def read_template_response_content(
    response: requests.Response,
    *,
    max_bytes: int | None = None,
    chunk_size: int = 64 * 1024,
) -> bytes:
    """Read a template download response while enforcing a hard byte limit."""

    limit = _max_template_download_size() if max_bytes is None else int(max_bytes)
    if limit <= 0:
        limit = int(settings.MAX_UPLOAD_SIZE)

    chunks: list[bytes] = []
    total_size = 0
    for chunk in iter_response_content(response, chunk_size=chunk_size):
        total_size += len(chunk)
        if total_size > limit:
            raise TemplateDownloadTooLargeError(
                "模板文件大小超过限制"
                f"（最大 {limit} 字节）"
            )
        chunks.append(chunk)

    return b"".join(chunks)
