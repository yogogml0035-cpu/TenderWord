from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Optional

from backend.skills.loader import load_skill_definitions
from backend.skills.types import (
    SkillDefinition,
    SkillExecutorBinding,
    SkillSummary,
    TaskSkillWorkflow,
)


def _split_workflow_entry(workflow_entry: str, *, skill_id: str) -> tuple[str, str]:
    normalized_entry = str(workflow_entry or "").strip()
    if ":" not in normalized_entry:
        raise ValueError(
            f"skill workflow_entry 格式非法: skill={skill_id}, workflow_entry={normalized_entry!r}"
        )

    module_part, attr_name = normalized_entry.split(":", 1)
    normalized_module = module_part.strip().replace("/", ".").replace("\\", ".").strip(".")
    normalized_attr = attr_name.strip()
    if not normalized_module or not normalized_attr:
        raise ValueError(
            f"skill workflow_entry 格式非法: skill={skill_id}, workflow_entry={normalized_entry!r}"
        )
    return normalized_module, normalized_attr


def _resolve_workflow_module_path(skill_dir: Path, module_part: str, *, skill_id: str) -> Path:
    module_segments = [segment for segment in module_part.split(".") if segment]
    candidate_file = skill_dir.joinpath(*module_segments).with_suffix(".py")
    if candidate_file.is_file():
        return candidate_file

    package_init = skill_dir.joinpath(*module_segments, "__init__.py")
    if package_init.is_file():
        return package_init

    raise ValueError(
        f"skill workflow 入口文件不存在: skill={skill_id}, module={module_part!r}"
    )


def _load_task_workflow(definition: SkillDefinition) -> TaskSkillWorkflow:
    binding = definition.executor_binding
    if binding is None:
        raise ValueError(f"skill 未绑定执行器: {definition.name}")
    if binding.executor_kind != "task":
        raise ValueError(f"skill 不是 task executor，不能加载 workflow: {definition.name}")

    module_part, attr_name = _split_workflow_entry(
        definition.workflow_entry,
        skill_id=definition.name,
    )
    module_path = _resolve_workflow_module_path(
        Path(definition.source_path).resolve().parent,
        module_part,
        skill_id=definition.name,
    )
    module_name = (
        f"backend.skills._runtime_{definition.name}_{module_part.replace('.', '_')}"
    )
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ValueError(
            f"skill workflow 无法加载模块: skill={definition.name}, module={module_path}"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    try:
        workflow_factory = getattr(module, attr_name)
    except AttributeError as exc:
        raise ValueError(
            f"skill workflow 缺少入口函数: skill={definition.name}, attr={attr_name!r}"
        ) from exc

    workflow = workflow_factory()
    if not isinstance(workflow, TaskSkillWorkflow):
        raise ValueError(
            f"skill workflow 入口返回类型非法: skill={definition.name}, attr={attr_name!r}"
        )
    if workflow.skill_id != definition.name:
        raise ValueError(
            "skill workflow skill_id 不匹配: "
            f"definition={definition.name!r}, workflow={workflow.skill_id!r}"
        )
    return workflow


class SkillRegistry:
    def __init__(self, definitions: tuple[SkillDefinition, ...]):
        self._definitions = definitions
        self._definitions_by_name = {item.name: item for item in definitions}
        self._workflow_cache: dict[str, TaskSkillWorkflow] = {}

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
        definition = self.get_definition(skill_id)
        if definition.executor_binding is None:
            raise KeyError(f"skill 未绑定执行器: {skill_id}")
        return definition.executor_binding

    def get_task_workflow(self, skill_id: str) -> TaskSkillWorkflow:
        cached = self._workflow_cache.get(skill_id)
        if cached is not None:
            return cached

        workflow = _load_task_workflow(self.get_definition(skill_id))
        self._workflow_cache[skill_id] = workflow
        return workflow


def build_skill_registry(*, skills_root: Path | None = None) -> SkillRegistry:
    definitions = load_skill_definitions(skills_root)
    return SkillRegistry(definitions=definitions)


_skill_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = build_skill_registry()
    return _skill_registry
