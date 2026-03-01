"""
从送审稿复制批注到清洁稿复制出的模板中（按内容锚定复用）。

规则：
- 仅复制“锚点范围之外”的批注（锚点范围由 insertion_before_text / insertion_after_text 定位）
- 批注在目标文档中按 scope_text + prefix/suffix 上下文做匹配定位
- 无法定位的批注会返回到 state，供人工确认
"""

from __future__ import annotations

import bisect
import pathlib
import re
import sys
import time
import logging
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.states import TenderGraphStateBase
from util.word_util import (
    create_word_application,
    close_word_application,
    open_document_with_retry,
    unprotect_document,
    save_document_with_retry,
)
from util.word_util import wdFindStop, wdCollapseEnd
from backend.nodes.common_word_nodes.get_comments import _get_insertion_range

logger = logging.getLogger(__name__)

DEFAULT_CONTEXT_CHARS = 50
MAX_FIND_CANDIDATES = 30
MIN_CONTEXT_SCORE = 0.55
MIN_PARA_SCORE = 0.70
POSITION_SEARCH_WINDOW_FRACTION = 0.10
MIN_POSITION_WINDOW_CHARS = 3000
MAX_POSITION_WINDOW_CHARS = 150000


@dataclass(frozen=True)
class CommentAnchor:
    comment_text: str
    scope_text: str
    prefix_text: str
    suffix_text: str
    paragraph_text: str
    position_ratio: Optional[float]
    norm_scope_text: str
    norm_prefix_text: str
    norm_suffix_text: str
    norm_paragraph_text: str


def _clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return (
        str(text)
        .replace("\x07", "")
        .replace("\r", "\n")
        .replace("\u00a0", " ")
        .strip()
    )


def _norm_text(text: Optional[str]) -> str:
    cleaned = _clean_text(text)
    cleaned = re.sub(r"\s+", "", cleaned)
    return cleaned


def _similarity_norm(na: str, nb: str) -> float:
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    la = len(na)
    lb = len(nb)
    max_len = max(la, lb)
    min_len = min(la, lb)
    if max_len == 0:
        return 1.0
    len_ratio = min_len / max_len
    if len_ratio < 0.35:
        return 0.0
    if max_len <= 160:
        return SequenceMatcher(None, na, nb).ratio()

    def _bigrams(s: str) -> set[str]:
        if len(s) < 2:
            return {s} if s else set()
        return {s[i : i + 2] for i in range(len(s) - 1)}

    ga = _bigrams(na)
    gb = _bigrams(nb)
    if not ga or not gb:
        return 0.0
    inter = len(ga & gb)
    union = len(ga | gb)
    if union == 0:
        return 0.0
    return (inter / union) * len_ratio


def _similarity(a: Optional[str], b: Optional[str]) -> float:
    return _similarity_norm(_norm_text(a), _norm_text(b))


def _overlaps(a_start: int, a_end: int, b_start: Optional[int], b_end: Optional[int]) -> bool:
    if b_start is None or b_end is None:
        return False
    return int(a_end) > int(b_start) and int(a_start) < int(b_end)


def _normalize_span(start: int, end: int) -> tuple[int, int]:
    s = int(start)
    e = int(end)
    if e <= s:
        e = s + 1
    return s, e


def _build_sorted_comment_spans(doc) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    spans: list[tuple[int, int]] = []
    try:
        for c in doc.Comments:
            try:
                scope = c.Scope
                spans.append(_normalize_span(scope.Start, scope.End))
            except Exception:
                continue
    except Exception:
        spans = []

    spans.sort(key=lambda x: (x[0], x[1]))
    starts = [s for s, _ in spans]
    max_ends: list[int] = []
    running = -1
    for _, e in spans:
        running = max(running, int(e))
        max_ends.append(running)
    return spans, starts, max_ends


def _comment_span_overlaps(starts: list[int], max_ends: list[int], query_start: int, query_end: int) -> bool:
    if not starts:
        return False
    s, e = _normalize_span(query_start, query_end)
    idx = bisect.bisect_left(starts, e) - 1
    if idx < 0:
        return False
    return int(max_ends[idx]) > int(s)


def _insert_comment_span(
    spans: list[tuple[int, int]],
    starts: list[int],
    max_ends: list[int],
    new_start: int,
    new_end: int,
) -> None:
    s, e = _normalize_span(new_start, new_end)
    i = bisect.bisect_left(starts, s)
    spans.insert(i, (s, e))
    starts.insert(i, s)
    if i >= len(max_ends):
        prev = max_ends[-1] if max_ends else -1
        max_ends.append(max(prev, e))
        return

    max_ends.insert(i, 0)
    prev = max_ends[i - 1] if i > 0 else -1
    running = prev
    for k in range(i, len(spans)):
        running = max(running, spans[k][1])
        max_ends[k] = running


def _build_anchor_from_comment(doc, comment, context_chars: int) -> CommentAnchor:
    scope = comment.Scope.Duplicate
    scope_start = int(scope.Start)
    scope_end = int(scope.End)
    doc_start = int(doc.Content.Start)
    doc_end = int(doc.Content.End)
    doc_len = max(1, doc_end - doc_start)
    position_ratio: Optional[float] = None
    try:
        position_ratio = max(0.0, min(1.0, (scope_start - doc_start) / doc_len))
    except Exception:
        position_ratio = None

    prefix_start = max(doc_start, scope_start - context_chars)
    suffix_end = min(doc_end, scope_end + context_chars)

    prefix_text = _clean_text(doc.Range(prefix_start, scope_start).Text)
    suffix_text = _clean_text(doc.Range(scope_end, suffix_end).Text)
    scope_text = _clean_text(scope.Text)
    comment_text = _clean_text(comment.Range.Text)

    paragraph_text = ""
    try:
        paragraph_text = _clean_text(scope.Paragraphs(1).Range.Text)
    except Exception:
        paragraph_text = ""

    return CommentAnchor(
        comment_text=comment_text,
        scope_text=scope_text,
        prefix_text=prefix_text,
        suffix_text=suffix_text,
        paragraph_text=paragraph_text,
        position_ratio=position_ratio,
        norm_scope_text=_norm_text(scope_text),
        norm_prefix_text=_norm_text(prefix_text),
        norm_suffix_text=_norm_text(suffix_text),
        norm_paragraph_text=_norm_text(paragraph_text),
    )


def _find_best_scope_match(doc, search_range, anchor: CommentAnchor, context_chars: int):
    needle = (anchor.scope_text or "").strip()
    if not needle:
        return None

    best_rng = None
    best_score = 0.0

    doc_start = int(doc.Content.Start)
    doc_end = int(doc.Content.End)
    window_start = int(search_range.Start)
    try:
        window_text = search_range.Text
        window_len = len(window_text)
    except Exception:
        window_text = None
        window_len = 0

    find_rng = search_range.Duplicate
    find_rng.Find.ClearFormatting()
    find_rng.Find.Text = needle
    find_rng.Find.Forward = True
    find_rng.Find.Wrap = wdFindStop
    find_rng.Find.MatchCase = False
    find_rng.Find.MatchWholeWord = False

    tries = 0
    while find_rng.Find.Execute():
        tries += 1
        candidate = find_rng.Duplicate
        c_start = int(candidate.Start)
        c_end = int(candidate.End)

        if window_text is not None:
            rel_start = max(0, c_start - window_start)
            rel_end = max(rel_start, c_end - window_start)
            rel_start = min(rel_start, window_len)
            rel_end = min(rel_end, window_len)

            prefix_slice = window_text[max(0, rel_start - context_chars) : rel_start]
            suffix_slice = window_text[rel_end : min(window_len, rel_end + context_chars)]
            score = (
                _similarity_norm(anchor.norm_prefix_text, _norm_text(prefix_slice))
                + _similarity_norm(anchor.norm_suffix_text, _norm_text(suffix_slice))
            ) / 2.0
        else:
            prefix_start = max(doc_start, c_start - context_chars)
            suffix_end = min(doc_end, c_end + context_chars)
            cand_prefix = _clean_text(doc.Range(prefix_start, c_start).Text)
            cand_suffix = _clean_text(doc.Range(c_end, suffix_end).Text)
            score = (
                _similarity_norm(anchor.norm_prefix_text, _norm_text(cand_prefix))
                + _similarity_norm(anchor.norm_suffix_text, _norm_text(cand_suffix))
            ) / 2.0
        if score > best_score:
            best_score = score
            best_rng = candidate

        if tries >= MAX_FIND_CANDIDATES:
            break
        find_rng.Collapse(wdCollapseEnd)
        find_rng.End = search_range.End

    if best_rng is not None and best_score >= MIN_CONTEXT_SCORE:
        return best_rng
    return None


def _iter_probe_texts(text: str) -> list[str]:
    cleaned = _clean_text(text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return []
    probes: list[str] = []
    for n in (80, 60, 40, 25):
        if len(cleaned) >= n:
            probes.append(cleaned[:n].strip())
    if len(cleaned) >= 60:
        probes.append(cleaned[-40:].strip())
        mid = max(0, (len(cleaned) // 2) - 20)
        probes.append(cleaned[mid : mid + 40].strip())
    uniq: list[str] = []
    seen: set[str] = set()
    for p in probes:
        if p and len(p) >= 10 and p not in seen:
            uniq.append(p)
            seen.add(p)
    return uniq


def _find_best_paragraph_match(doc, anchor: CommentAnchor, search_range=None):
    para_text = (anchor.paragraph_text or "").strip()
    if not para_text:
        return None

    best_para_rng = None
    best_score = 0.0

    probes = _iter_probe_texts(para_text)
    if not probes:
        return None

    base_rng = (search_range if search_range is not None else doc.Content).Duplicate
    for probe in probes:
        search_rng = base_rng.Duplicate
        search_rng.Find.ClearFormatting()
        search_rng.Find.Text = probe
        search_rng.Find.Forward = True
        search_rng.Find.Wrap = wdFindStop
        search_rng.Find.MatchCase = False
        search_rng.Find.MatchWholeWord = False

        tries = 0
        while search_rng.Find.Execute():
            tries += 1
            try:
                para_rng = search_rng.Paragraphs(1).Range.Duplicate
            except Exception:
                para_rng = None
            if para_rng is not None:
                cand_para_text = _clean_text(para_rng.Text)
                score = _similarity_norm(anchor.norm_paragraph_text, _norm_text(cand_para_text))
                if score > best_score:
                    best_score = score
                    best_para_rng = para_rng
                    if best_score >= 0.93:
                        break
            if tries >= MAX_FIND_CANDIDATES:
                break
            search_rng.Collapse(wdCollapseEnd)
            search_rng.End = base_rng.End
        if best_score >= 0.93:
            break

    if best_para_rng is not None and best_score >= MIN_PARA_SCORE:
        return best_para_rng
    return None


def _get_search_range_for_anchor(doc, anchor: CommentAnchor):
    ratio = anchor.position_ratio
    if ratio is None:
        return None
    doc_start = int(doc.Content.Start)
    doc_end = int(doc.Content.End)
    doc_len = max(1, doc_end - doc_start)
    center = doc_start + int(ratio * doc_len)
    window = int(doc_len * POSITION_SEARCH_WINDOW_FRACTION)
    window = max(MIN_POSITION_WINDOW_CHARS, min(MAX_POSITION_WINDOW_CHARS, window))
    start = max(doc_start, center - window)
    end = min(doc_end, center + window)
    if end <= start:
        return None
    try:
        return doc.Range(start, end)
    except Exception:
        return None


def copy_comments(state: TenderGraphStateBase, config) -> TenderGraphStateBase:
    start_time = time.perf_counter()
    print("[copy_comments] 开始执行...", flush=True)

    origin_tender_path = state.get("origin_tender_path")
    prepared_doc_path = state.get("prepared_doc_path")
    before_text = state.get("insertion_before_text")
    after_text = state.get("insertion_after_text")

    if not origin_tender_path or (isinstance(origin_tender_path, str) and origin_tender_path.strip() == ""):
        return TenderGraphStateBase(copy_comments_log="未上传送审稿，跳过复制批注", copy_comments_unmatched=[])
    if not prepared_doc_path:
        raise ValueError("copy_comments 需要 prepared_doc_path")

    origin_path = Path(origin_tender_path)
    if not origin_path.exists():
        return TenderGraphStateBase(copy_comments_log=f"送审稿不存在，跳过复制批注: {origin_tender_path}", copy_comments_unmatched=[])

    context_chars = int(state.get("copy_comments_context_chars") or DEFAULT_CONTEXT_CHARS)
    target_size = 18.0 if state.get("tender_type") == "xjcg" else 22.0

    dst_check_word = None
    dst_check_doc = None
    dst_check_com_initialized = False
    try:
        dst_check_word, dst_check_com_initialized = create_word_application(
            initial_delay=0.2,
            post_init_delay=0.4,
            use_existing=False,
            node_name="copy_comments-check-dst",
        )
        dst_check_doc = open_document_with_retry(
            word_app=dst_check_word,
            file_path=str(Path(prepared_doc_path).resolve()),
            read_only=True,
            node_name="copy_comments-check-dst",
        )
        try:
            existing_comment_count = int(dst_check_doc.Comments.Count)
        except Exception:
            try:
                existing_comment_count = sum(1 for _ in dst_check_doc.Comments)
            except Exception:
                existing_comment_count = 0
        if existing_comment_count > 0:
            elapsed = time.perf_counter() - start_time
            print(f"[copy_comments] 清洁稿已存在批注({existing_comment_count})，跳过复制批注，耗时 {elapsed:.2f}s")
            return TenderGraphStateBase(
                copy_comments_log=f"清洁稿已存在批注({existing_comment_count})，跳过复制批注，耗时 {elapsed:.2f}s",
                copy_comments_unmatched=[],
                copy_comments_added=0,
            )
    finally:
        close_word_application(
            word_app=dst_check_word,
            doc=dst_check_doc,
            com_initialized=dst_check_com_initialized,
            wait_time=0.0,
            node_name="copy_comments-check-dst",
        )

    word_app = None
    src_doc = None
    com_initialized = False

    anchors: list[CommentAnchor] = []
    src_range_start: Optional[int] = None
    src_range_end: Optional[int] = None

    try:
        word_app, com_initialized = create_word_application(
            initial_delay=0.2,
            post_init_delay=0.2,
            use_existing=False,
            node_name="copy_comments-src",
        )
        src_doc = open_document_with_retry(
            word_app=word_app,
            file_path=str(origin_path.resolve()),
            read_only=True,
            node_name="copy_comments-src",
        )

        if before_text and after_text:
            src_range_start, src_range_end = _get_insertion_range(
                src_doc, word_app, before_text, after_text, target_size
            )

        total = 0
        copied_candidates = 0
        for c in src_doc.Comments:
            total += 1
            try:
                scope = c.Scope.Duplicate
                if _overlaps(int(scope.Start), int(scope.End), src_range_start, src_range_end):
                    continue
                anchors.append(_build_anchor_from_comment(src_doc, c, context_chars))
                copied_candidates += 1
            except Exception:
                continue

        src_doc.Close(SaveChanges=False)
        src_doc = None
    finally:
        close_word_application(
            word_app=word_app,
            doc=src_doc,
            com_initialized=com_initialized,
            wait_time=0.0,
            node_name="copy_comments-src",
        )

    if not anchors:
        elapsed = time.perf_counter() - start_time
        return TenderGraphStateBase(
            copy_comments_log=f"送审稿无可复制批注（锚点范围外=0），耗时 {elapsed:.2f}s",
            copy_comments_unmatched=[],
            copy_comments_added=0,
        )

    dst_word = None
    dst_doc = None
    dst_com_initialized = False
    unmatched: list[dict] = []
    added = 0

    try:
        dst_word, dst_com_initialized = create_word_application(
            initial_delay=0.2,
            post_init_delay=0.6,
            use_existing=False,
            node_name="copy_comments-dst",
        )
        dst_doc = open_document_with_retry(
            word_app=dst_word,
            file_path=str(Path(prepared_doc_path).resolve()),
            read_only=False,
            node_name="copy_comments-dst",
        )
        unprotect_document(dst_doc, node_name="copy_comments-dst")

        dst_range_start: Optional[int] = None
        dst_range_end: Optional[int] = None
        if before_text and after_text:
            dst_range_start, dst_range_end = _get_insertion_range(
                dst_doc, dst_word, before_text, after_text, target_size
            )

        spans, span_starts, span_max_ends = _build_sorted_comment_spans(dst_doc)

        for idx, anchor in enumerate(anchors, 1):
            try:
                best_rng = None
                primary_rng = _get_search_range_for_anchor(dst_doc, anchor)
                if primary_rng is not None:
                    best_rng = _find_best_scope_match(dst_doc, primary_rng, anchor, context_chars)
                    if best_rng is None:
                        para_rng = _find_best_paragraph_match(dst_doc, anchor, primary_rng)
                        if para_rng is not None and (anchor.scope_text or "").strip():
                            scoped = para_rng.Duplicate
                            scoped.Find.ClearFormatting()
                            scoped.Find.Text = anchor.scope_text
                            scoped.Find.Forward = True
                            scoped.Find.Wrap = wdFindStop
                            scoped.Find.MatchCase = False
                            scoped.Find.MatchWholeWord = False
                            if scoped.Find.Execute():
                                best_rng = scoped.Duplicate
                            else:
                                end_pos = max(int(para_rng.Start), int(para_rng.End) - 1)
                                best_rng = dst_doc.Range(end_pos, end_pos)
                        elif para_rng is not None:
                            end_pos = max(int(para_rng.Start), int(para_rng.End) - 1)
                            best_rng = dst_doc.Range(end_pos, end_pos)

                if best_rng is None:
                    unmatched.append(
                        {
                            "index": idx,
                            "scope_text": anchor.scope_text,
                            "comment_text": anchor.comment_text,
                            "prefix_text": anchor.prefix_text,
                            "suffix_text": anchor.suffix_text,
                            "reason": "窗口内未匹配到定位点",
                        }
                    )
                    continue

                if _overlaps(int(best_rng.Start), int(best_rng.End), dst_range_start, dst_range_end):
                    unmatched.append(
                        {
                            "index": idx,
                            "scope_text": anchor.scope_text,
                            "comment_text": anchor.comment_text,
                            "reason": "目标位置落在锚点范围内，已跳过",
                        }
                    )
                    continue

                if _comment_span_overlaps(span_starts, span_max_ends, int(best_rng.Start), int(best_rng.End)):
                    unmatched.append(
                        {
                            "index": idx,
                            "scope_text": anchor.scope_text,
                            "comment_text": anchor.comment_text,
                            "reason": "目标位置已有批注，已跳过",
                        }
                    )
                    continue

                dst_doc.Comments.Add(Range=best_rng.Duplicate, Text=anchor.comment_text)
                _insert_comment_span(
                    spans,
                    span_starts,
                    span_max_ends,
                    int(best_rng.Start),
                    int(best_rng.End),
                )
                added += 1
            except Exception as e:
                unmatched.append(
                    {
                        "index": idx,
                        "scope_text": anchor.scope_text,
                        "comment_text": anchor.comment_text,
                        "reason": f"添加失败: {e}",
                    }
                )

        save_document_with_retry(dst_doc, node_name="copy_comments-dst")
    finally:
        close_word_application(
            word_app=dst_word,
            doc=dst_doc,
            com_initialized=dst_com_initialized,
            wait_time=0.0,
            node_name="copy_comments-dst",
        )

    elapsed = time.perf_counter() - start_time
    log = f"复制批注完成：候选={len(anchors)}，成功={added}，未匹配={len(unmatched)}，耗时 {elapsed:.2f}s"
    print(f"[copy_comments] {log}", flush=True)
    return TenderGraphStateBase(
        copy_comments_log=log,
        copy_comments_added=added,
        copy_comments_unmatched=unmatched,
    )
