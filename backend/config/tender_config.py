"""招标类型配置模块.

集中管理各种招标类型的配置参数，避免在多个节点文件中重复定义。
"""

from typing import Dict

# 招标类型对应的字体大小配置
# xjcg: 询价采购 - 小二 (18.0pt)
# gngk: 公开招标 - 二号 (22.0pt)
TARGET_SIZES: Dict[str, float] = {
    "xjcg": 18.0,
    "gngk": 22.0,
}


def get_target_size(tender_type: str) -> float:
    """获取指定招标类型的目标字号.

    Args:
        tender_type: 招标类型标识符 ('xjcg' 或 'gngk')

    Returns:
        目标字号（磅），如果类型未知则返回默认值 18.0
    """
    return TARGET_SIZES.get(tender_type, 18.0)
