from __future__ import annotations

import json
from typing import Dict

import requests

from backend.config.settings import settings
from backend.util.common_util.tender_number import normalize_gjgk_project_number


def _request_timeout_seconds() -> float:
    return float(settings.EXTERNAL_REQUEST_TIMEOUT_SECONDS)


def _normalize_fund_source_lx(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return None
    return normalized if normalized in (0, 1) else None


def _normalize_tender_type_payload(payload) -> Dict | None:
    if not isinstance(payload, dict):
        return None

    fund_lx = _normalize_fund_source_lx(payload.get("fund_lx"))
    if fund_lx is None:
        return None

    try:
        tender_lx = int(payload.get("tender_lx", 0))
        purchase_method = int(payload.get("purchase_method", 5))
    except (TypeError, ValueError):
        return None

    if tender_lx not in (0, 1, 2):
        return None

    return {
        "tender_lx": tender_lx,
        "purchase_method": purchase_method,
        "fund_lx": fund_lx,
    }


def _normalize_optional_int(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_gjgk_tender_type(tender_type: Dict | None) -> bool:
    if not isinstance(tender_type, dict):
        return False

    try:
        purchase_method = int(tender_type.get("purchase_method"))
    except (TypeError, ValueError):
        return False

    return purchase_method == 0


def fetch_tender_data(tender_no: str) -> Dict:
    """
    从接口获取招标数据

    接口返回格式为：
    {"data": {...}, "type": {"tender_lx": 0, "purchase_method": 0, "fund_lx": 1}}
    其中：
    - type 用于表单路由（例如 purchase_method=2 表示国内公开；
      purchase_method=5 表示询价采购；
      purchase_method=0 表示国际公开）
    - type.tender_lx 表示标的类型（0=货物, 1=工程, 2=服务）
    - data.fund_lx 会透传为业务字段 fund_source_lx
    - data.ifdzpt2 / data.ifzgcg 会透传给前端，用于修正默认插入锚点

    Args:
        tender_no: 招标编号

    Returns:
        包含 "data" 与 "type" 的字典：
        - data: 招标业务数据（project_name、project_number 等）
        - type: 招标类型，用于匹配表单，格式 {"tender_lx": int, "purchase_method": int, "fund_lx": 0|1}，
          若接口未返回或资金类型非法则为 None

    Raises:
        requests.RequestException: 当接口请求失败时
        ValueError: 当返回数据格式不正确时
    """
    try:
        response = requests.get(
            settings.TENDER_DATA_API_URL,
            params={"tenderno": tender_no},
            timeout=_request_timeout_seconds(),
        )
        response.raise_for_status()  # 如果状态码不是 200，会抛出异常

        # 解析 JSON 响应
        result = response.json()

        # 检查返回数据结构
        if "data" not in result:
            raise ValueError("接口返回数据中缺少 'data' 字段")

        data = result["data"]
        raw_tender_type = result.get("type")
        tender_type = _normalize_tender_type_payload(raw_tender_type)
        project_number = data.get("project_number", "")
        if _is_gjgk_tender_type(raw_tender_type):
            project_number = normalize_gjgk_project_number(project_number, tender_no)

        # 提取所需字段
        tender_data = {
            "project_name": data.get("project_name", ""),
            "project_number": project_number,
            "project_content": data.get("project_content", ""),
            "bzj_rule": data.get("bzj_rule", ""),
            "buyer_name": data.get("buyer_name", ""),
            "project_zbr_xbr": data.get("project_zbr_xbr", ""),
            "zbr_xbr_tel": data.get("zbr_xbr_tel", ""),
            "zbr_pinyin": data.get("zbr_pinyin", ""),
            "shell_start_date": f"{data.get('shell_start_date', '')}起"
            if data.get("shell_start_date", "")
            else "",
            "shell_end_date": f"{data.get('shell_end_date', '')}止"
            if data.get("shell_end_date", "")
            else "",
            "submit_date": data.get("submit_date", ""),
            "platform": data.get("platform", ""),
            "service_fee": "",  # data.get("service_fee", ""),
            "ifdzpt2": _normalize_optional_int(data.get("ifdzpt2")),
            "ifzgcg": _normalize_optional_int(data.get("ifzgcg")),
            "fund_source_lx": _normalize_fund_source_lx(data.get("fund_lx")),
        }

        return {"data": tender_data, "type": tender_type}

    except requests.exceptions.RequestException as e:
        raise requests.exceptions.RequestException(f"请求接口失败: {str(e)}")
    except json.JSONDecodeError as e:
        raise ValueError(f"接口返回数据不是有效的 JSON 格式: {str(e)}")
    except Exception as e:
        raise Exception(f"获取招标数据时发生未知错误: {str(e)}")
