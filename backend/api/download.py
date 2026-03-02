"""文件下载 API 路由.

提供文件下载功能，支持指定下载文件名.
包含路径遍历防护，确保只能下载 UPLOAD_DIR 目录下的文件.
"""

import logging
import pathlib
import urllib.parse
from typing import Optional

from fastapi import APIRouter, HTTPException, Path, Query, status
from fastapi.responses import FileResponse

from backend.config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/download", tags=["File Download"])


# ========================================
# 辅助函数
# ========================================
def validate_file_path(file_path: str) -> pathlib.Path:
    """验证文件路径安全性.

    Args:
        file_path: URL 编码的文件路径

    Returns:
        pathlib.Path: 解析后的安全路径

    Raises:
        HTTPException: 路径非法时抛出 403
    """
    # 解码 URL 编码的路径
    decoded_path = urllib.parse.unquote(file_path)

    # 解析为 Path 对象并规范化
    target_path = pathlib.Path(decoded_path).resolve()
    upload_dir = pathlib.Path(settings.UPLOAD_DIR).resolve()

    # 安全检查：防止目录遍历攻击
    try:
        target_path.relative_to(upload_dir)
    except ValueError:
        logger.warning(f"非法路径访问尝试: {file_path}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "error": {
                    "code": "ACCESS_DENIED",
                    "message": "访问被拒绝",
                    "details": "只能下载上传目录下的文件",
                },
            },
        )

    return target_path


# ========================================
# API 端点
# ========================================
@router.get(
    "/{file_path:path}",
    summary="下载文件",
    description="""
下载指定路径的文件。

**路径参数**:
- `file_path`: URL 编码的完整文件路径

**查询参数**:
- `download_name`: 下载时显示的文件名（可选）

**安全限制**:
- 只能下载 UPLOAD_DIR 目录下的文件
- 禁止目录遍历攻击（.. 路径）
""",
    responses={
        404: {"description": "文件不存在"},
        403: {"description": "访问被拒绝（路径非法）"},
        400: {"description": "请求参数错误"},
    },
)
async def download_file(
    file_path: str = Path(
        ...,
        description="URL 编码的文件路径",
        examples=["D%3A%2FUploadFiles%2Ftemplate.docx"],
    ),
    download_name: Optional[str] = Query(
        None,
        description="下载时显示的文件名（可选）",
    ),
) -> FileResponse:
    """下载文件.

    Args:
        file_path: URL 编码的文件路径
        download_name: 下载显示的文件名

    Returns:
        FileResponse: 文件响应

    Raises:
        HTTPException: 路径非法或文件不存在时抛出
    """
    logger.info(f"文件下载请求: file_path={file_path}, download_name={download_name}")

    # 验证路径安全性
    target_path = validate_file_path(file_path)

    # 检查文件是否存在
    if not target_path.exists():
        logger.warning(f"文件不存在: {target_path}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error": {
                    "code": "FILE_NOT_FOUND",
                    "message": "文件不存在",
                    "details": str(target_path.name),
                },
            },
        )

    # 检查是否为文件（非目录）
    if not target_path.is_file():
        logger.warning(f"路径不是文件: {target_path}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": {
                    "code": "NOT_A_FILE",
                    "message": "路径不是文件",
                    "details": str(target_path),
                },
            },
        )

    # 确定下载文件名
    filename = download_name or target_path.name

    logger.info(f"文件下载成功: {target_path.name} -> {filename}")

    return FileResponse(
        path=str(target_path),
        filename=filename,
        media_type="application/octet-stream",
    )
