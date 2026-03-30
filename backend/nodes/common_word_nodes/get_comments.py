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

from backend.states import TenderGraphStateBase
from backend.util.word_util import WordDocumentInspector, DocumentAnalysisResult
from backend.util.word_util import (
    create_word_application,
    close_word_application,
    open_document_with_retry,
)
from backend.util.word_util import (
    wdGoToPage,
    wdGoToAbsolute,
    wdActiveEndPageNumber,
)
from backend.util.word_util.anchor_utils import find_anchor_range
from backend.util.word_util.anchor_utils import resolve_anchor_content_range
from backend.config.tender_config import get_anchor_target_sizes
from backend.util.log_util.progress_log import progress_log


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


def _get_insertion_range(
    doc,
    word_app,
    before_text: str,
    after_text: str,
    before_size: float,
    after_size: float,
    *,
    tender_type: str | None = None,
    node_name: str = "get_comments",
    strict: bool = False,
):
    """
    根据 insertion_before_text / insertion_after_text 在文档中定位锚点，返回抽取范围 (range_start, range_end)。
    与 gngk_extract_tender_params 中的锚点逻辑一致：仅批注会按此范围过滤。

    Returns:
        (range_start, range_end) 或 (None, None)（未找到锚点或参数无效时）
    """
    if not before_text or not after_text:
        return None, None
    before_hit, after_hit = find_anchor_range(
        doc=doc,
        before_text=before_text,
        after_text=after_text,
        before_size=before_size,
        after_size=after_size,
        prefer_before="last",
        prefer_after="first",
    )
    if not before_hit:
        if strict:
            logger.warning("%s 未找到前置锚点 '%s'", node_name, before_text)
        else:
            logger.info("%s 未找到前置锚点 '%s'，不按范围过滤批注", node_name, before_text)
        return None, None
    if not after_hit:
        if strict:
            logger.warning("%s 未找到后置锚点 '%s'", node_name, after_text)
        else:
            logger.info("%s 未找到后置锚点 '%s'，不按范围过滤批注", node_name, after_text)
        return None, None
    content_range = resolve_anchor_content_range(
        doc=doc,
        word_app=word_app,
        before_hit=before_hit,
        after_hit=after_hit,
        tender_type=tender_type,
    )
    return content_range["range_start"], content_range["range_end"]


def _resolve_anchor_sizes(tender_type: str | None) -> tuple[float, float]:
    return get_anchor_target_sizes(str(tender_type or "xjcg"))


def _empty_plan_state(state: TenderGraphStateBase) -> TenderGraphStateBase:
    """
    未上传送审稿或文件无效时返回的空计划状态。
    
    仅返回本节点负责维护的计划相关字段，避免与并行节点产生状态冲突。
    """
    return TenderGraphStateBase(
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


def result_to_polished_comments(result: DocumentAnalysisResult) -> list[dict[str, str]]:
    """将提取到的 Word 批注转为 update_word 可复用的 polished_comments。"""
    return [
        {
            "reference_text": c.reference_text or "",
            "comment_text": c.content or "",
        }
        for c in result.comments
    ]


def extract_document_analysis_result(
    *,
    file_path: Path,
    before_text: str | None,
    after_text: str | None,
    tender_type: str | None,
    node_name: str,
    require_anchor_range: bool = False,
) -> DocumentAnalysisResult:
    """
    打开 Word 文档并按锚点区间提取批注/删除线/非黑字。

    Args:
        file_path: 待分析的 Word 文档路径
        before_text: 前置锚点文本
        after_text: 后置锚点文本
        tender_type: 招标类型，用于推导锚点目标字号
        node_name: 当前节点名，用于日志输出
        require_anchor_range: 为 True 时，必须成功定位锚点区间
    """
    word_app = None
    doc = None
    com_initialized = False

    try:
        progress_log.debug(f"[{node_name}] 开始执行...")
        logger.info("%s 开始执行，文档路径: %s", node_name, file_path)
        progress_log.debug(f"[{node_name}] 正在创建 Word 并打开文档...")
        word_app, com_initialized = create_word_application(
            initial_delay=0.3,
            post_init_delay=0.2,
            use_existing=False,
            node_name=node_name,
        )
        doc = open_document_with_retry(
            word_app,
            str(file_path),
            read_only=True,
            node_name=node_name,
        )
        inspector = WordDocumentInspector(
            word_app=word_app,
            doc=doc,
            node_name=node_name,
        )

        range_start, range_end = None, None
        if require_anchor_range and (not before_text or not after_text):
            raise ValueError(
                f"{node_name} 需要 insertion_before_text 和 insertion_after_text 来定位修改范围"
            )

        if before_text and after_text:
            before_size, after_size = _resolve_anchor_sizes(tender_type)
            range_start, range_end = _get_insertion_range(
                doc,
                word_app,
                before_text,
                after_text,
                before_size,
                after_size,
                tender_type=tender_type,
                node_name=node_name,
                strict=require_anchor_range,
            )
            if range_start is not None and range_end is not None:
                progress_log.debug(
                    f"[{node_name}] 锚点范围仅计算一次 -> [{range_start}, {range_end})，批注/删除线/非黑字均只在此范围内统计"
                )
            elif require_anchor_range:
                raise ValueError(
                    f"{node_name} 未能定位锚点范围: before_text={before_text!r}, after_text={after_text!r}"
                )
        else:
            logger.info(
                "%s 未提供 insertion_before_text / insertion_after_text，将在整篇文档内统计批注/删除线/非黑字",
                node_name,
            )

        return inspector.analyze_document(
            range_start=range_start,
            range_end=range_end,
        )
    finally:
        if doc is not None:
            try:
                doc.Close(SaveChanges=False)
            except Exception as e:
                logger.warning("关闭 %s 文档时出错: %s", node_name, e)
            doc = None
        close_word_application(
            word_app=word_app,
            doc=doc,
            com_initialized=com_initialized,
            wait_time=0.0,
            node_name=node_name,
        )


def get_comments(state: TenderGraphStateBase, config) -> TenderGraphStateBase:
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

    try:
        result = extract_document_analysis_result(
            file_path=file_path,
            before_text=state.get("insertion_before_text"),
            after_text=state.get("insertion_after_text"),
            tender_type=state.get("tender_type"),
            node_name="get_comments",
        )
    except Exception as e:
        logger.error("送审稿文档分析失败: %s", e, exc_info=True)
        return _empty_plan_state(state)

    updates = _result_to_state_updates(result)
    elapsed = time.perf_counter() - start_time
    progress_log.debug(
        "[get_comments] 执行完成, 耗时: {:.2f} 秒 ({:.0f} 毫秒)".format(elapsed, elapsed * 1000),
    )
    logger.info(
        "送审稿提取完成: 批注=%d, 删除线=%d, 非黑字=%d, 耗时=%.2fs",
        result.total_comments,
        result.total_strikethroughs,
        result.total_non_black_fonts,
        elapsed,
    )
    
    # 仅返回由本节点新增或更新的字段，避免在并行执行时覆写其他节点的状态
    return TenderGraphStateBase(**updates)
