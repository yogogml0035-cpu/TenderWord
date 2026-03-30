from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Type, TypedDict


@dataclass(frozen=True)
class SkillSummary:
    name: str
    description: str


@dataclass(frozen=True)
class SkillExecutorBinding:
    skill_id: str
    executor_kind: str
    dispatch_key: str
    route_literal: str


@dataclass(frozen=True)
class TaskSkillWorkflowNode:
    name: str
    handler: Callable[..., Any]


@dataclass(frozen=True)
class TaskSkillConditionalEdge:
    start: str
    condition: Callable[[Mapping[str, Any]], str]
    mapping: Mapping[str, str]


@dataclass(frozen=True)
class TaskSkillWorkflow:
    skill_id: str
    state_cls: Type[TypedDict]
    start_node: str
    end_node: str
    nodes: tuple[TaskSkillWorkflowNode, ...]
    edges: tuple[tuple[str, str], ...] = ()
    waiting_edges: tuple[tuple[tuple[str, ...], str], ...] = ()
    conditional_edges: tuple[TaskSkillConditionalEdge, ...] = ()
    total_nodes_estimator: Optional[Callable[[Mapping[str, Any]], int]] = None


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    description: str
    instruction: str
    source_path: str
    executor_binding: Optional[SkillExecutorBinding] = None
    workflow_entry: str = ""

    def as_summary(self) -> SkillSummary:
        return SkillSummary(name=self.name, description=self.description)
