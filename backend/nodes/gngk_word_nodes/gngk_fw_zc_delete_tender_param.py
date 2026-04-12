"""
国内公开（服务 / 自筹）删除招标参数节点。

独立实现完整的删除流程，不再复用 common delete_tender_param。
删除逻辑来自 gngk_fw_zc_update_word 中已验证的步骤1（定位受保护字段）、
步骤3（循环式删除）和步骤5（清理空段落），确保 delete → update
两步产出的文档与一步内建删除 + 插入的效果完全一致。
"""

from __future__ import annotations

import os
import pathlib
import re
import sys
import time
from typing import Any, Dict, Optional

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config.tender_config import get_anchor_target_sizes, get_default_anchor_texts
from backend.nodes.common_word_nodes.update_word import (
    _collect_protected_fields as _common_collect_protected_fields,
    _refresh_protected_fields as _common_refresh_protected_fields,
)
from backend.states import TenderGraphStateBase
from backend.util.log_util.progress_log import progress_log
from backend.util.word_util import (
    close_word_application,
    create_word_application,
    open_document_with_retry,
    save_document_with_retry,
    unprotect_document,
    wdActiveEndPageNumber,
    wdCollapseEnd,
    wdFindStop,
    wdGoToAbsolute,
    wdGoToPage,
    wdWithInTable,
)
from backend.util.word_util.anchor_utils import (
    find_anchor_range,
    resolve_anchor_content_range,
)

NODE_NAME = "gngk_fw_zc_delete_tender_param"
PROTECTED_FIELD_KEYWORDS = ("服务地点", "服务期限", "付款方式")

_CLEANUP_INVISIBLE_CHARS = (
    "\r",
    "\n",
    "\t",
    "\x07",
    "\x0b",
    "\x0c",
    "\a",
    "\u00a0",
    "\u2000",
    "\u2001",
    "\u2002",
    "\u2003",
    "\u2004",
    "\u2005",
    "\u2006",
    "\u2007",
    "\u2008",
    "\u2009",
    "\u200a",
    "\u200b",
    "\u3000",
    "\ufeff",
)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _normalize_cleanup_text(text: str) -> str:
    normalized = str(text or "")
    for ch in _CLEANUP_INVISIBLE_CHARS:
        normalized = normalized.replace(ch, "")
    return normalized.strip()


def _is_effectively_empty_text(text: str) -> bool:
    return _normalize_cleanup_text(text) == ""


def _require_all_protected_fields(
    protected_fields: Dict[str, Any],
    required_keywords: tuple[str, ...] = PROTECTED_FIELD_KEYWORDS,
) -> None:
    missing = [kw for kw in required_keywords if kw not in protected_fields]
    if missing:
        raise ValueError(f"缺少关键受保护字段: {', '.join(missing)}")


def _collect_protected_fields(*args, **kwargs) -> Dict[str, Any]:
    pf = _common_collect_protected_fields(*args, **kwargs)
    _require_all_protected_fields(pf)
    return pf


def _refresh_protected_fields(*args, **kwargs) -> Dict[str, Any]:
    pf = _common_refresh_protected_fields(*args, **kwargs)
    _require_all_protected_fields(pf)
    return pf


def _range_overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return not (a_end <= b_start or b_end <= a_start)


def _is_protected_range(rng, protected_fields: Dict[str, Any]) -> bool:
    try:
        rs = int(rng.Start)
        re_ = int(rng.End)
    except Exception:
        return False
    for prng in protected_fields.values():
        try:
            ps = int(prng.Start)
            pe = int(prng.End)
        except Exception:
            continue
        if _range_overlaps(rs, re_, ps, pe):
            return True
    return False


def _visible_text(text: str) -> str:
    if not text:
        return ""
    result = text
    for ch in ("\r", "\n", "\x07", "\x0b", "\x0c", "\a", " ", "\t",
               "\u00a0", "\u3000", "\u2000", "\u2001", "\u2002", "\u2003",
               "\u2004", "\u2005", "\u2006", "\u2007", "\u2008", "\u2009",
               "\u200a", "\u200b", "\ufeff"):
        result = result.replace(ch, "")
    return result.strip()


# ---------------------------------------------------------------------------
# 主删除函数
# ---------------------------------------------------------------------------

def gngk_fw_zc_delete_tender_param(
    state: TenderGraphStateBase, config
) -> TenderGraphStateBase:
    """
    删除锚点之间的内容，保留服务三字段（服务地点、服务期限、付款方式）。

    逻辑完全来自 gngk_fw_zc_update_word 中已验证的删除流程：
    步骤1 — 定位受保护字段
    步骤2 — 循环式删除（大块/表格/段落/字符 四策略）
    步骤3 — 多轮清理空段落、换行、空表格
    """
    start_time = time.perf_counter()
    print(f"[{NODE_NAME}] 开始执行...")
    progress_log.info(f"[{NODE_NAME}] 开始删除原始采购需求")

    prepared_doc_path = state.get("prepared_doc_path")
    insertion_before_text = state.get("insertion_before_text")
    insertion_after_text = state.get("insertion_after_text")
    tender_type = state.get("tender_type", "gngk_fw_zc")

    if not prepared_doc_path:
        raise ValueError("需要 prepared_doc_path 来删除 Word 文档中的内容")
    if not insertion_before_text or not insertion_after_text:
        print(f"[{NODE_NAME}] 警告: 未提供锚点文本，跳过删除")
        return TenderGraphStateBase(**dict(state))

    if not os.path.isabs(prepared_doc_path):
        prepared_doc_path = os.path.abspath(prepared_doc_path)
    if not os.path.exists(prepared_doc_path):
        raise FileNotFoundError(f"未找到文档: {prepared_doc_path}")
    if not os.access(prepared_doc_path, os.W_OK):
        raise PermissionError(f"无法写入文档: {prepared_doc_path}")

    before_size, after_size = get_anchor_target_sizes(str(tender_type or "gngk_fw_zc"))
    log_parts: list[str] = []

    word = None
    doc = None
    com_initialized = False

    try:
        word, com_initialized = create_word_application(
            initial_delay=2.0,
            post_init_delay=1.0,
            use_existing=False,
            verify=True,
            node_name=NODE_NAME,
        )

        try:
            doc = open_document_with_retry(
                word_app=word,
                file_path=prepared_doc_path,
                read_only=False,
                node_name=NODE_NAME,
            )
            log_parts.append(f"已打开文档: {prepared_doc_path}")

            if unprotect_document(doc, node_name=NODE_NAME):
                log_parts.append("已取消文档保护")

            # ---- 定位锚点 ----
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

            after_anchor_start = after_hit["start"]
            log_parts.append(
                f"✅ 前置锚点: 页={before_hit['page']}, "
                f"{before_hit['start']}-{before_hit['end']}"
            )
            log_parts.append(
                f"✅ 后置锚点: 页={after_hit['page']}, "
                f"{after_hit['start']}-{after_hit['end']}"
            )

            content_range = resolve_anchor_content_range(
                doc=doc,
                word_app=word,
                before_hit=before_hit,
                after_hit=after_hit,
                tender_type=str(tender_type or "gngk_fw_zc"),
                allow_empty=True,
            )
            insertion_bound_start = int(content_range["range_start"])
            insertion_bound_end = int(content_range["range_end"])
            computed_start_page = int(content_range["start_page"])

            # 动态追踪后置锚点位置（删除内容会使之移动）
            after_anchor_marker = doc.Range(
                int(after_anchor_start), int(after_anchor_start)
            )

            def get_bound_end() -> int:
                try:
                    return int(after_anchor_marker.Start)
                except Exception:
                    return int(insertion_bound_end)

            # ---- 章节标题安全校验 ----
            try:
                region_text = doc.Range(insertion_bound_start, insertion_bound_end).Text
                if re.search(r"第[一二三四五六七八九十0-9]+章", region_text):
                    raise ValueError("锚点之间检测到章节标题，停止删除以避免侵入其他章节")
            except Exception as e:
                if isinstance(e, ValueError):
                    raise

            # ==================================================================
            # 步骤1：定位受保护字段
            # ==================================================================
            selection = word.Selection
            target_page = computed_start_page
            selection.GoTo(wdGoToPage, wdGoToAbsolute, target_page)
            page_start = selection.Start
            page_start_page = selection.Information(wdActiveEndPageNumber)

            next_page = target_page + 1
            selection.GoTo(wdGoToPage, wdGoToAbsolute, next_page)
            page_end = selection.Start
            page_end_page = selection.Information(wdActiveEndPageNumber)

            if page_start_page != target_page or page_end == page_start:
                page_end = doc.Content.End
            elif page_end_page != next_page:
                page_end = doc.Content.End

            if page_end <= page_start:
                raise ValueError(f"目标页 {target_page} 范围为空，无法定位受保护字段")

            protected_keywords = list(PROTECTED_FIELD_KEYWORDS)
            target_range = (int(page_start), int(page_end))
            fallback_range = (int(insertion_bound_start), int(get_bound_end()))

            log_parts.append(
                f"步骤1：定位服务三字段，目标页={target_page}"
                f"({target_range[0]}-{target_range[1]})，"
                f"边界={fallback_range[0]}-{fallback_range[1]}"
            )

            protected_fields = _collect_protected_fields(
                doc=doc,
                keywords=protected_keywords,
                target_range=target_range,
                fallback_range=fallback_range,
            )
            for kw, prng in protected_fields.items():
                log_parts.append(
                    f"  找到受保护字段: {kw} ({int(prng.Start)}-{int(prng.End)})"
                )

            # ==================================================================
            # 步骤2：循环式删除（保护服务三字段）
            # ==================================================================
            bound_start = int(insertion_bound_start)
            bound_end = int(get_bound_end())
            log_parts.append(f"步骤2：清理插入区间（{bound_start}-{bound_end}）...")

            deleted_tables = 0
            deleted_paras = 0
            max_delete_steps = 2000
            delete_step = 0
            current_pos = bound_start

            while delete_step < max_delete_steps:
                delete_step += 1
                current_bound_end = int(get_bound_end())

                if current_pos >= current_bound_end:
                    break

                delete_rng = doc.Range(current_pos, current_bound_end)
                deleted_something = False

                # 策略1: 大块删除（区间内无保护字段时）
                has_protected = False
                try:
                    for _kw, _prng in protected_fields.items():
                        try:
                            _ps = int(_prng.Start)
                            _pe = int(_prng.End)
                            if not (_pe <= current_pos or _ps >= current_bound_end):
                                has_protected = True
                                break
                        except Exception:
                            continue
                except Exception:
                    pass

                if not has_protected:
                    try:
                        delete_rng.Delete()
                        log_parts.append(
                            f"  大块删除成功 ({current_pos}-{current_bound_end})"
                        )
                        break
                    except Exception:
                        pass

                # 策略2: 删除第一个非保护表格
                try:
                    tables = delete_rng.Tables
                    if tables.Count > 0:
                        tbl = tables(1)
                        tbl_rng = tbl.Range
                        tbl_start = int(tbl_rng.Start)
                        tbl_end = int(tbl_rng.End)

                        if _is_protected_range(tbl_rng, protected_fields):
                            current_pos = tbl_end
                            deleted_something = True
                        else:
                            if tbl_start > current_pos:
                                pre_rng = doc.Range(current_pos, tbl_start)
                                if not _is_protected_range(pre_rng, protected_fields):
                                    try:
                                        pre_rng.Delete()
                                        deleted_something = True
                                        continue
                                    except Exception:
                                        current_pos = tbl_start
                                        deleted_something = True
                                        continue

                            try:
                                tbl.Delete()
                                deleted_tables += 1
                                deleted_something = True
                                continue
                            except Exception:
                                try:
                                    tbl_rng.Delete()
                                    deleted_tables += 1
                                    deleted_something = True
                                    continue
                                except Exception:
                                    current_pos = tbl_end
                                    deleted_something = True
                                    continue
                except Exception:
                    pass

                # 策略3: 逐段落删除
                if not deleted_something:
                    try:
                        paras = delete_rng.Paragraphs
                        if paras.Count > 0:
                            para = paras(1)
                            para_rng = para.Range
                            para_start = int(para_rng.Start)
                            para_end = int(para_rng.End)

                            if _is_protected_range(para_rng, protected_fields):
                                current_pos = para_end
                                deleted_something = True
                            else:
                                try:
                                    para_rng.Delete()
                                    deleted_paras += 1
                                    deleted_something = True
                                    continue
                                except Exception:
                                    current_pos = para_end
                                    deleted_something = True
                                    continue
                    except Exception:
                        pass

                # 策略4: 小块字符删除
                if not deleted_something:
                    try:
                        chunk_size = min(50, current_bound_end - current_pos)
                        if chunk_size > 0:
                            chunk_end = current_pos + chunk_size
                            small_rng = doc.Range(current_pos, chunk_end)
                            if _is_protected_range(small_rng, protected_fields):
                                current_pos = chunk_end
                                continue
                            try:
                                small_rng.Delete()
                                continue
                            except Exception:
                                current_pos = chunk_end
                                continue
                    except Exception:
                        pass

                # 无法删除，强制前进
                if not deleted_something:
                    current_pos += 1
                    if current_pos >= current_bound_end:
                        break

            log_parts.append(
                f"步骤2完成：循环 {delete_step} 步，"
                f"删除表格 {deleted_tables} 个，段落 {deleted_paras} 个"
            )

            # ---- 刷新受保护字段位置 ----
            protected_fields = _refresh_protected_fields(
                doc=doc,
                keywords=protected_keywords,
                range_start=int(insertion_bound_start),
                range_end=int(get_bound_end()),
                existing_fields=protected_fields,
            )

            # ==================================================================
            # 步骤3：多轮清理空段落、换行、空表格
            # ==================================================================
            log_parts.append("步骤3：清理空段落与换行...")

            def build_cleanup_range():
                return doc.Range(
                    int(insertion_bound_start),
                    int(get_bound_end()),
                )

            max_passes = 5
            total_empty_deleted = 0

            for pass_num in range(1, max_passes + 1):
                # 3.1 删除空段落
                empty_deleted = 0
                final_paragraphs = list(build_cleanup_range().Paragraphs)
                for idx in range(len(final_paragraphs) - 1, -1, -1):
                    try:
                        paragraph = final_paragraphs[idx]
                        if paragraph.Range.Information(wdWithInTable):
                            continue
                        if _is_protected_range(paragraph.Range, protected_fields):
                            continue
                        if _is_effectively_empty_text(paragraph.Range.Text):
                            paragraph.Range.Delete()
                            empty_deleted += 1
                    except Exception:
                        pass

                total_empty_deleted += empty_deleted
                log_parts.append(
                    f"  第 {pass_num} 轮：删除空段 {empty_deleted} 个"
                )

                if empty_deleted == 0:
                    break

                # 3.2 清理可编辑段落中的换行
                cleaned_count = 0
                paragraphs_to_delete = []

                for paragraph in build_cleanup_range().Paragraphs:
                    if paragraph.Range.Information(wdWithInTable):
                        continue
                    paragraph_text = paragraph.Range.Text
                    if _is_effectively_empty_text(paragraph_text):
                        continue
                    if _is_protected_range(paragraph.Range, protected_fields):
                        continue

                    try:
                        paragraph_range = paragraph.Range
                        full_text = paragraph_range.Text
                        text_without_mark = full_text.rstrip("\r\n\a")
                        if _is_effectively_empty_text(text_without_mark):
                            continue

                        cleaned_text = (
                            text_without_mark.replace("\r", "")
                            .replace("\n", "")
                            .replace("\r\n", "")
                            .replace("\x07", "")
                            .replace("\x0b", "")
                            .replace("\x0c", "")
                        )
                        cleaned_text = re.sub(
                            r"[\t\u00a0\u2000-\u200b\u3000]+", " ", cleaned_text
                        )
                        cleaned_text = re.sub(r" {2,}", " ", cleaned_text).strip()

                        if cleaned_text and cleaned_text != text_without_mark:
                            paragraph_range.Text = cleaned_text + "\r"
                            cleaned_count += 1
                        elif not cleaned_text:
                            paragraphs_to_delete.append(paragraph_range)
                    except Exception:
                        pass

                for prng in reversed(paragraphs_to_delete):
                    try:
                        prng.Delete()
                    except Exception:
                        pass

                # 3.3 最终检查剩余空段落
                final_paragraphs = list(build_cleanup_range().Paragraphs)
                for paragraph in reversed(final_paragraphs):
                    try:
                        if paragraph.Range.Information(wdWithInTable):
                            continue
                        if _is_protected_range(paragraph.Range, protected_fields):
                            continue
                        if _is_effectively_empty_text(paragraph.Range.Text):
                            paragraph.Range.Delete()
                    except Exception:
                        pass

            # 3.4 修剪空表格尾行 / 删除完全空的表格
            try:
                def _row_is_empty(row) -> bool:
                    try:
                        cells = row.Cells
                        for ci in range(1, cells.Count + 1):
                            try:
                                txt = cells(ci).Range.Text
                            except Exception:
                                txt = ""
                            if _visible_text(txt):
                                return False
                        return True
                    except Exception:
                        return False

                def _trim_table_trailing_empty_rows(table) -> int:
                    removed = 0
                    try:
                        for ri in range(table.Rows.Count, 0, -1):
                            try:
                                row = table.Rows(ri)
                                if _row_is_empty(row):
                                    row.Delete()
                                    removed += 1
                                else:
                                    break
                            except Exception:
                                break
                    except Exception:
                        return removed
                    return removed

                tbl_range = doc.Range(
                    int(insertion_bound_start), int(get_bound_end())
                )
                tbls = tbl_range.Tables
                trimmed_tables = 0
                trimmed_rows = 0
                deleted_empty_tables = 0

                for ti in range(tbls.Count, 0, -1):
                    try:
                        tbl = tbls(ti)
                        rr = _trim_table_trailing_empty_rows(tbl)
                        if rr > 0:
                            trimmed_tables += 1
                            trimmed_rows += rr
                        if not _visible_text(tbl.Range.Text):
                            tbl.Range.Delete()
                            deleted_empty_tables += 1
                    except Exception:
                        continue

                if trimmed_tables > 0 or deleted_empty_tables > 0:
                    log_parts.append(
                        f"  修剪表格 {trimmed_tables} 个（删除空行 {trimmed_rows} 行），"
                        f"删除空表格 {deleted_empty_tables} 个"
                    )
            except Exception:
                pass

            log_parts.append("步骤3完成：已清理空段落与多余换行。")

            # ==================================================================
            # 保存文档
            # ==================================================================
            try:
                word.ScreenUpdating = False
            except Exception:
                pass

            progress_log.info(f"[{NODE_NAME}] 开始保存清理后的文档")
            save_document_with_retry(doc, node_name=NODE_NAME)
            log_parts.append("文档已保存。")
            progress_log.info(f"[{NODE_NAME}] 文档保存完成")

            try:
                word.ScreenUpdating = True
            except Exception:
                pass

        except Exception as e:
            log_parts.append(f"Word 处理过程中出错: {e}")
            raise
        finally:
            close_word_application(
                word_app=word,
                doc=doc,
                com_initialized=com_initialized,
                wait_time=1.5,
                node_name=NODE_NAME,
            )

    except Exception as e:
        from backend.graphs.base_graph import TaskCancelledException

        if isinstance(e, TaskCancelledException):
            progress_log.warning(f"[{NODE_NAME}] 任务已取消")
            raise

        error_msg = f"删除内容时发生错误: {e}"
        print(f"[{NODE_NAME}] {error_msg}")
        progress_log.error(f"[{NODE_NAME}] {error_msg}")
        import traceback
        traceback.print_exc()
        raise RuntimeError(error_msg) from e

    new_state_dict = dict(state)
    new_state = TenderGraphStateBase(**new_state_dict)

    duration = time.perf_counter() - start_time
    print(f"[{NODE_NAME}] 执行完成，耗时: {duration:.2f} 秒 ({duration * 1000:.0f} 毫秒)")
    progress_log.info(f"[{NODE_NAME}] 节点执行完成，耗时 {duration:.2f} 秒")

    try:
        for line in log_parts:
            print(f"[{NODE_NAME}] {line}")
    except Exception:
        pass

    return new_state


__all__ = [
    "gngk_fw_zc_delete_tender_param",
    "PROTECTED_FIELD_KEYWORDS",
]
