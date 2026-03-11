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
    project_info: str = ""
    tender_params: Any = ""
    origin_tender_params: Any = ""


@dataclass(frozen=True)
class CommentPromptInput:
    tender_type: str = "xjcg"
    polished_text: str = ""
    comment_plan_detail: Any = None
    strikethrough_plan: Any = None
    non_black_font_plan: Any = None


@dataclass(frozen=True)
class RewritePromptInput:
    base_text: str = ""
    user_prompt: str = ""


@dataclass(frozen=True)
class RewriteStateSnapshot:
    project_number: str = ""
    project_name: str = ""
    tender_type: str = ""
    prepared_doc_path: str = ""
    polished_text: str = ""

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
        )


@dataclass(frozen=True)
class RouteHistoryMessage:
    role: str
    content: str


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
class RewriteRelevancePromptInput:
    prompt: str
    latest_rewrite_state: Optional[RewriteStateSnapshot] = None


@dataclass(frozen=True)
class RouteOrReplyPromptInput:
    messages: Sequence[RouteHistoryMessage]
    latest_user_message: str
    latest_rewrite_state: Optional[RewriteStateSnapshot]
    has_rewrite_history: bool


@dataclass(frozen=True)
class RewriteTargetSelectionPromptInput:
    messages: Sequence[RewriteHistoryMessage]
    user_prompt: str


@dataclass(frozen=True)
class RewriteTargetSelectionBundle:
    rendered_prompt: RenderedPrompt
    assistant_candidates: Tuple[RewriteAssistantCandidate, ...]
