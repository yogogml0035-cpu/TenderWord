"""
国内公开（服务 / 自筹）文档生成 Graph 模块。
"""

from __future__ import annotations

from typing import Callable

from backend.graphs.gngk_hw_zc_tender_graph import GngkHwZcTenderGraph
from backend.nodes.gngk_word_nodes import (
    gngk_fw_zc_delete_tender_param,
    gngk_fw_zc_get_replacements,
    gngk_fw_zc_update_word,
)


class GngkFwZcTenderGraph(GngkHwZcTenderGraph):
    """国内公开（服务 / 自筹）文档生成 Graph。"""

    NODE_DELETE_TENDER_PARAM: Callable = gngk_fw_zc_delete_tender_param
    NODE_GET_REPLACEMENTS: Callable = gngk_fw_zc_get_replacements
    NODE_UPDATE_WORD: Callable = gngk_fw_zc_update_word
