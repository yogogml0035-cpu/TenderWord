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

logger = logging.getLogger(__name__)


def _empty_plan_state(state: XjcgTenderGraphState) -> XjcgTenderGraphState:
    """未上传送审稿或文件无效时返回的空计划状态"""
    new_state_dict = dict(state)
    new_state_dict.update({
        "comment_plan": [],
        "comment_plan_detail": [],
        "strikethrough_plan": [],
        "non_black_font_plan": [],
    })
    return XjcgTenderGraphState(**new_state_dict)


def _result_to_state_updates(result: DocumentAnalysisResult) -> dict:
    """将 DocumentAnalysisResult 转为可写入 state 的字典"""
    comment_plan = [c.content for c in result.comments]
    comment_plan_detail = [
        {
            "author": c.author,
            "date": c.date,
            "content": c.content,
            "scope_text": c.scope_text,
            "page_number": getattr(c, "page_number", 0),
        }
        for c in result.comments
    ]
    strikethrough_plan = [
        {
            "paragraph_text": s.paragraph_text,
            "strikethrough_text": s.strikethrough_text,
            "page_number": getattr(s, "page_number", 0),
        }
        for s in result.strikethroughs
    ]
    non_black_font_plan = [
        {
            "paragraph_text": f.paragraph_text,
            "font_text": f.font_text,
            "color_name": f.color_name,
            "page_number": getattr(f, "page_number", 0),
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
    从送审稿 Word 文档中提取批注、删除线、非黑色字体

    与 test_document_inspector 一致：在节点内创建 Word、打开文档，
    然后只调用 WordDocumentInspector(word_app, doc).analyze_document()，不另写 from_path。
    分析完成后关闭文档。

    Args:
        state: LangGraph 状态，包含 review_draft_path
        config: 节点配置（当前未使用）

    Returns:
        更新后的状态，包含 comment_plan、comment_plan_detail、
        strikethrough_plan、non_black_font_plan
    """
    start_time = time.perf_counter()
    review_draft_path = state.get("review_draft_path")

    if not review_draft_path or (isinstance(review_draft_path, str) and review_draft_path.strip() == ""):
        logger.info("未上传送审稿文件，批注/删除线/非黑字计划均为空")
        return _empty_plan_state(state)

    file_path = Path(review_draft_path)
    if not file_path.exists():
        logger.warning("送审稿文件不存在: %s", review_draft_path)
        return _empty_plan_state(state)

    print("[get_comments] 开始执行...", flush=True)
    logger.info("get_comments 开始执行，送审稿路径: %s", review_draft_path)

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
        # 直接调用工具模块的分析方法，不再用 analyze_document_from_path
        result = inspector.analyze_document()
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

    new_state_dict = dict(state)
    new_state_dict.update(updates)
    return XjcgTenderGraphState(**new_state_dict)
