"""Shared Word comment extraction helpers for rewrite and edit flows."""

from __future__ import annotations

import logging
from pathlib import Path

from backend.config.tender_config import get_anchor_target_sizes
from backend.util.log_util.progress_log import progress_log
from backend.util.word_util import (
    DocumentAnalysisResult,
    WordDocumentInspector,
    close_word_application,
    create_word_application,
    open_document_with_retry,
)
from backend.util.word_util.anchor_utils import (
    find_anchor_range,
    resolve_anchor_content_range,
)

logger = logging.getLogger(__name__)


def _get_anchor_content_range(
    doc,
    word_app,
    before_text: str,
    after_text: str,
    before_size: float,
    after_size: float,
    *,
    tender_type: str | None = None,
    node_name: str,
    strict: bool = False,
) -> tuple[int | None, int | None]:
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


def result_to_polished_comments(
    result: DocumentAnalysisResult,
) -> list[dict[str, str]]:
    """Convert Word comments into the standard writeback instruction shape."""

    return [
        {
            "reference_text": comment.reference_text or "",
            "comment_text": comment.content or "",
        }
        for comment in result.comments
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
    """Open a Word document and analyze comments/styles inside an optional anchor range."""

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
            before_size, after_size = get_anchor_target_sizes(str(tender_type or "xjcg"))
            range_start, range_end = _get_anchor_content_range(
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
                    f"[{node_name}] 锚点范围 -> [{range_start}, {range_end})，批注/删除线/非黑字均只在此范围内统计"
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
            except Exception as exc:
                logger.warning("关闭 %s 文档时出错: %s", node_name, exc)
            doc = None
        close_word_application(
            word_app=word_app,
            doc=doc,
            com_initialized=com_initialized,
            wait_time=0.0,
            node_name=node_name,
        )
