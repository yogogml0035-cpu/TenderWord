from __future__ import annotations

from backend.retrieval.bad_case_loader import (
    DEFAULT_BAD_CASE_DIR,
    DEFAULT_COMMENT_BAD_CASE_FILE,
    build_bad_case_chunks,
    load_bad_case_chunks,
    load_bad_cases,
    parse_bad_cases,
)
from backend.retrieval.bm25 import BM25Index
from backend.retrieval.hybrid import HybridHit


def test_default_bad_case_file_uses_formal_retrieval_directory() -> None:
    assert DEFAULT_BAD_CASE_DIR.name == "bad_cases"
    assert DEFAULT_BAD_CASE_DIR.parent.name == "retrieval"
    assert DEFAULT_COMMENT_BAD_CASE_FILE == DEFAULT_BAD_CASE_DIR / "comment_bad_cases.md"


def test_loader_reads_formal_v2_main_file() -> None:
    cases = load_bad_cases()
    chunks = load_bad_case_chunks()

    assert DEFAULT_COMMENT_BAD_CASE_FILE.exists()
    assert cases[0].case_id == "TW_COMMENT_BC2_001"
    assert cases[0].fields["risk_type"] == "参数指纹"
    assert "精确小数" in cases[0].fields["risk_pattern"]
    assert cases[0].fields["recommended_comment_policy"]
    assert cases[0].fields["applicability_boundary"]
    assert cases[0].fields["anchor_policy"]
    assert chunks[0].case_id == "TW_COMMENT_BC2_001"
    assert chunks[0].metadata["risk_type"] == "参数指纹"


def test_v2_bad_cases_build_chunks_consumed_by_bm25_and_hybrid_hit() -> None:
    raw_text = """
---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_BC2_TEST
risk_layer: general_tender
risk_type: 参数指纹
risk_pattern: 异常精确小数或非整数指标
recommended_comment_policy:
  - 建议提示：确认精度是否必要。
applicability_boundary:
  - 强制标准可保留。
anchor_policy: 锚点取包含指标名称和精确数值的完整分句。
---END_BAD_CASE---
"""

    cases = parse_bad_cases(raw_text)
    chunks = build_bad_case_chunks(cases)
    bm25_index = BM25Index([chunk.text for chunk in chunks])
    bm25_hits = bm25_index.score("精确小数 指标")
    hybrid_hit = HybridHit(
        rank=1,
        chunk=chunks[bm25_hits[0].index],
        hybrid_score=1.0,
        bm25_score=bm25_hits[0].score,
        vector_score=0.0,
    )

    assert cases[0].fields["recommended_comment_policy"].startswith("- 建议提示")
    assert cases[0].fields["applicability_boundary"].startswith("- 强制标准")
    assert cases[0].fields["anchor_policy"].startswith("锚点取")
    assert bm25_hits
    assert hybrid_hit.chunk.case_id == "TW_COMMENT_BC2_TEST"
    assert hybrid_hit.chunk.metadata["risk_pattern"] == "异常精确小数或非整数指标"


def test_legacy_bad_case_parser_remains_supported() -> None:
    raw_text = """
案例编号：1 参数过窄
问题类别：合规风险
原始条款：设备重量为 12.34kg。
正确批注要点：建议确认该精度是否必要。
"""

    cases = parse_bad_cases(raw_text)
    chunks = build_bad_case_chunks(cases)

    assert cases[0].case_id == "1"
    assert cases[0].fields["问题类别"] == "合规风险"
    assert chunks[0].chunk_id == "case_01:full"
    assert chunks[0].metadata["category"] == "合规风险"
