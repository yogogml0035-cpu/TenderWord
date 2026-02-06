"""
从送审稿 Word 文档中提取批注、删除线、非黑色字体

本节点直接调用 util.word_document_inspector 工具模块的 WordDocumentInspector.analyze_document()：
- 在节点内完成：创建 Word、打开送审稿文档、关闭文档（与 test_document_inspector 一致）
- 将 DocumentAnalysisResult 映射为 state 字段（comment_plan、comment_plan_detail、
  strikethrough_plan、non_black_font_plan）

该节点在 prepare_template 节点之后执行。
"""

from __future__ import annotations

import pathlib
import sys
import time
import logging
from pathlib import Path

# 添加项目根目录到 sys.path
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from states import XjcgTenderGraphState
from util.word_document_inspector import WordDocumentInspector, DocumentAnalysisResult
from util.word_application_util import (
    create_word_application,
    close_word_application,
    open_document_with_retry,
)
from util.word_constants import (
    wdGoToPage,
    wdGoToAbsolute,
    wdActiveEndPageNumber,
)

logger = logging.getLogger(__name__)


def _iter_paragraph_hits(doc, text: str, target_size: float):
    """遍历所有段落，返回所有匹配 text 且字号接近 target_size 的候选。"""
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
            is_font = font_name in ("宋体", "SimSun")
            is_size = abs(float(font_size) - float(target_size)) < 0.5
            hits.append({
                "page": int(page),
                "start": int(para.Range.Start),
                "end": int(para.Range.End),
                "font": str(font_name),
                "size": float(font_size),
                "is_font": is_font,
                "is_size": is_size,
            })
        except Exception:
            continue
    return hits


def _pick_anchor(hits, prefer_last: bool = True):
    """从候选里选一个锚点：默认选页码最大的（避开目录）。"""
    if not hits:
        return None
    strict = [h for h in hits if h["is_font"] and h["is_size"]]
    pool = strict if strict else hits
    pool.sort(key=lambda x: (x["page"], x["start"]))
    return pool[-1] if prefer_last else pool[0]


def _get_insertion_range(doc, word_app, before_text: str, after_text: str, target_size: float):
    """
    根据 insertion_before_text / insertion_after_text 在文档中定位锚点，返回抽取范围 (range_start, range_end)。
    与 gngk_extract_tender_params 中的锚点逻辑一致：仅批注会按此范围过滤。

    Returns:
        (range_start, range_end) 或 (None, None)（未找到锚点或参数无效时）
    """
    if not before_text or not after_text:
        return None, None
    before_hits = _iter_paragraph_hits(doc, before_text, target_size)
    before_hit = _pick_anchor(before_hits, prefer_last=True)
    if not before_hit:
        logger.info("get_comments 未找到前置锚点 '%s'，不按范围过滤批注", before_text)
        return None, None
    before_end_pos = before_hit["end"]
    before_page = before_hit["page"]
    try:
        selection = word_app.Selection
        selection.GoTo(wdGoToPage, wdGoToAbsolute, before_page + 1)
        next_page_start = selection.Start
        if next_page_start > before_end_pos:
            before_end_pos = next_page_start
    except Exception:
        pass
    after_hits = _iter_paragraph_hits(doc, after_text, target_size)
    after_hits = [h for h in after_hits if h["start"] >= before_end_pos]
    after_hit = _pick_anchor(after_hits, prefer_last=False)
    if not after_hit:
        logger.info("get_comments 未找到后置锚点 '%s'，不按范围过滤批注", after_text)
        return None, None
    after_start_pos = after_hit["start"]
    return before_end_pos, after_start_pos


def _empty_plan_state(state: XjcgTenderGraphState) -> XjcgTenderGraphState:
    """
    未上传送审稿或文件无效时返回的空计划状态。
    
    仅返回本节点负责维护的计划相关字段，避免与并行节点产生状态冲突。
    """
    return XjcgTenderGraphState(
        comment_plan=[],
        comment_plan_detail=[],
        strikethrough_plan=[],
        non_black_font_plan=[],
    )


def _result_to_state_updates(result: DocumentAnalysisResult) -> dict:
    """将 DocumentAnalysisResult 转为可写入 state 的字典"""
    comment_plan = [c.content for c in result.comments]
    comment_plan_detail = [
        {"content": c.content, "scope_text": c.scope_text, "reference_text": c.reference_text}
        for c in result.comments
    ]
    strikethrough_plan = [
        {
            "paragraph_text": s.paragraph_text,
            "strikethrough_text": s.strikethrough_text,
            "reference_text": s.strikethrough_text,
        }
        for s in result.strikethroughs
    ]
    non_black_font_plan = [
        {
            "paragraph_text": f.paragraph_text,
            "font_text": f.font_text,
            "reference_text": f.font_text,
        }
        for f in result.non_black_fonts
    ]
    return {
        "comment_plan": comment_plan,
        "comment_plan_detail": comment_plan_detail,
        "strikethrough_plan": strikethrough_plan,
        "non_black_font_plan": non_black_font_plan,
    }


def get_comments(state: XjcgTenderGraphState, config) -> XjcgTenderGraphState:
    """
    从送审稿 Word 文档中提取批注、删除线、非黑色字体。

    若 state 中提供 insertion_before_text 与 insertion_after_text，则按与
    gngk_extract_tender_params 相同的锚点逻辑在文档中定位范围（只计算一次），
    仅在该范围内统计批注、删除线、非黑字（批注按 Scope 与范围有交集，删除线/非黑字按段落 Range 与范围有交集）。

    Args:
        state: LangGraph 状态，包含 origin_tender_path；可选 insertion_before_text、
            insertion_after_text、tender_type（用于字号：xjcg=18，否则 22）
        config: 节点配置（当前未使用）

    Returns:
        更新后的状态，包含 comment_plan、comment_plan_detail、
        strikethrough_plan、non_black_font_plan
    """
    start_time = time.perf_counter()
    origin_tender_path = state.get("origin_tender_path")

    if not origin_tender_path or (isinstance(origin_tender_path, str) and origin_tender_path.strip() == ""):
        logger.info("未上传送审稿文件，批注/删除线/非黑字计划均为空")
        return _empty_plan_state(state)

    file_path = Path(origin_tender_path)
    if not file_path.exists():
        logger.warning("送审稿文件不存在: %s", origin_tender_path)
        return _empty_plan_state(state)

    print("[get_comments] 开始执行...", flush=True)
    logger.info("get_comments 开始执行，送审稿路径: %s", origin_tender_path)

    word_app = None
    doc = None
    com_initialized = False

    try:
        print("[get_comments] 正在创建 Word 并打开送审稿...", flush=True)
        word_app, com_initialized = create_word_application(
            initial_delay=0.3,
            post_init_delay=0.2,
            use_existing=False,
            node_name="get_comments",
        )
        doc = open_document_with_retry(
            word_app,
            str(file_path),
            read_only=True,
            node_name="get_comments",
        )
        inspector = WordDocumentInspector(
            word_app=word_app,
            doc=doc,
            node_name="get_comments",
        )
        # 锚点范围只计算一次：根据 insertion_before_text / insertion_after_text 定位 [range_start, range_end)，
        # 然后一次性传入 inspector，批注/删除线/非黑字均只在该范围内统计（不再重复算范围）
        range_start, range_end = None, None
        before_text = state.get("insertion_before_text")
        after_text = state.get("insertion_after_text")
        if not before_text or not after_text:
            logger.info(
                "get_comments 未提供 insertion_before_text / insertion_after_text，将在整篇文档内统计批注/删除线/非黑字"
            )
        if before_text and after_text:
            target_size = 18.0 if state.get("tender_type") == "xjcg" else 22.0
            range_start, range_end = _get_insertion_range(
                doc, word_app, before_text, after_text, target_size
            )
            if range_start is not None and range_end is not None:
                print(
                    "[get_comments] 锚点范围仅计算一次 -> [%d, %d)，批注/删除线/非黑字均只在此范围内统计"
                    % (range_start, range_end),
                    flush=True,
                )
        result = inspector.analyze_document(
            range_start=range_start,
            range_end=range_end,
        )
    except Exception as e:
        logger.error("送审稿文档分析失败: %s", e, exc_info=True)
        return _empty_plan_state(state)
    finally:
        if doc is not None:
            try:
                doc.Close(SaveChanges=False)
            except Exception as e:
                logger.warning("关闭送审稿文档时出错: %s", e)
            doc = None
        close_word_application(
            word_app=word_app,
            doc=doc,
            com_initialized=com_initialized,
            wait_time=0.0,
            node_name="get_comments",
        )

    updates = _result_to_state_updates(result)
    elapsed = time.perf_counter() - start_time
    print(
        "[get_comments] 执行完成, 耗时: {:.2f} 秒 ({:.0f} 毫秒)".format(elapsed, elapsed * 1000),
        flush=True,
    )
    logger.info(
        "送审稿提取完成: 批注=%d, 删除线=%d, 非黑字=%d, 耗时=%.2fs",
        result.total_comments,
        result.total_strikethroughs,
        result.total_non_black_fonts,
        elapsed,
    )
    
    # 仅返回由本节点新增或更新的字段，避免在并行执行时覆写其他节点的状态
    return XjcgTenderGraphState(**updates)
