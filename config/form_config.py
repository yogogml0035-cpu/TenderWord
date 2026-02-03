"""
表单配置模块

提供表单配置类和 URL 参数匹配功能，支持基于 URL 参数的表单路由。

主要组件：
- FormConfig: 表单配置数据类
- FORM_REGISTRY: 表单配置注册表
- match_form_by_url_params: URL 参数匹配函数
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
        url_params={"tender_lx": 1, "purchase_method": 1, "fund_lx": 0},
        description="生成国内公开招标采购文件"
    ),
}


def match_form_by_url_params(
    tender_lx: Optional[str],
    purchase_method: Optional[str],
    fund_lx: Optional[str]
) -> Optional[FormConfig]:
    """
    根据 URL 参数匹配表单配置
    
    此函数用于表单路由系统，根据 URL 中的参数组合匹配对应的表单配置。
    如果找到匹配的配置，返回该配置；否则返回 None。
    
    Args:
        tender_lx: 招标类型参数（字符串格式）
                  - "0": 询价
                  - "1": 公开招标
                  - "2": 邀请招标
        purchase_method: 采购方式参数（字符串格式）
                        - "5": 询价采购
                        - "1": 公开招标
                        - "2": 邀请招标
        fund_lx: 资金类型参数（字符串格式）
                - "0": 国内
                - "1": 国际
    
    Returns:
        匹配的表单配置对象，如果没有匹配则返回 None
    
    Examples:
        >>> # 匹配询价采购表单
        >>> config = match_form_by_url_params("0", "5", "0")
        >>> config.form_id
        'xjcg_tender'
        
        >>> # 参数不匹配，返回 None
        >>> config = match_form_by_url_params("1", "1", "0")
        >>> config is None
        True
        
        >>> # 参数缺失，返回 None
        >>> config = match_form_by_url_params(None, "5", "0")
        >>> config is None
        True
    
    Notes:
        - 所有参数都必须提供，缺少任何一个参数都会返回 None
        - 参数必须是有效的整数字符串，否则返回 None
        - 参数组合必须完全匹配注册表中的某个配置
    """
    # 检查是否所有参数都提供了
    if not all([tender_lx, purchase_method, fund_lx]):
        return None
    
    # 尝试将字符串参数转换为整数
    try:
        params = {
            "tender_lx": int(tender_lx),
            "purchase_method": int(purchase_method),
            "fund_lx": int(fund_lx)
        }
    except (ValueError, TypeError):
        # 参数格式不正确，返回 None
        return None
    
    # 遍历注册表，查找匹配的表单配置
    for form_config in FORM_REGISTRY.values():
        if form_config.url_params == params:
            return form_config
    
    # 没有找到匹配的配置
    return None
