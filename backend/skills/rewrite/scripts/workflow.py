from __future__ import annotations

from backend.nodes.common_word_nodes import (
    delete_tender_param,
    get_rewrite_comments,
    update_word,
)
from backend.nodes.skills_nodes.rewrite_nodes import resolve_rewrite_target, rewrite_text
from backend.skills.types import (
    TaskSkillConditionalEdge,
    TaskSkillWorkflow,
    TaskSkillWorkflowNode,
)
from backend.skills.rewrite.scripts.runtime import estimate_total_nodes, select_comment_branch
from backend.states import TaskSkillGraphState


def get_workflow() -> TaskSkillWorkflow:
    return TaskSkillWorkflow(
        skill_id="rewrite",
        state_cls=TaskSkillGraphState,
        start_node="resolve_rewrite_target",
        end_node="update_word",
        nodes=(
            TaskSkillWorkflowNode("resolve_rewrite_target", resolve_rewrite_target),
            TaskSkillWorkflowNode("get_rewrite_comments", get_rewrite_comments),
            TaskSkillWorkflowNode("delete_section", delete_tender_param),
            TaskSkillWorkflowNode("rewrite_text", rewrite_text),
            TaskSkillWorkflowNode("update_word", update_word),
        ),
        edges=(
            ("get_rewrite_comments", "delete_section"),
            ("resolve_rewrite_target", "rewrite_text"),
        ),
        waiting_edges=(
            (("delete_section", "rewrite_text"), "update_word"),
        ),
        conditional_edges=(
            TaskSkillConditionalEdge(
                start="resolve_rewrite_target",
                condition=select_comment_branch,
                mapping={
                    "get_rewrite_comments": "get_rewrite_comments",
                    "delete_section": "delete_section",
                },
            ),
        ),
        total_nodes_estimator=estimate_total_nodes,
    )
