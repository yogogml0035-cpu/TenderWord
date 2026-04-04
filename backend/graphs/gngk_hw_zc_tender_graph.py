"""
国内公开（货物 / 自筹）文档生成 Graph 模块。
"""

from __future__ import annotations

from typing import Callable

from backend.graphs.base_graph import StandardTenderWorkflowGraph
from backend.nodes.common_word_nodes import (
    copy_comments,
    delete_tender_param,
    generate_comments,
    generate_polished_text,
    get_comments,
    prepare_template,
    replace_content,
    update_word,
)
from backend.nodes.common_word_nodes import extract_tender_params
from backend.nodes.gngk_word_nodes import gngk_get_replacements
from backend.states import GngkTenderGraphState


class GngkHwZcTenderGraph(StandardTenderWorkflowGraph):
    """国内公开（货物 / 自筹）文档生成 Graph。"""

    STATE_CLS = GngkTenderGraphState

    NODE_PREPARE_TEMPLATE: Callable = prepare_template
    NODE_GET_COMMENTS: Callable = get_comments
    NODE_COPY_COMMENTS: Callable = copy_comments
    NODE_EXTRACT_TENDER_PARAMS: Callable = extract_tender_params
    NODE_DELETE_TENDER_PARAM: Callable = delete_tender_param
    NODE_GET_REPLACEMENTS: Callable = gngk_get_replacements
    NODE_REPLACE_CONTENT: Callable = replace_content
    NODE_GENERATE_POLISHED_TEXT: Callable = generate_polished_text
    NODE_GENERATE_COMMENTS: Callable = generate_comments
    NODE_UPDATE_WORD: Callable = update_word
