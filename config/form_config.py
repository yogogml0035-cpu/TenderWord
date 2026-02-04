"""
表单配置模块

提供表单配置和基于接口返回 type 的表单路由（不再通过 URL 传 tender_lx/purchase_method/fund_lx）。

主要组件：
- FormConfig: 表单配置数据类
- FORM_REGISTRY: 表单配置注册表
- match_form_by_type: 根据接口返回的 type 匹配表单
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class FormConfig:
    """
    表单配置类
    
    封装表单的元数据和 URL 参数映射，用于表单路由系统。
    
    Attributes:
        form_id: 表单唯一标识符（如 "xjcg_tender"）
        tab_name: 显示的标签名称（如 "生成询价采购文件"）
        graph_name: 关联的 graph 名称（如 "xjcg_tender_graph"）
        state_name: 关联的 state 名称（如 "XjcgTenderGraphState"）
        url_params: URL 参数映射字典，用于匹配表单
                   例如: {"tender_lx": 0, "purchase_method": 5, "fund_lx": 0}
        description: 表单描述（可选）
    
    Examples:
        >>> config = FormConfig(
        ...     form_id="xjcg_tender",
        ...     tab_name="生成询价采购文件",
        ...     graph_name="xjcg_tender_graph",
        ...     state_name="XjcgTenderGraphState",
        ...     url_params={"tender_lx": 0, "purchase_method": 5, "fund_lx": 0},
        ...     description="生成询价采购文件（现有功能）"
        ... )
    """
    form_id: str
    tab_name: str
    graph_name: str
    state_name: str
    url_params: Dict[str, int]
    description: str = ""


# 表单配置注册表
# 所有表单配置都应在此注册，以便表单路由系统使用
FORM_REGISTRY: Dict[str, FormConfig] = {
    "xjcg_tender": FormConfig(
        form_id="xjcg_tender",
        tab_name="生成询价采购文件",
        graph_name="xjcg_tender_graph",
        state_name="XjcgTenderGraphState",
        url_params={"tender_lx": 0, "purchase_method": 5, "fund_lx": 0},
        description="生成询价采购文件（现有功能）"
    ),
    "gngk_tender": FormConfig(
        form_id="gngk_tender",
        tab_name="生成国内公开招标文件",
        graph_name="gngk_tender_graph",
        state_name="GngkTenderGraphState",
        url_params={"tender_lx": 0, "purchase_method": 2, "fund_lx": 0},
        description="生成国内公开招标采购文件"
    ),
}


def match_form_by_type(type_dict: Optional[Dict]) -> Optional[FormConfig]:
    """
    根据接口返回的 type 匹配表单配置（不再通过 URL 传 tender_lx/purchase_method/fund_lx）。
    
    用于表单路由：在应用层根据 tenderno 调接口拿到 data+type 后，用 type 决定展示哪个表单。
    
    Args:
        type_dict: 接口返回的 type 字典，格式 {"tender_lx": int, "purchase_method": int, "fund_lx": int}
                   例如 {"tender_lx": 0, "purchase_method": 2, "fund_lx": 0} 为国内公开，
                   {"tender_lx": 0, "purchase_method": 5, "fund_lx": 0} 为询价采购。
    
    Returns:
        匹配的表单配置对象，如果没有匹配则返回 None
    
    Examples:
        >>> config = match_form_by_type({"tender_lx": 0, "purchase_method": 5, "fund_lx": 0})
        >>> config.form_id
        'xjcg_tender'
        >>> config = match_form_by_type({"tender_lx": 0, "purchase_method": 2, "fund_lx": 0})
        >>> config.form_id
        'gngk_tender'
        >>> match_form_by_type(None) is None
        True
    """
    if not type_dict or not isinstance(type_dict, dict):
        return None
    try:
        params = {
            "tender_lx": int(type_dict.get("tender_lx")),
            "purchase_method": int(type_dict.get("purchase_method")),
            "fund_lx": int(type_dict.get("fund_lx")),
        }
    except (ValueError, TypeError):
        return None
    for form_config in FORM_REGISTRY.values():
        if form_config.url_params == params:
            return form_config
    return None
