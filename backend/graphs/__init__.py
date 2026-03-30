"""
Graphs 模块

该模块包含所有 Graph 类的定义。

目录结构：
- base_graph.py: 基础 Graph 类，提供通用功能
- xjcg_tender_graph.py: 询价采购文档生成 Graph
- [future_graph].py: 未来的新 Graph

使用示例：
    from backend.graphs import XjcgTenderGraph
    
    graph = XjcgTenderGraph()
    compiled_graph = graph.compile()
    result = graph.invoke(initial_state)
"""

from .base_graph import (
    BaseGraph,
    CrossProcessFileLock,
    TaskCancelledException,
    wrap_node_with_progress,
    invoke_with_timing,
    invoke_with_timing_async,
)
from .skill_graph import SkillGraph
from .xjcg_tender_graph import XjcgTenderGraph
from .gngk_tender_graph import GngkTenderGraph
from .gjgk_tender_graph import GjgkTenderGraph
from .user_graph import UserGraph

__all__ = [
    "BaseGraph",
    "CrossProcessFileLock",
    "TaskCancelledException",
    "wrap_node_with_progress",
    "invoke_with_timing",
    "invoke_with_timing_async",
    "SkillGraph",
    "XjcgTenderGraph",
    "GngkTenderGraph",
    "GjgkTenderGraph",
    "UserGraph",
]
