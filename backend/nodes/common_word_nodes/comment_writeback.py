from __future__ import annotations

import time
from typing import Any, Iterable, Mapping, TypedDict

from backend.util.word_util import (
    calculate_retry_delay,
    is_rpc_error,
    wdFindStop,
)

MAX_COMMENT_ADD_RETRIES = 3


class CommentWritebackIssue(TypedDict, total=False):
    index: int
    reason: str
    reference_text: str
    comment_text: str
    error: str


class CommentWritebackResult(TypedDict):
    total: int
    attempted: int
    added: int
    failed: int
    skipped: int
    issues: list[CommentWritebackIssue]


def _ranges_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return not (int(a_end) <= int(b_start) or int(b_end) <= int(a_start))


def _get_comment_range(comment) -> Any | None:
    for attr in ("Scope", "Reference", "Range"):
        try:
            value = getattr(comment, attr)
        except Exception:
            value = None
        if value is not None:
            return value
    return None


def _has_comment_on_range(doc, target_rng) -> bool:
    try:
        comments = doc.Comments
    except Exception:
        return False

    try:
        count = int(comments.Count)
    except Exception:
        return False

    for idx in range(1, count + 1):
        try:
            comment = comments(idx)
        except Exception:
            continue

        comment_rng = _get_comment_range(comment)
        if comment_rng is None:
            continue

        try:
            comment_start = int(comment_rng.Start)
            comment_end = int(comment_rng.End)
            target_start = int(target_rng.Start)
            target_end = int(target_rng.End)
        except Exception:
            continue

        if _ranges_overlap(comment_start, comment_end, target_start, target_end):
            return True

    return False


def _build_search_texts(reference_text: str) -> list[str]:
    search_texts: list[str] = []
    for candidate in (
        str(reference_text or ""),
        str(reference_text or "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\r"),
    ):
        normalized = str(candidate or "")
        if normalized and normalized not in search_texts:
            search_texts.append(normalized)

    # Table-oriented matching: markdown-style rows like "A | B"
    raw = str(reference_text or "")
    if "|" in raw:
        # Strip pipe characters and collapse whitespace
        pipe_stripped = " ".join(raw.replace("|", " ").split())
        if pipe_stripped and pipe_stripped not in search_texts:
            search_texts.append(pipe_stripped)

    return search_texts


def _append_issue(
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


def _append_issue_summary(
    *,
    log_parts: list[str],
    step_label: str,
    issues: list[CommentWritebackIssue],
) -> None:
    if not issues:
        return

    reason_counts: dict[str, int] = {}
    for issue in issues:
        reason = str(issue.get("reason") or "unknown")
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

    ordered_summary = ", ".join(
        f"{reason}={count}" for reason, count in sorted(reason_counts.items())
    )
    log_parts.append(f"{step_label}未匹配原因：{ordered_summary}")


def write_polished_comments(
    *,
    doc,
    polished_comments: Iterable[Mapping[str, Any]] | None,
    bound_start: int,
    bound_end: int,
    log_parts: list[str],
    step_label: str = "步骤6",
) -> CommentWritebackResult:
    comments = list(polished_comments or [])
    result: CommentWritebackResult = {
        "total": len(comments),
        "attempted": 0,
        "added": 0,
        "failed": 0,
        "skipped": 0,
        "issues": [],
    }

    if not comments:
        log_parts.append(f"{step_label}：无 polished_comments，跳过批注插入。")
        return result

    log_parts.append(f"{step_label}：根据 polished_comments 插入批注...")

    search_start = int(bound_start)
    search_end = int(bound_end)
    if search_end <= search_start:
        for idx, instruction in enumerate(comments, start=1):
            reference_text = str(instruction.get("reference_text") or "").strip()
            comment_text = str(instruction.get("comment_text") or "").strip()
            if not reference_text or not comment_text:
                result["skipped"] += 1
                _append_issue(
                    result["issues"],
                    index=idx,
                    reason="missing_reference_or_comment_text",
                    reference_text=reference_text,
                    comment_text=comment_text,
                )
                continue
            result["attempted"] += 1
            result["failed"] += 1
            _append_issue(
                result["issues"],
                index=idx,
                reason="empty_search_bound",
                reference_text=reference_text,
                comment_text=comment_text,
            )
        log_parts.append(
            f"{step_label}完成：成功添加 0/{len(comments)} 条批注，失败 {result['failed']} 条，跳过 {result['skipped']} 条。"
        )
        _append_issue_summary(
            log_parts=log_parts,
            step_label=step_label,
            issues=result["issues"],
        )
        return result

    last_used_end_by_ref: dict[str, int] = {}

    for idx, instruction in enumerate(comments, start=1):
        reference_text = str(instruction.get("reference_text") or "").strip()
        comment_text = str(instruction.get("comment_text") or "").strip()

        if not reference_text or not comment_text:
            result["skipped"] += 1
            _append_issue(
                result["issues"],
                index=idx,
                reason="missing_reference_or_comment_text",
                reference_text=reference_text,
                comment_text=comment_text,
            )
            log_parts.append(f"  批注 [{idx}] 缺少引用文本或批注内容，已跳过。")
            continue

        result["attempted"] += 1
        inserted_here = False
        overlapped_existing_comment = False

        for find_text in _build_search_texts(reference_text):
            current_start = int(last_used_end_by_ref.get(reference_text, search_start))

            while current_start < search_end:
                find_range = doc.Range(current_start, search_end)
                finder = find_range.Find
                finder.ClearFormatting()
                finder.Text = find_text
                finder.Forward = True
                finder.Wrap = wdFindStop
                finder.MatchCase = False
                finder.MatchWholeWord = False

                if not finder.Execute():
                    break

                try:
                    match_start = int(find_range.Start)
                    match_end = int(find_range.End)
                except Exception:
                    break

                if _has_comment_on_range(doc, find_range):
                    overlapped_existing_comment = True
                    log_parts.append(
                        f"  批注 [{idx}] 位置已存在批注，继续向后查找 reference_text={reference_text[:40]}..."
                    )
                    current_start = max(match_end, current_start + 1)
                    continue

                add_exc: Exception | None = None
                for attempt in range(MAX_COMMENT_ADD_RETRIES):
                    try:
                        doc.Comments.Add(Range=find_range.Duplicate, Text=comment_text)
                        add_exc = None
                        break
                    except Exception as exc:
                        add_exc = exc
                        if is_rpc_error(exc) and attempt < MAX_COMMENT_ADD_RETRIES - 1:
                            delay = calculate_retry_delay(attempt)
                            time.sleep(delay)
                            continue
                if add_exc is not None:
                    result["failed"] += 1
                    _append_issue(
                        result["issues"],
                        index=idx,
                        reason="comment_add_failed",
                        reference_text=reference_text,
                        comment_text=comment_text,
                        error=str(add_exc),
                    )
                    log_parts.append(
                        f"  批注 [{idx}] 添加失败 (重试 {MAX_COMMENT_ADD_RETRIES} 次后仍失败, reference_text={reference_text[:40]}...): {add_exc}"
                    )
                    inserted_here = True
                else:
                    result["added"] += 1
                    last_used_end_by_ref[reference_text] = match_end
                    log_parts.append(
                        f"  批注 [{idx}] 已添加: reference_text={reference_text[:40]}... -> comment_text={comment_text[:40]}..."
                    )
                    inserted_here = True
                break

            if inserted_here:
                break

        if inserted_here:
            continue

        if overlapped_existing_comment:
            result["skipped"] += 1
            reason = "overlapping_comment_exists"
            log_parts.append(
                f"  批注 [{idx}] 目标范围已存在批注，按保守去重策略跳过: {reference_text[:50]}..."
            )
        else:
            result["failed"] += 1
            reason = "reference_text_not_found"
            log_parts.append(
                f"  批注 [{idx}] 未找到可插入的位置或未匹配到引用文本: {reference_text[:50]}..."
            )

        _append_issue(
            result["issues"],
            index=idx,
            reason=reason,
            reference_text=reference_text,
            comment_text=comment_text,
        )

    log_parts.append(
        f"{step_label}完成：成功添加 {result['added']}/{len(comments)} 条批注，失败 {result['failed']} 条，跳过 {result['skipped']} 条。"
    )
    _append_issue_summary(
        log_parts=log_parts,
        step_label=step_label,
        issues=result["issues"],
    )
    return result
