from __future__ import annotations

from pathlib import Path
from typing import Mapping, Optional

from backend.skills.loader import load_skill_definitions
from backend.skills.types import SkillDefinition, SkillExecutorBinding, SkillSummary


DEFAULT_TASK_SKILL_BINDINGS: dict[str, SkillExecutorBinding] = {
    "rewrite": SkillExecutorBinding(
        skill_id="rewrite",
        executor_kind="task",
        dispatch_key="rewrite",
        route_literal="rewrite",
    )
}


class SkillRegistry:
    def __init__(
        self,
        definitions: tuple[SkillDefinition, ...],
        executor_bindings: Mapping[str, SkillExecutorBinding],
    ):
        self._definitions = definitions
        self._definitions_by_name = {item.name: item for item in definitions}
        self._executor_bindings = dict(executor_bindings)

    def list_definitions(self) -> tuple[SkillDefinition, ...]:
        return self._definitions

    def list_skill_summaries(self) -> tuple[SkillSummary, ...]:
        return tuple(item.as_summary() for item in self._definitions)

    def list_skill_ids(self) -> tuple[str, ...]:
        return tuple(item.name for item in self._definitions)

    def get_definition(self, skill_id: str) -> SkillDefinition:
        try:
            return self._definitions_by_name[skill_id]
        except KeyError as exc:
            raise KeyError(f"未注册的 skill: {skill_id}") from exc

    def get_executor_binding(self, skill_id: str) -> SkillExecutorBinding:
        try:
            return self._executor_bindings[skill_id]
        except KeyError as exc:
            raise KeyError(f"skill 未绑定执行器: {skill_id}") from exc


def build_skill_registry(
    *,
    skills_root: Path | None = None,
    executor_bindings: Mapping[str, SkillExecutorBinding] | None = None,
) -> SkillRegistry:
    resolved_bindings = dict(
        DEFAULT_TASK_SKILL_BINDINGS if executor_bindings is None else executor_bindings
    )
    definitions = load_skill_definitions(skills_root)
    definition_names = {item.name for item in definitions}
    binding_names = set(resolved_bindings)

    missing_bindings = sorted(definition_names - binding_names)
    if missing_bindings:
        raise ValueError(
            "存在 skill 但没有同名后端执行器: "
            + ", ".join(missing_bindings)
        )

    missing_definitions = sorted(binding_names - definition_names)
    if missing_definitions:
        raise ValueError(
            "存在后端执行器绑定但缺少对应 SKILL.md: "
            + ", ".join(missing_definitions)
        )

    return SkillRegistry(definitions=definitions, executor_bindings=resolved_bindings)


_skill_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = build_skill_registry()
    return _skill_registry
