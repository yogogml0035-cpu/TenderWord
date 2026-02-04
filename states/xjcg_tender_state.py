"""
询价采购文档生成 State 定义

本模块定义了询价采购文档生成 Graph 使用的状态类：
- XjcgTenderGraphState: 询价采购 Graph 的主状态类
- TextFormatState: 文本格式化子图的状态类
- CommentInstruction: 批注指令类型定义

这些状态类继承自 BaseState，获得通用字段（task_id, user_session_id）。

需求引用：2.2, 3.2.3
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, TypedDict

from .base_state import BaseState


class CommentInstruction(TypedDict):
    """
    批注指令类型定义
    
    用于描述需要在 Word 文档中添加的批注信息。
    
    Attributes:
        reference_text: 批注引用的文本内容
        comment_text: 批注的具体内容
    """
    reference_text: str
    comment_text: str


class XjcgTenderGraphState(BaseState):
    """
    询价采购文档生成 Graph 的状态定义
    
    继承自 BaseState，包含询价采购文档生成过程中的所有状态字段。
    使用 total=False 允许字段可选，提高灵活性。
    
    文件路径相关字段：
        origin_tender_path: 技术需求草稿文件路径
        tender_param_paths: 技术参数文件路径列表
        prepared_doc_path: 当前加工中的文档路径
    
    内容相关字段：
        origin_tender_params: 上一次项目文档参考的技术参数内容
        tender_params: 技术参数内容
        polished_text: 大模型润色后的文本
    
    替换和插入相关字段：
        replacements: Word 模板替换对列表
        placeholder_mapping: 字段名到占位符的映射关系
        insertion_before_text: 插入位置的前置文本
        insertion_after_text: 插入位置的后置文本
    
    批注相关字段：
        review_draft_path: 送审稿文件路径（可选）
        comment_plan: 从送审稿文档提取的批注内容文本列表（兼容旧逻辑）
        comment_plan_detail: 批注详情列表（作者、日期、内容、范围、页码）
        strikethrough_plan: 删除线段落列表（段落原文、删除线内容、页码）
        non_black_font_plan: 非黑色字体列表（段落原文、非黑字内容、颜色名、页码）
        comments_summary: 批注添加结果摘要
    
    日志相关字段：
        insertion_log: Word 写入过程的状态记录
        replacement_log: 内容替换过程的状态记录
    
    项目信息字段：
        project_name: 项目名称
        project_number: 项目编号
        project_content: 项目名称及数量
        bzj_rule: 保证金规则
        buyer_name: 采购人名称
        project_zbr_xbr: 项目负责人和项目协助人
        zbr_xbr_tel: 负责人和协助人电话
        zbr_pinyin: 负责人拼音
        shell_start_date: 投标开始日期
        shell_end_date: 投标结束日期
        submit_date: 提交日期
        platform: 平台信息
        service_fee: 服务费
    
    执行状态字段：
        generate_polished_done: generate_polished_text 节点是否完成
        replace_content_done: replace_content 节点是否完成
    """
    # 文件路径
    origin_tender_path: str
    tender_param_paths: List[str]
    prepared_doc_path: str
    
    # 内容
    origin_tender_params: str
    tender_params: str
    polished_text: str
    
    # 替换和插入
    replacements: List[Tuple[str, str]]
    placeholder_mapping: Dict[str, str]
    insertion_before_text: str
    insertion_after_text: str
    
    # 批注
    review_draft_path: Optional[str]  # 送审稿文件路径
    comment_plan: List[str]  # 从送审稿文档提取的批注内容文本列表（兼容旧逻辑）
    comment_plan_detail: List[Dict[str, Any]]  # 批注详情（author, date, content, scope_text, page_number）
    strikethrough_plan: List[Dict[str, Any]]  # 删除线段落（paragraph_text, strikethrough_text, page_number）
    non_black_font_plan: List[Dict[str, Any]]  # 非黑色字体（paragraph_text, font_text, color_name, page_number）
    
    # 日志
    insertion_log: str
    replacement_log: str
    
    # 项目信息
    project_name: str
    project_number: str
    project_content: str
    bzj_rule: str
    buyer_name: str
    project_zbr_xbr: str
    zbr_xbr_tel: str
    zbr_pinyin: str
    shell_start_date: str
    shell_end_date: str
    submit_date: str
    platform: str
    service_fee: str
    
    # 执行状态
    generate_polished_done: bool
    replace_content_done: bool
