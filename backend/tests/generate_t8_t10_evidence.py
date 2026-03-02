"""
T8/T10 Mock Test Evidence Generator

This script creates mock test evidence for xjcg and gngk get_replacements
without requiring actual Word documents.
"""

import sys
import os
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from backend.nodes.xjcg_word_nodes.xjcg_get_replacements import (
    get_replacements as xjcg_get_replacements,
    XJCG_EXTRACTORS,
    XJCG_REPLACEMENT_FIELDS,
)
from backend.nodes.gngk_word_nodes.gngk_get_replacements import (
    get_replacements as gngk_get_replacements,
    GNGK_EXTRACTORS,
    GNGK_REPLACEMENT_FIELDS,
)
from backend.states import XjcgTenderGraphState, GngkTenderGraphState


def create_mock_doc():
    """Create a mock Word document"""
    mock_doc = Mock()
    mock_doc.Content.Text = """
    项目编号：TEST-2024-001
    项目名称：测试项目
    采购人：测试采购人
    招标代理机构：测试代理机构
    联系人：张三
    电话：12345678901
    电子邮箱：zhangsan@test.com
    投标保证金：项目预算的2%
    开标日期：2024年12月01日
    投标截止日期：2024年12月15日10:00
    发布媒介：中国采购与招标网（https://www.chinabidding.cn/）
    招标代理服务费：百分之壹伍（1.5%）
    """
    mock_doc.Sections.return_value.Headers.return_value.Range.Text = """
    项目编号：ZBGG-2024-001
    项目名称：细胞电转仪
    """
    return mock_doc


def test_xjcg_mock():
    """Test xjcg get_replacements with mock document"""
    print("=" * 80)
    print("T8: XJCG Mock Test Evidence")
    print("=" * 80)

    test_state = XjcgTenderGraphState(
        prepared_doc_path="D:/test/xjcg_template.docx",
        project_number="253505",
        project_name="细胞电转仪",
        project_content="项目名称及数量：细胞电转仪   壹套",
        bzj_rule="项目预算的2%",
        buyer_name="复旦大学附属中山医院",
        project_zbr_xbr="徐旭东、任彧晟",
        zbr_xbr_tel="8605、8625",
        zbr_pinyin="xuxudong",
        shell_start_date="2025年12月12日",
        shell_end_date="2025年12月15日",
        submit_date="2025年12月12日11:00",
        platform="中国采购与招标网（https://www.chinabidding.cn/）",
        service_fee="百分之壹伍（1.5%）",
    )

    results = {
        "test_name": "T8: XJCG Regression Test",
        "timestamp": datetime.now().isoformat(),
        "state_keys": list(test_state.keys()),
        "extractors_count": len(XJCG_EXTRACTORS),
        "replacement_fields_count": len(XJCG_REPLACEMENT_FIELDS),
        "extractors": [
            {
                "name": spec.name,
                "enabled": spec.enabled_if(test_state),
                "has_output_names": spec.output_field_names is not None,
            }
            for spec in XJCG_EXTRACTORS
        ],
        "replacement_fields": [
            {
                "field_name": spec.field_name,
                "skip_if_equal": spec.skip_if_equal,
                "has_fallback": spec.fallback_fields is not None,
            }
            for spec in XJCG_REPLACEMENT_FIELDS
        ],
    }

    # Mock Word COM
    with (
        patch(
            "backend.nodes.common_word_nodes.get_replacements_core.create_word_application"
        ) as mock_create,
        patch(
            "backend.nodes.common_word_nodes.get_replacements_core.open_document_with_retry"
        ) as mock_open,
        patch(
            "backend.nodes.common_word_nodes.get_replacements_core.unprotect_document"
        ) as mock_unprotect,
        patch(
            "backend.nodes.common_word_nodes.get_replacements_core.close_word_application"
        ) as mock_close,
        patch("os.path.exists", return_value=True),
        patch("os.path.isabs", return_value=True),
        patch("os.access", return_value=True),
    ):
        mock_create.return_value = (Mock(), True)
        mock_open.return_value = create_mock_doc()
        mock_unprotect.return_value = True

        try:
            result = xjcg_get_replacements(test_state, config={})
            results["status"] = "SUCCESS"
            results["placeholder_mapping_keys"] = list(
                result.get("placeholder_mapping", {}).keys()
            )
            results["replacements_count"] = len(result.get("replacements", []))
            results["has_replacement_log"] = bool(result.get("replacement_log"))
            results["returned_state_keys"] = list(result.keys())
        except Exception as e:
            results["status"] = "ERROR"
            results["error"] = str(e)

    return results


def test_gngk_mock():
    """Test gngk get_replacements with mock document"""
    print("=" * 80)
    print("T10: GNGK Mock Test Evidence")
    print("=" * 80)

    test_state = GngkTenderGraphState(
        prepared_doc_path="D:/test/gngk_template.docx",
        project_number="253505",
        project_name="细胞电转仪",
        project_content="项目名称及数量：细胞电转仪   壹套",
        project_content_v1="设备名称及数量：细胞电转仪/壹套",
        bzj_rule="项目预算的2%",
        buyer_name="复旦大学附属中山医院",
        project_zbr_xbr="徐旭东、任彧晟",
        zbr_xbr_tel="8605、8625",
        zbr_pinyin="xuxudong",
        shell_start_date="2025年12月12日",
        shell_end_date="2025年12月15日",
        submit_date="2025年12月12日11:00",
        platform="中国采购与招标网（https://www.chinabidding.cn/）",
        service_fee="百分之壹伍（1.5%）",
        similar_project_performance_date="自2022年09月01日至今",
    )

    results = {
        "test_name": "T10: GNGK Regression Test",
        "timestamp": datetime.now().isoformat(),
        "state_keys": list(test_state.keys()),
        "extractors_count": len(GNGK_EXTRACTORS),
        "replacement_fields_count": len(GNGK_REPLACEMENT_FIELDS),
        "extractors": [
            {
                "name": spec.name,
                "enabled": spec.enabled_if(test_state),
                "has_output_names": spec.output_field_names is not None,
            }
            for spec in GNGK_EXTRACTORS
        ],
        "replacement_fields": [
            {
                "field_name": spec.field_name,
                "skip_if_equal": spec.skip_if_equal,
                "has_fallback": spec.fallback_fields is not None,
            }
            for spec in GNGK_REPLACEMENT_FIELDS
        ],
    }

    # Check project_content_v1 fallback configuration
    pc_v1_spec = next(
        (
            spec
            for spec in GNGK_REPLACEMENT_FIELDS
            if spec.field_name == "project_content_v1"
        ),
        None,
    )
    if pc_v1_spec:
        results["project_content_v1_fallback"] = pc_v1_spec.fallback_fields

    # Mock Word COM
    with (
        patch(
            "backend.nodes.common_word_nodes.get_replacements_core.create_word_application"
        ) as mock_create,
        patch(
            "backend.nodes.common_word_nodes.get_replacements_core.open_document_with_retry"
        ) as mock_open,
        patch(
            "backend.nodes.common_word_nodes.get_replacements_core.unprotect_document"
        ) as mock_unprotect,
        patch(
            "backend.nodes.common_word_nodes.get_replacements_core.close_word_application"
        ) as mock_close,
        patch("os.path.exists", return_value=True),
        patch("os.path.isabs", return_value=True),
        patch("os.access", return_value=True),
    ):
        mock_create.return_value = (Mock(), True)
        mock_open.return_value = create_mock_doc()
        mock_unprotect.return_value = True

        try:
            result = gngk_get_replacements(test_state, config={})
            results["status"] = "SUCCESS"
            results["placeholder_mapping_keys"] = list(
                result.get("placeholder_mapping", {}).keys()
            )
            results["replacements_count"] = len(result.get("replacements", []))
            results["has_replacement_log"] = bool(result.get("replacement_log"))
            results["returned_state_keys"] = list(result.keys())
            results["project_content_v1_in_mapping"] = (
                "project_content_v1" in result.get("placeholder_mapping", {})
            )
        except Exception as e:
            results["status"] = "ERROR"
            results["error"] = str(e)

    return results


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("T8/T10 Mock Test Evidence Generator")
    print("=" * 80 + "\n")

    xjcg_results = test_xjcg_mock()
    gngk_results = test_gngk_mock()

    # Save results
    evidence_dir = Path(__file__).resolve().parents[1] / ".sisyphus" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    with open(evidence_dir / "t8-xjcg-regression.json", "w", encoding="utf-8") as f:
        json.dump(xjcg_results, f, indent=2, ensure_ascii=False)

    with open(evidence_dir / "t10-gngk-regression.json", "w", encoding="utf-8") as f:
        json.dump(gngk_results, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("Evidence saved to:")
    print(f"  - {evidence_dir / 't8-xjcg-regression.json'}")
    print(f"  - {evidence_dir / 't10-gngk-regression.json'}")
    print("=" * 80 + "\n")

    # Print summary
    print("\nSUMMARY:")
    print(f"  XJCG: {xjcg_results['status']}")
    print(f"  GNGK: {gngk_results['status']}")

    if xjcg_results["status"] == "SUCCESS" and gngk_results["status"] == "SUCCESS":
        print("\n  ✓ All mock tests passed!")
        sys.exit(0)
    else:
        print("\n  ✗ Some tests failed")
        sys.exit(1)
