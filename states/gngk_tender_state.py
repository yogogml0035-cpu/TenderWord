"""
国内公开招标文档生成 State 定义

本模块定义了国内公开招标文档生成 Graph 使用的状态类：
- GngkTenderGraphState: 国内公开招标 Graph 的主状态类
- TextFormatState: 文本格式化子图的状态类
- CommentInstruction: 批注指令类型定义

这些状态类继承自 BaseState，获得通用字段（task_id, user_session_id, tender_type）。

需求引用：2.2, 3.2.3
"""

from __future__ import annotations

from typing import Any, Annotated, Dict, List, Tuple, TypedDict
from operator import or_

from .base_state import TenderGraphStateBase, CommentInstruction


class GngkTenderGraphState(TenderGraphStateBase, total=False):
    """
    国内公开招标文档生成 Graph 的状态定义
    
    继承自 BaseState，包含国内公开招标文档生成过程中的所有状态字段。
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
        comment_plan: 批注指令列表
        comments_summary: 批注添加结果摘要
    
    日志相关字段：
        insertion_log: Word 写入过程的状态记录
        replacement_log: 内容替换过程的状态记录
    
    项目信息字段：
        project_name: 项目名称
        project_number: 项目编号
        project_content: 项目名称及数量
        project_content_v1: 项目内容（第二章 项目名称下一段至招标人前）
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
        similar_project_performance_date: 类似项目业绩日期（自xxxx年xx月xx日至今）
    
    执行状态字段：
        generate_polished_done: generate_polished_text 节点是否完成
        replace_content_done: replace_content 节点是否完成
    """

    clean_draft_path: str
    project_content_v1: str
