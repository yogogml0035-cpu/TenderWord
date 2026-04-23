from __future__ import annotations

import pathlib
import re
import sys
from typing import List, Optional

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.nodes.common_word_nodes.get_replacements_core import run_get_replacements
from backend.nodes.gngk_word_nodes.gngk_get_replacements import (
    build_gngk_common_extractors,
    build_gngk_common_replacement_fields,
)
from backend.states import GngkTenderGraphState


def _clean_project_content_line(value: str) -> str:
    return value.replace("\x07", "").strip()


def extract_gngk_fw_zc_project_content(
    doc_content: str, state: GngkTenderGraphState, log_parts: List[str]
) -> Optional[str]:
    """Extract the service project-content line, including budget text."""
    if not doc_content or not state.get("project_content"):
        return None

    start_marker = "2、项目基本信息"
    end_marker = "3、合格投标人资格条件"
    start_pos = doc_content.find(start_marker)
    if start_pos == -1:
        log_parts.append("fw_zc: 未找到起始标记 '2、项目基本信息'，尝试全文提取")
        search_start = 0
    else:
        log_parts.append(f"fw_zc: 在位置 {start_pos} 找到起始标记 '{start_marker}'")
        search_start = start_pos + len(start_marker)

    end_pos = doc_content.find(end_marker, search_start)
    if end_pos == -1:
        search_end = len(doc_content)
        if start_pos != -1:
            log_parts.append(f"fw_zc: 未找到结束标记 '{end_marker}'，使用文档尾部")
    else:
        search_end = end_pos
        log_parts.append(f"fw_zc: 在位置 {end_pos} 找到结束标记 '{end_marker}'")

    search_range = doc_content[search_start:search_end]
    match = re.search(r"项目名称\s*[：:][^\r\n\x07]+", search_range)
    if not match and search_start != 0:
        log_parts.append("fw_zc: 项目基本信息范围内未找到项目名称行，尝试全文提取")
        search_range = doc_content
        match = re.search(r"项目名称\s*[：:][^\r\n\x07]+", search_range)

    if not match:
        log_parts.append("fw_zc: 未找到可提取的项目名称整行")
        return None

    extracted = _clean_project_content_line(match.group(0))
    if extracted:
        log_parts.append(f"fw_zc: 提取 project_content 整行: {extracted}")
        return extracted

    log_parts.append("fw_zc: project_content 整行提取为空")
    return None


GNGK_FW_ZC_EXTRACTORS = build_gngk_common_extractors(
    project_content_extractor=extract_gngk_fw_zc_project_content,
)
GNGK_FW_ZC_REPLACEMENT_FIELDS = build_gngk_common_replacement_fields()


def gngk_fw_zc_get_replacements(
    state: GngkTenderGraphState, config
) -> GngkTenderGraphState:
    return run_get_replacements(
        state=state,
        config=config,
        extractors=GNGK_FW_ZC_EXTRACTORS,
        replacement_fields=GNGK_FW_ZC_REPLACEMENT_FIELDS,
    )


__all__ = [
    "GNGK_FW_ZC_EXTRACTORS",
    "GNGK_FW_ZC_REPLACEMENT_FIELDS",
    "extract_gngk_fw_zc_project_content",
    "gngk_fw_zc_get_replacements",
]


if __name__ == "__main__":
    test_doc_paths = [
        "backend/test_doc/253677-信息系统开发运维服务-招标文件-初稿1 - 审2.doc",
    ]

    for doc_idx, test_doc_path_str in enumerate(test_doc_paths, 1):
        test_doc_path = (ROOT / test_doc_path_str).resolve()

        print("\n" + "=" * 80)
        print(f"测试 {doc_idx}/{len(test_doc_paths)}: fw_zc get_replacements 节点")
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
            "project_number": "测试数字",
            "project_name": "信息系统开发运维测试",
            "project_content": "项目名称：信息系统开发运维测试          壹套（项目预算：人民币测万元）",
            "bzj_rule": "项目预算的2%",
            "buyer_name": "上海市皮肤病医院测试",
            "project_zbr_xbr": "测试、陈雯婷",
            "zbr_xbr_tel": "8611、8612",
            "zbr_pinyin": "cheshi",
            "platform": "“测试”（https://www.chinabidding.cn/）",
        }

        try:
            result_state = gngk_fw_zc_get_replacements(test_state, config=None)

            placeholder_mapping = result_state.get("placeholder_mapping", {})
            if placeholder_mapping:
                print(f"\n找到 {len(placeholder_mapping)} 个占位符:\n")
                for field_name, placeholder_value in placeholder_mapping.items():
                    print(f"{field_name}: {repr(placeholder_value)}")
                    print()
            else:
                print("\n未找到任何占位符")

            replacements = result_state.get("replacements", [])
            print(f"\n生成 {len(replacements)} 对替换:\n")
            for old_value, new_value in replacements:
                print(f"{repr(old_value)} -> {repr(new_value)}")
                print()

        except Exception as e:
            print(f"\n错误: {e}")
            import traceback

            traceback.print_exc()
            print("\n继续测试下一个文件...\n")
            continue
