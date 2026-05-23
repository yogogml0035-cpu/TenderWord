from __future__ import annotations

import pathlib
import sys
from typing import List

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.nodes.common_word_nodes.get_replacements_core import (
    ExtractorSpec,
    ReplacementFieldSpec,
    run_get_replacements,
)
from backend.nodes.gngk_word_nodes.gngk_get_replacements import (
    build_gngk_common_extractors,
    build_gngk_common_replacement_fields,
)
from backend.states import GngkTenderGraphState


GNGK_HW_ZC_EXTRACTORS: List[ExtractorSpec] = build_gngk_common_extractors()
GNGK_HW_ZC_REPLACEMENT_FIELDS: List[
    ReplacementFieldSpec
] = build_gngk_common_replacement_fields()
GNGK_EXTRACTORS = GNGK_HW_ZC_EXTRACTORS
GNGK_REPLACEMENT_FIELDS = GNGK_HW_ZC_REPLACEMENT_FIELDS


def gngk_hw_zc_get_replacements(
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
            "bzj_rule": "项目预算的2%",
            "buyer_name": "复旦大学附属中山医院",
            "investment": "140",
            "project_zbr_xbr": "徐旭东、任彧晟",
            "zbr_xbr_tel": "8605、8625",
            "zbr_pinyin": "xuxudong",
            "shell_start_date": "2025年12月12日",
            "shell_end_date": "2025年12月15日",
            "submit_date": "2025年12月12日11:00",
            "platform": "中国采购与招标网（https://www.chinabidding.cn/）",
            "service_fee": "百分之壹伍（1.5%）",
        }

        try:
            result_state = gngk_hw_zc_get_replacements(test_state, config=None)

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
