from __future__ import annotations

import pathlib
import re
import sys
from typing import List, Optional

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.nodes.common_word_nodes.get_replacements_core import (
    ExtractorSpec,
    ReplacementFieldSpec,
    run_get_replacements,
)
from backend.nodes.common_word_nodes.get_replacements_shared import (
    build_common_replacement_fields,
    extract_public_tender_buyer_name,
    extract_public_tender_bzj_rule,
    extract_public_tender_contact_fields,
    extract_public_tender_project_content,
    extract_project_name,
    extract_project_number_from_bid_header,
    extract_public_tender_platform,
    extract_service_fee,
    extract_shell_dates,
    extract_submit_date,
)
from backend.states import GngkTenderGraphState


def extract_project_content_v1(
    doc_content: str, state: GngkTenderGraphState, log_parts: List[str]
) -> Optional[str]:
    """从正文中提取 project_content（v1）"""
    if not doc_content:
        return None
    if not state.get("project_content") and not state.get("project_content_v1"):
        return None

    chapter_match = re.search(r"第二章\s*投标人须知", doc_content)
    if not chapter_match:
        log_parts.append("未找到起始章节标记「第二章 投标人须知」")
        return None
    chapter_pos = chapter_match.start()
    log_parts.append(f"在位置 {chapter_pos} 找到章节标记「第二章 投标人须知」")

    search_after_chapter = chapter_match.end()
    project_name_marker = re.compile(r"项目名称\s*[：:]")
    match_pn = project_name_marker.search(doc_content[search_after_chapter:])
    if not match_pn:
        log_parts.append("在章节之后未找到「项目名称：」")
        return None

    pn_pos = search_after_chapter + match_pn.start()
    log_parts.append(f"在位置 {pn_pos} 找到「项目名称：」")

    pn_line_start = pn_pos
    while pn_line_start > 0 and doc_content[pn_line_start - 1] not in ("\n", "\r"):
        pn_line_start -= 1
    pn_line_end = pn_pos
    while pn_line_end < len(doc_content) and doc_content[pn_line_end] not in (
        "\n",
        "\r",
    ):
        pn_line_end += 1
    while pn_line_end < len(doc_content) and doc_content[pn_line_end] in ("\n", "\r"):
        pn_line_end += 1
    content_start = pn_line_end
    log_parts.append(f"「项目名称：」下一段起始位置: {content_start}")

    device_marker = re.compile(r"设备名称及数量\s*[：:]")
    match_device = device_marker.search(doc_content[content_start:])
    if not match_device:
        log_parts.append("在内容起始之后未找到「设备名称及数量：」")
        return None

    device_pos = content_start + match_device.start()
    log_parts.append(f"在位置 {device_pos} 找到「设备名称及数量：」")

    candidates = []
    for ch in ("\x07", "\r", "\n"):
        idx = doc_content.find(ch, device_pos)
        if idx != -1:
            candidates.append(idx)
    end_pos = min(candidates) if candidates else len(doc_content)

    raw_extracted = doc_content[device_pos:end_pos]
    extracted_content = raw_extracted.replace("\x07", "").strip()

    if extracted_content:
        log_parts.append(
            f"成功提取 project_content_v1，长度: {len(extracted_content)} 字符"
        )
        log_parts.append(f"提取内容: {repr(extracted_content)}")
        return extracted_content
    log_parts.append("提取区间为空")
    return None


def extract_similar_project_performance_date(
    doc_content: str, state: GngkTenderGraphState, log_parts: List[str]
) -> Optional[str]:
    del state
    if not doc_content:
        return None

    marker = "2、类似项目业绩"
    marker_pos = doc_content.find(marker)
    if marker_pos == -1:
        log_parts.append("未找到标记 '2、类似项目业绩'")
        return None

    next_item_pos = doc_content.find("3、", marker_pos + len(marker))
    search_end = (
        next_item_pos
        if next_item_pos != -1
        else min(len(doc_content), marker_pos + 8000)
    )
    search_range = doc_content[marker_pos:search_end]

    pattern = r"(自\d{4}年\d{1,2}月\d{1,2}日至今)"
    match = re.search(pattern, search_range)
    if match:
        extracted = match.group(1).strip()
        log_parts.append(f"在“2、类似项目业绩”条目中提取日期: {extracted}")
        return extracted

    log_parts.append(
        "在“2、类似项目业绩”条目范围内未找到日期模式 '自xxxx年xx月xx日至今'"
    )
    return None


GNGK_EXTRACTORS: List[ExtractorSpec] = [
    ExtractorSpec(
        name="project_content",
        enabled_if=lambda state: state.get("project_content") is not None,
        extract_callable=extract_public_tender_project_content,
    ),
    ExtractorSpec(
        name="project_content_v1",
        enabled_if=lambda state: state.get("project_content") is not None
        or state.get("project_content_v1") is not None,
        extract_callable=extract_project_content_v1,
    ),
    ExtractorSpec(
        name="project_number",
        enabled_if=lambda state: state.get("project_number") is not None,
        extract_callable=extract_project_number_from_bid_header,
    ),
    ExtractorSpec(
        name="project_name",
        enabled_if=lambda state: state.get("project_name") is not None,
        extract_callable=extract_project_name,
    ),
    ExtractorSpec(
        name="bzj_rule",
        enabled_if=lambda state: state.get("bzj_rule") is not None,
        extract_callable=extract_public_tender_bzj_rule,
    ),
    ExtractorSpec(
        name="buyer_name",
        enabled_if=lambda state: state.get("buyer_name") is not None,
        extract_callable=extract_public_tender_buyer_name,
    ),
    ExtractorSpec(
        name="contact_fields",
        enabled_if=lambda state: any(
            [
                state.get("project_zbr_xbr"),
                state.get("zbr_xbr_tel"),
                state.get("zbr_pinyin"),
            ]
        ),
        extract_callable=extract_public_tender_contact_fields,
        output_field_names=["project_zbr_xbr", "zbr_xbr_tel", "zbr_pinyin"],
    ),
    ExtractorSpec(
        name="shell_dates",
        enabled_if=lambda state: state.get("shell_start_date") is not None
        or state.get("shell_end_date") is not None,
        extract_callable=extract_shell_dates,
        output_field_names=["shell_start_date", "shell_end_date"],
    ),
    ExtractorSpec(
        name="submit_date",
        enabled_if=lambda state: state.get("submit_date") is not None,
        extract_callable=extract_submit_date,
    ),
    ExtractorSpec(
        name="platform",
        enabled_if=lambda state: state.get("platform") is not None,
        extract_callable=extract_public_tender_platform,
    ),
    ExtractorSpec(
        name="service_fee",
        enabled_if=lambda state: state.get("service_fee") is not None,
        extract_callable=extract_service_fee,
    ),
    ExtractorSpec(
        name="similar_project_performance_date",
        enabled_if=lambda state: state.get("similar_project_performance_date")
        is not None,
        extract_callable=extract_similar_project_performance_date,
    ),
]


_GNGK_BASE_REPLACEMENT_FIELDS = build_common_replacement_fields()
GNGK_REPLACEMENT_FIELDS: List[ReplacementFieldSpec] = [
    _GNGK_BASE_REPLACEMENT_FIELDS[0],
    ReplacementFieldSpec(
        field_name="project_content_v1",
        skip_if_equal=True,
        fallback_fields=["project_content"],
    ),
    *_GNGK_BASE_REPLACEMENT_FIELDS[1:],
    ReplacementFieldSpec(field_name="similar_project_performance_date"),
]


def gngk_get_replacements(
    state: GngkTenderGraphState, config
) -> GngkTenderGraphState:
    """Thin wrapper around the shared get_replacements core."""
    return run_get_replacements(
        state=state,
        config=config,
        extractors=GNGK_EXTRACTORS,
        replacement_fields=GNGK_REPLACEMENT_FIELDS,
    )


if __name__ == "__main__":
    import pathlib
    import sys

    ROOT = pathlib.Path(__file__).resolve().parents[3]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from backend.states import GngkTenderGraphState

    test_doc_paths = [
        "backend\\test_doc\\东松-眼科激光治疗仪260070-招标文件-初稿1 - 审2.doc",
    ]

    for doc_idx, test_doc_path_str in enumerate(test_doc_paths, 1):
        test_doc_path = (ROOT / test_doc_path_str).resolve()

        print("\n" + "=" * 80)
        print(f"测试 {doc_idx}/{len(test_doc_paths)}: get_replacements 节点")
        print("=" * 80)
        print(f"测试文档路径: {test_doc_path}")
        print(f"文档是否存在: {test_doc_path.exists()}")
        print()

        if not test_doc_path.exists():
            print(f"警告: 文档不存在: {test_doc_path}，跳过此文件")
            print()
            continue

        test_state: GngkTenderGraphState = {
            "prepared_doc_path": str(test_doc_path),
            "project_number": "253505",
            "project_name": "细胞电转仪",
            "project_content": "项目名称及数量：细胞电转仪   壹套",
            "project_content_v1": "设备名称及数量：细胞电转仪/壹套",
            "bzj_rule": "项目预算的2%",
            "buyer_name": "复旦大学附属中山医院",
            "project_zbr_xbr": "徐旭东、任彧晟",
            "zbr_xbr_tel": "8605、8625",
            "zbr_pinyin": "xuxudong",
            "shell_start_date": "2025年12月12日",
            "shell_end_date": "2025年12月15日",
            "submit_date": "2025年12月12日11:00",
            "platform": "中国采购与招标网（https://www.chinabidding.cn/）",
            "service_fee": "百分之壹伍（1.5%）",
            "similar_project_performance_date": "自2022年09月01日至今",
        }

        try:
            result_state = gngk_get_replacements(test_state, config=None)

            placeholder_mapping = result_state.get("placeholder_mapping", {})
            if placeholder_mapping:
                print(f"\n找到 {len(placeholder_mapping)} 个占位符:\n")
                for field_name, placeholder_value in placeholder_mapping.items():
                    print(f"{field_name}: {repr(placeholder_value)}")
                    print()
            else:
                print("\n未找到任何占位符")

        except Exception as e:
            print(f"\n错误: {e}")
            import traceback

            traceback.print_exc()
            print("\n继续测试下一个文件...\n")
            continue
