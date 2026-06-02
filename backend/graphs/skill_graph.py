"""Generic task-skill graph driven by skill workflow metadata."""

from __future__ import annotations

from typing import Optional

from langgraph.graph import END, START, StateGraph

from backend.graphs.base_graph import BaseGraph

from .task_skill_types import TaskSkillWorkflow
from .task_skill_workflows import get_task_skill_workflow


class SkillGraph(BaseGraph):
    SKILL_ID: Optional[str] = None

    def __init__(self, *, skill_id: Optional[str] = None):
        super().__init__()
        self._skill_id = str(skill_id or getattr(type(self), "SKILL_ID", "")).strip()
        if not self._skill_id:
            raise ValueError("SkillGraph 缺少 skill_id")
        self._workflow: Optional[TaskSkillWorkflow] = None

    @classmethod
    def for_skill(cls, skill_id: str) -> type["SkillGraph"]:
        normalized_skill_id = str(skill_id or "").strip()
        if not normalized_skill_id:
            raise ValueError("skill_id 不能为空")
        class_name = (
            "".join(part.capitalize() for part in normalized_skill_id.split("_"))
            + "SkillGraph"
        )
        return type(class_name, (cls,), {"SKILL_ID": normalized_skill_id})

    def _get_workflow(self) -> TaskSkillWorkflow:
        if self._workflow is None:
            self._workflow = get_task_skill_workflow(self._skill_id)
        return self._workflow

    def get_state_class(self):
        return self._get_workflow().state_cls

    def estimate_total_nodes(self, initial_state: dict) -> int:
        workflow = self._get_workflow()
        if workflow.total_nodes_estimator is None:
            return super().estimate_total_nodes(initial_state)
        return max(1, int(workflow.total_nodes_estimator(initial_state)))

    def build_graph(self) -> StateGraph:
        workflow = self._get_workflow()
        builder = StateGraph(workflow.state_cls)

        node_names = {node.name for node in workflow.nodes}
        if workflow.start_node not in node_names:
            raise ValueError(
                f"skill workflow start_node 未注册: skill={workflow.skill_id}, node={workflow.start_node}"
            )
        if workflow.end_node not in node_names:
            raise ValueError(
                f"skill workflow end_node 未注册: skill={workflow.skill_id}, node={workflow.end_node}"
            )

        for node in workflow.nodes:
            builder.add_node(node.name, self.wrap_node(node.name, node.handler))

        builder.add_edge(START, workflow.start_node)
        for start, end in workflow.edges:
            builder.add_edge(start, end)
        for starts, end in workflow.waiting_edges:
            builder.add_edge(list(starts), end)
        for conditional_edge in workflow.conditional_edges:
            builder.add_conditional_edges(
                conditional_edge.start,
                conditional_edge.condition,
                dict(conditional_edge.mapping),
            )
        builder.add_edge(workflow.end_node, END)
        return builder
