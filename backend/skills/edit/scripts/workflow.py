from __future__ import annotations

from backend.nodes.skills_nodes.edit_nodes import (
    edit_text,
    extract_edit_context,
    resolve_edit_target,
)
from backend.nodes.skills_nodes.tender_aware_word_dispatch import (
    dispatch_tender_aware_delete_section,
    dispatch_tender_aware_update_word,
)
from backend.skills.edit.scripts.runtime import estimate_total_nodes
from backend.skills.types import TaskSkillWorkflow, TaskSkillWorkflowNode
from backend.states import TaskSkillGraphState


def get_workflow() -> TaskSkillWorkflow:
    return TaskSkillWorkflow(
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
        total_nodes_estimator=estimate_total_nodes,
    )
