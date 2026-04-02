"""
国内公开（自筹）文档生成 Graph 模块。
"""

from __future__ import annotations
from typing import Callable

from backend.graphs.base_graph import StandardTenderWorkflowGraph
from backend.states import GngkTenderGraphState
from backend.nodes.common_word_nodes import (
    prepare_template,
    generate_polished_text,
    replace_content,
    get_comments,
    copy_comments,
    generate_comments,
    delete_tender_param,
    update_word,
)
from backend.nodes.common_word_nodes import extract_tender_params
from backend.nodes.gngk_word_nodes import get_replacements


class GngkZcTenderGraph(StandardTenderWorkflowGraph):
    """国内公开（自筹）文档生成 Graph。"""

    STATE_CLS = GngkTenderGraphState

    NODE_PREPARE_TEMPLATE: Callable = prepare_template
    NODE_GET_COMMENTS: Callable = get_comments
    NODE_COPY_COMMENTS: Callable = copy_comments
    NODE_EXTRACT_TENDER_PARAMS: Callable = extract_tender_params
    NODE_DELETE_TENDER_PARAM: Callable = delete_tender_param
    NODE_GET_REPLACEMENTS: Callable = get_replacements
    NODE_REPLACE_CONTENT: Callable = replace_content
    NODE_GENERATE_POLISHED_TEXT: Callable = generate_polished_text
    NODE_GENERATE_COMMENTS: Callable = generate_comments
    NODE_UPDATE_WORD: Callable = update_word
