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
    国内公开招标 Graph 的主状态类

    继承自 TenderGraphStateBase，添加了国内公开招标特有的字段。

    """
    project_content_v1: str
