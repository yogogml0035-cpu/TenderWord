from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field, field_validator

COMMENT_AGENT_NODE = "comment_agent"
VALIDATE_COMMENT_REFERENCES_TOOL = "validate_comment_references"
WRITE_VALIDATED_COMMENTS_TOOL = "write_validated_comments_to_word"

ValidationStatus = Literal["passed", "failed", "skipped"]

class CommentCandidate(BaseModel):
    reference_text: str = ""
    comment_text: str = ""

    @field_validator("reference_text", "comment_text", mode="before")
    @classmethod
    def _coerce_text(cls, value: Any) -> str:
        return str(value or "")

class CommentValidationIssue(BaseModel):
    index: int = Field(..., ge=1)
    status: ValidationStatus
    reason: str
    original_reference_text: str = ""
    reference_text: str = ""
    comment_text: str = ""
    candidate_fragments: list[str] = Field(default_factory=list)
    start: int | None = None
    end: int | None = None

class CommentValidationResult(BaseModel):
    passed: list[CommentValidationIssue] = Field(default_factory=list)
    failed: list[CommentValidationIssue] = Field(default_factory=list)
    skipped: list[CommentValidationIssue] = Field(default_factory=list)

    @property
    def passed_count(self) -> int:
        return len(self.passed)

    @property
    def failed_count(self) -> int:
        return len(self.failed)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)

class CommentAgentToolSnapshot(BaseModel):
    round: int = Field(..., ge=1)
    proposed_comments: list[dict[str, str]] = Field(default_factory=list)
    validation: CommentValidationResult

class CommentAgentAuditPayload(TypedDict, total=False):
    task_id: str
    notice: str
    initial_comments: list[dict[str, str]]
    ai_messages: list[str]
    validation_results: list[dict[str, Any]]
    tool_snapshots: list[dict[str, Any]]
    final_proposed_comments: list[dict[str, str]]
    final_passed: list[dict[str, Any]]
    final_failed: list[dict[str, Any]]
    final_skipped: list[dict[str, Any]]
    writeback_result: dict[str, Any] | None

class CommentAgentResult(BaseModel):
    validation: CommentValidationResult
    writeback_result: dict[str, Any]
    audit_log_path: Path | None = None
    ai_messages: list[str] = Field(default_factory=list)
    final_proposed_comments: list[dict[str, str]] = Field(default_factory=list)

__all__ = [
    "COMMENT_AGENT_NODE",
    "VALIDATE_COMMENT_REFERENCES_TOOL",
    "WRITE_VALIDATED_COMMENTS_TOOL",
    "CommentAgentAuditPayload",
    "CommentAgentResult",
    "CommentAgentToolSnapshot",
    "CommentCandidate",
    "CommentValidationIssue",
    "CommentValidationResult",
    "ValidationStatus",
]
