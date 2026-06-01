"""招标数据 API 路由.

提供招标数据获取相关端点。
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Path, status
from pydantic import BaseModel, Field

from backend.models.tender import TenderData, TenderType
from backend.util.common_util import fetch_tender_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tender", tags=["Tender"])
SUPPORTED_PURCHASE_METHODS = {0, 2, 5}


# ========================================
# 响应模型
# ========================================
class TenderResponse(BaseModel):
    """招标数据 API 响应模型."""

    success: bool = Field(..., description="请求是否成功")
    data: Optional[TenderData] = Field(None, description="招标数据")
    type: Optional[TenderType] = Field(None, description="招标类型信息")
    warning: Optional[Dict[str, Any]] = Field(None, description="非阻断提示信息")
    message: str = Field(..., description="响应消息")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="响应时间戳",
    )


class TenderErrorResponse(BaseModel):
    """错误响应模型."""

    success: bool = Field(default=False, description="请求失败")
    error: Dict[str, Any] = Field(..., description="错误信息")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="响应时间戳",
    )


# ========================================
# API 端点
# ========================================
@router.get(
    "/{tender_no}",
    response_model=TenderResponse,
    responses={
        404: {"model": TenderErrorResponse, "description": "招标编号不存在"},
        502: {"model": TenderErrorResponse, "description": "数据获取失败"},
    },
    summary="获取招标数据",
    description="根据招标编号从外部系统获取招标项目详细信息。",
)
async def get_tender_data(
    tender_no: str = Path(
        ...,
        description="招标编号（包含前缀）",
        min_length=1,
        examples=["ZBGG-2024-001"],
    ),
) -> TenderResponse:
    """获取招标数据.

    Args:
        tender_no: 招标编号

    Returns:
        TenderResponse: 包含招标数据和类型信息的响应

    Raises:
        HTTPException: 当招标编号不存在或数据获取失败时
    """
    logger.info(f"获取招标数据: tender_no={tender_no}")

    try:
        # 调用现有的获取函数
        result = fetch_tender_data(tender_no)

        # 提取数据
        tender_data_dict = result.get("data", {})
        tender_type_dict = result.get("type")

        # 构建 TenderData 模型
        tender_data = TenderData(
            project_name=tender_data_dict.get("project_name", ""),
            project_number=tender_data_dict.get("project_number", ""),
            project_content=tender_data_dict.get("project_content", ""),
            buyer_name=tender_data_dict.get("buyer_name", ""),
            investment=tender_data_dict.get("investment", ""),
            bzj_rule=tender_data_dict.get("bzj_rule", ""),
            project_zbr_xbr=tender_data_dict.get("project_zbr_xbr", ""),
            zbr_xbr_tel=tender_data_dict.get("zbr_xbr_tel", ""),
            zbr_pinyin=tender_data_dict.get("zbr_pinyin", ""),
            shell_start_date=tender_data_dict.get("shell_start_date", ""),
            shell_end_date=tender_data_dict.get("shell_end_date", ""),
            submit_date=tender_data_dict.get("submit_date", ""),
            platform=tender_data_dict.get("platform", ""),
            service_fee=tender_data_dict.get("service_fee", ""),
            ifdzpt2=tender_data_dict.get("ifdzpt2"),
            ifzgcg=tender_data_dict.get("ifzgcg"),
            tender_lx=tender_data_dict.get("tender_lx"),
            fund_source_lx=tender_data_dict.get("fund_source_lx"),
        )

        # 构建 TenderType 模型（可能为 None）
        tender_type = None
        warning = None
        if tender_type_dict:
            normalized_fund_lx = tender_type_dict.get("fund_lx")
            if normalized_fund_lx in (0, 1):
                tender_type = TenderType(
                    tender_lx=tender_type_dict.get("tender_lx", 0),
                    purchase_method=tender_type_dict.get("purchase_method", 5),
                    fund_lx=normalized_fund_lx,
                )
                if tender_type.purchase_method not in SUPPORTED_PURCHASE_METHODS:
                    warning = {
                        "code": "TENDER_UNSUPPORTED_PURCHASE_METHOD",
                        "message": "当前采购方式暂不支持",
                        "details": {
                            "purchase_method": tender_type.purchase_method,
                        },
                    }

        logger.info(f"招标数据获取成功: tender_no={tender_no}")

        return TenderResponse(
            success=True,
            data=tender_data,
            type=tender_type,
            warning=warning,
            message="数据获取成功",
        )

    except ValueError as e:
        # 数据格式错误或招标编号不存在
        error_msg = str(e)
        logger.warning(f"招标数据格式错误: tender_no={tender_no}, error={error_msg}")

        # 判断是招标编号不存在还是数据格式错误
        if "缺少" in error_msg or "不是有效" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error": {
                        "code": "TENDER_NOT_FOUND",
                        "message": "招标编号不存在",
                        "details": error_msg,
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error": {
                        "code": "TENDER_INVALID_DATA",
                        "message": "招标数据格式错误",
                        "details": error_msg,
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

    except Exception as e:
        # 网络错误或其他未知错误
        error_msg = str(e)
        logger.error(f"招标数据获取失败: tender_no={tender_no}, error={error_msg}")

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "success": False,
                "error": {
                    "code": "TENDER_FETCH_FAILED",
                    "message": "招标数据获取失败",
                    "details": error_msg,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
