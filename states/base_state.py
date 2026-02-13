"""
Base State module for the project refactoring.

This module defines TypedDict schemas shared by LangGraph state objects.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, TypedDict


class BaseState(TypedDict, total=False):
    """
    基础 State 类，定义所有 graph 共享的字段
    
    使用 total=False 允许字段可选，提高灵活性。
    所有具体的 state 类都应该继承此类以获得通用字段。
    
    字段说明：
        task_id: 任务ID，用于进度追踪和取消
        user_session_id: 用户会话ID，用于多用户隔离
        tender_type: 招标类型标识符（"xjcg"、"gngk" 等）
    
    使用示例：
        class MyGraphState(BaseState):
            # 添加特定字段
            my_field: str
            another_field: int
    """
    # 任务标识
    task_id: str                    # 任务ID，用于进度追踪和取消
    user_session_id: str            # 用户会话ID，用于多用户隔离
    tender_type: str                # 招标类型标识符（"xjcg"、"gngk" 等）


class CommentInstruction(TypedDict):
    reference_text: str
    comment_text: str


class TenderGraphStateBase(BaseState, total=False):
    origin_tender_path: str
    tender_param_paths: List[str]
    clean_draft_path: Optional[str]
    prepared_doc_path: str

    origin_tender_params: str
    tender_params: str
    polished_text: str

    replacements: List[Tuple[str, str]]
    placeholder_mapping: Dict[str, str]
    insertion_before_text: str
    insertion_after_text: str

    comment_plan_detail: List[Dict[str, Any]]
    strikethrough_plan: List[Dict[str, Any]]
    non_black_font_plan: List[Dict[str, Any]]
    polished_comments: List[CommentInstruction]

    insertion_log: str
    replacement_log: str
    copy_comments_log: str
    copy_comments_added: int
    copy_comments_unmatched: List[Dict[str, Any]]
    comments_summary: str

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
    
    generate_polished_done: bool
    replace_content_done: bool
    
