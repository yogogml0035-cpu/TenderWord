"""
从 rewrite 目标文档中提取锚点区间内的旧批注。

该节点在删除原段落前执行，将旧批注转换为 polished_comments，
供 update_word 节点在插入新内容后尝试重新写回批注。
"""

from __future__ import annotations

import logging
import pathlib
import sys
import time
from pathlib import Path

# 添加项目根目录到 sys.path
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.nodes.common_word_nodes.get_comments import (
    extract_document_analysis_result,
    result_to_polished_comments,
)
from backend.states import RewriteGraphState
from backend.util.log_util.progress_log import progress_log


logger = logging.getLogger(__name__)


def get_rewrite_comments(state: RewriteGraphState, config) -> RewriteGraphState:
    """
    在 rewrite 删除原内容之前，提取锚点区间内的旧批注并写入 polished_comments。

    与 get_comments 不同，本节点采用 strict 语义：
    - 必须存在可读文档
    - 必须提供前后锚点
    - 必须成功定位锚点区间
    - Word/Inspector 异常直接抛出，终止 rewrite 任务
    """
    start_time = time.perf_counter()
    document_path = state.get("prepared_doc_path") or state.get("origin_tender_path")
    if not document_path or (
        isinstance(document_path, str) and document_path.strip() == ""
    ):
        raise ValueError("get_rewrite_comments 需要 prepared_doc_path 或 origin_tender_path")

    file_path = Path(str(document_path))
    if not file_path.exists():
        raise FileNotFoundError(f"get_rewrite_comments 文档不存在: {file_path}")

    result = extract_document_analysis_result(
        file_path=file_path,
        before_text=state.get("insertion_before_text"),
        after_text=state.get("insertion_after_text"),
        tender_type=state.get("tender_type"),
        node_name="get_rewrite_comments",
        require_anchor_range=True,
    )
    polished_comments = result_to_polished_comments(result)

    elapsed = time.perf_counter() - start_time
    progress_log.info(
        "[get_rewrite_comments] 提取到 %d 条原批注，后续将尝试在 rewrite 后回写。",
        len(polished_comments),
    )
    logger.info(
        "get_rewrite_comments 执行完成: 批注=%d, 耗时=%.2fs",
        len(polished_comments),
        elapsed,
    )
    return RewriteGraphState(polished_comments=polished_comments)
