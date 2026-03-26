"""Template candidate proxy APIs."""

from __future__ import annotations

import logging
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

from backend.models.common import ErrorResponse
from backend.models.template_candidates import (
    TemplateCandidateListData,
    TemplateCandidateListResponse,
    TemplateCandidateSelectRequest,
    TemplateSelectData,
    TemplateSelectedFile,
    TemplateSelectedFiles,
    TemplateSelectFailure,
    TemplateSelectResponse,
)
from backend.util.common_util.template_candidates import (
    INVALID_TEMPLATE_YEAR_MESSAGE,
    OLD_TEMPLATE_MESSAGE,
    build_template_download_name,
    derive_template_blocked_reason,
    fetch_template_candidates,
    fetch_template_file,
    infer_remote_filename,
    resolve_template_media_type,
)
from backend.util.common_util.upload_storage import persist_file_bytes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/template-candidates", tags=["Template Candidates"])


def _build_error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: object | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": details,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


def _build_content_disposition(filename: str) -> str:
    quoted = urllib.parse.quote(filename)
    return f"inline; filename*=UTF-8''{quoted}"


def _build_selected_file(file_info: dict) -> TemplateSelectedFile:
    return TemplateSelectedFile(
        file_path=file_info["file_path"],
        file_name=file_info["file_name"],
        original_name=file_info["original_name"],
        size=file_info["file_size"],
        upload_time=datetime.now(timezone.utc).isoformat(),
    )


@router.get(
    "",
    response_model=TemplateCandidateListResponse,
    responses={
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        502: {"model": ErrorResponse, "description": "候选模板获取失败"},
    },
    summary="获取模板候选列表",
    description="根据招标编号从外部系统代理获取模板候选列表。",
)
async def get_template_candidates(
    tenderno: str = Query(..., min_length=1, description="招标编号"),
) -> TemplateCandidateListResponse:
    try:
        candidates = fetch_template_candidates(
            tenderno=tenderno,
        )
    except ValueError as exc:
        logger.warning("模板候选数据格式错误: tenderno=%s error=%s", tenderno, exc)
        raise _build_error_response(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="TEMPLATE_CANDIDATE_INVALID",
            message="模板候选数据格式错误",
            details=str(exc),
        ) from exc
    except requests.exceptions.RequestException as exc:
        logger.error("模板候选获取失败: tenderno=%s error=%s", tenderno, exc)
        raise _build_error_response(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="TEMPLATE_CANDIDATE_FETCH_FAILED",
            message="模板候选获取失败",
            details=str(exc),
        ) from exc

    return TemplateCandidateListResponse(
        success=True,
        data=TemplateCandidateListData(candidates=candidates),
        message="模板候选获取成功",
    )


@router.get(
    "/download",
    responses={
        400: {"model": ErrorResponse, "description": "模板文件链接非法"},
        403: {"model": ErrorResponse, "description": "模板文件源不允许访问"},
        502: {"model": ErrorResponse, "description": "模板文件下载失败"},
    },
    summary="代理下载模板文件",
    description="代理外部模板文件链接，供前端新标签打开或直接下载。",
)
async def download_template_candidate(
    file_url: str = Query(..., min_length=1, description="外部模板文件链接"),
    download_name: Optional[str] = Query(None, description="下载显示名称"),
) -> Response:
    try:
        upstream_response = fetch_template_file(file_url)
    except ValueError as exc:
        logger.warning("模板文件链接非法: %s", exc)
        message = str(exc)
        status_code = (
            status.HTTP_403_FORBIDDEN
            if "主机" in message
            else status.HTTP_400_BAD_REQUEST
        )
        code = "TEMPLATE_SOURCE_DENIED" if status_code == status.HTTP_403_FORBIDDEN else "TEMPLATE_URL_INVALID"
        raise _build_error_response(
            status_code=status_code,
            code=code,
            message="模板文件链接非法",
            details=message,
        ) from exc
    except requests.exceptions.RequestException as exc:
        logger.error("模板文件代理下载失败: %s", exc)
        raise _build_error_response(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="TEMPLATE_FILE_DOWNLOAD_FAILED",
            message="模板文件下载失败",
            details=str(exc),
        ) from exc

    inferred_name = infer_remote_filename(upstream_response, file_url, "template")
    if download_name and not Path(download_name).suffix:
        filename = f"{download_name}{Path(inferred_name).suffix}"
    else:
        filename = download_name or inferred_name
    media_type = resolve_template_media_type(
        upstream_response.headers.get("Content-Type"),
        filename,
    )
    headers = {"Content-Disposition": _build_content_disposition(filename)}
    return Response(
        content=upstream_response.content,
        media_type=media_type,
        headers=headers,
    )


@router.post(
    "/select",
    response_model=TemplateSelectResponse,
    responses={
        400: {"model": ErrorResponse, "description": "模板选择请求不合法"},
        403: {"model": ErrorResponse, "description": "模板文件源不允许访问"},
        409: {"model": ErrorResponse, "description": "模板年份过旧"},
        502: {"model": ErrorResponse, "description": "模板文件选择失败"},
    },
    summary="选择模板并保存到上传区",
    description="根据所选推荐模板下载送审稿并落入上传目录，同时回填到发售稿和送审稿上传槽位。",
)
async def select_template_candidate(
    request: TemplateCandidateSelectRequest,
) -> TemplateSelectResponse:
    candidate = request.candidate
    blocked_reason = derive_template_blocked_reason(candidate.year)
    if blocked_reason == OLD_TEMPLATE_MESSAGE:
        raise _build_error_response(
            status_code=status.HTTP_409_CONFLICT,
            code="TEMPLATE_TOO_OLD",
            message=OLD_TEMPLATE_MESSAGE,
        )
    if blocked_reason == INVALID_TEMPLATE_YEAR_MESSAGE:
        raise _build_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="TEMPLATE_YEAR_INVALID",
            message=INVALID_TEMPLATE_YEAR_MESSAGE,
        )

    selected_files = TemplateSelectedFiles()
    failures: list[TemplateSelectFailure] = []

    recommended_template_url = candidate.shener
    if not recommended_template_url:
        failures.extend(
            [
                TemplateSelectFailure(slot="clean_draft", message="推荐模板链接不存在"),
                TemplateSelectFailure(slot="origin_tender", message="推荐模板链接不存在"),
            ]
        )
    else:
        try:
            upstream_response = fetch_template_file(recommended_template_url)
            remote_filename = infer_remote_filename(
                upstream_response,
                recommended_template_url,
                f"{candidate.tendername}-送审稿",
            )
            save_name = build_template_download_name(candidate.tendername, "送审稿", remote_filename)
            template_content = upstream_response.content
            template_content_type = upstream_response.headers.get(
                "Content-Type",
                "application/octet-stream",
            )
        except ValueError as exc:
            failures.extend(
                [
                    TemplateSelectFailure(slot="clean_draft", message=str(exc)),
                    TemplateSelectFailure(slot="origin_tender", message=str(exc)),
                ]
            )
        except requests.exceptions.RequestException as exc:
            failures.extend(
                [
                    TemplateSelectFailure(slot="clean_draft", message=str(exc)),
                    TemplateSelectFailure(slot="origin_tender", message=str(exc)),
                ]
            )
        else:
            for slot in ("clean_draft", "origin_tender"):
                try:
                    file_info = persist_file_bytes(
                        original_name=save_name,
                        content=template_content,
                        content_type=template_content_type,
                    )
                except HTTPException as exc:
                    detail = exc.detail if isinstance(exc.detail, dict) else {}
                    failure_message = detail.get("message") or "模板文件保存失败"
                    failure_details = detail.get("details")
                    if failure_details:
                        failure_message = f"{failure_message}: {failure_details}"
                    failures.append(TemplateSelectFailure(slot=slot, message=failure_message))
                    continue

                if slot == "clean_draft":
                    selected_files.clean_draft = _build_selected_file(file_info)
                else:
                    selected_files.origin_tender = _build_selected_file(file_info)

    if selected_files.clean_draft is None and selected_files.origin_tender is None:
        raise _build_error_response(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="TEMPLATE_SELECT_FAILED",
            message="模板文件选择失败",
            details=[failure.model_dump() for failure in failures],
        )

    partial_success = bool(failures)
    return TemplateSelectResponse(
        success=True,
        data=TemplateSelectData(
            selected_files=selected_files,
            failed_slots=failures,
            partial_success=partial_success,
        ),
        message="模板部分回填成功" if partial_success else "模板回填成功",
    )
