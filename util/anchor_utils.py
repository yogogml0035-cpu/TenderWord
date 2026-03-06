import re

from util.word_constants import (
    wdFindStop,
    wdCollapseEnd,
    wdActiveEndPageNumber,
)


def iter_anchor_text_variants(text: str) -> list[str]:
    if text is None:
        return []
    cur = str(text).replace("\u3000", " ")
    variants: list[str] = []
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
    for candidate in iter_anchor_text_variants(text):
        hit = find_once(candidate)
        if hit:
            return hit, candidate
    return None, text


def find_word_anchor(doc_content, text: str, start_pos: int = 0, target_size: float = 18.0, fonts=None):
    if fonts is None:
        fonts = ("宋体", "SimSun")

    def _find_once(candidate: str):
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
                    "font": font_name,
                    "size": font_size,
                }
            find_rng.Collapse(wdCollapseEnd)
            find_rng.End = doc_content.End
        return None

    for candidate in iter_anchor_text_variants(text):
        hit = _find_once(candidate)
        if hit:
            hit["used_text"] = candidate
            return hit
    return None


def norm_space_text(text: str) -> str:
    if text is None:
        return ""
    text = str(text).replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def iter_paragraph_anchor_hits(
    doc,
    text: str,
    target_size: float,
    *,
    fonts=None,
    normalize_space: bool = False,
    strip_control: bool = False,
    with_page_info: bool = True,
):
    if fonts is None:
        fonts = ("宋体", "SimSun")
    want = norm_space_text(text) if normalize_space else ("" if text is None else str(text).strip())
    hits = []
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
):
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


def pick_anchor(hits, prefer_last: bool = True):
    if not hits:
        return None
    strict = [h for h in hits if h.get("is_font") and h.get("is_size")]
    pool = strict if strict else hits
    if pool and "page" in pool[0]:
        pool.sort(key=lambda x: (x.get("page", 0), x.get("start", 0)))
    else:
        pool.sort(key=lambda x: x.get("start", 0))
    return pool[-1] if prefer_last else pool[0]


def pick_after_anchor(hits, min_start: int):
    if not hits:
        return None
    hits2 = [h for h in hits if int(h.get("start", -1)) >= int(min_start)]
    if not hits2:
        return None
    strict = [h for h in hits2 if h.get("is_font") and h.get("is_size")]
    pool = strict if strict else hits2
    pool.sort(key=lambda x: (x.get("start", 0), x.get("page", 0)))
    return pool[0]
