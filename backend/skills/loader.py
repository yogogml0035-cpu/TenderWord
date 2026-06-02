from __future__ import annotations

import re
from pathlib import Path

from backend.skills.types import SkillDefinition, SkillExecutorBinding

_REQUIRED_FRONTMATTER_FIELDS = frozenset({"name", "description"})
_LEGACY_EXECUTOR_FIELDS = frozenset(
    {
        "executor_kind",
        "dispatch_key",
        "route_literal",
    }
)
_SUPPORTED_FRONTMATTER_FIELDS = frozenset(
    _REQUIRED_FRONTMATTER_FIELDS | _LEGACY_EXECUTOR_FIELDS | {"workflow_entry"}
)
_FRONTMATTER_PATTERN = re.compile(
    r"\A---\s*\r?\n(?P<frontmatter>.*?)\r?\n---\s*\r?\n?(?P<body>.*)\Z",
    re.DOTALL,
)


def _default_skills_root() -> Path:
    return Path(__file__).resolve().parent


def _parse_frontmatter_block(frontmatter_text: str, source_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_no, raw_line in enumerate(frontmatter_text.splitlines(), start=2):
        line = raw_line.strip()
        if not line:
            continue
        if ":" not in raw_line:
            raise ValueError(
                f"Skill frontmatter 格式非法: {source_path} line {line_no}: {raw_line!r}"
            )

        key, raw_value = raw_line.split(":", 1)
        normalized_key = key.strip()
        normalized_value = raw_value.strip()
        if normalized_key not in _SUPPORTED_FRONTMATTER_FIELDS:
            raise ValueError(
                f"Skill frontmatter 字段不受支持: {source_path} field={normalized_key!r}"
            )
        if not normalized_value:
            raise ValueError(
                f"Skill frontmatter 字段不能为空: {source_path} field={normalized_key!r}"
            )
        if normalized_key in values:
            raise ValueError(
                f"Skill frontmatter 字段重复: {source_path} field={normalized_key!r}"
            )
        values[normalized_key] = normalized_value

    missing_required_fields = sorted(_REQUIRED_FRONTMATTER_FIELDS - set(values))
    if missing_required_fields:
        raise ValueError(
            "Skill frontmatter 缺少字段: "
            f"{source_path} missing={', '.join(missing_required_fields)}"
        )

    present_legacy_fields = _LEGACY_EXECUTOR_FIELDS & set(values)
    if present_legacy_fields and present_legacy_fields != _LEGACY_EXECUTOR_FIELDS:
        missing_legacy_fields = sorted(_LEGACY_EXECUTOR_FIELDS - set(values))
        raise ValueError(
            "Skill frontmatter 缺少 legacy task 字段: "
            f"{source_path} missing={', '.join(missing_legacy_fields)}"
        )
    return values


def _infer_task_runtime_defaults(
    skill_file: Path,
    *,
    skill_name: str,
) -> tuple[SkillExecutorBinding | None, str]:
    workflow_file = skill_file.parent / "scripts" / "workflow.py"
    if not workflow_file.is_file():
        return None, ""

    return (
        SkillExecutorBinding(
            skill_id=skill_name,
            executor_kind="task",
            dispatch_key=skill_name,
            route_literal=skill_name,
        ),
        "scripts.workflow:get_workflow",
    )


def _parse_skill_definition(skill_file: Path) -> SkillDefinition:
    content = skill_file.read_text(encoding="utf-8")
    matched = _FRONTMATTER_PATTERN.match(content)
    if matched is None:
        raise ValueError(f"Skill 文件缺少合法 frontmatter: {skill_file}")

    metadata = _parse_frontmatter_block(matched.group("frontmatter"), skill_file)
    instruction = matched.group("body").strip()
    if not instruction:
        raise ValueError(f"Skill instruction 不能为空: {skill_file}")

    skill_name = metadata["name"]
    executor_binding = None
    if _LEGACY_EXECUTOR_FIELDS <= set(metadata):
        executor_binding = SkillExecutorBinding(
            skill_id=skill_name,
            executor_kind=metadata["executor_kind"],
            dispatch_key=metadata["dispatch_key"],
            route_literal=metadata["route_literal"],
        )

    workflow_entry = str(metadata.get("workflow_entry") or "").strip()
    inferred_binding, inferred_workflow_entry = _infer_task_runtime_defaults(
        skill_file,
        skill_name=skill_name,
    )
    if executor_binding is None:
        executor_binding = inferred_binding
    if not workflow_entry:
        workflow_entry = inferred_workflow_entry

    return SkillDefinition(
        name=skill_name,
        description=metadata["description"],
        instruction=instruction,
        source_path=str(skill_file.resolve()),
        executor_binding=executor_binding,
        workflow_entry=workflow_entry,
    )


def load_skill_definitions(skills_root: Path | None = None) -> tuple[SkillDefinition, ...]:
    root = Path(skills_root) if skills_root is not None else _default_skills_root()
    if not root.exists():
        raise FileNotFoundError(f"Skill 根目录不存在: {root}")

    definitions: list[SkillDefinition] = []
    seen_names: dict[str, Path] = {}

    for directory in sorted(path for path in root.iterdir() if path.is_dir()):
        skill_file = directory / "SKILL.md"
        if not skill_file.is_file():
            continue

        definition = _parse_skill_definition(skill_file)
        previous_path = seen_names.get(definition.name)
        if previous_path is not None:
            raise ValueError(
                "Skill name 必须全局唯一: "
                f"name={definition.name!r}, first={previous_path}, second={skill_file}"
            )
        seen_names[definition.name] = skill_file
        definitions.append(definition)

    definitions.sort(key=lambda item: item.name)
    return tuple(definitions)
