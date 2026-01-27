"""
配置模块

此模块包含表单配置和路由系统。

导出：
- FormConfig: 表单配置类
- FORM_REGISTRY: 表单注册表
- match_form_by_url_params: URL 参数匹配函数
"""

from .form_config import FormConfig, FORM_REGISTRY, match_form_by_url_params

__all__ = [
    "FormConfig",
    "FORM_REGISTRY",
    "match_form_by_url_params",
]
