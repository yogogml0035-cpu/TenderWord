from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_REQUIRED_FRONTMATTER_FIELDS = frozenset({"name", "description"})
_FRONTMATTER_PATTERN = re.compile(
    r"\A---\s*\r?\n(?P<frontmatter>.*?)\r?\n---\s*\r?\n?(?P<body>.*)\Z",
    re.DOTALL,
)


@dataclass(frozen=True)
class SkillGuide:
    name: str
    description: str
    instruction: str
    source_path: str


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
        if normalized_key not in _REQUIRED_FRONTMATTER_FIELDS:
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

    missing_fields = sorted(_REQUIRED_FRONTMATTER_FIELDS - set(values))
    if missing_fields:
        raise ValueError(
            "Skill frontmatter 缺少字段: "
            f"{source_path} missing={', '.join(missing_fields)}"
        )
    return values


@lru_cache(maxsize=None)
def get_skill_guide(skill_id: str, *, skills_root: Path | None = None) -> SkillGuide:
    root = Path(skills_root) if skills_root is not None else _default_skills_root()
    skill_file = root / str(skill_id).strip() / "SKILL.md"
    if not skill_file.is_file():
        raise FileNotFoundError(f"Skill 文件不存在: {skill_file}")

    content = skill_file.read_text(encoding="utf-8")
    matched = _FRONTMATTER_PATTERN.match(content)
    if matched is None:
        raise ValueError(f"Skill 文件缺少合法 frontmatter: {skill_file}")

    metadata = _parse_frontmatter_block(matched.group("frontmatter"), skill_file)
    instruction = matched.group("body").strip()
    if not instruction:
        raise ValueError(f"Skill instruction 不能为空: {skill_file}")

    return SkillGuide(
        name=metadata["name"],
        description=metadata["description"],
        instruction=instruction,
        source_path=str(skill_file.resolve()),
    )
