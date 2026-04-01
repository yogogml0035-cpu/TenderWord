from __future__ import annotations

from pathlib import Path

import pytest

from backend.skills.loader import load_skill_definitions
from backend.skills.registry import build_skill_registry


def _rewrite_frontmatter(
    *,
    name: str = "rewrite",
    description: str = "rewrite description",
    executor_kind: str = "task",
    dispatch_key: str = "rewrite",
    route_literal: str = "rewrite",
    workflow_entry: str = "scripts.workflow:get_workflow",
) -> str:
    return "\n".join(
        (
            f"name: {name}",
            f"description: {description}",
            f"executor_kind: {executor_kind}",
            f"dispatch_key: {dispatch_key}",
            f"route_literal: {route_literal}",
            f"workflow_entry: {workflow_entry}",
        )
    )


def _write_skill(
    root: Path,
    directory_name: str,
    *,
    frontmatter: str,
    instruction: str = "Skill instruction body",
) -> Path:
    skill_dir = root / directory_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        f"---\n{frontmatter}\n---\n\n{instruction}\n",
        encoding="utf-8",
    )
    return skill_file


def _write_workflow_script(skill_dir: Path, *, body: str | None = None) -> None:
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    workflow_file = scripts_dir / "workflow.py"
    workflow_file.write_text(
        body
        or (
            "from backend.skills.types import TaskSkillWorkflow, TaskSkillWorkflowNode\n"
            "\n"
            "def _noop(state, config=None):\n"
            "    return state\n"
            "\n"
            "def get_workflow():\n"
            "    return TaskSkillWorkflow(\n"
            "        skill_id='rewrite',\n"
            "        state_cls=dict,\n"
            "        start_node='resolve_rewrite_target',\n"
            "        end_node='update_word',\n"
            "        nodes=(\n"
            "            TaskSkillWorkflowNode('resolve_rewrite_target', _noop),\n"
            "            TaskSkillWorkflowNode('update_word', _noop),\n"
            "        ),\n"
            "        edges=(('resolve_rewrite_target', 'update_word'),),\n"
            "    )\n"
        ),
        encoding="utf-8",
    )


def test_load_skill_definitions_scans_valid_skill_markdown(tmp_path):
    skills_root = tmp_path / "backend" / "skills"
    skill_file = _write_skill(
        skills_root,
        "rewrite_impl",
        frontmatter=_rewrite_frontmatter(),
        instruction="Rewrite instruction body",
    )

    definitions = load_skill_definitions(skills_root)

    assert len(definitions) == 1
    assert definitions[0].name == "rewrite"
    assert definitions[0].description == "rewrite description"
    assert definitions[0].instruction == "Rewrite instruction body"
    assert definitions[0].source_path == str(skill_file.resolve())
    assert definitions[0].workflow_entry == "scripts.workflow:get_workflow"
    assert definitions[0].executor_binding is not None
    assert definitions[0].executor_binding.skill_id == "rewrite"
    assert definitions[0].executor_binding.executor_kind == "task"
    assert definitions[0].executor_binding.dispatch_key == "rewrite"
    assert definitions[0].executor_binding.route_literal == "rewrite"


def test_load_skill_definitions_rejects_missing_required_fields(tmp_path):
    skills_root = tmp_path / "backend" / "skills"
    _write_skill(
        skills_root,
        "rewrite_impl",
        frontmatter="name: rewrite",
    )

    with pytest.raises(ValueError, match="缺少字段"):
        load_skill_definitions(skills_root)


def test_load_skill_definitions_rejects_unsupported_frontmatter_field(tmp_path):
    skills_root = tmp_path / "backend" / "skills"
    _write_skill(
        skills_root,
        "rewrite_impl",
        frontmatter=_rewrite_frontmatter() + "\nkind: task",
    )

    with pytest.raises(ValueError, match="字段不受支持"):
        load_skill_definitions(skills_root)


def test_load_skill_definitions_rejects_duplicate_names(tmp_path):
    skills_root = tmp_path / "backend" / "skills"
    _write_skill(
        skills_root,
        "rewrite_impl_a",
        frontmatter=_rewrite_frontmatter(description="first"),
    )
    _write_skill(
        skills_root,
        "rewrite_impl_b",
        frontmatter=_rewrite_frontmatter(description="second"),
    )

    with pytest.raises(ValueError, match="全局唯一"):
        load_skill_definitions(skills_root)


def test_build_skill_registry_reads_binding_from_skill_frontmatter(tmp_path):
    skills_root = tmp_path / "backend" / "skills"
    _write_skill(
        skills_root,
        "rewrite_impl",
        frontmatter=_rewrite_frontmatter(),
    )

    registry = build_skill_registry(skills_root=skills_root)
    binding = registry.get_executor_binding("rewrite")

    assert binding.skill_id == "rewrite"
    assert binding.executor_kind == "task"
    assert binding.dispatch_key == "rewrite"
    assert binding.route_literal == "rewrite"


def test_skill_registry_get_task_workflow_loads_and_caches_workflow(tmp_path):
    skills_root = tmp_path / "backend" / "skills"
    skill_file = _write_skill(
        skills_root,
        "rewrite_impl",
        frontmatter=_rewrite_frontmatter(),
    )
    _write_workflow_script(skill_file.parent)

    registry = build_skill_registry(skills_root=skills_root)
    workflow = registry.get_task_workflow("rewrite")

    assert workflow.skill_id == "rewrite"
    assert workflow.start_node == "resolve_rewrite_target"
    assert workflow.end_node == "update_word"
    assert workflow is registry.get_task_workflow("rewrite")


def test_skill_registry_get_task_workflow_rejects_missing_entry_file(tmp_path):
    skills_root = tmp_path / "backend" / "skills"
    _write_skill(
        skills_root,
        "rewrite_impl",
        frontmatter=_rewrite_frontmatter(workflow_entry="scripts.missing:get_workflow"),
    )

    registry = build_skill_registry(skills_root=skills_root)

    with pytest.raises(ValueError, match="入口文件不存在"):
        registry.get_task_workflow("rewrite")


def test_skill_registry_get_task_workflow_rejects_invalid_return_type(tmp_path):
    skills_root = tmp_path / "backend" / "skills"
    skill_file = _write_skill(
        skills_root,
        "rewrite_impl",
        frontmatter=_rewrite_frontmatter(),
    )
    _write_workflow_script(
        skill_file.parent,
        body=(
            "def get_workflow():\n"
            "    return {'skill_id': 'rewrite'}\n"
        ),
    )

    registry = build_skill_registry(skills_root=skills_root)

    with pytest.raises(ValueError, match="返回类型非法"):
        registry.get_task_workflow("rewrite")
