from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    description: str
    instruction: str
    source_path: str

    def as_summary(self) -> "SkillSummary":
        return SkillSummary(name=self.name, description=self.description)


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
