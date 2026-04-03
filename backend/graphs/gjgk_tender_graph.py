"""国际公开文档生成 Graph 模块。"""

from __future__ import annotations

from typing import Callable

from backend.graphs.base_graph import StandardTenderWorkflowGraph
from backend.nodes.common_word_nodes import (
    copy_comments,
    extract_tender_params,
    generate_comments,
    generate_polished_text,
    get_comments,
    prepare_template,
    replace_content,
)
from backend.nodes.gjgk_word_nodes import (
    gjgk_delete_tender_param,
    gjgk_get_replacements,
)
from backend.nodes.gjgk_word_nodes.gjgk_update_word import gjgk_update_word
from backend.states import GjgkTenderGraphState


class GjgkTenderGraph(StandardTenderWorkflowGraph):
    """国际公开文档生成 Graph。"""

    STATE_CLS = GjgkTenderGraphState

    NODE_PREPARE_TEMPLATE: Callable = prepare_template
    NODE_GET_COMMENTS: Callable = get_comments
    NODE_COPY_COMMENTS: Callable = copy_comments
    NODE_EXTRACT_TENDER_PARAMS: Callable = extract_tender_params
    NODE_DELETE_TENDER_PARAM: Callable = gjgk_delete_tender_param
    NODE_GET_REPLACEMENTS: Callable = gjgk_get_replacements
    NODE_REPLACE_CONTENT: Callable = replace_content
    NODE_GENERATE_POLISHED_TEXT: Callable = generate_polished_text
    NODE_GENERATE_COMMENTS: Callable = generate_comments
    NODE_UPDATE_WORD: Callable = gjgk_update_word

    def get_word_operation_steps(self) -> tuple[tuple[str, Callable], ...]:
        return (
            ("delete_tender_param", type(self).NODE_DELETE_TENDER_PARAM),
            ("get_replacements", type(self).NODE_GET_REPLACEMENTS),
        )

    def get_post_update_steps(self) -> tuple[tuple[str, Callable], ...]:
        return (("replace_content", type(self).NODE_REPLACE_CONTENT),)
