from __future__ import annotations

from typing import Callable, Type

from langgraph.graph import END, START, StateGraph

from backend.graphs.base_graph import BaseGraph
from backend.nodes.common_word_nodes.comment_agent import comment_agent_writeback
from backend.nodes.common_word_nodes.comment_supplement import (
    finalize_comment_supplement,
    generate_comment_supplement_comments,
    prepare_comment_supplement,
)
from backend.states import TenderGraphStateBase

NODE_PREPARE_COMMENT_SUPPLEMENT = "prepare_comment_supplement"
NODE_GENERATE_COMMENTS = "generate_comments"
NODE_COMMENT_AGENT = "comment_agent"
NODE_FINALIZE_COMMENT_SUPPLEMENT = "finalize_comment_supplement"

class CommentSupplementGraph(BaseGraph):
    """补充批注任务 graph，复用 BaseGraph 锁、取消检查和进度包装。"""

    STATE_CLS = TenderGraphStateBase

    NODE_PREPARE_COMMENT_SUPPLEMENT: Callable = prepare_comment_supplement
    NODE_GENERATE_COMMENTS: Callable = generate_comment_supplement_comments
    NODE_COMMENT_AGENT: Callable = comment_agent_writeback
    NODE_FINALIZE_COMMENT_SUPPLEMENT: Callable = finalize_comment_supplement

    def get_state_class(self) -> Type[TenderGraphStateBase]:
        return self.STATE_CLS

    def estimate_total_nodes(self, initial_state: dict) -> int:
        del initial_state
        return 4

    def build_graph(self) -> StateGraph:
        builder = StateGraph(self.STATE_CLS)

        builder.add_node(
            NODE_PREPARE_COMMENT_SUPPLEMENT,
            self.wrap_node(
                NODE_PREPARE_COMMENT_SUPPLEMENT,
                getattr(type(self), "NODE_PREPARE_COMMENT_SUPPLEMENT"),
            ),
        )
        builder.add_node(
            NODE_GENERATE_COMMENTS,
            self.wrap_node(
                NODE_GENERATE_COMMENTS,
                getattr(type(self), "NODE_GENERATE_COMMENTS"),
            ),
        )
        builder.add_node(
            NODE_COMMENT_AGENT,
            self.wrap_node(
                NODE_COMMENT_AGENT,
                getattr(type(self), "NODE_COMMENT_AGENT"),
            ),
        )
        builder.add_node(
            NODE_FINALIZE_COMMENT_SUPPLEMENT,
            self.wrap_node(
                NODE_FINALIZE_COMMENT_SUPPLEMENT,
                getattr(type(self), "NODE_FINALIZE_COMMENT_SUPPLEMENT"),
            ),
        )

        builder.add_edge(START, NODE_PREPARE_COMMENT_SUPPLEMENT)
        builder.add_edge(NODE_PREPARE_COMMENT_SUPPLEMENT, NODE_GENERATE_COMMENTS)
        builder.add_edge(NODE_GENERATE_COMMENTS, NODE_COMMENT_AGENT)
        builder.add_edge(NODE_COMMENT_AGENT, NODE_FINALIZE_COMMENT_SUPPLEMENT)
        builder.add_edge(NODE_FINALIZE_COMMENT_SUPPLEMENT, END)
        return builder
