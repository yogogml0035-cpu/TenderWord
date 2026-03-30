"""
锚点定位工具函数（回归 master 语义）。

核心语义：
1. 文本按空格变体递减匹配；
2. 段落扫描优先，严格字体/字号候选优先；
3. Find.Execute 作为兜底。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from backend.config.tender_config import (
    CONTENT_START_MODE_NEXT_PAGE_START,
    CONTENT_START_MODE_SAME_PAGE_AFTER_ANCHOR,
    get_content_start_mode,
)
from backend.util.word_util.word_constants import (
    wdActiveEndPageNumber,
    wdCollapseEnd,
    wdFindStop,
    wdGoToAbsolute,
    wdGoToPage,
)


def iter_anchor_text_variants(text: str) -> List[str]:
    """生成锚点文本的空格变体序列。"""
    if text is None:
        return []
    cur = str(text).replace("\u3000", " ")
    variants: List[str] = []
    seen: set[str] = set()
    while True:
        if cur not in seen:
            variants.append(cur)
            seen.add(cur)
        if " " not in cur:
            break
        if "  " in cur:
            cur = re.sub(r" {2,}", lambda m: " " * (len(m.group(0)) - 1), cur)
        else:
            cur = cur.replace(" ", "")
    return variants


def find_anchor_with_variants(text: str, find_once):
    """按文本变体依次调用查找函数，命中即返回。"""
    for candidate in iter_anchor_text_variants(text):
        hit = find_once(candidate)
        if hit:
            return hit, candidate
    return None, text


def norm_space_text(text: str) -> str:
    """规整文本中的连续空白。"""
    if text is None:
        return ""
    normalized = str(text).replace("\u3000", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def iter_paragraph_anchor_hits(
    doc,
    text: str,
    target_size: float,
    *,
    fonts=None,
    normalize_space: bool = False,
    strip_control: bool = False,
    with_page_info: bool = True,
) -> List[Dict[str, Any]]:
    """
    段落扫描命中集合。

    语义与 master 保持一致：先文本匹配，再计算字体/字号匹配标记。
    """
    if fonts is None:
        fonts = ("宋体", "SimSun")
    want = norm_space_text(text) if normalize_space else ("" if text is None else str(text).strip())
    hits: List[Dict[str, Any]] = []
    for para in doc.Paragraphs:
        try:
            raw = para.Range.Text
            if strip_control:
                raw = raw.replace("\r", "").replace("\a", "")
            got = norm_space_text(raw) if normalize_space else str(raw).strip()
            if got != want:
                continue
            font_name = para.Range.Font.Name
            font_size = para.Range.Font.Size
            is_font = str(font_name) in fonts
            is_size = abs(float(font_size) - float(target_size)) < 0.5
            hit = {
                "start": int(para.Range.Start),
                "end": int(para.Range.End),
                "font": str(font_name),
                "size": float(font_size),
                "is_font": is_font,
                "is_size": is_size,
            }
            if with_page_info:
                hit["page"] = int(para.Range.Information(wdActiveEndPageNumber))
            hits.append(hit)
        except Exception:
            continue
    return hits


def iter_paragraph_anchor_hits_with_variants(
    doc,
    text: str,
    target_size: float,
    *,
    fonts=None,
    normalize_space: bool = False,
    strip_control: bool = False,
    with_page_info: bool = True,
) -> Tuple[List[Dict[str, Any]], str]:
    """按文本变体扫描段落，返回首个命中的候选集与命中文本。"""
    for candidate in iter_anchor_text_variants(text):
        hits = iter_paragraph_anchor_hits(
            doc,
            candidate,
            target_size,
            fonts=fonts,
            normalize_space=normalize_space,
            strip_control=strip_control,
            with_page_info=with_page_info,
        )
        if hits:
            return hits, candidate
    return [], text


def pick_anchor(hits: List[Dict[str, Any]], prefer_last: bool = True) -> Optional[Dict[str, Any]]:
    """
    从候选中选锚点。

    规则：严格匹配（字体+字号）优先；然后按页码+start 排序，取 first/last。
    """
    if not hits:
        return None
    strict = [h for h in hits if h.get("is_font") and h.get("is_size")]
    pool = strict if strict else hits
    if pool and "page" in pool[0]:
        pool.sort(key=lambda x: (x.get("page", 0), x.get("start", 0)))
    else:
        pool.sort(key=lambda x: x.get("start", 0))
    return pool[-1] if prefer_last else pool[0]


def pick_after_anchor(hits: List[Dict[str, Any]], min_start: int) -> Optional[Dict[str, Any]]:
    """选取起始位置不小于 min_start 的最早后置锚点。"""
    if not hits:
        return None
    hits2 = [h for h in hits if int(h.get("start", -1)) >= int(min_start)]
    if not hits2:
        return None
    strict = [h for h in hits2 if h.get("is_font") and h.get("is_size")]
    pool = strict if strict else hits2
    pool.sort(key=lambda x: (x.get("start", 0), x.get("page", 0)))
    return pool[0]


def find_word_anchor(
    doc_content,
    text: str,
    start_pos: int = 0,
    target_size: float = 18.0,
    fonts=None,
) -> Optional[Dict[str, Any]]:
    """用 Find.Execute 按文本变体查找锚点。"""
    if fonts is None:
        fonts = ("宋体", "SimSun")

    def _find_once(candidate: str) -> Optional[Dict[str, Any]]:
        find_rng = doc_content.Duplicate
        find_rng.Start = max(0, int(start_pos))
        find_rng.End = doc_content.End
        finder = find_rng.Find
        finder.ClearFormatting()
        finder.Text = candidate
        finder.Forward = True
        finder.Wrap = wdFindStop
        finder.MatchCase = False
        finder.MatchWholeWord = False
        while finder.Execute():
            try:
                font_name = find_rng.Font.Name
                font_size = find_rng.Font.Size
                is_font = str(font_name) in fonts
                is_size = abs(float(font_size) - float(target_size)) < 0.5
                if is_font and is_size:
                    page = find_rng.Information(wdActiveEndPageNumber)
                    return {
                        "page": int(page),
                        "start": int(find_rng.Start),
                        "end": int(find_rng.End),
                        "used_text": candidate,
                        "font": str(font_name),
                        "size": float(font_size),
                        "is_font": is_font,
                        "is_size": is_size,
                    }
            except Exception:
                pass
            find_rng.Collapse(wdCollapseEnd)
            find_rng.End = doc_content.End
        return None

    for candidate in iter_anchor_text_variants(text):
        hit = _find_once(candidate)
        if hit:
            hit["used_text"] = candidate
            return hit
    return None


def _iter_paragraph_hits(doc, text: str, target_size: float) -> List[Dict[str, Any]]:
    """兼容旧名称：段落扫描候选。"""
    return iter_paragraph_anchor_hits(doc, text, target_size)


def _pick_anchor(hits: List[Dict[str, Any]], prefer_last: bool = True) -> Optional[Dict[str, Any]]:
    """兼容旧名称：候选选择。"""
    return pick_anchor(hits, prefer_last=prefer_last)


def find_anchor_with_find(
    doc, text: str, target_size: float, start_pos: int = None
) -> Optional[Dict[str, Any]]:
    """兼容旧名称：Find.Execute 兜底。"""
    actual_start = 0 if start_pos is None else int(start_pos)
    return find_word_anchor(
        doc_content=doc.Content,
        text=text,
        start_pos=actual_start,
        target_size=target_size,
    )


def find_anchor_range(
    doc,
    before_text: str,
    after_text: str,
    target_size: float | None = None,
    *,
    before_size: float | None = None,
    after_size: float | None = None,
    prefer_before: str = "last",
    prefer_after: str = "first",
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """统一查找前后锚点：段落扫描优先，Find.Execute 兜底。"""
    default_size = 18.0 if target_size is None else float(target_size)
    resolved_before_size = default_size if before_size is None else float(before_size)
    resolved_after_size = resolved_before_size if after_size is None else float(after_size)

    before_hits, used_before_text = iter_paragraph_anchor_hits_with_variants(
        doc,
        before_text,
        resolved_before_size,
        normalize_space=True,
        strip_control=False,
        with_page_info=True,
    )
    before_hit = pick_anchor(before_hits, prefer_last=(prefer_before == "last"))
    if before_hit:
        before_hit = dict(before_hit)
        before_hit.setdefault("used_text", used_before_text)
    if not before_hit:
        before_hit = find_word_anchor(
            doc_content=doc.Content,
            text=before_text,
            start_pos=0,
            target_size=resolved_before_size,
        )
    if not before_hit:
        return None, None

    before_end_pos = int(before_hit["end"])
    after_hits, used_after_text = iter_paragraph_anchor_hits_with_variants(
        doc,
        after_text,
        resolved_after_size,
        normalize_space=True,
        strip_control=False,
        with_page_info=True,
    )
    after_hits = [h for h in after_hits if int(h.get("start", -1)) >= before_end_pos]
    after_hit = pick_anchor(after_hits, prefer_last=(prefer_after == "last"))
    if after_hit:
        after_hit = dict(after_hit)
        after_hit.setdefault("used_text", used_after_text)
    if not after_hit:
        after_hit = find_word_anchor(
            doc_content=doc.Content,
            text=after_text,
            start_pos=before_end_pos,
            target_size=resolved_after_size,
        )

    return before_hit, after_hit


def _probe_range_page(
    doc,
    start: int,
    end: int,
    *,
    probe_end: bool,
    fallback_page: int,
) -> int:
    """尽量用实际 range 位置回推页码，失败时回退到锚点页码。"""
    try:
        doc_start = max(0, int(start))
        doc_end = max(doc_start, int(end))
        if doc_end <= doc_start:
            probe_start = doc_start
            probe_end_pos = doc_start + 1
        elif probe_end:
            probe_start = max(doc_start, doc_end - 1)
            probe_end_pos = doc_end
        else:
            probe_start = doc_start
            probe_end_pos = min(doc_end, doc_start + 1)
        probe_rng = doc.Range(probe_start, probe_end_pos)
        return int(probe_rng.Information(wdActiveEndPageNumber))
    except Exception:
        return int(fallback_page)


def resolve_anchor_content_range(
    *,
    doc,
    word_app,
    before_hit: Dict[str, Any],
    after_hit: Dict[str, Any],
    tender_type: str | None = None,
    content_start_mode: str | None = None,
    allow_empty: bool = False,
) -> Dict[str, int]:
    """根据 tender type 规则，把锚点命中解析为正文区间和真实页码。"""
    before_page = int(before_hit["page"])
    before_end_pos = int(before_hit["end"])
    after_page = int(after_hit["page"])
    after_start_pos = int(after_hit["start"])

    resolved_start_mode = (
        str(content_start_mode or "").strip()
        or get_content_start_mode(str(tender_type or "xjcg"))
    )
    if resolved_start_mode not in {
        CONTENT_START_MODE_NEXT_PAGE_START,
        CONTENT_START_MODE_SAME_PAGE_AFTER_ANCHOR,
    }:
        resolved_start_mode = CONTENT_START_MODE_NEXT_PAGE_START

    range_start = before_end_pos
    if resolved_start_mode == CONTENT_START_MODE_NEXT_PAGE_START:
        if after_page <= before_page:
            raise ValueError(
                "后置锚点页码不大于前置锚点页码: "
                f"before_page={before_page}, after_page={after_page}"
            )
        try:
            selection = word_app.Selection
            selection.GoTo(wdGoToPage, wdGoToAbsolute, before_page + 1)
            next_page_start = int(selection.Start)
            if next_page_start > range_start:
                range_start = next_page_start
        except Exception:
            pass
    else:
        if after_page < before_page:
            raise ValueError(
                "后置锚点页码早于前置锚点页码: "
                f"before_page={before_page}, after_page={after_page}"
            )

    range_end = after_start_pos
    if range_end < range_start or (range_end == range_start and not allow_empty):
        raise ValueError(
            "锚点范围非法: "
            f"range_start={range_start}, range_end={range_end}, "
            f"before_page={before_page}, after_page={after_page}"
        )

    fallback_start_page = (
        before_page + 1
        if resolved_start_mode == CONTENT_START_MODE_NEXT_PAGE_START
        else before_page
    )
    fallback_end_page = (
        max(fallback_start_page, after_page - 1)
        if after_page > fallback_start_page
        else fallback_start_page
    )

    start_page = _probe_range_page(
        doc,
        range_start,
        range_end,
        probe_end=False,
        fallback_page=fallback_start_page,
    )
    end_page = _probe_range_page(
        doc,
        range_start,
        range_end,
        probe_end=True,
        fallback_page=fallback_end_page,
    )
    if end_page < start_page:
        end_page = start_page

    return {
        "range_start": int(range_start),
        "range_end": int(range_end),
        "start_page": int(start_page),
        "end_page": int(end_page),
        "before_page": before_page,
        "after_page": after_page,
    }


__all__ = [
    "iter_anchor_text_variants",
    "find_anchor_with_variants",
    "find_word_anchor",
    "norm_space_text",
    "iter_paragraph_anchor_hits",
    "iter_paragraph_anchor_hits_with_variants",
    "pick_anchor",
    "pick_after_anchor",
    "find_anchor_range",
    "resolve_anchor_content_range",
    "find_anchor_with_find",
    "_iter_paragraph_hits",
    "_pick_anchor",
]
