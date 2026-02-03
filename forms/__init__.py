"""
Forms module for the project refactoring.

This module contains form classes and the create_form factory function.
Forms are responsible for:
- Rendering user input interfaces
- Validating user inputs
- Preparing initial state for graph execution

Exports:
- BaseForm: Base class for all forms
- XjcgTenderForm: Form for inquiry procurement document generation
- GngkTenderForm: Form for domestic public tender document generation
- create_form: Factory function to create form instances
"""

from .base_form import BaseForm
from .xjcg_tender_form import XjcgTenderForm
from .gngk_tender_form import GngkTenderForm


def create_form(form_config):
    """
    表单工厂函数
    
    根据表单配置创建对应的表单实例。
    
    Args:
        form_config: 表单配置对象（FormConfig 实例），包含 form_id 等元数据
    
    Returns:
        对应的表单实例（BaseForm 子类）
    
    Raises:
        ValueError: 如果 form_id 未知或未注册
    
    Examples:
        >>> from config.form_config import FORM_REGISTRY
        >>> config = FORM_REGISTRY["xjcg_tender"]
        >>> form = create_form(config)
        >>> isinstance(form, XjcgTenderForm)
        True
    
    Notes:
        - 新增表单时，需要在 form_map 中注册对应的表单类
        - 表单类必须继承自 BaseForm
        - 表单类必须实现所有抽象方法
    """
    # 表单类映射表
    # 新增表单时，在此添加映射关系
    form_map = {
        "xjcg_tender": XjcgTenderForm,
        "domestic_public_tender": XjcgTenderForm,  # 暂时复用现有表单类
        "gngk_tender": GngkTenderForm,  # 国内公开招标表单
    }
    
    # 获取表单类
    form_class = form_map.get(form_config.form_id)
    if not form_class:
        raise ValueError(f"Unknown form_id: {form_config.form_id}")
    
    # 创建并返回表单实例
    return form_class(form_config)


__all__ = ["BaseForm", "XjcgTenderForm", "GngkTenderForm", "create_form"]
