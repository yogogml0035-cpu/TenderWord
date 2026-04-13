"""
统一删除招标参数节点（回归 master 风格）。
"""

from __future__ import annotations

import os
import pathlib
import re
import shutil
import sys
import time

# 添加仓库根目录到 sys.path，便于直接运行当前脚本进行本地调试
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Dict, Optional

from backend.states import TenderGraphStateBase
from backend.config.tender_config import (
    CONTENT_UPDATE_MODE_DIRECT_REPLACE,
    get_tender_type_family,
    get_anchor_target_sizes,
    get_content_update_mode,
    get_default_anchor_texts,
)
from backend.util.log_util.progress_log import progress_log
from backend.util.word_util import (
    create_word_application,
    close_word_application,
    open_document_with_retry,
    save_document_with_retry,
    unprotect_document,
    wdCollapseEnd,
    wdFindStop,
    wdGoToPage,
    wdGoToAbsolute,
)
from backend.util.word_util.anchor_utils import (
    find_anchor_range,
    iter_anchor_text_variants,
    resolve_anchor_content_range,
)
from backend.helper.word_helper.range_utils import (
    is_range_locked,
    find_safe_insert_position,
)

NODE_NAME = "delete_tender_param"
HEARTBEAT_INTERVAL_SECONDS = 5.0


def _visible_log(message: str) -> None:
    progress_log.info(f"[{NODE_NAME}] {message}")


def _uses_wide_scan_window(tender_type: str | None) -> bool:
    return get_tender_type_family(tender_type) in {"gngk", "gjgk"}


def _calculate_elapsed_seconds(
    start_monotonic: float, current_monotonic: Optional[float] = None
) -> float:
    current = time.monotonic() if current_monotonic is None else current_monotonic
    return max(0.0, current - start_monotonic)


def _check_cancelled(config) -> None:
    if not isinstance(config, dict):
        return
    configurable = config.get("configurable")
    if not isinstance(configurable, dict):
        return
    task_id = configurable.get("task_id")
    if not task_id:
        return

    from backend.graphs.base_graph import TaskCancelledException
    from backend.task.task_queue_manager import get_task_queue

    if get_task_queue().is_task_cancelled(task_id):
        raise TaskCancelledException(f"任务 {task_id} 已被用户取消")


def _find_anchor_fast(
    doc_content, text: str, min_start: int = 0, target_size: float = 18.0
) -> Optional[Dict[str, int]]:
    """沿用 master/xjcg 的 Find.Execute 逻辑快速重定位后置锚点。"""
    candidates = iter_anchor_text_variants(text)
    for candidate in candidates:
        find_rng = doc_content.Duplicate
        find_rng.Start = max(0, int(min_start))
        find_rng.End = doc_content.End
        finder = find_rng.Find
        finder.ClearFormatting()
        finder.Text = candidate
        finder.Forward = True
        finder.Wrap = wdFindStop
        finder.MatchCase = False
        finder.MatchWholeWord = False
        while finder.Execute():
            try:
                font_name = str(find_rng.Font.Name)
                font_size = float(find_rng.Font.Size)
                is_font = font_name in ("宋体", "SimSun")
                is_size = abs(font_size - float(target_size)) < 0.5
                if is_font and is_size:
                    return {"start": int(find_rng.Start), "end": int(find_rng.End)}
            except Exception:
                pass
            find_rng.Collapse(wdCollapseEnd)
            find_rng.End = doc_content.End
    return None

def _find_paragraph_containing_any(
    doc,
    texts: tuple[str, ...],
    min_start: int = 0,
    max_start: Optional[int] = None,
):
    """在指定起点之后，查找首个包含任一文本的段落。"""
    for para in doc.Paragraphs:
        try:
            rng = para.Range
            range_start = int(rng.Start)
            range_end = int(rng.End)
            if range_end < int(min_start):
                continue
            if max_start is not None and range_start > int(max_start):
                break
            para_text = str(getattr(rng, "Text", "") or "")
            if any(text in para_text for text in texts):
                return rng
        except Exception:
            continue
    return None


def _find_first_visible_insert_offset(paragraph_text: str) -> int:
    """优先将换行插入到编号前，否则回退到首个可见字符前。"""
    if not paragraph_text:
        return 0

    digit_match = re.search(r"\d", paragraph_text)
    if digit_match:
        return digit_match.start()

    for idx, char in enumerate(paragraph_text):
        if not char.isspace() and char not in ("\r", "\n", "\a"):
            return idx
    return 0


def _insert_paragraph_break_before_delivery(
    doc,
    delivery_para_rng,
    fallback_pos: Optional[int],
    *,
    tender_type: str = "xjcg",
    log=_visible_log,
) -> bool:
    """在交付日期段落前补一个段落边界，失败时回退到原删除起点。"""
    paragraph_candidates = []
    if delivery_para_rng is not None:
        try:
            para_text_raw = str(getattr(delivery_para_rng, "Text", "") or "")
            primary_offset = _find_first_visible_insert_offset(para_text_raw)
            paragraph_start = int(delivery_para_rng.Start)
            paragraph_candidates = [
                paragraph_start + primary_offset,
                paragraph_start,
            ]

            safe_insert_pos = find_safe_insert_position(
                doc,
                paragraph_candidates,
                max_forward_scan_chars=24 if _uses_wide_scan_window(tender_type) else 8,
                field_name="交付日期",
                log=log,
            )
            if safe_insert_pos is not None:
                doc.Range(safe_insert_pos, safe_insert_pos).InsertBefore("\r")
                return True
        except Exception:
            pass

    if fallback_pos is None:
        return False

    fallback_insert_pos = find_safe_insert_position(
        doc,
        [fallback_pos],
        max_forward_scan_chars=24 if _uses_wide_scan_window(tender_type) else 8,
        field_name="交付日期",
        log=log,
    )
    if fallback_insert_pos is None:
        return False

    try:
        doc.Range(fallback_insert_pos, fallback_insert_pos).InsertParagraphAfter()
        return True
    except Exception:
        return False


def _ensure_paragraph_break_after_payment(
    doc,
    payment_para_rng,
    max_scan_chars: int = 4000,
    *,
    tender_type: str = "xjcg",
    log=_visible_log,
) -> bool:
    """在付款方式段落后补回车，必要时跳过受保护位置向后探测。"""
    if payment_para_rng is None:
        return False

    try:
        payment_end = int(payment_para_rng.End)
        doc_end = int(doc.Content.End)
    except Exception:
        return False

    need_insert = True
    if payment_end < doc_end:
        try:
            next_char = doc.Range(payment_end, min(payment_end + 1, doc_end)).Text
            if next_char == "\r":
                need_insert = False
        except Exception:
            pass

    if not need_insert:
        return False

    max_pos = min(doc_end, payment_end + max_scan_chars)
    safe_insert_pos = find_safe_insert_position(
        doc,
        range(payment_end, max_pos + 1),
        max_forward_scan_chars=8 if _uses_wide_scan_window(tender_type) else 0,
        field_name="付款方式",
        log=log,
    )
    if safe_insert_pos is None:
        return False

    try:
        doc.Range(safe_insert_pos, safe_insert_pos).InsertBefore("\r")
        return True
    except Exception:
        return False


def _restore_protected_field_paragraph_boundaries(
    doc,
    before_text: str,
    before_end_pos: Optional[int],
    *,
    target_size: float = 18.0,
    tender_type: str = "xjcg",
    log=_visible_log,
) -> None:
    """恢复删除后受保护字段周围的段落边界，避免字段与正文黏连。"""
    del before_text, target_size

    try:
        doc_end = int(doc.Content.End)
    except Exception:
        doc_end = 0

    search_start = min(max(0, int(before_end_pos or 0)), doc_end)
    search_window = 20000 if _uses_wide_scan_window(tender_type) else 12000
    search_end = min(doc_end, search_start + search_window)

    if log:
        log(
            f"开始修复删除后段落边界，扫描范围 {search_start}-{search_end}"
        )

    delivery_para_rng = _find_paragraph_containing_any(
        doc,
        ("交付日期：", "交付日期:"),
        min_start=search_start,
        max_start=search_end,
    )
    if log:
        log('开始修复"交付日期"前的段落边界')
    if delivery_para_rng is None:
        print(
            '[delete_tender_param] 提示: 在局部扫描范围内未找到"交付日期"锚点，回退到删除起点补段落边界'
        )
        if log:
            log('在局部扫描范围内未找到"交付日期"字段，回退到删除起点补段落边界')
    delivery_fixed = _insert_paragraph_break_before_delivery(
        doc,
        delivery_para_rng,
        before_end_pos,
        tender_type=tender_type,
        log=log,
    )
    if delivery_fixed:
        print('[delete_tender_param] 已补齐"交付日期"前的段落边界')
        if log:
            log('已补齐"交付日期"前的段落边界')
    else:
        print('[delete_tender_param] 警告: 未能补齐"交付日期"前的段落边界')
        if log:
            log('未能补齐"交付日期"前的段落边界')

    payment_para_rng = _find_paragraph_containing_any(
        doc,
        ("付款方式：", "付款方式:"),
        min_start=search_start,
        max_start=search_end,
    )
    if log:
        log('开始修复"付款方式"后的回车')
    if payment_para_rng is None:
        print('[delete_tender_param] 提示: 在局部扫描范围内未找到"付款方式"锚点，跳过补回车')
        if log:
            log('在局部扫描范围内未找到"付款方式"字段，跳过补回车')
        return

    if _ensure_paragraph_break_after_payment(
        doc,
        payment_para_rng,
        tender_type=tender_type,
        log=log,
    ):
        print('[delete_tender_param] 已补齐"付款方式"后的回车')
        if log:
            log('已补齐"付款方式"后的回车')
    else:
        print('[delete_tender_param] 提示: "付款方式"后已存在回车或未找到可编辑位置')
        if log:
            log('"付款方式"后已存在回车或未找到可编辑位置')


def delete_tender_param(state: TenderGraphStateBase, config) -> TenderGraphStateBase:
    """
    根据前后锚点定位，删除文档中锚点之间的内容。

    从 state 中读取：
    - insertion_before_text: 插入位置的前置文本
    - insertion_after_text: 插入位置的后置文本
    - prepared_doc_path: WPS/Word 文档路径
    - tender_type: 招标类型（'xjcg' 或 'gngk'）

    删除锚点之间的内容并保存文档。
    """
    start_time = time.monotonic()
    print(f"[delete_tender_param] 开始执行...")
    _visible_log("开始删除原始采购需求")

    prepared_doc_path = state.get("prepared_doc_path")
    before_text = state.get("insertion_before_text")
    after_text = state.get("insertion_after_text")
    tender_type = state.get("tender_type", "xjcg")

    if not prepared_doc_path:
        raise ValueError("需要 prepared_doc_path 来删除 WPS/Word 文档中的内容")

    if not before_text or not after_text:
        # 如果没有提供前后文本，跳过删除
        print(
            f"[delete_tender_param] 警告: 未提供 insertion_before_text 或 insertion_after_text，跳过删除"
        )
        return TenderGraphStateBase(**dict(state))

    # 确保路径是绝对路径（WPS/Word COM 对象需要绝对路径）
    if not os.path.isabs(prepared_doc_path):
        prepared_doc_path = os.path.abspath(prepared_doc_path)

    # 检查文件是否存在
    if not os.path.exists(prepared_doc_path):
        raise FileNotFoundError(f"未找到准备好的文档: {prepared_doc_path}")

    # 检查文件是否可写
    if not os.access(prepared_doc_path, os.W_OK):
        raise PermissionError(f"无法写入准备好的文档: {prepared_doc_path}")

    before_size, after_size = get_anchor_target_sizes(str(tender_type or "xjcg"))
    print(
        f"[delete_tender_param] 招标类型: {tender_type}, 前置字号: {before_size}, 后置字号: {after_size}"
    )

    word = None
    doc = None
    com_initialized = False

    try:
        # 使用统一的工具函数创建 Word 应用程序
        # 独立实例 + 预留时间，避免前序节点关闭未完成导致句柄失效
        _visible_log("开始打开待清理文档")
        word, com_initialized = create_word_application(
            initial_delay=2.0,  # 创建前等待 2 秒，让之前的实例有时间完全关闭
            post_init_delay=1.0,  # 给 Word 初始化的时间
            use_existing=False,  # 不使用已运行的实例，创建新的独立实例
            verify=True,
            node_name="delete_tender_param",
        )

        # 使用统一的工具函数打开文档（带重试机制）
        doc = open_document_with_retry(
            word_app=word,
            file_path=prepared_doc_path,
            read_only=False,  # 需要写入以删除内容
            node_name="delete_tender_param",
        )
        _visible_log("文档打开完成，准备定位采购需求锚点")

        # 使用统一的工具函数取消文档保护
        unprotect_document(doc, node_name="delete_tender_param")
        doc_content = doc.Content

        # === 使用统一的双策略查找锚点 ===
        print(f"[delete_tender_param] 正在查找锚点...")
        print(f"  前置文本: '{before_text}'")
        print(f"  后置文本: '{after_text}'")
        _visible_log("开始查找删除范围锚点")

        before_hit, after_hit = find_anchor_range(
            doc=doc,
            before_text=before_text,
            after_text=after_text,
            before_size=before_size,
            after_size=after_size,
            prefer_before="last",  # 前置选页码最大的，避开目录
            prefer_after="first",  # 后置选页码最小的，取第一个后续章节
        )

        if not before_hit:
            msg = f"未找到前置锚点: {before_text}"
            print(f"[delete_tender_param] 错误: {msg}")
            _visible_log(msg)
            raise ValueError(msg)
        if not after_hit:
            msg = f"未找到后置锚点: {after_text}"
            print(f"[delete_tender_param] 错误: {msg}")
            _visible_log(msg)
            raise ValueError(msg)

        used_before_text = before_hit.get("used_text", before_text)
        used_after_text = after_hit.get("used_text", after_text)
        if used_before_text != before_text:
            print(
                f"[delete_tender_param] 前置锚点 '{before_text}' 未命中，改用 '{used_before_text}'"
            )
            before_text = used_before_text
        if used_after_text != after_text:
            print(
                f"[delete_tender_param] 后置锚点 '{after_text}' 未命中，改用 '{used_after_text}'"
            )
            after_text = used_after_text

        before_page = int(before_hit["page"])
        before_end_pos = int(before_hit["end"])
        after_page = int(after_hit["page"])
        after_start_pos = int(after_hit["start"])
        after_end_pos = int(after_hit["end"])

        print(
            f"✅ 前置锚点: 页={before_page}, end={before_end_pos}, 字体={before_hit['font']}, 字号={before_hit['size']}"
        )
        print(
            f"✅ 后置锚点: 页={after_page}, start={after_start_pos}, end={after_end_pos}, 字体={after_hit['font']}, 字号={after_hit['size']}"
        )

        content_range = resolve_anchor_content_range(
            doc=doc,
            word_app=word,
            before_hit=before_hit,
            after_hit=after_hit,
            tender_type=str(tender_type or "xjcg"),
        )
        range_start = int(content_range["range_start"])
        range_end = int(content_range["range_end"])
        start_page = int(content_range["start_page"])
        end_page = int(content_range["end_page"])
        content_update_mode = get_content_update_mode(str(tender_type or "xjcg"))

        # === 开始删除锚点之间的内容 ===
        print("开始删除锚点之间的内容")
        print(f"删除范围: {range_start} -> {range_end}")
        _visible_log(
            f"锚点定位完成，开始删除第 {start_page} 至 {end_page} 页内容"
        )

        # 合法性校验，避免 Range 越界
        doc_end = doc.Content.End
        if (
            range_end is None
            or range_start is None
            or range_end <= range_start
            or range_end > doc_end
            or range_start < 0
            or range_start > doc_end
        ):
            msg = (
                "锚点位置异常，无法执行删除: "
                f"range_start={range_start}, range_end={range_end}, doc_end={doc_end}"
            )
            print(f"[delete_tender_param] 错误: {msg}")
            _visible_log(msg)
            raise ValueError(msg)

        if content_update_mode == CONTENT_UPDATE_MODE_DIRECT_REPLACE:
            print("[delete_tender_param] gjgk direct_replace 模式，直接删除完整正文区间")
            _visible_log("gjgk 走 direct_replace 模式，直接删除正文区间")
            doc.Range(range_start, range_end).Delete()
            print(f"[delete_tender_param] 内容删除完成，页码范围: {start_page} - {end_page}")
            _visible_log(f"删除完成，页码范围 {start_page}-{end_page}，准备保存文档")
            _visible_log("开始保存清理后的文档")
            save_document_with_retry(doc, node_name=NODE_NAME)
            _visible_log("文档保存完成")
            new_state_dict = dict(state)
            elapsed_time = _calculate_elapsed_seconds(start_time)
            print(
                f"[delete_tender_param] 执行完成，耗时: {elapsed_time:.2f} 秒 ({elapsed_time * 1000:.0f} 毫秒)"
            )
            _visible_log(f"节点执行完成，耗时 {elapsed_time:.2f} 秒")
            return TenderGraphStateBase(**new_state_dict)

        print("采用优化策略：大块删除 + 失败时逐步缩小")
        max_steps = 500  # 减少最大步数，因为新策略更高效
        step_idx = 0
        current_pos = range_start

        # 性能监控
        perf_stats = {
            "refresh_time": 0,
            "delete_time": 0,
            "table_time": 0,
            "para_time": 0,
        }
        last_heartbeat_at = time.monotonic()

        while step_idx < max_steps:
            _check_cancelled(config)
            step_idx += 1

            # 每 50 步刷新一次文档末尾位置
            if step_idx % 50 == 0:
                doc_end = doc_content.End

            # 快速重新定位后置锚点（不获取页码）
            t0 = time.time()
            after_hit_refresh = _find_anchor_fast(
                doc_content,
                after_text,
                min_start=current_pos,
                target_size=after_size,
            )
            perf_stats["refresh_time"] += time.time() - t0

            if not after_hit_refresh:
                print("✅ 删除完成：未找到后置锚点（可能已被删除或到达目标）")
                break

            after_start_pos = after_hit_refresh["start"]
            after_end_pos = after_hit_refresh["end"]
            now = time.monotonic()
            if now - last_heartbeat_at >= HEARTBEAT_INTERVAL_SECONDS:
                elapsed = _calculate_elapsed_seconds(start_time, now)
                _visible_log(
                    f"仍在删除原始采购需求，已执行 {step_idx} 步，当前范围 {current_pos}->{after_start_pos}，耗时 {elapsed:.1f} 秒"
                )
                last_heartbeat_at = now

            # 检查是否已到达锚点
            if after_start_pos <= current_pos:
                print("✅ 删除完成：已到达后置锚点")
                break

            # 边界检查
            if after_start_pos > doc_end or current_pos < 0 or current_pos > doc_end:
                print(
                    f"⚠️ 位置异常，停止删除。current_pos={current_pos}, after_start_pos={after_start_pos}, doc_end={doc_end}"
                )
                break

            delete_rng = doc.Range(current_pos, after_start_pos)

            # 策略 1: 尝试大块删除整个范围
            try:
                if step_idx % 10 == 1:  # 每 10 步打印一次进度
                    print(
                        f"  步骤 {step_idx}: 尝试删除 {current_pos} -> {after_start_pos} (大小: {after_start_pos - current_pos})"
                    )
                t0 = time.time()
                delete_rng.Delete()
                perf_stats["delete_time"] += time.time() - t0
                # 成功删除，继续下一轮
                continue
            except Exception:
                perf_stats["delete_time"] += time.time() - t0
                # 大块删除失败，可能有锁定内容
                if step_idx % 10 == 1:
                    print("  大块删除失败，切换到逐元素删除")

            # 策略 2: 逐元素删除（表格优先，然后段落）
            deleted_something = False

            # 2.1 尝试删除第一张表格
            try:
                t0 = time.time()
                tables = delete_rng.Tables
                if tables.Count > 0:
                    tbl = tables(1)  # 使用索引而不是 list()
                    tbl_rng = tbl.Range

                    # 检查表格是否超出删除范围
                    if tbl_rng.End > after_start_pos:
                        # 只删除到锚点之前
                        safe_del_rng = doc.Range(tbl_rng.Start, after_start_pos)
                        if is_range_locked(doc, safe_del_rng):
                            current_pos = after_start_pos
                        else:
                            try:
                                safe_del_rng.Delete()
                                current_pos = after_start_pos
                                deleted_something = True
                            except Exception:
                                current_pos = after_start_pos
                        perf_stats["table_time"] += time.time() - t0
                        continue

                    if is_range_locked(doc, tbl_rng):
                        current_pos = min(tbl_rng.End, after_start_pos)
                        deleted_something = True
                        perf_stats["table_time"] += time.time() - t0
                        continue

                    # 尝试删除表格
                    try:
                        tbl.Delete()
                        deleted_something = True
                        perf_stats["table_time"] += time.time() - t0
                        continue
                    except Exception:
                        # 删除失败，跳过这个表格
                        current_pos = min(tbl_rng.End, after_start_pos)
                        deleted_something = True
                        perf_stats["table_time"] += time.time() - t0
                        continue
                perf_stats["table_time"] += time.time() - t0
            except Exception:
                perf_stats["table_time"] += time.time() - t0

            # 2.2 尝试删除第一个段落
            if not deleted_something:
                try:
                    t0 = time.time()
                    paras = delete_rng.Paragraphs
                    if paras.Count > 0:
                        para_rng = paras(1).Range  # 使用索引而不是 list()

                        # 检查段落是否超出删除范围
                        if para_rng.End > after_start_pos:
                            safe_del_rng = doc.Range(para_rng.Start, after_start_pos)
                            if is_range_locked(doc, safe_del_rng):
                                current_pos = after_start_pos
                            else:
                                try:
                                    safe_del_rng.Delete()
                                    current_pos = after_start_pos
                                    deleted_something = True
                                except Exception:
                                    current_pos = after_start_pos
                            perf_stats["para_time"] += time.time() - t0
                            continue

                        if is_range_locked(doc, para_rng):
                            current_pos = min(para_rng.End, after_start_pos)
                            deleted_something = True
                            perf_stats["para_time"] += time.time() - t0
                            continue

                        # 尝试删除段落
                        try:
                            para_rng.Delete()
                            deleted_something = True
                            perf_stats["para_time"] += time.time() - t0
                            continue
                        except Exception:
                            # 删除失败，跳过这个段落
                            current_pos = min(para_rng.End, after_start_pos)
                            deleted_something = True
                            perf_stats["para_time"] += time.time() - t0
                            continue
                    perf_stats["para_time"] += time.time() - t0
                except Exception:
                    perf_stats["para_time"] += time.time() - t0

            # 策略 3: 尝试删除小块字符（50 字符）
            if not deleted_something:
                try:
                    chunk_size = min(50, after_start_pos - current_pos)
                    if chunk_size > 0:
                        chunk_end = current_pos + chunk_size
                        small_rng = doc.Range(current_pos, chunk_end)
                        if is_range_locked(doc, small_rng):
                            current_pos = chunk_end
                            deleted_something = True
                            continue
                        try:
                            t0 = time.time()
                            small_rng.Delete()
                            perf_stats["delete_time"] += time.time() - t0
                            deleted_something = True
                            continue
                        except Exception:
                            perf_stats["delete_time"] += time.time() - t0
                            # 字符块也删不掉，跳过
                            current_pos = chunk_end
                            continue
                except Exception:
                    pass

            # 如果什么都删不掉，强制前进避免死循环
            if not deleted_something:
                print(f"  ⚠️ 步骤 {step_idx}: 无法删除任何内容，强制前进 1 个位置")
                current_pos += 1
                if current_pos >= after_start_pos:
                    print("✅ 已到达后置锚点")
                    break

        # 打印性能统计
        print(f"\n性能统计 (总步数: {step_idx}):")
        print(f"  锚点刷新耗时: {perf_stats['refresh_time']:.2f}秒")
        print(f"  大块删除耗时: {perf_stats['delete_time']:.2f}秒")
        print(f"  表格处理耗时: {perf_stats['table_time']:.2f}秒")
        print(f"  段落处理耗时: {perf_stats['para_time']:.2f}秒")

        print(f"[delete_tender_param] 内容删除完成，页码范围: {start_page} - {end_page}")
        _visible_log(f"删除完成，页码范围 {start_page}-{end_page}，准备保存文档")

        try:
            _restore_protected_field_paragraph_boundaries(
                doc=doc,
                before_text=before_text,
                before_end_pos=range_start,
                target_size=before_size,
                tender_type=tender_type,
            )
        except Exception as layout_e:
            print(f"[delete_tender_param] 警告: 删除后段落边界修正失败: {layout_e}")
            _visible_log(f"删除后段落边界修正失败: {layout_e}")

        # 保存清理后的文档
        try:
            print("  开始保存文档...")
            try:
                word.ScreenUpdating = False
            except Exception:
                pass

            print("  正在保存文档（这可能需要几秒钟）...")
            _visible_log("开始保存清理后的文档")
            save_document_with_retry(doc, node_name=NODE_NAME)
            print("  文档已保存（删除完成）")
            _visible_log("文档保存完成")

            try:
                word.ScreenUpdating = True
            except Exception:
                pass
        except Exception as save_e:
            print(f"  警告: 保存文档失败: {save_e}")

    except Exception as e:
        from backend.graphs.base_graph import TaskCancelledException

        if isinstance(e, TaskCancelledException):
            progress_log.warning(f"[{NODE_NAME}] 任务已取消")
            raise

        error_msg = f"删除内容时发生错误: {e}"
        print(f"[delete_tender_param] {error_msg}")
        progress_log.error(f"[{NODE_NAME}] {error_msg}")
        # 打印详细的错误堆栈信息
        import traceback

        print(f"[delete_tender_param] 详细错误堆栈:")
        traceback.print_exc()
        # 终止图运行：抛出异常而不是吞掉错误
        raise RuntimeError(error_msg) from e

    finally:
        print("[delete_tender_param] 开始清理资源...")
        _visible_log("开始清理 Word 资源")
        # 使用统一的工具函数关闭 Word 应用程序
        close_word_application(
            word_app=word,
            doc=doc,
            com_initialized=com_initialized,
            wait_time=1.5,
            node_name="delete_tender_param",
        )
        _visible_log("Word 资源清理完成")

    # 更新状态
    new_state_dict = dict(state)

    elapsed_time = _calculate_elapsed_seconds(start_time)
    print(
        f"[delete_tender_param] 执行完成，耗时: {elapsed_time:.2f} 秒 ({elapsed_time * 1000:.0f} 毫秒)"
    )
    _visible_log(f"节点执行完成，耗时 {elapsed_time:.2f} 秒")

    return TenderGraphStateBase(**new_state_dict)


if __name__ == "__main__":
    """测试 delete_tender_param 节点的删除功能"""
    print("=" * 80)
    print("开始测试 delete_tender_param 节点 (common)")
    print("=" * 80)

    tender_type = "gjgk"
    source_doc_path = (
        BACKEND_ROOT / "test_doc" / "254DSITC2512-招标文件-发售稿-财政模板.doc"
    )
    before_text, after_text = get_default_anchor_texts(tender_type)
    test_doc_path = source_doc_path.with_name(
        f"{source_doc_path.stem}-delete-test{source_doc_path.suffix}"
    )

    # 检查测试文件是否存在
    if not source_doc_path.exists():
        print(f"错误: 测试文件不存在: {source_doc_path}")
        sys.exit(1)

    shutil.copy2(source_doc_path, test_doc_path)

    print(f"测试类型: {tender_type} (国际公开)")
    print(f"源文件: {source_doc_path}")
    print(f"测试副本: {test_doc_path}")
    print(f"源文件存在: {source_doc_path.exists()}")
    print(f"文件大小: {source_doc_path.stat().st_size / 1024:.2f} KB")
    print()

    # 构造测试状态
    test_state: TenderGraphStateBase = {
        "tender_type": tender_type,
        "prepared_doc_path": str(test_doc_path),
        "insertion_before_text": before_text,
        "insertion_after_text": after_text,
    }

    print("测试状态:")
    for key, value in test_state.items():
        print(f"  {key}: {value}")
    print()

    # 执行删除节点
    try:
        print("开始执行删除操作...")
        print("-" * 80)
        result_state = delete_tender_param(test_state, config=None)
        print("-" * 80)
        print()
        print("✅ 删除操作执行完成")
        print(f"删除结果文件: {test_doc_path}")
        print()
        print("返回状态:")
        for key, value in result_state.items():
            if isinstance(value, str) and len(value) > 100:
                print(f"  {key}: {value[:100]}...")
            else:
                print(f"  {key}: {value}")
    except Exception as e:
        print()
        print("❌ 删除操作失败")
        print(f"错误信息: {e}")
        import traceback

        print()
        print("详细错误堆栈:")
        traceback.print_exc()
        sys.exit(1)

    print()
    print("=" * 80)
    print("测试完成")
    print("=" * 80)
