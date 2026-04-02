"""
国内公开（财政）文档生成 Graph 模块。
"""

from __future__ import annotations

from backend.graphs.gngk_zc_tender_graph import GngkZcTenderGraph


class GngkCzTenderGraph(GngkZcTenderGraph):
    """国内公开（财政）文档生成 Graph。

    节点编排与自筹版完全一致，仅入口 form_type 不同。
    """
