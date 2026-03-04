"""
统一删除招标参数节点

从文档中删除锚点之间的内容，基于前后锚点定位。
支持多种招标类型（询价采购、国内公开等），通过 tender_type 参数动态调整字体大小。

使用 find_anchor_range() 统一双策略定位：
1. 段落扫描优先（从 GNGK 实现）
2. Find.Execute 兜底（从 XJCG 实现）

删除策略：
1. 优先大块删除（效率高）
2. 失败时逐元素删除（表格优先，然后段落）
3. 保护字段检测：跳过受保护内容
"""

from __future__ import annotations

import os
import time
import pathlib
import sys

# 添加项目根目录到 sys.path
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from typing import Dict, Any, Optional

from backend.states import TenderGraphStateBase
from backend.config.tender_config import TARGET_SIZES
from backend.util.word_util import (
    create_word_application,
    close_word_application,
    open_document_with_retry,
    unprotect_document,
    wdGoToPage,
    wdGoToAbsolute,
)
from backend.util.word_util.anchor_utils import find_anchor_range




def _find_anchor_fast(doc, text: str, min_start: int = 0) -> Optional[Dict[str, int]]:
    """
    快速查找锚点（不获取页码信息），用于循环中的 refresh。

    Args:
        doc: Word 文档对象
        text: 要匹配的文本
        min_start: 最小起始位置（用于过滤）

    Returns:
        {"start": int, "end": int} 或 None
    """
    for para in doc.Paragraphs:
        try:
            rng = para.Range
            if rng.Start < min_start:
                continue
            if rng.Text.strip() == text:
                return {"start": int(rng.Start), "end": int(rng.End)}
        except Exception:
            pass
    return None


def _is_range_locked(rng, doc) -> bool:
    """
    检测范围是否被保护（含字段保护检测）。

    Args:
        rng: Word Range 对象
        doc: Word Document 对象

    Returns:
        True 如果被保护，False 如果可编辑
    """
    # 检查 Range.Locked 属性
    try:
        if hasattr(rng, "Locked") and rng.Locked:
            return True
    except Exception:
        pass

    # 检查字段锁定
    try:
        fields = rng.Fields
        count = fields.Count
        for i in range(1, count + 1):
            try:
                field = fields(i)
                if hasattr(field, "Locked") and field.Locked:
                    return True
            except Exception:
                continue
    except Exception:
        pass

    # 通过尝试写入检测保护
    try:
        marker = "\u200b"  # 零宽空格
        test_pos = rng.End
        probe_rng = doc.Range(test_pos, test_pos)
        probe_rng.InsertAfter(marker)
        inserted = doc.Range(test_pos, test_pos + 1)
        if inserted.Text == marker:
            inserted.Delete()
            return False
    except Exception as probe_e:
        err = str(probe_e).lower()
        if "锁定" in err or "locked" in err or "-2146823683" in err:
            return True
    return False


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
    start_time = time.time()
    print(f"[delete_tender_param] 开始执行...")

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

    # 根据招标类型获取目标字体大小
    target_size = TARGET_SIZES.get(tender_type, 18.0)
    print(f"[delete_tender_param] 招标类型: {tender_type}, 目标字号: {target_size}")

    word = None
    doc = None
    com_initialized = False

    try:
        # 使用统一的工具函数创建 Word 应用程序
        # 独立实例 + 预留时间，避免前序节点关闭未完成导致句柄失效
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

        # 使用统一的工具函数取消文档保护
        unprotect_document(doc, node_name="delete_tender_param")

        # === 使用统一的双策略查找锚点 ===
        print(f"[delete_tender_param] 正在查找锚点...")
        print(f"  前置文本: '{before_text}'")
        print(f"  后置文本: '{after_text}'")

        before_hit, after_hit = find_anchor_range(
            doc=doc,
            before_text=before_text,
            after_text=after_text,
            target_size=target_size,
            prefer_before="last",  # 前置选页码最大的，避开目录
            prefer_after="first",  # 后置选页码最小的，取第一个后续章节
        )

        if not before_hit:
            print(f"[delete_tender_param] 警告: 未找到前置文本 '{before_text}'")
        elif not after_hit:
            print(f"[delete_tender_param] 警告: 未找到后置文本 '{after_text}'")
        else:
            before_page = before_hit["page"]
            before_end_pos = before_hit["end"]
            after_page = after_hit["page"]
            after_start_pos = after_hit["start"]
            after_end_pos = after_hit["end"]

            print(
                f"✅ 前置锚点: 页={before_page}, end={before_end_pos}, 字体={before_hit['font']}, 字号={before_hit['size']}"
            )
            print(
                f"✅ 后置锚点: 页={after_page}, start={after_start_pos}, end={after_end_pos}, 字体={after_hit['font']}, 字号={after_hit['size']}"
            )

            if after_page <= before_page:
                print(
                    f"错误: 后置文本页码 ({after_page}) 小于等于前置文本页码 ({before_page})"
                )
            else:
                # 将 before_end_pos 对齐到下一页起始
                try:
                    selection = word.Selection
                    selection.GoTo(wdGoToPage, wdGoToAbsolute, before_page + 1)
                    next_page_start = selection.Start
                    if next_page_start > before_end_pos:
                        before_end_pos = next_page_start
                        print(f"将 before_end_pos 对齐到下一页起始: {before_end_pos}")
                except Exception as adj_e:
                    print(f"警告: 无法对齐 before_end_pos 到下一页起始: {adj_e}")

                # === 开始删除锚点之间的内容 ===
                print("开始删除锚点之间的内容")
                print(f"删除范围: {before_end_pos} -> {after_start_pos}")

                # 合法性校验，避免 Range 越界
                doc_end = doc.Content.End
                if (
                    after_start_pos is None
                    or before_end_pos is None
                    or after_start_pos <= before_end_pos
                    or after_start_pos > doc_end
                    or before_end_pos < 0
                    or before_end_pos > doc_end
                ):
                    print(
                        f"错误: 锚点位置异常，放弃删除。before_end_pos={before_end_pos}, after_start_pos={after_start_pos}, doc_end={doc_end}"
                    )
                else:
                    print("采用优化策略：大块删除 + 失败时逐步缩小")
                    max_steps = 500  # 减少最大步数，因为新策略更高效
                    step_idx = 0
                    current_pos = before_end_pos

                    # 性能监控
                    perf_stats = {
                        "refresh_time": 0,
                        "delete_time": 0,
                        "table_time": 0,
                        "para_time": 0,
                    }

                    while step_idx < max_steps:
                        step_idx += 1

                        # 每 50 步刷新一次文档末尾位置
                        if step_idx % 50 == 0:
                            doc_end = doc.Content.End

                        # 快速重新定位后置锚点（不获取页码）
                        t0 = time.time()
                        after_hit_refresh = _find_anchor_fast(
                            doc, after_text, current_pos
                        )
                        perf_stats["refresh_time"] += time.time() - t0

                        if not after_hit_refresh:
                            print(
                                "✅ 删除完成：未找到后置锚点（可能已被删除或到达目标）"
                            )
                            break

                        after_start_pos = after_hit_refresh["start"]
                        after_end_pos = after_hit_refresh["end"]

                        # 检查是否已到达锚点
                        if after_start_pos <= current_pos:
                            print("✅ 删除完成：已到达后置锚点")
                            break

                        # 边界检查
                        if (
                            after_start_pos > doc_end
                            or current_pos < 0
                            or current_pos > doc_end
                        ):
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
                        except Exception as big_del_e:
                            perf_stats["delete_time"] += time.time() - t0
                            # 大块删除失败，可能有锁定内容
                            if step_idx % 10 == 1:
                                print(f"  大块删除失败，切换到逐元素删除")

                        # 策略 2: 逐元素删除（表格优先，然后段落）
                        deleted_something = False

                        # 2.1 尝试删除第一张表格
                        try:
                            t0 = time.time()
                            tables = delete_rng.Tables
                            if tables.Count > 0:
                                tbl = tables(1)  # 使用索引而不是 list()
                                tbl_rng = tbl.Range

                                # 检查表格是否超出删除范围（保护感知）
                                if tbl_rng.End > after_start_pos:
                                    # 只删除到锚点之前
                                    safe_del_rng = doc.Range(
                                        tbl_rng.Start, after_start_pos
                                    )
                                    if _is_range_locked(safe_del_rng, doc):
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

                                # 检查表格是否受保护
                                if _is_range_locked(tbl_rng, doc):
                                    # 跳过受保护表格，移动指针到表格末尾继续
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

                                    # 检查段落是否超出删除范围（保护感知）
                                    if para_rng.End > after_start_pos:
                                        safe_del_rng = doc.Range(
                                            para_rng.Start, after_start_pos
                                        )
                                        if _is_range_locked(safe_del_rng, doc):
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

                                    # 检查段落是否受保护
                                    if _is_range_locked(para_rng, doc):
                                        # 跳过受保护段落，移动指针到段末
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
                                    # 检查保护
                                    if _is_range_locked(small_rng, doc):
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
                            print(
                                f"  ⚠️ 步骤 {step_idx}: 无法删除任何内容，强制前进 1 个位置"
                            )
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

                    # 记录页码范围供后续节点参考
                    start_page = before_page + 1
                    end_page = after_page - 1
                    print(
                        f"[delete_tender_param] 内容删除完成，页码范围: {start_page} - {end_page}"
                    )

                    # 保存清理后的文档
                    try:
                        print("  开始保存文档...")
                        try:
                            word.ScreenUpdating = False
                        except Exception:
                            pass

                        print("  正在保存文档（这可能需要几秒钟）...")
                        doc.Save()
                        print("  文档已保存（删除完成）")

                        try:
                            word.ScreenUpdating = True
                        except Exception:
                            pass
                    except Exception as save_e:
                        print(f"  警告: 保存文档失败: {save_e}")

    except Exception as e:
        error_msg = f"删除内容时发生错误: {e}"
        print(f"[delete_tender_param] {error_msg}")
        # 打印详细的错误堆栈信息
        import traceback

        print(f"[delete_tender_param] 详细错误堆栈:")
        traceback.print_exc()
        # 终止图运行：抛出异常而不是吞掉错误
        raise RuntimeError(error_msg) from e

    finally:
        print("[delete_tender_param] 开始清理资源...")
        # 使用统一的工具函数关闭 Word 应用程序
        close_word_application(
            word_app=word,
            doc=doc,
            com_initialized=com_initialized,
            wait_time=1.5,
            node_name="delete_tender_param",
        )

    # 更新状态
    new_state_dict = dict(state)

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(
        f"[delete_tender_param] 执行完成，耗时: {elapsed_time:.2f} 秒 ({elapsed_time * 1000:.0f} 毫秒)"
    )

    return TenderGraphStateBase(**new_state_dict)


if __name__ == "__main__":
    """测试 delete_tender_param 节点的删除功能"""
    print("=" * 80)
    print("开始测试 delete_tender_param 节点 (common)")
    print("=" * 80)

    # 构造测试文档路径
    test_doc_path = ROOT / "test_word" / "251534-招标文件-清洁稿 copy.doc"

    # 检查测试文件是否存在
    if not test_doc_path.exists():
        print(f"错误: 测试文件不存在: {test_doc_path}")
        sys.exit(1)

    print(f"测试文件: {test_doc_path}")
    print(f"文件存在: {test_doc_path.exists()}")
    print(f"文件大小: {test_doc_path.stat().st_size / 1024:.2f} KB")
    print()

    # 构造测试状态
    test_state: TenderGraphStateBase = {
        "tender_type": "gngk",
        "prepared_doc_path": str(test_doc_path),
        "insertion_before_text": "第三章 招标内容及要求",
        "insertion_after_text": "第四章 投标文件有关格式",
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
