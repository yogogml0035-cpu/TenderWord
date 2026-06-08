from __future__ import annotations

import logging
from pathlib import Path

from backend.retrieval.bad_case_loader import (
    BAD_CASE_CONTEXT_AVAILABLE,
    BAD_CASE_CONTEXT_UNAVAILABLE,
    DEFAULT_BAD_CASE_DIR,
    DEFAULT_COMMENT_BAD_CASE_FILE,
    build_bad_case_chunks,
    load_bad_case_directory,
    load_bad_case_chunks,
    load_bad_cases,
    parse_bad_cases,
)
from backend.retrieval.bm25 import BM25Index
from backend.retrieval.comment_bad_case_runtime import (
    CLAUSE_SPLIT_MODE_CLAUSE_ONLY,
    CLAUSE_SPLIT_MODE_FALLBACK_FULL_TEXT,
    build_clause_only_query,
    clear_bad_case_runtime_cache,
    load_bad_case_runtime_index,
    split_polished_text_into_clauses,
)
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


def test_directory_loader_scans_markdown_files_by_file_name(tmp_path: Path) -> None:
    _write_v2_bad_case(tmp_path, "b.md", "TW_COMMENT_B", "B 风险")
    _write_v2_bad_case(tmp_path, "a.md", "TW_COMMENT_A", "A 风险")

    result = load_bad_case_directory(tmp_path)
    chunks = load_bad_case_chunks(tmp_path)

    assert result.available is True
    assert result.bad_case_context_status == BAD_CASE_CONTEXT_AVAILABLE
    assert [source.file_name for source in result.source_files] == ["a.md", "b.md"]
    assert [case.case_id for case in result.cases] == ["TW_COMMENT_A", "TW_COMMENT_B"]
    assert chunks[0].case_id == "TW_COMMENT_A"


def test_directory_loader_skips_bad_files_and_records_log_payload(
    tmp_path: Path,
    caplog,
) -> None:
    _write_v2_bad_case(tmp_path, "good.md", "TW_COMMENT_GOOD", "正常风险")
    (tmp_path / "broken.md").write_text(
        "---BEGIN_BAD_CASE---\nnot a parseable bad case\n",
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING, logger="backend.retrieval.bad_case_loader"):
        result = load_bad_case_directory(tmp_path)

    payload = result.to_log_payload()

    assert result.available is True
    assert [source.file_name for source in result.source_files] == ["good.md"]
    assert [failure.file_name for failure in result.failed_files] == ["broken.md"]
    assert result.failed_files[0].reason == "no bad cases parsed"
    assert any(
        "skipping bad case file broken.md" in item.message for item in caplog.records
    )
    assert payload["load_summary"]["successful_file_count"] == 1
    assert payload["load_summary"]["failed_file_count"] == 1
    assert payload["load_summary"]["failed_files"][0]["file_name"] == "broken.md"
    assert payload["failure_summary"] is None


def test_directory_loader_returns_unavailable_for_empty_or_all_bad_directory(
    tmp_path: Path,
) -> None:
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    empty_result = load_bad_case_directory(empty_dir)

    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    (bad_dir / "broken.md").write_text("not a bad case", encoding="utf-8")
    bad_result = load_bad_case_directory(bad_dir)
    bad_payload = bad_result.to_log_payload()

    assert empty_result.available is False
    assert empty_result.bad_case_context_status == BAD_CASE_CONTEXT_UNAVAILABLE
    assert empty_result.to_log_payload()["failure_summary"]["status"] == (
        BAD_CASE_CONTEXT_UNAVAILABLE
    )
    assert bad_result.available is False
    assert bad_result.bad_case_context_status == BAD_CASE_CONTEXT_UNAVAILABLE
    assert bad_payload["load_summary"]["successful_file_count"] == 0
    assert bad_payload["load_summary"]["failed_files"][0]["file_name"] == "broken.md"
    assert bad_payload["failure_summary"]["status"] == BAD_CASE_CONTEXT_UNAVAILABLE
    assert bad_payload["failure_summary"]["reason"] == (
        "all bad case files failed to parse"
    )


def test_bad_case_runtime_index_caches_chunks_and_bm25_index(tmp_path: Path) -> None:
    clear_bad_case_runtime_cache()
    _write_v2_bad_case(tmp_path, "case.md", "TW_COMMENT_CACHE_1", "精确小数风险")

    first = load_bad_case_runtime_index(tmp_path)
    second = load_bad_case_runtime_index(tmp_path)

    assert first is second
    assert first.chunks is second.chunks
    assert first.bm25_index is second.bm25_index
    assert first.bm25_index.score("精确小数")


def test_bad_case_runtime_index_reloads_when_file_signature_changes(
    tmp_path: Path,
) -> None:
    clear_bad_case_runtime_cache()
    case_file = tmp_path / "case.md"
    _write_v2_bad_case(tmp_path, case_file.name, "TW_COMMENT_CACHE_1", "精确小数风险")
    first = load_bad_case_runtime_index(tmp_path)

    _write_v2_bad_case(
        tmp_path,
        case_file.name,
        "TW_COMMENT_CACHE_2",
        "异常资格条件和排他性条款风险",
    )
    second = load_bad_case_runtime_index(tmp_path)

    assert second is not first
    assert second.bm25_index is not first.bm25_index
    assert second.chunks[0].case_id == "TW_COMMENT_CACHE_2"
    assert second.bm25_index.score("排他性条款")


def test_bad_case_runtime_index_does_not_create_disk_cache_files(
    tmp_path: Path,
) -> None:
    clear_bad_case_runtime_cache()
    _write_v2_bad_case(tmp_path, "case.md", "TW_COMMENT_CACHE_1", "精确小数风险")
    before = sorted(path.name for path in tmp_path.iterdir())

    runtime_index = load_bad_case_runtime_index(tmp_path)
    runtime_index.bm25_index.score("第一篇正文")
    runtime_index.bm25_index.score("第二篇正文")
    load_bad_case_runtime_index(tmp_path)

    after = sorted(path.name for path in tmp_path.iterdir())
    assert after == before


def test_split_polished_text_uses_clause_only_package_section_rules() -> None:
    polished_text = """
第1包：心率设备
一、项目概述
1、设备名称及数量：心率设备 壹套
续行内容保留在同一条款。
2、交付日期：接到通知后一周内交付
二、技术需求
1、★设备采用无线信号采集终端
第2包：肌电设备
一、项目概述
1、设备名称及数量：肌电设备 壹套
"""

    split_result = split_polished_text_into_clauses(polished_text)
    payload = split_result.to_log_payload()

    assert split_result.clause_split_mode == CLAUSE_SPLIT_MODE_CLAUSE_ONLY
    assert [clause.clause_id for clause in split_result.clauses] == [
        "clause_001",
        "clause_002",
        "clause_003",
        "clause_004",
    ]
    assert split_result.clauses[0].package == "第1包：心率设备"
    assert split_result.clauses[0].section == "一、项目概述"
    assert split_result.clauses[0].title == "1、设备名称及数量：心率设备 壹套"
    assert split_result.clauses[0].text == (
        "1、设备名称及数量：心率设备 壹套\n续行内容保留在同一条款。"
    )
    assert (
        build_clause_only_query(split_result.clauses[0])
        == split_result.clauses[0].text
    )
    assert "第1包" not in build_clause_only_query(split_result.clauses[0])
    assert split_result.clauses[2].section == "二、技术需求"
    assert split_result.clauses[3].package == "第2包：肌电设备"
    assert payload["clause_split_mode"] == CLAUSE_SPLIT_MODE_CLAUSE_ONLY


def test_split_polished_text_falls_back_to_full_text_when_no_numeric_clause() -> None:
    polished_text = """
一、项目概述
（一）供应商资格要求
1.1 具备医疗器械经营备案凭证
表格单元格：质保期不少于五年
"""

    split_result = split_polished_text_into_clauses(polished_text)
    clause = split_result.clauses[0]
    payload = split_result.to_log_payload()

    assert split_result.clause_split_mode == CLAUSE_SPLIT_MODE_FALLBACK_FULL_TEXT
    assert len(split_result.clauses) == 1
    assert clause.clause_id == "clause_001"
    assert clause.title == CLAUSE_SPLIT_MODE_FALLBACK_FULL_TEXT
    assert clause.text == polished_text.strip()
    assert build_clause_only_query(clause) == polished_text.strip()
    assert payload["clause_split_mode"] == CLAUSE_SPLIT_MODE_FALLBACK_FULL_TEXT
    assert payload["clauses"][0]["query_text"] == polished_text.strip()


def test_split_polished_text_returns_empty_fallback_for_blank_text() -> None:
    split_result = split_polished_text_into_clauses("\n  \n")

    assert split_result.clause_split_mode == CLAUSE_SPLIT_MODE_FALLBACK_FULL_TEXT
    assert split_result.clauses == []


def _write_v2_bad_case(
    directory: Path,
    file_name: str,
    case_id: str,
    risk_pattern: str,
) -> None:
    (directory / file_name).write_text(
        f"""
---BEGIN_BAD_CASE---
bad_case_id: {case_id}
risk_layer: general_tender
risk_type: 参数指纹
risk_pattern: {risk_pattern}
recommended_comment_policy:
  - 建议提示：确认该要求是否必要。
applicability_boundary:
  - 有明确标准依据时可保留。
anchor_policy: 锚点取完整分句。
---END_BAD_CASE---
""",
        encoding="utf-8",
    )
