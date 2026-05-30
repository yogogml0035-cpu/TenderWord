"""国内公开（货物 / 财政）同页直替换 Word 回填节点。"""

from __future__ import annotations

from typing import Any

from backend.config.tender_config import (
    CONTENT_UPDATE_MODE_DIRECT_REPLACE,
    get_anchor_target_sizes,
    get_content_update_mode,
    get_default_anchor_texts,
)
from backend.helper.word_helper.inline_style_ops import (
    apply_inline_style_fragments,
    summarize_style_writeback_result,
)
from backend.helper.word_helper.delete_ops import (
    delete_range_content_preserving_locked_blocks as _delete_original_content,
    trim_leading_layout_controls_preserving_locked_blocks as _trim_leading_layout_controls,
)
from backend.nodes.common_word_nodes.comment_writeback import (
    build_comment_writeback_summary_payload,
    write_polished_comments,
)
from backend.nodes.gjgk_word_nodes.gjgk_update_word import (
    _build_insert_items,
    _describe_range_state,
    _ensure_insert_range,
    _find_first_insert_position_on_anchor_page,
    _find_next_editable_pos_bounded,
    _find_next_editable_pos_on_page_bounded,
    _insert_table,
    _insert_text_line,
    _prime_empty_insert_slot,
    _remove_marker_paragraphs,
    _reposition_insert_range_if_locked,
    _set_collapsed_range,
    cleanup_blank_paragraphs,
    is_locked_exception,
)
from backend.states import GngkTenderGraphState
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

NODE_NAME = "gngk_hw_cz_update_word"
DEFAULT_TENDER_TYPE = "gngk_hw_cz"


def _visible_log(message: str) -> None:
    progress_log.info(f"[{NODE_NAME}] {message}")


def _merge_adjacent_text_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把连续文本行合并为一次 Word 写入，减少连续撞锁定边界的机会。"""
    merged: list[dict[str, Any]] = []
    pending_lines: list[str] = []

    def flush_pending() -> None:
        if not pending_lines:
            return
        merged.append({"type": "text", "line": "\n".join(pending_lines)})
        pending_lines.clear()

    for item in items:
        if item.get("type") == "text":
            pending_lines.append(str(item.get("line", "")))
            continue
        flush_pending()
        merged.append(item)

    flush_pending()
    return merged


def gngk_hw_cz_update_word(
    state: GngkTenderGraphState, config
) -> GngkTenderGraphState:
    del config
    prepared_doc_path = state.get("prepared_doc_path")
    polished_text = state.get("polished_text")
    tender_type = str(state.get("tender_type") or DEFAULT_TENDER_TYPE)
    default_before_text, default_after_text = get_default_anchor_texts(tender_type)
    insertion_before_text = state.get("insertion_before_text") or default_before_text
    insertion_after_text = state.get("insertion_after_text") or default_after_text
    verbose_style_progress_logs = bool(state.get("verbose_style_progress_logs"))
    suppress_comment_progress_logs = bool(state.get("suppress_comment_progress_logs"))
    suppress_ai_comment_writeback = bool(state.get("suppress_ai_comment_writeback"))

    if not prepared_doc_path:
        raise ValueError("需要 prepared_doc_path 来插入 gngk_hw_cz 内容")
    if not polished_text:
        raise ValueError("需要 polished_text 来插入 gngk_hw_cz 内容")
    if not insertion_before_text or not insertion_after_text:
        raise ValueError(
            "gngk_hw_cz 插入必须提供 insertion_before_text 和 insertion_after_text"
        )
    if get_content_update_mode(tender_type) != CONTENT_UPDATE_MODE_DIRECT_REPLACE:
        raise ValueError(
            f"{NODE_NAME} 仅支持 direct_replace 模式，当前类型 {tender_type} 不符合要求"
        )

    before_size, after_size = get_anchor_target_sizes(tender_type)
    raw_items = _build_insert_items(polished_text)
    if not raw_items:
        raise ValueError("gngk_hw_cz 插入内容为空，无法执行更新")

    has_explicit_blank_lines = any(
        item.get("type") == "text" and item.get("line") == "" for item in raw_items
    )
    items = _merge_adjacent_text_items(raw_items)

    log_parts = [f"共解析插入项 {len(items)} 条"]
    word = None
    doc = None
    com_initialized = False
    comment_writeback_summary = ""
    comment_writeback_added = 0
    comment_writeback_failed = 0
    comment_writeback_skipped = 0
    comment_writeback_errors: list[dict[str, str]] = []
    comment_writeback_result_payload = None
    style_writeback_summary = ""
    style_writeback_result: dict[str, Any] | None = None

    try:
        _visible_log("开始执行 gngk_hw_cz 同页回填")
        word, com_initialized = create_word_application(
            initial_delay=0.0,
            post_init_delay=1.0,
            use_existing=False,
            verify=False,
            node_name=NODE_NAME,
        )
        doc = open_document_with_retry(
            word_app=word,
            file_path=prepared_doc_path,
            read_only=False,
            node_name=NODE_NAME,
        )
        log_parts.append(f"已打开文档: {prepared_doc_path}")

        if unprotect_document(doc, node_name=NODE_NAME):
            log_parts.append("已取消文档保护")

        before_hit, after_hit = find_anchor_range(
            doc,
            insertion_before_text,
            insertion_after_text,
            before_size=before_size,
            after_size=after_size,
            prefer_before="last",
            prefer_after="first",
        )
        if not before_hit:
            raise ValueError(f"未找到前置锚点段落: {insertion_before_text}")
        if not after_hit:
            raise ValueError(f"未找到后置锚点段落: {insertion_after_text}")

        content_range = resolve_anchor_content_range(
            doc=doc,
            word_app=word,
            before_hit=before_hit,
            after_hit=after_hit,
            tender_type=tender_type,
            allow_empty=True,
        )
        range_start = int(content_range["range_start"])
        range_end = int(content_range["range_end"])
        start_page = int(content_range["start_page"])
        end_page = int(content_range["end_page"])
        log_parts.append(
            f"锚点范围 {range_start}-{range_end}，页码 {start_page}-{end_page}"
        )

        after_anchor_marker = doc.Range(int(after_hit["start"]), int(after_hit["start"]))
        insert_cursor_bound_end = [None]

        def get_insertion_bound_end() -> int:
            try:
                anchor_bound_end = int(after_anchor_marker.Start)
            except Exception:
                anchor_bound_end = int(range_end)

            cursor_bound_end = insert_cursor_bound_end[0]
            if cursor_bound_end is None:
                return anchor_bound_end
            return max(anchor_bound_end, int(cursor_bound_end))

        _delete_original_content(
            doc,
            range_start=range_start,
            get_bound_end=get_insertion_bound_end,
            log_parts=log_parts,
        )
        log_parts.append(
            f"删除阶段完成: start={range_start}, bound_end={int(get_insertion_bound_end())}, "
            f"anchor_after={int(after_hit['start'])}"
        )

        insert_start = _trim_leading_layout_controls(
            doc,
            range_start=range_start,
            get_bound_end=get_insertion_bound_end,
            log_parts=log_parts,
        )
        insert_start = _find_first_insert_position_on_anchor_page(
            doc,
            start_pos=insert_start,
            bound_start=range_start,
            get_bound_end=get_insertion_bound_end,
            anchor_page=start_page,
        )
        log_parts.append(f"同页插入起点定位为 {insert_start}（页 {start_page}）")
        log_parts.append(
            _describe_range_state(doc, doc.Range(insert_start, insert_start), label="插入起点状态")
        )
        insert_range = doc.Range(insert_start, insert_start)
        _set_collapsed_range(insert_range, insert_start)
        insert_cursor_bound_end[0] = int(insert_start)
        bootstrap_marker = None
        if range_start == range_end and items:
            bootstrap_marker = _prime_empty_insert_slot(
                doc,
                insert_range,
                bound_start=insert_start,
                get_bound_end=get_insertion_bound_end,
                log_parts=log_parts,
            )
            insert_cursor_bound_end[0] = int(insert_start)

        inserted_count = 0
        for item_idx, item in enumerate(items, start=1):
            attempts = 0
            while attempts < 80:
                attempts += 1
                try:
                    _ensure_insert_range(
                        doc,
                        insert_range,
                        bound_start=insert_start,
                        get_bound_end=get_insertion_bound_end,
                    )
                    item_type = item.get("type")
                    if item_type == "text":
                        log_parts.append(
                            f"准备插入[{item_idx}/{len(items)}] 文本, attempt={attempts}, "
                            f"cursor={int(insert_range.Start)}, bound_end={int(get_insertion_bound_end())}"
                        )
                        _insert_text_line(
                            doc,
                            insert_range,
                            item["line"],
                            bound_start=insert_start,
                            get_bound_end=get_insertion_bound_end,
                            log_parts=log_parts,
                        )
                        insert_cursor_bound_end[0] = max(
                            int(insert_cursor_bound_end[0] or insert_start),
                            int(insert_range.Start),
                            int(insert_range.End),
                        )
                        _reposition_insert_range_if_locked(
                            doc,
                            insert_range,
                            insert_start=insert_start,
                            anchor_page=start_page,
                            get_bound_end=get_insertion_bound_end,
                            log_parts=log_parts,
                        )
                        insert_cursor_bound_end[0] = max(
                            int(insert_cursor_bound_end[0] or insert_start),
                            int(insert_range.Start),
                            int(insert_range.End),
                        )
                        inserted_count += 1
                        log_parts.append(
                            f"[{inserted_count}/{len(items)}] 已插入文本: {item['line'][:40]} "
                            f"(游标 {int(insert_range.Start)} / 上界 {int(get_insertion_bound_end())})"
                        )
                        break

                    log_parts.append(
                        f"准备插入[{item_idx}/{len(items)}] 表格, attempt={attempts}, "
                        f"cursor={int(insert_range.Start)}, bound_end={int(get_insertion_bound_end())}, "
                        f"rows={len(item.get('rows', []))}"
                    )
                    _insert_table(
                        doc,
                        insert_range,
                        item["rows"],
                        bound_start=insert_start,
                        get_bound_end=get_insertion_bound_end,
                        log_parts=log_parts,
                    )
                    insert_cursor_bound_end[0] = max(
                        int(insert_cursor_bound_end[0] or insert_start),
                        int(insert_range.Start),
                        int(insert_range.End),
                    )
                    _reposition_insert_range_if_locked(
                        doc,
                        insert_range,
                        insert_start=insert_start,
                        anchor_page=start_page,
                        get_bound_end=get_insertion_bound_end,
                        log_parts=log_parts,
                    )
                    insert_cursor_bound_end[0] = max(
                        int(insert_cursor_bound_end[0] or insert_start),
                        int(insert_range.Start),
                        int(insert_range.End),
                    )
                    inserted_count += 1
                    log_parts.append(
                        f"[{inserted_count}/{len(items)}] 已插入表格，行数 {len(item['rows'])} "
                        f"(游标 {int(insert_range.Start)} / 上界 {int(get_insertion_bound_end())})"
                    )
                    break
                except Exception as exc:
                    try:
                        current_state = _describe_range_state(
                            doc, insert_range, label="插入失败点"
                        )
                    except Exception:
                        current_state = "插入失败点状态获取失败"
                    log_parts.append(
                        f"插入异常 item={item_idx}/{len(items)} attempt={attempts}: {exc}; {current_state}"
                    )

                    if is_locked_exception(exc):
                        try:
                            cur_pos = int(insert_range.Start)
                        except Exception:
                            cur_pos = int(insert_start)

                        next_pos = _find_next_editable_pos_bounded(
                            doc,
                            start_pos=cur_pos + 1,
                            bound_start=insert_start,
                            get_bound_end=get_insertion_bound_end,
                            raise_on_missing=False,
                        )
                        if next_pos is None or next_pos <= cur_pos:
                            next_pos = _find_next_editable_pos_on_page_bounded(
                                doc,
                                start_pos=cur_pos + 1,
                                anchor_page=start_page,
                                get_bound_end=get_insertion_bound_end,
                            )
                        if next_pos is None or next_pos <= cur_pos:
                            next_pos = _find_next_editable_pos_bounded(
                                doc,
                                start_pos=insert_start,
                                bound_start=insert_start,
                                get_bound_end=get_insertion_bound_end,
                                raise_on_missing=False,
                            )
                        if next_pos is None:
                            log_parts.append(
                                "锁定降级失败: bounded/同页扫描/回退insert_start均未找到可编辑点位，终止当前插入"
                            )
                            raise

                        _set_collapsed_range(insert_range, next_pos)
                        log_parts.append(
                            f"锁定降级: 游标从 {cur_pos} 移动到 {next_pos} 后重试"
                        )
                        insert_cursor_bound_end[0] = max(
                            int(insert_cursor_bound_end[0] or insert_start),
                            int(insert_range.Start),
                            int(insert_range.End),
                        )
                        continue
                    raise

        inserted_end = int(insert_range.Start)
        if bootstrap_marker:
            bootstrap_search_end = max(
                int(inserted_end),
                int(get_insertion_bound_end()),
                int(after_hit["start"]),
            )
            removed_bootstrap = _remove_marker_paragraphs(
                doc,
                marker_text=bootstrap_marker,
                search_start=insert_start,
                search_end=bootstrap_search_end,
                log_parts=log_parts,
            )
            if removed_bootstrap == 0:
                removed_bootstrap = _remove_marker_paragraphs(
                    doc,
                    marker_text=bootstrap_marker,
                    search_start=0,
                    search_end=int(doc.Content.End),
                    log_parts=log_parts,
                )
                if removed_bootstrap > 0:
                    log_parts.append("bootstrap 标记未在插入边界内命中，已回退到全文清理")

        inserted_end = int(insert_range.Start)
        if has_explicit_blank_lines:
            log_parts.append("检测到输入包含显式空行，跳过空白段落清理")
        else:
            cleanup_blank_paragraphs(
                doc,
                range_start=insert_start,
                range_end=inserted_end,
                log_parts=log_parts,
            )

        comment_step_label = "步骤6"
        if "inline_style_fragments" in state:
            style_writeback_result = apply_inline_style_fragments(
                doc=doc,
                inline_style_fragments=state.get("inline_style_fragments"),
                style_writeback_mode=str(state.get("style_writeback_mode") or "full"),
                bound_start=int(range_start),
                bound_end=int(get_insertion_bound_end()),
                log_parts=log_parts,
                step_label="步骤6",
                progress_logger=progress_log.info if verbose_style_progress_logs else None,
                diagnostic_logger=progress_log.debug if verbose_style_progress_logs else None,
            )
            style_writeback_summary = summarize_style_writeback_result(
                style_writeback_result
            )
            comment_step_label = "步骤7"

        if suppress_ai_comment_writeback:
            log_parts.append(
                f"{comment_step_label}：agent 模式跳过确定性批注写入，交由 comment_agent 处理。"
            )
        else:
            polished_comments = state.get("polished_comments") or []
            generated_count = state.get("generated_comment_count", 0)
            comment_writeback_result = write_polished_comments(
                doc=doc,
                polished_comments=polished_comments,
                bound_start=int(range_start),
                bound_end=int(get_insertion_bound_end()),
                log_parts=log_parts,
                step_label=comment_step_label,
            )

            summary_payload = build_comment_writeback_summary_payload(
                generated_count=generated_count,
                writeback_result=comment_writeback_result,
            )
            added = summary_payload["added"]
            failed = summary_payload["failed"]
            skipped = summary_payload["skipped"]
            issues = comment_writeback_result.get("issues", [])

            summary = summary_payload["summary"]
            if not suppress_comment_progress_logs:
                if summary_payload["warning"]:
                    progress_log.warning(summary)
                else:
                    progress_log.info(summary)

            comment_writeback_summary = summary
            comment_writeback_result_payload = summary_payload
            comment_writeback_added = added
            comment_writeback_failed = failed
            comment_writeback_skipped = skipped
            comment_writeback_errors = [
                {
                    "reference_text": issue.get("reference_text", ""),
                    "reason": issue.get("reason", ""),
                    "error": issue.get("error", ""),
                }
                for issue in issues
            ]

        save_document_with_retry(doc, node_name=NODE_NAME)
        log_parts.append("文档已保存")
        _visible_log("gngk_hw_cz 同页回填完成")
    except Exception as exc:
        try:
            if doc is not None:
                log_parts.append(
                    _describe_range_state(doc, doc.Content, label="异常时文档内容范围")
                )
        except Exception:
            pass
        error_message = f"gngk_hw_cz Word 更新失败: {exc}"
        log_parts.append(error_message)
        _visible_log(error_message)
        recent_logs = " | ".join(log_parts[-25:])
        raise RuntimeError(f"{error_message}; 最近日志: {recent_logs}") from exc
    finally:
        close_word_application(
            word_app=word,
            doc=doc,
            com_initialized=com_initialized,
            wait_time=1.0,
            node_name=NODE_NAME,
        )

    new_state = dict(state)
    new_state["insertion_log"] = "; ".join(log_parts)
    new_state["comment_writeback_summary"] = comment_writeback_summary
    new_state["comment_writeback_added"] = comment_writeback_added
    new_state["comment_writeback_failed"] = comment_writeback_failed
    new_state["comment_writeback_skipped"] = comment_writeback_skipped
    new_state["comment_writeback_errors"] = comment_writeback_errors
    new_state["comment_writeback_result"] = comment_writeback_result_payload
    new_state["style_writeback_summary"] = style_writeback_summary
    new_state["style_writeback_result"] = style_writeback_result
    return GngkTenderGraphState(**new_state)
