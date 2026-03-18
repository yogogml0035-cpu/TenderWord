"""
Generic rewrite workflow graph.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from backend.graphs.base_graph import BaseGraph
from backend.nodes.common_word_nodes import (
    delete_tender_param,
    get_rewrite_comments,
    update_word,
)
from backend.nodes.skills_nodes.rewrite_nodes import resolve_rewrite_target, rewrite_text
from backend.states import RewriteGraphState


class RewriteGraph(BaseGraph):
    STATE_CLS = RewriteGraphState

    def get_state_class(self):
        return self.STATE_CLS

    def estimate_total_nodes(self, initial_state: dict) -> int:
        return 5 if self._has_uploaded_origin_tender(initial_state) else 4

    @staticmethod
    def _has_uploaded_origin_tender(state: RewriteGraphState | dict) -> bool:
        if "source_origin_tender_path" not in state:
            return True
        path = state.get("source_origin_tender_path")
        return bool(path and str(path).strip())

    def _select_comment_branch(self, state: RewriteGraphState) -> str:
        return (
            "get_rewrite_comments"
            if self._has_uploaded_origin_tender(state)
            else "delete_section"
        )

    def build_graph(self) -> StateGraph:
        builder = StateGraph(self.STATE_CLS)
        builder.add_node(
            "resolve_rewrite_target",
            self.wrap_node("resolve_rewrite_target", resolve_rewrite_target),
        )
        builder.add_node(
            "get_rewrite_comments",
            self.wrap_node("get_rewrite_comments", get_rewrite_comments),
        )
        builder.add_node(
            "delete_section",
            self.wrap_node("delete_section", delete_tender_param),
        )
        builder.add_node(
            "rewrite_text",
            self.wrap_node("rewrite_text", rewrite_text),
        )
        builder.add_node(
            "update_word",
            self.wrap_node("update_word", update_word),
        )

        builder.add_edge(START, "resolve_rewrite_target")
        builder.add_conditional_edges(
            "resolve_rewrite_target",
            self._select_comment_branch,
            {
                "get_rewrite_comments": "get_rewrite_comments",
                "delete_section": "delete_section",
            },
        )
        builder.add_edge("get_rewrite_comments", "delete_section")
        builder.add_edge("resolve_rewrite_target", "rewrite_text")
        builder.add_edge(["delete_section", "rewrite_text"], "update_word")
        builder.add_edge("update_word", END)
        return builder
