"""gjgk 专用：删除招标参数节点。"""

from __future__ import annotations

import os
import pathlib
import sys
import time
from typing import Optional

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.states import TenderGraphStateBase
from backend.config.tender_config import (
    CONTENT_UPDATE_MODE_DIRECT_REPLACE,
    get_anchor_target_sizes,
    get_content_update_mode,
)
from backend.util.log_util.progress_log import progress_log
from backend.util.word_util import (
    close_word_application,
    create_word_application,
    open_document_with_retry,
    save_document_with_retry,
    unprotect_document,
)
from backend.util.word_util.anchor_utils import (
    find_anchor_range,
    resolve_anchor_content_range,
)

NODE_NAME = "gjgk_delete_tender_param"


def _visible_log(message: str) -> None:
    progress_log.info(f"[{NODE_NAME}] {message}")


def _calculate_elapsed_seconds(
    start_monotonic: float, current_monotonic: Optional[float] = None
) -> float:
    current = time.monotonic() if current_monotonic is None else current_monotonic
    return max(0.0, current - start_monotonic)


def gjgk_delete_tender_param(
    state: TenderGraphStateBase, config
) -> TenderGraphStateBase:
    """gjgk 流程专用：按双锚点定位并直接删除正文区间。"""
    del config
    start_time = time.monotonic()
    print(f"[{NODE_NAME}] 开始执行...")
    _visible_log("开始删除 gjgk 原始采购需求")

    prepared_doc_path = state.get("prepared_doc_path")
    before_text = state.get("insertion_before_text")
    after_text = state.get("insertion_after_text")
    tender_type = "gjgk"

    if not prepared_doc_path:
        raise ValueError("需要 prepared_doc_path 来删除 WPS/Word 文档中的内容")

    if not before_text or not after_text:
        print(f"[{NODE_NAME}] 警告: 未提供 insertion_before_text 或 insertion_after_text，跳过删除")
        return TenderGraphStateBase(**dict(state))

    if not os.path.isabs(prepared_doc_path):
        prepared_doc_path = os.path.abspath(prepared_doc_path)

    if not os.path.exists(prepared_doc_path):
        raise FileNotFoundError(f"未找到准备好的文档: {prepared_doc_path}")

    if not os.access(prepared_doc_path, os.W_OK):
        raise PermissionError(f"无法写入准备好的文档: {prepared_doc_path}")

    before_size, after_size = get_anchor_target_sizes(tender_type)
    print(
        f"[{NODE_NAME}] 招标类型: {tender_type}, 前置字号: {before_size}, 后置字号: {after_size}"
    )

    if get_content_update_mode(tender_type) != CONTENT_UPDATE_MODE_DIRECT_REPLACE:
        raise ValueError("gjgk_delete_tender_param 仅支持 gjgk direct_replace 模式")

    word = None
    doc = None
    com_initialized = False

    try:
        _visible_log("开始打开待清理文档")
        word, com_initialized = create_word_application(
            initial_delay=2.0,
            post_init_delay=1.0,
            use_existing=False,
            verify=True,
            node_name=NODE_NAME,
        )

        doc = open_document_with_retry(
            word_app=word,
            file_path=prepared_doc_path,
            read_only=False,
            node_name=NODE_NAME,
        )
        _visible_log("文档打开完成，准备定位采购需求锚点")

        unprotect_document(doc, node_name=NODE_NAME)

        print(f"[{NODE_NAME}] 正在查找锚点...")
        print(f"  前置文本: '{before_text}'")
        print(f"  后置文本: '{after_text}'")

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
            raise ValueError(f"未找到前置锚点: {before_text}")
        if not after_hit:
            raise ValueError(f"未找到后置锚点: {after_text}")

        used_before_text = before_hit.get("used_text", before_text)
        used_after_text = after_hit.get("used_text", after_text)
        if used_before_text != before_text:
            print(
                f"[{NODE_NAME}] 前置锚点 '{before_text}' 未命中，改用 '{used_before_text}'"
            )
        if used_after_text != after_text:
            print(
                f"[{NODE_NAME}] 后置锚点 '{after_text}' 未命中，改用 '{used_after_text}'"
            )

        content_range = resolve_anchor_content_range(
            doc=doc,
            word_app=word,
            before_hit=before_hit,
            after_hit=after_hit,
            tender_type=tender_type,
        )
        range_start = int(content_range["range_start"])
        range_end = int(content_range["range_end"])
        start_page = int(content_range["start_page"])
        end_page = int(content_range["end_page"])

        print(f"[{NODE_NAME}] 删除范围: {range_start} -> {range_end}")

        doc_end = int(doc.Content.End)
        if (
            range_end <= range_start
            or range_end > doc_end
            or range_start < 0
            or range_start > doc_end
        ):
            raise ValueError(
                "锚点位置异常，无法执行删除: "
                f"range_start={range_start}, range_end={range_end}, doc_end={doc_end}"
            )

        doc.Range(range_start, range_end).Delete()
        _visible_log(f"删除完成，页码范围 {start_page}-{end_page}，准备保存文档")

        save_document_with_retry(doc, node_name=NODE_NAME)
        _visible_log("文档保存完成")

    except Exception as e:
        from backend.graphs.base_graph import TaskCancelledException

        if isinstance(e, TaskCancelledException):
            progress_log.warning(f"[{NODE_NAME}] 任务已取消")
            raise

        error_msg = f"删除内容时发生错误: {e}"
        print(f"[{NODE_NAME}] {error_msg}")
        progress_log.error(f"[{NODE_NAME}] {error_msg}")
        raise RuntimeError(error_msg) from e

    finally:
        _visible_log("开始清理 Word 资源")
        close_word_application(
            word_app=word,
            doc=doc,
            com_initialized=com_initialized,
            wait_time=1.5,
            node_name=NODE_NAME,
        )
        _visible_log("Word 资源清理完成")

    elapsed_time = _calculate_elapsed_seconds(start_time)
    print(
        f"[{NODE_NAME}] 执行完成，耗时: {elapsed_time:.2f} 秒 ({elapsed_time * 1000:.0f} 毫秒)"
    )
    _visible_log(f"节点执行完成，耗时 {elapsed_time:.2f} 秒")

    return TenderGraphStateBase(**dict(state))
