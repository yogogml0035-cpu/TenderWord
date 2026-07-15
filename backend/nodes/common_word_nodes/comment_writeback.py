from __future__ import annotations

import re
import time
from typing import Any, Iterable, Mapping, TypedDict

from backend.util.word_util import (
    calculate_retry_delay,
    is_rpc_error,
    wdFindStop,
)

MAX_COMMENT_ADD_RETRIES = 3
_FALLBACK_IGNORED_TEXT_RE = re.compile(
    r"""[\s\u00a0\u3000,，.。:：;；、!?！？"'“”‘’`~\-—_·•/\\|()（）\[\]【】<>《》\r\n\v\f\x07]+"""
)


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


class CommentWritebackSummaryPayload(TypedDict):
    summary: str
    generated: int
    added: int
    failed: int
    skipped: int
    warning: bool


def _coerce_non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def build_comment_writeback_summary_payload(
    *,
    generated_count: Any,
    writeback_result: Mapping[str, Any] | None,
) -> CommentWritebackSummaryPayload:
    generated = _coerce_non_negative_int(generated_count)
    result = writeback_result or {}
    added = _coerce_non_negative_int(result.get("added"))
    failed = _coerce_non_negative_int(result.get("failed"))
    skipped = _coerce_non_negative_int(result.get("skipped"))
    summary = f"AI批注写入: 生成={generated}, 成功={added}, 失败={failed}, 跳过={skipped}"
    return {
        "summary": summary,
        "generated": generated,
        "added": added,
        "failed": failed,
        "skipped": skipped,
        "warning": generated > 0 and failed > 0,
    }


def empty_comment_writeback_result() -> CommentWritebackResult:
    return {
        "total": 0,
        "attempted": 0,
        "added": 0,
        "failed": 0,
        "skipped": 0,
        "issues": [],
    }


def merge_comment_writeback_results(
    *results: Mapping[str, Any] | None,
) -> CommentWritebackResult:
    merged = empty_comment_writeback_result()
    for result in results:
        if not result:
            continue
        merged["total"] += _coerce_non_negative_int(result.get("total"))
        merged["attempted"] += _coerce_non_negative_int(result.get("attempted"))
        merged["added"] += _coerce_non_negative_int(result.get("added"))
        merged["failed"] += _coerce_non_negative_int(result.get("failed"))
        merged["skipped"] += _coerce_non_negative_int(result.get("skipped"))
        issues = result.get("issues") or []
        if isinstance(issues, list):
            merged["issues"].extend(issues)
    return merged


def apply_correction_and_ai_comments(
    *,
    doc,
    state: Mapping[str, Any],
    bound_start: int,
    bound_end: int,
    log_parts: list[str],
    step_label: str = "步骤6",
    suppress_ai_comment_writeback: bool = False,
) -> tuple[CommentWritebackResult, CommentWritebackSummaryPayload]:
    """先写更正批注，再写普通 AI 批注；suppress 只跳过普通批注。"""
    correction_comments = list(state.get("correction_comments") or [])
    polished_comments = list(state.get("polished_comments") or [])
    generated_count = _coerce_non_negative_int(state.get("generated_comment_count"))

    correction_result = empty_comment_writeback_result()
    if correction_comments:
        correction_result = write_polished_comments(
            doc=doc,
            polished_comments=correction_comments,
            bound_start=bound_start,
            bound_end=bound_end,
            log_parts=log_parts,
            step_label=f"{step_label}-更正批注",
        )
    else:
        log_parts.append(f"{step_label}-更正批注：无 correction_comments，跳过。")

    ai_result = empty_comment_writeback_result()
    if suppress_ai_comment_writeback:
        log_parts.append(
            f"{step_label}：跳过普通 AI 批注写入（agent 模式或 comment_generation_mode=off）。"
        )
    elif polished_comments:
        ai_result = write_polished_comments(
            doc=doc,
            polished_comments=polished_comments,
            bound_start=bound_start,
            bound_end=bound_end,
            log_parts=log_parts,
            step_label=step_label,
        )
    else:
        log_parts.append(f"{step_label}：无 polished_comments，跳过普通批注。")

    merged = merge_comment_writeback_results(correction_result, ai_result)
    # 汇总：更正批注 + 普通批注；generated 以普通批注生成数 + 更正数为准，避免 agent 覆盖后丢失更正计数。
    total_generated = generated_count + _coerce_non_negative_int(correction_result.get("total"))
    summary = build_comment_writeback_summary_payload(
        generated_count=total_generated,
        writeback_result=merged,
    )
    if correction_result.get("added"):
        summary["summary"] = (
            f"更正批注成功={correction_result['added']}；{summary['summary']}"
        )
    return merged, summary


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


def _normalized_text_with_positions(text: str) -> tuple[str, list[int]]:
    normalized_parts: list[str] = []
    positions: list[int] = []

    for pos, char in enumerate(str(text or "")):
        if _FALLBACK_IGNORED_TEXT_RE.fullmatch(char):
            continue
        lowered = char.lower()
        if not lowered:
            continue
        for normalized_char in lowered:
            normalized_parts.append(normalized_char)
            positions.append(pos)

    return "".join(normalized_parts), positions


def _get_doc_end(doc, fallback: int) -> int:
    try:
        return max(0, int(doc.Content.End))
    except Exception:
        return max(0, int(fallback))


def _read_range_text(doc, start: int, end: int) -> str:
    try:
        return str(getattr(doc.Range(int(start), int(end)), "Text", "") or "")
    except Exception:
        return ""


def _find_normalized_ranges(
    doc,
    *,
    reference_text: str,
    search_start: int,
    search_end: int,
) -> list[Any]:
    if int(search_end) <= int(search_start):
        return []

    normalized_reference, _ = _normalized_text_with_positions(reference_text)
    if not normalized_reference:
        return []

    raw_text = _read_range_text(doc, int(search_start), int(search_end))
    if not raw_text:
        return []

    normalized_text, positions = _normalized_text_with_positions(raw_text)
    if not normalized_text or not positions:
        return []

    matches: list[Any] = []
    offset = 0
    while True:
        match_start = normalized_text.find(normalized_reference, offset)
        if match_start < 0:
            break
        match_end = match_start + len(normalized_reference)
        try:
            absolute_start = int(search_start) + int(positions[match_start])
            absolute_end = int(search_start) + int(positions[match_end - 1]) + 1
            if absolute_end > absolute_start:
                matches.append(doc.Range(absolute_start, absolute_end))
        except Exception:
            pass
        offset = match_start + 1

    return matches


def _add_comment_with_retries(doc, target_range, comment_text: str) -> Exception | None:
    add_exc: Exception | None = None
    for attempt in range(MAX_COMMENT_ADD_RETRIES):
        try:
            doc.Comments.Add(Range=target_range.Duplicate, Text=comment_text)
            return None
        except Exception as exc:
            add_exc = exc
            if is_rpc_error(exc) and attempt < MAX_COMMENT_ADD_RETRIES - 1:
                delay = calculate_retry_delay(attempt)
                time.sleep(delay)
                continue
    return add_exc


def _try_normalized_comment_insert(
    *,
    doc,
    reference_text: str,
    comment_text: str,
    current_start: int,
    search_start: int,
    search_end: int,
    log_parts: list[str],
    idx: int,
) -> tuple[str, int]:
    bounded_matches = _find_normalized_ranges(
        doc,
        reference_text=reference_text,
        search_start=int(current_start),
        search_end=int(search_end),
    )
    expanded_to_document = False
    matches = bounded_matches

    if not matches:
        doc_end = _get_doc_end(doc, search_end)
        if doc_end > search_end or search_start > 0:
            matches = _find_normalized_ranges(
                doc,
                reference_text=reference_text,
                search_start=0,
                search_end=doc_end,
            )
            expanded_to_document = bool(matches)

    if not matches:
        return "not_found", int(current_start)

    if len(matches) > 1:
        reason = "全文" if expanded_to_document else "锚点范围"
        log_parts.append(
            f"  批注 [{idx}] 规范化匹配在{reason}命中多处，跳过以避免错插: {reference_text[:50]}..."
        )
        return "normalized_reference_not_unique", int(current_start)

    target_range = matches[0]
    try:
        match_start = int(target_range.Start)
        match_end = int(target_range.End)
    except Exception:
        return "not_found", int(current_start)

    if _has_comment_on_range(doc, target_range):
        log_parts.append(
            f"  批注 [{idx}] 规范化匹配位置已存在批注，按保守去重策略跳过: {reference_text[:50]}..."
        )
        return "overlapping_comment_exists", max(match_end, int(current_start) + 1)

    add_exc = _add_comment_with_retries(doc, target_range, comment_text)
    if add_exc is not None:
        log_parts.append(
            f"  批注 [{idx}] 规范化匹配后添加失败 (重试 {MAX_COMMENT_ADD_RETRIES} 次后仍失败, reference_text={reference_text[:40]}...): {add_exc}"
        )
        return f"comment_add_failed:{add_exc}", max(match_end, int(current_start) + 1)

    scope = "全文唯一" if expanded_to_document else "规范化"
    log_parts.append(
        f"  批注 [{idx}] 已通过{scope}匹配添加: reference_text={reference_text[:40]}... -> comment_text={comment_text[:40]}..."
    )
    return "added", match_end


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

    doc_end = _get_doc_end(doc, int(bound_end))
    search_start = min(max(0, int(bound_start)), doc_end)
    search_end = min(max(search_start, int(bound_end)), doc_end)
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
        added_here = 0
        skipped_overlap_here = 0
        failed_here = 0

        for find_text in _build_search_texts(reference_text):
            # 一旦某个搜索变体已经匹配到至少一处，就不再尝试其它变体，
            # 避免对同一锚点的不同文本表示重复写入。
            if added_here > 0 or skipped_overlap_here > 0 or failed_here > 0:
                break
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
                    skipped_overlap_here += 1
                    log_parts.append(
                        f"  批注 [{idx}] 位置已存在批注，继续向后查找 reference_text={reference_text[:40]}..."
                    )
                    current_start = max(match_end, current_start + 1)
                    continue

                add_exc = _add_comment_with_retries(doc, find_range, comment_text)
                if add_exc is not None:
                    failed_here += 1
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
                else:
                    added_here += 1
                    last_used_end_by_ref[reference_text] = match_end
                    log_parts.append(
                        f"  批注 [{idx}] 已添加: reference_text={reference_text[:40]}... -> comment_text={comment_text[:40]}..."
                    )
                current_start = max(match_end, current_start + 1)

        normalized_attempted = (
            added_here == 0 and skipped_overlap_here == 0 and failed_here == 0
        )
        if normalized_attempted:
            normalized_status, normalized_end = _try_normalized_comment_insert(
                doc=doc,
                reference_text=reference_text,
                comment_text=comment_text,
                current_start=int(last_used_end_by_ref.get(reference_text, search_start)),
                search_start=search_start,
                search_end=search_end,
                log_parts=log_parts,
                idx=idx,
            )
            if normalized_status == "added":
                added_here += 1
                last_used_end_by_ref[reference_text] = int(normalized_end)
            elif normalized_status.startswith("comment_add_failed:"):
                failed_here += 1
                _append_issue(
                    result["issues"],
                    index=idx,
                    reason="comment_add_failed",
                    reference_text=reference_text,
                    comment_text=comment_text,
                    error=normalized_status.split(":", 1)[1],
                )
            elif normalized_status == "normalized_reference_not_unique":
                failed_here += 1
                _append_issue(
                    result["issues"],
                    index=idx,
                    reason="normalized_reference_not_unique",
                    reference_text=reference_text,
                    comment_text=comment_text,
                )
            elif normalized_status == "overlapping_comment_exists":
                skipped_overlap_here += 1

        result["added"] += added_here
        result["failed"] += failed_here

        if added_here > 0:
            # 已成功写入：既有批注位置已自然被跳过，不重复计入 skipped。
            if added_here > 1:
                log_parts.append(
                    f"  批注 [{idx}] 锚点在范围内出现多处，已在 {added_here} 个未批注位置分别写入同一条批注。"
                )
        elif failed_here > 0:
            # 添加失败已经追加过 issue，无需额外处理。
            pass
        elif skipped_overlap_here > 0:
            # 所有匹配位置均已存在批注：按本条候选计一次 skipped，
            # 不按重叠位置累加，保持与既有摘要（按候选条数）口径一致。
            result["skipped"] += 1
            _append_issue(
                result["issues"],
                index=idx,
                reason="overlapping_comment_exists",
                reference_text=reference_text,
                comment_text=comment_text,
            )
            log_parts.append(
                f"  批注 [{idx}] 所有匹配位置均已存在批注，按保守去重策略跳过: {reference_text[:50]}..."
            )
        else:
            # 无任何匹配，记为未找到。
            result["failed"] += 1
            _append_issue(
                result["issues"],
                index=idx,
                reason="reference_text_not_found",
                reference_text=reference_text,
                comment_text=comment_text,
            )
            log_parts.append(
                f"  批注 [{idx}] 未找到可插入的位置或未匹配到引用文本: {reference_text[:50]}..."
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
