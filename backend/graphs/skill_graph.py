"""Rewrite skill graph.

显式实现 rewrite 任务流程的 LangGraph，取代原先 SkillGraph.for_skill +
TaskSkillWorkflow 的元数据驱动框架。当前只服务 rewrite 一种 skill，
节点、边、条件分支直接写在这里，便于阅读和维护。
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from backend.graphs.base_graph import BaseGraph
from backend.nodes.common_word_nodes import get_rewrite_comments
from backend.nodes.skills_nodes.rewrite_nodes import (
    extract_rewrite_context,
    resolve_rewrite_target,
    rewrite_text,
)
from backend.nodes.skills_nodes.tender_aware_word_dispatch import (
    dispatch_tender_aware_delete_section,
    dispatch_tender_aware_update_word,
)
from backend.skills.rewrite.scripts.runtime import (
    estimate_total_nodes as estimate_rewrite_nodes,
)
from backend.skills.rewrite.scripts.runtime import select_comment_branch, select_resolve_branch
from backend.states import TaskSkillGraphState


# rewrite 流程的节点名称顺序，供测试与诊断引用
REWRITE_NODE_NAMES = (
    "resolve_rewrite_target",
    "extract_rewrite_context",
    "get_rewrite_comments",
    "delete_section",
    "rewrite_text",
    "update_word",
)

REWRITE_START_NODE = "resolve_rewrite_target"
REWRITE_END_NODE = "update_word"

# 节点名称 -> 处理函数
REWRITE_NODE_HANDLERS = {
    "resolve_rewrite_target": resolve_rewrite_target,
    "extract_rewrite_context": extract_rewrite_context,
    "get_rewrite_comments": get_rewrite_comments,
    "delete_section": dispatch_tender_aware_delete_section,
    "rewrite_text": rewrite_text,
    "update_word": dispatch_tender_aware_update_word,
}


class RewriteSkillGraph(BaseGraph):
    """rewrite 任务的显式 graph 实现。"""

    def get_state_class(self):
        return TaskSkillGraphState

    def estimate_total_nodes(self, initial_state: dict) -> int:
        return max(1, int(estimate_rewrite_nodes(initial_state)))

    def build_graph(self) -> StateGraph:
        builder = StateGraph(TaskSkillGraphState)

        for node_name in REWRITE_NODE_NAMES:
            builder.add_node(node_name, self.wrap_node(node_name, REWRITE_NODE_HANDLERS[node_name]))

        builder.add_edge(START, REWRITE_START_NODE)
        builder.add_edge("get_rewrite_comments", "delete_section")
        builder.add_edge("extract_rewrite_context", "rewrite_text")
        builder.add_edge(["delete_section", "rewrite_text"], "update_word")

        builder.add_conditional_edges(
            "resolve_rewrite_target",
            select_resolve_branch,
            {
                "extract_rewrite_context": "extract_rewrite_context",
                "rewrite_text": "rewrite_text",
            },
        )
        builder.add_conditional_edges(
            "rewrite_text",
            select_comment_branch,
            {
                "get_rewrite_comments": "get_rewrite_comments",
                "delete_section": "delete_section",
            },
        )
        builder.add_edge(REWRITE_END_NODE, END)
        return builder
