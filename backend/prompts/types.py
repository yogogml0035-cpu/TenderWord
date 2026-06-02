from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence, Tuple

@dataclass(frozen=True)
class RenderedPrompt:
    system_prompt: str
    user_prompt: str

    def as_tuple(self) -> tuple[str, str]:
        return self.system_prompt, self.user_prompt


@dataclass(frozen=True)
class GeneratePromptInput:
    tender_type: str = "xjcg"
    generation_style: str = "template"
    project_info: str = ""
    tender_params: Any = ""
    template_reference_text: Any = ""


@dataclass(frozen=True)
class CommentPromptInput:
    tender_type: str = "xjcg"
    polished_text: str = ""


@dataclass(frozen=True)
class RewriteStateSnapshot:
    project_number: str = ""
    project_name: str = ""
    tender_type: str = ""
    prepared_doc_path: str = ""
    polished_text: str = ""
    tender_params: str = ""

    @classmethod
    def from_mapping(
        cls, data: Optional[Mapping[str, Any]]
    ) -> Optional["RewriteStateSnapshot"]:
        if not data:
            return None

        return cls(
            project_number=str(data.get("project_number") or "").strip(),
            project_name=str(data.get("project_name") or "").strip(),
            tender_type=str(data.get("tender_type") or "").strip(),
            prepared_doc_path=str(data.get("prepared_doc_path") or "").strip(),
            polished_text=str(data.get("polished_text") or "").strip(),
            tender_params=str(data.get("tender_params") or "").strip(),
        )


@dataclass(frozen=True)
class TaskSkillPromptSection:
    title: str
    content: str


@dataclass(frozen=True)
class TaskSkillPromptInput:
    skill_id: str
    instruction: str
    sections: Sequence[TaskSkillPromptSection]


@dataclass(frozen=True)
class RewriteHistoryMessage:
    role: str
    content: str
    rewrite_state: Optional[RewriteStateSnapshot] = None
    created_at: float = 0.0


@dataclass(frozen=True)
class RewriteAssistantCandidate:
    assistant_index: int
    content: str
    created_at: float
    rewrite_state: RewriteStateSnapshot


@dataclass(frozen=True)
class RewriteTargetSelectionPromptInput:
    messages: Sequence[RewriteHistoryMessage]
    user_prompt: str


@dataclass(frozen=True)
class RewriteTargetSelectionBundle:
    rendered_prompt: RenderedPrompt
    assistant_candidates: Tuple[RewriteAssistantCandidate, ...]


@dataclass(frozen=True)
class TemplateCandidateRankingItem:
    row_index: int
    tendername: str


@dataclass(frozen=True)
class TemplateCandidateRankingPromptInput:
    project_name: str
    candidates: Sequence[TemplateCandidateRankingItem]
