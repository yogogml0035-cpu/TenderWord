"""
配置模块

此模块包含表单配置和基于接口 type 的路由系统。

导出：
- FormConfig: 表单配置类
- FORM_REGISTRY: 表单注册表
- match_form_by_type: 根据接口返回 type 匹配表单
"""

from .form_config import FormConfig, FORM_REGISTRY, match_form_by_type

__all__ = [
    "FormConfig",
    "FORM_REGISTRY",
    "match_form_by_type",
]
