"""
锚点定位工具函数

统一提供两种锚点定位策略：
1. 段落扫描（_iter_paragraph_hits + _pick_anchor）- 从 GNGK 提取
2. Find.Execute 兜底（find_anchor_with_find）- 从 XJCG 提取

使用 find_anchor_range() 统一调用，自动选择最佳策略。
"""

from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any

from backend.util.word_util import (
    wdActiveEndPageNumber,
    wdFindStop,
    wdCollapseEnd,
)


def _iter_paragraph_hits(doc, text: str, target_size: float) -> List[Dict[str, Any]]:
    """
    遍历所有段落，返回所有匹配 text 且字号接近 target_size 的候选。

    从 GNGK extract_tender_params 提取的段落扫描逻辑。

    Args:
        doc: Word 文档对象
        text: 要查找的文本（精确匹配，去除首尾空白）
        target_size: 目标字号（如 18.0 或 22.0）

    Returns:
        候选列表，每个候选包含：
        - page: 页码
        - start: 起始位置
        - end: 结束位置
        - font: 字体名称
        - size: 字号
        - is_font: 是否匹配目标字体（宋体/SimSun）
        - is_size: 是否匹配目标字号（容差 < 0.5）
    """
    hits = []
    for para in doc.Paragraphs:
        try:
            raw = para.Range.Text
            stripped = raw.strip()
            if stripped != text:
                continue

            font_name = para.Range.Font.Name
            font_size = para.Range.Font.Size
            page = para.Range.Information(wdActiveEndPageNumber)

            # 字体可放宽：只要是宋体/SimSun即可；字号按容差匹配
            is_font = font_name == "宋体" or font_name == "SimSun"
            is_size = abs(float(font_size) - float(target_size)) < 0.5

            hits.append(
                {
                    "page": int(page),
                    "start": int(para.Range.Start),
                    "end": int(para.Range.End),
                    "font": str(font_name),
                    "size": float(font_size),
                    "is_font": is_font,
                    "is_size": is_size,
                }
            )
        except Exception:
            continue
    return hits


def _pick_anchor(
    hits: List[Dict[str, Any]], prefer_last: bool = True
) -> Optional[Dict[str, Any]]:
    """
    从候选里选一个锚点：默认选页码最大的（避开目录）。

    从 GNGK extract_tender_params 提取的命中选取逻辑。

    Args:
        hits: _iter_paragraph_hits 返回的候选列表
        prefer_last: True 则选页码最大的（默认），False 则选页码最小的

    Returns:
        选中的候选字典，如果无候选则返回 None
    """
    if not hits:
        return None
    # 优先：字体正确 + 字号正确
    strict = [h for h in hits if h["is_font"] and h["is_size"]]
    pool = strict if strict else hits
    pool.sort(key=lambda x: (x["page"], x["start"]))
    return pool[-1] if prefer_last else pool[0]


def find_anchor_with_find(
    doc, text: str, target_size: float, start_pos: int = None
) -> Optional[Dict[str, Any]]:
    """
    使用 Find.Execute 查找锚点（兜底策略）。

    从 XJCG extract_tender_params 提取的 Find.Execute 循环查找逻辑。
    当段落扫描找不到时，使用此方法作为兜底。

    Args:
        doc: Word 文档对象
        text: 要查找的文本
        target_size: 目标字号（如 18.0）
        start_pos: 搜索起始位置（可选，默认从文档开头）

    Returns:
        找到的锚点字典，包含 page, start, end, font, size；
        如果未找到则返回 None
    """
    doc_content = doc.Content
    find_rng = doc_content.Duplicate

    # 如果指定了起始位置，调整搜索范围
    if start_pos is not None:
        find_rng.Start = start_pos
        find_rng.End = doc_content.End

    find_obj = find_rng.Find
    find_obj.ClearFormatting()
    find_obj.Text = text
    find_obj.Forward = True
    find_obj.Wrap = wdFindStop
    find_obj.MatchCase = False
    find_obj.MatchWholeWord = False

    while find_obj.Execute():
        try:
            # 检查字体和字号
            font_name = find_rng.Font.Name
            font_size = find_rng.Font.Size
            is_font = font_name == "宋体" or font_name == "SimSun"
            is_size = abs(font_size - target_size) < 0.5

            if is_font and is_size:
                page = find_rng.Information(wdActiveEndPageNumber)
                return {
                    "page": int(page),
                    "start": int(find_rng.Start),
                    "end": int(find_rng.End),
                    "font": str(font_name),
                    "size": float(font_size),
                    "is_font": is_font,
                    "is_size": is_size,
                }
            else:
                # 继续搜索下一个匹配项
                find_rng.Collapse(wdCollapseEnd)
                find_rng.End = doc_content.End
        except Exception:
            # 出错时继续搜索
            find_rng.Collapse(wdCollapseEnd)
            find_rng.End = doc_content.End
            continue

    return None


def find_anchor_range(
    doc,
    before_text: str,
    after_text: str,
    target_size: float,
    prefer_before: str = "last",
    prefer_after: str = "first",
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    统一双策略函数：查找前置锚点和后置锚点。

    策略：
    1. 先尝试段落扫描（_iter_paragraph_hits + _pick_anchor）
    2. 若无候选，启用 Find.Execute 兜底（find_anchor_with_find）

    Args:
        doc: Word 文档对象
        before_text: 前置锚点文本
        after_text: 后置锚点文本
        target_size: 目标字号（18.0 用于询价，22.0 用于公开招标）
        prefer_before: 前置锚点选取策略，'last' 选页码最大的（避开目录），'first' 选最小的
        prefer_after: 后置锚点选取策略，'first' 选页码最小的（第一个后续章节），'last' 选最大的

    Returns:
        (before_dict, after_dict) 元组：
        - before_dict: 前置锚点信息，包含 page, start, end, font, size 等
        - after_dict: 后置锚点信息
        - 如果某个锚点未找到，对应项为 None
    """
    # === 1. 查找前置锚点 ===
    # 尝试段落扫描
    before_hits = _iter_paragraph_hits(doc, before_text, target_size)
    before_hit = _pick_anchor(before_hits, prefer_last=(prefer_before == "last"))

    # 如果段落扫描失败，使用 Find.Execute 兜底
    if not before_hit:
        before_hit = find_anchor_with_find(doc, before_text, target_size)

    if not before_hit:
        return (None, None)

    before_end_pos = before_hit["end"]

    # === 2. 查找后置锚点 ===
    # 尝试段落扫描（只保留在前置锚点之后出现的）
    after_hits = _iter_paragraph_hits(doc, after_text, target_size)
    after_hits = [h for h in after_hits if h["start"] >= before_end_pos]
    after_hit = _pick_anchor(after_hits, prefer_last=(prefer_after == "last"))

    # 如果段落扫描失败，使用 Find.Execute 兜底（从前置锚点之后开始）
    if not after_hit:
        after_hit = find_anchor_with_find(
            doc, after_text, target_size, start_pos=before_end_pos
        )

    return (before_hit, after_hit)


# 导出的公共 API
__all__ = [
    "find_anchor_range",
    "find_anchor_with_find",
    "_iter_paragraph_hits",
    "_pick_anchor",
]
