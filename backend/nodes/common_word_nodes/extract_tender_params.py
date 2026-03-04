"""
统一招标参数提取节点

从文档中提取招标参数内容，基于前后锚点定位。
支持多种招标类型（询价采购、国内公开等），通过 tender_type 参数动态调整字体大小。

使用 find_anchor_range() 统一双策略定位：
1. 段落扫描优先（从 GNGK 实现）
2. Find.Execute 兜底（从 XJCG 实现）
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

from typing import Dict, List, Tuple, Any, Optional

from backend.states import TenderGraphStateBase
from backend.config.tender_config import TARGET_SIZES
from backend.util.word_util import (
    create_word_application,
    close_word_application,
    open_document_with_retry,
    unprotect_document,
    extract_content_with_tables,
    extract_text_from_word_file,
    wdGoToPage,
    wdGoToAbsolute,
)
from backend.util.word_util.anchor_utils import find_anchor_range



def extract_tender_params(state: TenderGraphStateBase, config) -> TenderGraphStateBase:
    """
    根据前后锚点定位，提取文档中的参数内容。

    从 state 中读取：
    - insertion_before_text: 插入位置的前置文本
    - insertion_after_text: 插入位置的后置文本
    - clean_draft_path: 清洁稿文档路径（优先使用）
    - origin_tender_path: 送审稿文档路径（备选）
    - tender_type: 招标类型（'xjcg' 或 'gngk'）
    - tender_param_paths: 技术参数文件路径列表（可选）

    提取的内容存储到：
    - origin_tender_params: 从文档提取的原始内容
    - tender_params: 从技术参数文件提取的内容（如有）
    - start_page: 提取内容起始页码
    - end_page: 提取内容结束页码
    """
    start_time = time.time()
    print(f"[extract_tender_params] 开始执行...")

    # 获取输入参数
    clean_draft_path = state.get("clean_draft_path")
    origin_tender_path = state.get("origin_tender_path")
    before_text = state.get("insertion_before_text")
    after_text = state.get("insertion_after_text")
    tender_type = state.get("tender_type", "xjcg")

    # 确定提取源路径
    extract_source_path = clean_draft_path or origin_tender_path
    if not extract_source_path or (
        isinstance(extract_source_path, str) and extract_source_path.strip() == ""
    ):
        raise ValueError(
            "需要 clean_draft_path（清洁稿）或 origin_tender_path（送审稿）来提取文档中的内容"
        )

    # 如果没有提供前后文本，返回空内容
    if not before_text or not after_text:
        print(
            f"[extract_tender_params] 警告: 未提供 insertion_before_text 或 insertion_after_text，跳过提取"
        )
        return TenderGraphStateBase(
            origin_tender_params="",
            tender_params="",
        )

    # 确保路径是绝对路径
    if not os.path.isabs(extract_source_path):
        extract_source_path = os.path.abspath(extract_source_path)

    # 检查文件是否存在
    if not os.path.exists(extract_source_path):
        raise FileNotFoundError(f"未找到待提取文档: {extract_source_path}")

    # 检查文件是否可读
    if not os.access(extract_source_path, os.R_OK):
        raise PermissionError(f"无法读取待提取文档: {extract_source_path}")

    # 根据招标类型获取目标字体大小
    target_size = TARGET_SIZES.get(tender_type, 18.0)
    print(f"[extract_tender_params] 招标类型: {tender_type}, 目标字号: {target_size}")

    extracted_content = ""
    start_page = None
    end_page = None
    wps = None
    doc = None
    com_initialized = False

    try:
        # 使用统一的工具函数创建 Word 应用程序
        wps, com_initialized = create_word_application(
            initial_delay=0.5,
            post_init_delay=0.5,
            use_existing=False,  # 并发环境下必须使用独立实例
            verify=True,
            node_name="extract_tender_params",
        )

        # 使用统一的工具函数打开文档（带重试机制）
        doc = open_document_with_retry(
            word_app=wps,
            file_path=extract_source_path,
            read_only=True,
            node_name="extract_tender_params",
        )

        # 使用统一的工具函数取消文档保护
        unprotect_document(doc, node_name="extract_tender_params")

        # === 使用统一的双策略查找锚点 ===
        print(f"[extract_tender_params] 正在查找锚点...")
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
            print(f"[extract_tender_params] 警告: 未找到前置文本 '{before_text}'")
            extracted_content = ""
        elif not after_hit:
            print(f"[extract_tender_params] 警告: 未找到后置文本 '{after_text}'")
            extracted_content = ""
        else:
            before_page = before_hit["page"]
            before_end_pos = before_hit["end"]
            after_page = after_hit["page"]
            after_start_pos = after_hit["start"]

            print(
                f"[extract_tender_params] 前置锚点: 页={before_page}, end={before_end_pos}, 字体={before_hit['font']}, 字号={before_hit['size']}"
            )
            print(
                f"[extract_tender_params] 后置锚点: 页={after_page}, start={after_start_pos}, 字体={after_hit['font']}, 字号={after_hit['size']}"
            )

            if after_page <= before_page:
                print(
                    f"[extract_tender_params] 错误: 后置文本页码 ({after_page}) 小于等于前置文本页码 ({before_page})"
                )
                extracted_content = ""
            else:
                # 将 before_end_pos 对齐到下一页起始
                try:
                    selection = wps.Selection
                    selection.GoTo(wdGoToPage, wdGoToAbsolute, before_page + 1)
                    next_page_start = selection.Start
                    if next_page_start > before_end_pos:
                        before_end_pos = next_page_start
                        print(
                            f"[extract_tender_params] 将 before_end_pos 对齐到下一页起始: {before_end_pos}"
                        )
                except Exception as adj_e:
                    print(
                        f"[extract_tender_params] 警告: 无法对齐 before_end_pos 到下一页起始: {adj_e}"
                    )

                # 提取两个锚点之间的内容
                between_rng = doc.Range(before_end_pos, after_start_pos)
                extracted_content = extract_content_with_tables(between_rng)

                # 统计提取结果
                total_chars = len(extracted_content)
                non_whitespace_chars = len(
                    [c for c in extracted_content if not c.isspace()]
                )
                line_count = len(extracted_content.splitlines())
                table_count = len(list(between_rng.Tables))

                print(
                    f"[extract_tender_params] 成功提取内容，总长度: {total_chars} 字符，非空白: {non_whitespace_chars} 字符，行数: {line_count}，表格: {table_count} 个"
                )

                # 记录页码范围
                start_page = before_page + 1
                end_page = after_page - 1
                print(f"[extract_tender_params] 页码范围: {start_page} - {end_page}")

    except Exception as e:
        error_msg = f"提取内容时发生错误: {e}"
        print(f"[extract_tender_params] {error_msg}")
        import traceback

        traceback.print_exc()
        raise RuntimeError(error_msg) from e

    finally:
        print("[extract_tender_params] 开始清理资源...")
        close_word_application(
            word_app=wps,
            doc=doc,
            com_initialized=com_initialized,
            wait_time=1.0,
            node_name="extract_tender_params",
        )

    # 构建更新字典
    updates: Dict[str, Any] = {
        "origin_tender_params": extracted_content,
    }

    # 保存页码范围（仅在成功计算时写入）
    if start_page is not None:
        updates["start_page"] = start_page
    if end_page is not None:
        updates["end_page"] = end_page

    # 处理技术参数文件
    tender_param_paths = state.get("tender_param_paths")
    if tender_param_paths and not isinstance(tender_param_paths, (list, tuple)):
        tender_param_paths = [tender_param_paths]

    if tender_param_paths:
        print(f"[extract_tender_params] 检测到技术参数文件，开始提取...")
        tender_params_parts: List[str] = []

        for tender_param_file_path in tender_param_paths:
            if not tender_param_file_path:
                continue

            file_path_obj = pathlib.Path(str(tender_param_file_path))
            if not file_path_obj.exists():
                raise ValueError(f"技术参数文件不存在: {file_path_obj}")
            if not file_path_obj.is_file():
                raise ValueError(f"技术参数路径不是文件: {file_path_obj}")

            file_text = extract_text_from_word_file(str(file_path_obj))
            print(
                f"[extract_tender_params] 从文件提取完成: {file_path_obj.name}，长度: {len(file_text)}"
            )
            tender_params_parts.append(file_text)

        tender_params = "\n\n".join([p for p in tender_params_parts if p]).strip()
        updates["tender_params"] = tender_params

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"[extract_tender_params] 执行完成，耗时: {elapsed_time:.2f} 秒")

    # 返回 TypedDict 实例
    return TenderGraphStateBase(**updates)


if __name__ == "__main__":
    """
    测试模块：测试统一提取功能
    """
    import pathlib
    import sys

    ROOT = pathlib.Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    # 测试文档路径
    test_doc_paths = [
        ("test_word/251534-招标文件-清洁稿.doc", "gngk"),
        # ("TenderFile/252699-询价文件.doc", "xjcg"),
    ]

    for doc_idx, (test_doc_path_str, tender_type) in enumerate(test_doc_paths, 1):
        test_doc_path = (ROOT / test_doc_path_str).resolve()

        print("\n" + "=" * 80)
        print(f"测试 {doc_idx}/{len(test_doc_paths)}: extract_tender_params (common)")
        print("=" * 80)
        print(f"测试文档: {test_doc_path}")
        print(f"招标类型: {tender_type}")
        print(f"文档存在: {test_doc_path.exists()}")
        print()

        if not test_doc_path.exists():
            print(f"警告: 文档不存在，跳过")
            continue

        if doc_idx > 1:
            print("等待之前的 Word 实例关闭...")
            time.sleep(1.0)

        # 根据类型设置锚点文本
        if tender_type == "xjcg":
            before_text = "第三章  采购需求"
            after_text = "第四章  响应文件有关格式"
        else:
            before_text = "第三章 招标内容及要求"
            after_text = "第四章 投标文件有关格式"

        test_state: TenderGraphStateBase = {
            "tender_type": tender_type,
            "clean_draft_path": str(test_doc_path),
            "insertion_before_text": before_text,
            "insertion_after_text": after_text,
        }

        try:
            result = extract_tender_params(test_state, config=None)

            content = result.get("origin_tender_params", "")
            if content:
                print(f"\n成功提取，长度: {len(content)} 字符")
                print(
                    f"页码范围: {result.get('start_page')} - {result.get('end_page')}"
                )

                # 保存到文件
                output_file = (
                    test_doc_path.parent / f"{test_doc_path.stem}_extracted_common.txt"
                )
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"已保存到: {output_file}")
            else:
                print("\n未提取到内容")

        except Exception as e:
            print(f"\n错误: {e}")
            import traceback

            traceback.print_exc()
