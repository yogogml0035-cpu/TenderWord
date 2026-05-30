from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from backend.agents.comments.types import (
    VALIDATE_COMMENT_REFERENCES_TOOL,
    WRITE_VALIDATED_COMMENTS_TOOL,
    CommentCandidate,
    CommentAgentToolSnapshot,
    CommentValidationIssue,
    CommentValidationResult,
)
from backend.nodes.common_word_nodes.comment_writeback import (
    CommentWritebackIssue,
    CommentWritebackResult,
    _add_comment_with_retries,
    _build_search_texts,
    _has_comment_on_range,
)
from backend.util.word_util import wdFindStop

MAX_CANDIDATE_FRAGMENTS = 3

class ValidateCommentReferencesInput(BaseModel):
    proposed_comments: list[dict[str, Any]] = Field(
        default_factory=list,
        description="AI 修复后的批注候选数组，只允许修改 reference_text。",
    )

class WriteValidatedCommentsInput(BaseModel):
    proposed_comments: list[dict[str, Any]] = Field(
        default_factory=list,
        description="已通过或准备重新校验的批注候选数组。",
    )

@dataclass
class CommentAgentToolContext:
    initial_comments: list[dict[str, str]]
    polished_text: str
    log_parts: list[str] = field(default_factory=list)
    validation_results: list[dict[str, Any]] = field(default_factory=list)
    tool_snapshots: list[CommentAgentToolSnapshot] = field(default_factory=list)
    final_proposed_comments: list[dict[str, str]] = field(default_factory=list)
    writeback_result: CommentWritebackResult | None = None

def normalize_comment_candidates(
    comments: list[Mapping[str, Any]] | None,
) -> list[CommentCandidate]:
    normalized: list[CommentCandidate] = []
    for item in comments or []:
        if isinstance(item, Mapping):
            normalized.append(
                CommentCandidate(
                    reference_text=item.get("reference_text", ""),
                    comment_text=item.get("comment_text", ""),
                )
            )
    return normalized

def _snippet(value: str, limit: int = 120) -> str:
    normalized = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit - 1]}..."

def _split_reference_fragments(polished_text: str) -> list[str]:
    raw = str(polished_text or "")
    fragments = [
        fragment.strip()
        for fragment in re.split(r"[\r\n。；;！？!?]+", raw)
        if fragment and fragment.strip()
    ]
    if fragments:
        return fragments

    fallback: list[str] = []
    step = 80
    for start in range(0, len(raw), step):
        fragment = raw[start : start + step].strip()
        if fragment:
            fallback.append(fragment)
    return fallback

def _build_similar_fragments(
    *,
    reference_text: str,
    polished_text: str,
) -> list[str]:
    reference = str(reference_text or "").strip()
    if not reference:
        return [_snippet(fragment) for fragment in _split_reference_fragments(polished_text)[:MAX_CANDIDATE_FRAGMENTS]]

    scored: list[tuple[float, str]] = []
    for fragment in _split_reference_fragments(polished_text):
        score = difflib.SequenceMatcher(None, reference, fragment).ratio()
        if reference in fragment:
            score += 1.0
        scored.append((score, fragment))

    scored.sort(key=lambda item: item[0], reverse=True)
    snippets = [
        _snippet(fragment)
        for score, fragment in scored[:MAX_CANDIDATE_FRAGMENTS]
        if score > 0
    ]
    if snippets:
        return snippets
    return [
        _snippet(fragment)
        for _score, fragment in scored[:MAX_CANDIDATE_FRAGMENTS]
    ]

def _find_exact_occurrences(text: str, reference_text: str) -> list[tuple[int, int]]:
    occurrences: list[tuple[int, int]] = []
    if not reference_text:
        return occurrences

    offset = 0
    while True:
        start = text.find(reference_text, offset)
        if start < 0:
            break
        end = start + len(reference_text)
        occurrences.append((start, end))
        offset = start + 1
    return occurrences

def _validation_issue(
    *,
    index: int,
    status: str,
    reason: str,
    initial: CommentCandidate | None,
    proposed: CommentCandidate | None,
    polished_text: str,
    start: int | None = None,
    end: int | None = None,
) -> CommentValidationIssue:
    reference_text = proposed.reference_text if proposed else ""
    return CommentValidationIssue(
        index=index,
        status=status,  # type: ignore[arg-type]
        reason=reason,
        original_reference_text=initial.reference_text if initial else "",
        reference_text=reference_text,
        comment_text=proposed.comment_text if proposed else (initial.comment_text if initial else ""),
        candidate_fragments=[] if status == "passed" else _build_similar_fragments(
            reference_text=reference_text or (initial.reference_text if initial else ""),
            polished_text=polished_text,
        ),
        start=start,
        end=end,
    )

def validate_comment_reference_candidates(
    *,
    initial_comments: list[Mapping[str, Any]] | None,
    proposed_comments: list[Mapping[str, Any]] | None,
    polished_text: str,
) -> CommentValidationResult:
    initial = normalize_comment_candidates(initial_comments)
    proposed = normalize_comment_candidates(proposed_comments)
    polished = str(polished_text or "")

    result = CommentValidationResult()

    for zero_based_index, initial_item in enumerate(initial):
        index = zero_based_index + 1
        proposed_item = proposed[zero_based_index] if zero_based_index < len(proposed) else None

        if not initial_item.reference_text.strip() or not initial_item.comment_text.strip():
            result.skipped.append(
                _validation_issue(
                    index=index,
                    status="skipped",
                    reason="missing_initial_reference_or_comment_text",
                    initial=initial_item,
                    proposed=proposed_item or initial_item,
                    polished_text=polished,
                )
            )
            continue

        if proposed_item is None:
            result.failed.append(
                _validation_issue(
                    index=index,
                    status="failed",
                    reason="missing_candidate",
                    initial=initial_item,
                    proposed=None,
                    polished_text=polished,
                )
            )
            continue

        if proposed_item.comment_text != initial_item.comment_text:
            result.failed.append(
                _validation_issue(
                    index=index,
                    status="failed",
                    reason="comment_text_changed",
                    initial=initial_item,
                    proposed=proposed_item,
                    polished_text=polished,
                )
            )
            continue

        reference_text = proposed_item.reference_text.strip()
        if not reference_text:
            result.failed.append(
                _validation_issue(
                    index=index,
                    status="failed",
                    reason="missing_reference_text",
                    initial=initial_item,
                    proposed=proposed_item,
                    polished_text=polished,
                )
            )
            continue

        occurrences = _find_exact_occurrences(polished, reference_text)
        if not occurrences:
            result.failed.append(
                _validation_issue(
                    index=index,
                    status="failed",
                    reason="reference_text_not_found_in_polished_text",
                    initial=initial_item,
                    proposed=proposed_item,
                    polished_text=polished,
                )
            )
            continue
        if len(occurrences) > 1:
            result.failed.append(
                _validation_issue(
                    index=index,
                    status="failed",
                    reason="reference_text_not_unique_in_polished_text",
                    initial=initial_item,
                    proposed=proposed_item,
                    polished_text=polished,
                )
            )
            continue

        start, end = occurrences[0]
        result.passed.append(
            _validation_issue(
                index=index,
                status="passed",
                reason="passed",
                initial=initial_item,
                proposed=proposed_item,
                polished_text=polished,
                start=start,
                end=end,
            )
        )

    if len(proposed) > len(initial):
        for extra_index in range(len(initial), len(proposed)):
            result.failed.append(
                _validation_issue(
                    index=extra_index + 1,
                    status="failed",
                    reason="unexpected_candidate",
                    initial=None,
                    proposed=proposed[extra_index],
                    polished_text=polished,
                )
            )

    return result

def _append_write_issue(
    issues: list[CommentWritebackIssue],
    *,
    index: int,
    reason: str,
    reference_text: str,
    comment_text: str,
    error: str = "",
) -> None:
    issue: CommentWritebackIssue = {
        "index": int(index),
        "reason": str(reason),
        "reference_text": str(reference_text or "")[:120],
        "comment_text": str(comment_text or "")[:120],
    }
    if error:
        issue["error"] = str(error)
    issues.append(issue)

def _find_word_anchor_ranges(
    *,
    doc,
    reference_text: str,
    search_start: int,
    search_end: int,
) -> list[Any]:
    matches: list[Any] = []
    if int(search_end) <= int(search_start):
        return matches

    for find_text in _build_search_texts(reference_text):
        current_start = int(search_start)
        while current_start < int(search_end):
            find_range = doc.Range(current_start, int(search_end))
            finder = find_range.Find
            finder.ClearFormatting()
            finder.Text = find_text
            finder.Forward = True
            finder.Wrap = wdFindStop
            finder.MatchCase = False
            finder.MatchWholeWord = False

            if not finder.Execute():
                break

            match_start = int(find_range.Start)
            match_end = int(find_range.End)
            if match_end <= match_start:
                break
            if not any(
                int(existing.Start) == match_start and int(existing.End) == match_end
                for existing in matches
            ):
                matches.append(find_range.Duplicate)
            current_start = max(match_end, current_start + 1)
    return matches

def write_validated_comment_candidates_to_word(
    *,
    doc,
    initial_comments: list[Mapping[str, Any]] | None,
    proposed_comments: list[Mapping[str, Any]] | None,
    polished_text: str,
    bound_start: int,
    bound_end: int | None,
    log_parts: list[str] | None = None,
) -> tuple[CommentValidationResult, CommentWritebackResult]:
    validation = validate_comment_reference_candidates(
        initial_comments=initial_comments,
        proposed_comments=proposed_comments,
        polished_text=polished_text,
    )
    comments_by_index = {
        item.index: item
        for item in validation.passed
    }
    result: CommentWritebackResult = {
        "total": len(comments_by_index),
        "attempted": 0,
        "added": 0,
        "failed": len(validation.failed),
        "skipped": len(validation.skipped),
        "issues": [],
    }
    for issue in validation.failed:
        _append_write_issue(
            result["issues"],
            index=issue.index,
            reason=issue.reason,
            reference_text=issue.reference_text,
            comment_text=issue.comment_text,
        )
    for issue in validation.skipped:
        _append_write_issue(
            result["issues"],
            index=issue.index,
            reason=issue.reason,
            reference_text=issue.reference_text,
            comment_text=issue.comment_text,
        )

    if doc is None:
        for item in validation.passed:
            result["failed"] += 1
            _append_write_issue(
                result["issues"],
                index=item.index,
                reason="missing_word_document",
                reference_text=item.reference_text,
                comment_text=item.comment_text,
            )
        return validation, result

    doc_end = int(bound_end) if bound_end is not None else int(getattr(doc.Content, "End", 0))
    search_start = max(0, int(bound_start))
    search_end = max(search_start, doc_end)
    logs = log_parts if log_parts is not None else []

    for index, item in comments_by_index.items():
        result["attempted"] += 1
        ranges = _find_word_anchor_ranges(
            doc=doc,
            reference_text=item.reference_text,
            search_start=search_start,
            search_end=search_end,
        )
        if not ranges:
            result["failed"] += 1
            _append_write_issue(
                result["issues"],
                index=index,
                reason="reference_text_not_found_in_word_bound",
                reference_text=item.reference_text,
                comment_text=item.comment_text,
            )
            continue
        if len(ranges) > 1:
            result["failed"] += 1
            _append_write_issue(
                result["issues"],
                index=index,
                reason="reference_text_not_unique_in_word_bound",
                reference_text=item.reference_text,
                comment_text=item.comment_text,
            )
            continue

        target_range = ranges[0]
        if _has_comment_on_range(doc, target_range):
            result["skipped"] += 1
            _append_write_issue(
                result["issues"],
                index=index,
                reason="overlapping_comment_exists",
                reference_text=item.reference_text,
                comment_text=item.comment_text,
            )
            continue

        add_exc = _add_comment_with_retries(doc, target_range, item.comment_text)
        if add_exc is not None:
            result["failed"] += 1
            _append_write_issue(
                result["issues"],
                index=index,
                reason="comment_add_failed",
                reference_text=item.reference_text,
                comment_text=item.comment_text,
                error=str(add_exc),
            )
            continue

        result["added"] += 1
        logs.append(
            f"comment_agent 批注 [{index}] 已写入: reference_text={item.reference_text[:40]}..."
        )

    return validation, result

def create_comment_agent_tools(context: CommentAgentToolContext) -> list[StructuredTool]:
    def _record_snapshot(
        *,
        proposed_comments: list[dict[str, Any]],
        validation: CommentValidationResult,
    ) -> CommentAgentToolSnapshot:
        normalized_proposed = [
            item.model_dump(mode="json")
            for item in normalize_comment_candidates(proposed_comments)
        ]
        snapshot = CommentAgentToolSnapshot(
            round=len(context.tool_snapshots) + 1,
            proposed_comments=normalized_proposed,
            validation=validation,
        )
        context.tool_snapshots.append(snapshot)
        context.validation_results.append(validation.model_dump(mode="json"))
        return snapshot

    def validate_comment_references(
        proposed_comments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """校验 AI 修复后的批注锚点，只允许同 index 修改 reference_text。"""
        validation = validate_comment_reference_candidates(
            initial_comments=context.initial_comments,
            proposed_comments=proposed_comments,
            polished_text=context.polished_text,
        )
        snapshot = _record_snapshot(
            proposed_comments=proposed_comments,
            validation=validation,
        )
        return snapshot.validation.model_dump(mode="json")

    def write_validated_comments_to_word(
        proposed_comments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """提交最终候选。这里只重新校验并记录候选，真正 Word 写入由 graph 节点线程执行。"""
        validation = validate_comment_reference_candidates(
            initial_comments=context.initial_comments,
            proposed_comments=proposed_comments,
            polished_text=context.polished_text,
        )
        context.final_proposed_comments = [
            item.model_dump(mode="json")
            for item in normalize_comment_candidates(proposed_comments)
        ]
        return {
            "validation": validation.model_dump(mode="json"),
            "submitted": True,
            "runtime_writeback": "deferred_to_graph_node_thread",
        }

    return [
        StructuredTool.from_function(
            validate_comment_references,
            name=VALIDATE_COMMENT_REFERENCES_TOOL,
            description=(
                "校验批注候选。输入 AI 修复后的 proposed_comments；工具会拒绝 "
                "comment_text 变化，只允许修复 reference_text。"
            ),
            args_schema=ValidateCommentReferencesInput,
        ),
        StructuredTool.from_function(
            write_validated_comments_to_word,
            name=WRITE_VALIDATED_COMMENTS_TOOL,
            description=(
                "提交最终批注候选。工具只重新执行确定性校验并记录候选；真正 Word 写入由 "
                "comment_agent 运行时在 graph 节点线程完成。"
            ),
            args_schema=WriteValidatedCommentsInput,
        ),
    ]

__all__ = [
    "CommentAgentToolContext",
    "ValidateCommentReferencesInput",
    "WriteValidatedCommentsInput",
    "create_comment_agent_tools",
    "normalize_comment_candidates",
    "validate_comment_reference_candidates",
    "write_validated_comment_candidates_to_word",
]
