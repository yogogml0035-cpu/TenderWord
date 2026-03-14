from __future__ import annotations

import json
from typing import Dict

import requests


def fetch_tender_data(tender_no: str) -> Dict:
    """
    从接口获取招标数据

    接口返回格式为：
    {"data": {...}, "type": {"tender_lx": 0, "purchase_method": 2, "fund_lx": 0}}
    其中 type 用于表单路由（国内公开 0,2,0 / 询价采购 0,5,0）。

    Args:
        tender_no: 招标编号

    Returns:
        包含 "data" 与 "type" 的字典：
        - data: 招标业务数据（project_name、project_number 等）
        - type: 招标类型，用于匹配表单，格式 {"tender_lx": int, "purchase_method": int, "fund_lx": int}，
          若接口未返回则为 None

    Raises:
        requests.RequestException: 当接口请求失败时
        ValueError: 当返回数据格式不正确时
    """
    url = f"http://dserp.dongsong-cn.com/dongsong//servlet/tender.TenderJsonAction?tenderno={tender_no}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # 如果状态码不是 200，会抛出异常

        # 解析 JSON 响应
        result = response.json()

        # 检查返回数据结构
        if "data" not in result:
            raise ValueError("接口返回数据中缺少 'data' 字段")

        data = result["data"]
        # 提取所需字段
        tender_data = {
            "project_name": data.get("project_name", ""),
            "project_number": data.get("project_number", ""),
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
        }

        # 接口返回的 type 用于表单路由（不通过 URL 传 tender_lx/purchase_method/fund_lx）
        tender_type = result.get("type")

        return {"data": tender_data, "type": tender_type}

    except requests.exceptions.RequestException as e:
        raise requests.exceptions.RequestException(f"请求接口失败: {str(e)}")
    except json.JSONDecodeError as e:
        raise ValueError(f"接口返回数据不是有效的 JSON 格式: {str(e)}")
    except Exception as e:
        raise Exception(f"获取招标数据时发生未知错误: {str(e)}")
