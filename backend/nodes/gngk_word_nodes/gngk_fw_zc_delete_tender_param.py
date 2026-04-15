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

from backend.config.tender_config import (
    get_anchor_target_sizes,
    get_default_anchor_texts,
    get_protected_field_profile,
)
from backend.helper.word_helper.protected_fields import (
    collect_profile_protected_fields,
    refresh_profile_protected_fields,
    normalize_protected_field_paragraphs,
)
from backend.helper.word_helper.range_utils import is_protected_range, range_overlaps
from backend.helper.word_helper.cleanup_ops import multi_pass_cleanup
from backend.states import TenderGraphStateBase
from backend.util.log_util.progress_log import progress_log
from backend.util.word_util import (
    close_word_application,
    create_word_application,
    open_document_with_retry,
    save_document_with_retry,
    unprotect_document,
    wdActiveEndPageNumber,
    wdGoToAbsolute,
    wdGoToPage,
)
from backend.util.word_util.anchor_utils import (
    find_anchor_range,
    resolve_anchor_content_range,
)

NODE_NAME = "gngk_fw_zc_delete_tender_param"
GNGK_THREE_FIELD_PROFILE = get_protected_field_profile("gngk_fw_zc")
SERVICE_LOCATION_MARKER, SERVICE_TERM_MARKER, PAYMENT_METHOD_MARKER = (
    GNGK_THREE_FIELD_PROFILE.ordered_markers
)


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
    protected_profile = get_protected_field_profile(str(tender_type or "gngk_fw_zc"))

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

            protected_markers = list(protected_profile.ordered_markers)
            target_range = (int(page_start), int(page_end))
            fallback_range = (int(insertion_bound_start), int(get_bound_end()))

            log_parts.append(
                f"步骤1：定位服务三字段，目标页={target_page}"
                f"({target_range[0]}-{target_range[1]})，"
                f"边界={fallback_range[0]}-{fallback_range[1]}"
            )
            normalized_marker_count = normalize_protected_field_paragraphs(
                doc,
                protected_markers,
                target_range[0],
                fallback_range[1],
                log_parts=log_parts,
            )
            if normalized_marker_count > 0:
                log_parts.append(
                    f"  已预规范化服务三字段冒号 {normalized_marker_count} 处。"
                )

            protected_fields = collect_profile_protected_fields(
                doc=doc,
                profile=protected_profile,
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

                        if is_protected_range(tbl_rng, protected_fields):
                            current_pos = tbl_end
                            deleted_something = True
                        else:
                            if tbl_start > current_pos:
                                pre_rng = doc.Range(current_pos, tbl_start)
                                if not is_protected_range(pre_rng, protected_fields):
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

                            if is_protected_range(para_rng, protected_fields):
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
                            if is_protected_range(small_rng, protected_fields):
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
            refreshed_marker_count = normalize_protected_field_paragraphs(
                doc,
                protected_markers,
                int(insertion_bound_start),
                int(get_bound_end()),
                log_parts=log_parts,
            )
            if refreshed_marker_count > 0:
                log_parts.append(
                    f"  重绑前再次规范化服务三字段冒号 {refreshed_marker_count} 处。"
                )
            protected_fields = refresh_profile_protected_fields(
                doc=doc,
                profile=protected_profile,
                range_start=int(insertion_bound_start),
                range_end=int(get_bound_end()),
                existing_fields=protected_fields,
            )

            # ==================================================================
            # 步骤3：多轮清理空段落、换行、空表格
            # ==================================================================
            log_parts.append("步骤3：清理空段落与换行...")

            multi_pass_cleanup(
                doc,
                build_range_fn=lambda: (int(insertion_bound_start), int(get_bound_end())),
                is_protected_fn=lambda rng: is_protected_range(rng, protected_fields),
                log_parts=log_parts,
                max_passes=5,
                step_label="步骤3",
            )

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
    "GNGK_THREE_FIELD_PROFILE",
]
