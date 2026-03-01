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

from typing import Any, Dict, List

from .base_state import TenderGraphStateBase


class XjcgTenderGraphState(TenderGraphStateBase, total=False):
    """
    询价采购 Graph 的主状态类

    继承自 TenderGraphStateBase，添加了询价采购招标特有的字段。
    """
