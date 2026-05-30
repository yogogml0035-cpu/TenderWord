from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from pydantic import BaseModel, Field, field_validator, model_validator


class GenerationAgentProtocolError(ValueError):
    """Raised when the generation agent returns an invalid contract payload."""


class GenerationAgentToolCallUnsupportedError(RuntimeError):
    """Raised when the selected model or runner cannot use DeepAgents tools."""


class AuditFinding(BaseModel):
    evidence: str = Field(..., min_length=1)
    fix_hint: str = Field(..., min_length=1)

    @field_validator("evidence", "fix_hint")
    @classmethod
    def _strip_non_empty(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized


class ContentAgentFinalOutput(BaseModel):
    polished_text: str = Field(..., min_length=1)
    audit_findings: list[AuditFinding] = Field(default_factory=list)
    revision_rounds: int = Field(default=0, ge=0)
    workspace_dir: Path | None = None

    @field_validator("polished_text")
    @classmethod
    def _strip_polished_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("polished_text 不能为空")
        return normalized


class GenerationAgentState(TypedDict, total=False):
    messages: list[Any]
    structured_response: Any
    tender_type: str
    generation_style: str
    project_info: str
    tender_params: Any
    origin_tender_params: Any
    model_provider: str
    draft_text: str
    draft_path: str
    current_text: str
    current_text_path: str
    findings: list[dict[str, str]]
    audit_findings: list[dict[str, str]]
    audit_path: str
    revision_round: int
    revision_path: str
    no_revision: bool
    polished_text: str


class AgentStepPayload(BaseModel):
    step_type: str
    round: int = Field(..., ge=1)
    node: str
    content: str | None = None
    findings: list[AuditFinding] = Field(default_factory=list)
    comment_agent: dict[str, Any] | None = None
    is_complete: bool = False

    @model_validator(mode="after")
    def _validate_step_payload(self) -> "AgentStepPayload":
        if self.step_type == "audit" and self.content:
            self.content = self.content.strip()
        if self.step_type in {"draft", "revision", "final"} and not str(self.content or "").strip():
            raise ValueError(f"{self.step_type} step requires content")
        if self.step_type == "audit" and self.content is None:
            self.content = ""
        return self


__all__ = [
    "AgentStepPayload",
    "AuditFinding",
    "GenerationAgentProtocolError",
    "GenerationAgentState",
    "GenerationAgentToolCallUnsupportedError",
    "ContentAgentFinalOutput",
]
