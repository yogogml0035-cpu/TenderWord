from __future__ import annotations

from pathlib import Path

import pytest

from backend.skills.loader import load_skill_definitions
from backend.skills.registry import build_skill_registry
from backend.skills.types import SkillExecutorBinding


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


def test_load_skill_definitions_scans_valid_skill_markdown(tmp_path):
    skills_root = tmp_path / "backend" / "skills"
    _write_skill(
        skills_root,
        "rewrite_impl",
        frontmatter="name: rewrite\ndescription: rewrite description",
        instruction="Rewrite instruction body",
    )

    definitions = load_skill_definitions(skills_root)

    assert len(definitions) == 1
    assert definitions[0].name == "rewrite"
    assert definitions[0].description == "rewrite description"
    assert definitions[0].instruction == "Rewrite instruction body"


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
        frontmatter="name: rewrite\ndescription: rewrite description\nkind: task",
    )

    with pytest.raises(ValueError, match="字段不受支持"):
        load_skill_definitions(skills_root)


def test_load_skill_definitions_rejects_duplicate_names(tmp_path):
    skills_root = tmp_path / "backend" / "skills"
    _write_skill(
        skills_root,
        "rewrite_impl_a",
        frontmatter="name: rewrite\ndescription: first",
    )
    _write_skill(
        skills_root,
        "rewrite_impl_b",
        frontmatter="name: rewrite\ndescription: second",
    )

    with pytest.raises(ValueError, match="全局唯一"):
        load_skill_definitions(skills_root)


def test_build_skill_registry_requires_executor_binding(tmp_path):
    skills_root = tmp_path / "backend" / "skills"
    _write_skill(
        skills_root,
        "rewrite_impl",
        frontmatter="name: rewrite\ndescription: rewrite description",
    )

    with pytest.raises(ValueError, match="没有同名后端执行器"):
        build_skill_registry(skills_root=skills_root, executor_bindings={})


def test_build_skill_registry_requires_skill_file_for_registered_binding(tmp_path):
    skills_root = tmp_path / "backend" / "skills"
    skills_root.mkdir(parents=True, exist_ok=True)
    bindings = {
        "rewrite": SkillExecutorBinding(
            skill_id="rewrite",
            executor_kind="task",
            dispatch_key="rewrite",
            route_literal="rewrite",
        )
    }

    with pytest.raises(ValueError, match="缺少对应 SKILL.md"):
        build_skill_registry(skills_root=skills_root, executor_bindings=bindings)
