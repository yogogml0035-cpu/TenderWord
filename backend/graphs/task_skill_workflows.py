from __future__ import annotations

from backend.nodes.common_word_nodes import get_rewrite_comments
from backend.nodes.skills_nodes.edit_nodes import (
    edit_text,
    extract_edit_context,
    resolve_edit_target,
)
from backend.nodes.skills_nodes.rewrite_nodes import resolve_rewrite_target, rewrite_text
from backend.nodes.skills_nodes.tender_aware_word_dispatch import (
    dispatch_tender_aware_delete_section,
    dispatch_tender_aware_update_word,
)
from backend.skills.edit.scripts.runtime import estimate_total_nodes as estimate_edit_nodes
from backend.skills.rewrite.scripts.runtime import (
    estimate_total_nodes as estimate_rewrite_nodes,
)
from backend.skills.rewrite.scripts.runtime import select_comment_branch
from backend.states import TaskSkillGraphState

from .task_skill_types import (
    TaskSkillConditionalEdge,
    TaskSkillWorkflow,
    TaskSkillWorkflowNode,
)


_TASK_SKILL_WORKFLOWS = {
    "rewrite": TaskSkillWorkflow(
        skill_id="rewrite",
        state_cls=TaskSkillGraphState,
        start_node="resolve_rewrite_target",
        end_node="update_word",
        nodes=(
            TaskSkillWorkflowNode("resolve_rewrite_target", resolve_rewrite_target),
            TaskSkillWorkflowNode("get_rewrite_comments", get_rewrite_comments),
            TaskSkillWorkflowNode("delete_section", dispatch_tender_aware_delete_section),
            TaskSkillWorkflowNode("rewrite_text", rewrite_text),
            TaskSkillWorkflowNode("update_word", dispatch_tender_aware_update_word),
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
        total_nodes_estimator=estimate_rewrite_nodes,
    ),
    "edit": TaskSkillWorkflow(
        skill_id="edit",
        state_cls=TaskSkillGraphState,
        start_node="resolve_edit_target",
        end_node="update_word",
        nodes=(
            TaskSkillWorkflowNode("resolve_edit_target", resolve_edit_target),
            TaskSkillWorkflowNode("extract_edit_context", extract_edit_context),
            TaskSkillWorkflowNode("delete_section", dispatch_tender_aware_delete_section),
            TaskSkillWorkflowNode("edit_text", edit_text),
            TaskSkillWorkflowNode("update_word", dispatch_tender_aware_update_word),
        ),
        edges=(
            ("resolve_edit_target", "extract_edit_context"),
            ("extract_edit_context", "delete_section"),
            ("extract_edit_context", "edit_text"),
        ),
        waiting_edges=(
            (("delete_section", "edit_text"), "update_word"),
        ),
        total_nodes_estimator=estimate_edit_nodes,
    ),
}


def get_task_skill_workflow(skill_id: str) -> TaskSkillWorkflow:
    normalized_skill_id = str(skill_id or "").strip()
    try:
        return _TASK_SKILL_WORKFLOWS[normalized_skill_id]
    except KeyError as exc:
        raise KeyError(f"未注册的 task skill workflow: {normalized_skill_id}") from exc
