"""
国内公开（货物 / 财政）文档生成 Graph 模块。
"""

from __future__ import annotations

from typing import Callable

from backend.graphs.gngk_hw_zc_tender_graph import GngkHwZcTenderGraph
from backend.nodes.gngk_word_nodes import (
    gngk_hw_cz_delete_tender_param,
    gngk_hw_cz_update_word,
)


class GngkHwCzTenderGraph(GngkHwZcTenderGraph):
    """国内公开（货物 / 财政）文档生成 Graph。"""

    NODE_DELETE_TENDER_PARAM: Callable = gngk_hw_cz_delete_tender_param
    NODE_UPDATE_WORD: Callable = gngk_hw_cz_update_word
