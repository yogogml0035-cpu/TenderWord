from __future__ import annotations

import logging
from pathlib import Path

import pytest

from backend.retrieval.bad_case_loader import (
    BAD_CASE_CONTEXT_AVAILABLE,
    BAD_CASE_CONTEXT_UNAVAILABLE,
    BadCaseChunk,
    DEFAULT_BAD_CASE_DIR,
    DEFAULT_COMMENT_BAD_CASE_FILE,
    build_bad_case_chunks,
    load_bad_case_directory,
    load_bad_case_chunks,
    load_bad_cases,
    parse_bad_cases,
)
from backend.retrieval.bm25 import BM25Hit, BM25Index
from backend.retrieval.config import RetrievalConfig
from backend.retrieval.comment_bad_case_runtime import (
    BAD_CASE_PROMPT_CONTEXT_FIELDS,
    CLAUSE_SPLIT_MODE_CLAUSE_ONLY,
    CLAUSE_SPLIT_MODE_FALLBACK_FULL_TEXT,
    DEFAULT_BAD_CASE_PROMPT_CONTEXT_LIMIT,
    RETRIEVAL_MODE_BM25_ONLY,
    RETRIEVAL_MODE_HYBRID,
    BadCaseRetrievalHit,
    BadCaseRetrievalResult,
    ClauseRetrievalResult,
    ClauseSplitResult,
    QueryClause,
    build_bad_case_prompt_context,
    build_clause_only_query,
    clear_bad_case_runtime_cache,
    load_bad_case_runtime_index,
    retrieve_bad_case_hits,
    retrieve_bad_case_hits_bm25_only,
    select_injected_bad_case_hits,
    split_polished_text_into_clauses,
)
from backend.retrieval.hybrid import HybridHit
from backend.retrieval.qdrant_store import VectorHit


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


def test_bm25_only_retrieval_uses_cached_index_and_filters_top3(
    tmp_path: Path,
    monkeypatch,
) -> None:
    clear_bad_case_runtime_cache()
    _write_v2_bad_case(tmp_path, "a.md", "TW_COMMENT_BM25_A", "心率小数精度")
    _write_v2_bad_case(tmp_path, "b.md", "TW_COMMENT_BM25_B", "心率固定档位")
    _write_v2_bad_case(tmp_path, "c.md", "TW_COMMENT_BM25_C", "心率边界符号")
    _write_v2_bad_case(tmp_path, "d.md", "TW_COMMENT_BM25_D", "心率宣传表述")
    runtime_index = load_bad_case_runtime_index(tmp_path)
    full_chunk_indexes = [
        index
        for index, chunk in enumerate(runtime_index.chunks)
        if chunk.field == "full"
    ]
    query_texts: list[str] = []

    def fake_score(query: str) -> list[BM25Hit]:
        query_texts.append(query)
        return [
            BM25Hit(index=full_chunk_indexes[0], score=10.0),
            BM25Hit(index=full_chunk_indexes[1], score=9.5),
            BM25Hit(index=full_chunk_indexes[2], score=9.0),
            BM25Hit(index=full_chunk_indexes[3], score=1.0),
        ]

    monkeypatch.setattr(runtime_index.bm25_index, "score", fake_score)

    result = retrieve_bad_case_hits_bm25_only(
        """
一、技术需求
1、心率指标应支持精确小数显示。
2、心率指标应支持固定档位。
""",
        directory=tmp_path,
    )

    assert result.retrieval_mode == RETRIEVAL_MODE_BM25_ONLY
    assert query_texts == [
        "1、心率指标应支持精确小数显示。",
        "2、心率指标应支持固定档位。",
    ]
    assert len(result.clause_results) == 2
    for clause_result in result.clause_results:
        assert len(clause_result.pre_filter_hits) == 4
        assert len(clause_result.filtered_hits) == 3
        assert [hit.rank for hit in clause_result.filtered_hits] == [1, 2, 3]
        assert [round(hit.score, 3) for hit in clause_result.filtered_hits] == [
            1.0,
            0.944,
            0.889,
        ]
        assert all(hit.score > 0.8 for hit in clause_result.filtered_hits)
        assert all(hit.vector_score == 0.0 for hit in clause_result.filtered_hits)
        assert all(
            hit.retrieval_mode == RETRIEVAL_MODE_BM25_ONLY
            for hit in clause_result.filtered_hits
        )
    assert len(result.filtered_hits) == 6
    assert result.to_log_payload()["retrieval_mode"] == RETRIEVAL_MODE_BM25_ONLY


def test_bm25_only_retrieval_returns_payload_when_directory_unavailable(
    tmp_path: Path,
) -> None:
    clear_bad_case_runtime_cache()
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    result = retrieve_bad_case_hits_bm25_only(
        "一、技术需求\n1、心率指标应支持精确小数显示。",
        directory=empty_dir,
    )
    payload = result.to_log_payload()

    assert result.retrieval_mode == RETRIEVAL_MODE_BM25_ONLY
    assert result.filtered_hits == []
    assert result.clause_results[0].filtered_hits == []
    assert payload["failure_summary"]["status"] == "bad_case_context unavailable"
    assert payload["warnings"]


def test_retrieval_log_payload_includes_sources_clauses_hits_and_injection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    clear_bad_case_runtime_cache()
    _write_v2_bad_case(tmp_path, "a.md", "TW_COMMENT_LOG_A", "心率小数精度")
    _write_v2_bad_case(tmp_path, "b.md", "TW_COMMENT_LOG_B", "心率固定档位")
    _write_v2_bad_case(tmp_path, "c.md", "TW_COMMENT_LOG_C", "心率宣传表述")
    runtime_index = load_bad_case_runtime_index(tmp_path)
    full_chunk_indexes = [
        index
        for index, chunk in enumerate(runtime_index.chunks)
        if chunk.field == "full"
    ]

    def fake_score(query: str) -> list[BM25Hit]:
        return [
            BM25Hit(index=full_chunk_indexes[0], score=10.0),
            BM25Hit(index=full_chunk_indexes[1], score=9.5),
            BM25Hit(index=full_chunk_indexes[2], score=1.0),
        ]

    monkeypatch.setattr(runtime_index.bm25_index, "score", fake_score)

    result = retrieve_bad_case_hits_bm25_only(
        """
一、技术需求
1、心率指标应支持精确小数显示。
2、心率指标应支持固定档位。
""",
        directory=tmp_path,
    )
    payload = result.to_log_payload()

    assert [source["file_name"] for source in payload["source_files"]] == [
        "a.md",
        "b.md",
        "c.md",
    ]
    assert payload["load_summary"]["successful_file_count"] == 3
    assert payload["load_summary"]["failed_file_count"] == 0
    assert payload["clause_split_summary"]["clause_split_mode"] == (
        CLAUSE_SPLIT_MODE_CLAUSE_ONLY
    )
    assert payload["retrieval_mode"] == RETRIEVAL_MODE_BM25_ONLY
    assert payload["failure_summary"] is None
    assert len(payload["clauses"]) == 2
    assert payload["clauses"][0]["clause"]["text"] == (
        "1、心率指标应支持精确小数显示。"
    )
    assert [hit["case_id"] for hit in payload["clauses"][0]["pre_filter_hits"]] == [
        "TW_COMMENT_LOG_A",
        "TW_COMMENT_LOG_B",
        "TW_COMMENT_LOG_C",
    ]
    assert [hit["case_id"] for hit in payload["clauses"][0]["filtered_hits"]] == [
        "TW_COMMENT_LOG_A",
        "TW_COMMENT_LOG_B",
    ]
    assert [
        (entry["injection_rank"], entry["case_id"], round(entry["score"], 3))
        for entry in payload["injected_bad_cases"]
    ] == [
        (1, "TW_COMMENT_LOG_A", 1.0),
        (2, "TW_COMMENT_LOG_B", 0.944),
    ]
    assert payload["injected_bad_cases"][0]["risk_type"] == "参数指纹"
    assert payload["injected_bad_cases"][0]["recommended_comment_policy"]


def test_retrieval_log_payload_is_writable_when_no_hits(tmp_path: Path) -> None:
    clear_bad_case_runtime_cache()
    _write_v2_bad_case(tmp_path, "case.md", "TW_COMMENT_NO_HIT", "心率小数精度")

    result = retrieve_bad_case_hits_bm25_only(
        "一、技术需求\n1、普通交付条款。",
        directory=tmp_path,
        score_threshold=1.1,
    )
    payload = result.to_log_payload()

    assert payload["source_files"][0]["file_name"] == "case.md"
    assert payload["failure_summary"] is None
    assert payload["clauses"][0]["clause"]["text"] == "1、普通交付条款。"
    assert payload["clauses"][0]["pre_filter_hits"] == []
    assert payload["clauses"][0]["filtered_hits"] == []
    assert payload["injected_bad_cases"] == []


def test_hybrid_retrieval_uses_embedding_and_qdrant_when_available(
    tmp_path: Path,
    monkeypatch,
) -> None:
    clear_bad_case_runtime_cache()
    _write_v2_bad_case(tmp_path, "a.md", "TW_COMMENT_HYBRID_A", "心率小数精度")
    _write_v2_bad_case(tmp_path, "b.md", "TW_COMMENT_HYBRID_B", "心率固定档位")
    _write_v2_bad_case(tmp_path, "c.md", "TW_COMMENT_HYBRID_C", "心率边界符号")
    _write_v2_bad_case(tmp_path, "d.md", "TW_COMMENT_HYBRID_D", "心率宣传表述")
    runtime_index = load_bad_case_runtime_index(tmp_path)
    full_chunk_indexes = [
        index
        for index, chunk in enumerate(runtime_index.chunks)
        if chunk.field == "full"
    ]
    query_texts: list[str] = []

    def fake_score(query: str) -> list[BM25Hit]:
        query_texts.append(query)
        return [
            BM25Hit(index=full_chunk_indexes[0], score=10.0),
            BM25Hit(index=full_chunk_indexes[1], score=9.5),
            BM25Hit(index=full_chunk_indexes[2], score=9.0),
            BM25Hit(index=full_chunk_indexes[3], score=1.0),
        ]

    monkeypatch.setattr(runtime_index.bm25_index, "score", fake_score)
    embedder = _FakeEmbeddingClient()
    store = _FakeQdrantStore(
        vector_hits=[
            VectorHit(index=full_chunk_indexes[0], score=10.0, payload={}),
            VectorHit(index=full_chunk_indexes[1], score=9.5, payload={}),
            VectorHit(index=full_chunk_indexes[2], score=9.0, payload={}),
            VectorHit(index=full_chunk_indexes[3], score=1.0, payload={}),
        ]
    )

    result = retrieve_bad_case_hits(
        """
一、技术需求
1、心率指标应支持精确小数显示。
2、心率指标应支持固定档位。
""",
        directory=tmp_path,
        config_loader=_fake_retrieval_config,
        embedding_client_factory=lambda config: embedder,
        qdrant_store_factory=lambda config: store,
    )

    assert result.retrieval_mode == RETRIEVAL_MODE_HYBRID
    assert query_texts == [
        "1、心率指标应支持精确小数显示。",
        "2、心率指标应支持固定档位。",
    ]
    assert embedder.queries == query_texts
    assert store.healthcheck_count == 1
    assert store.query_vectors == [[0.1, 0.2], [0.1, 0.2]]
    assert len(result.clause_results) == 2
    for clause_result in result.clause_results:
        assert len(clause_result.pre_filter_hits) == 4
        assert len(clause_result.filtered_hits) == 3
        assert [hit.rank for hit in clause_result.filtered_hits] == [1, 2, 3]
        assert [round(hit.score, 3) for hit in clause_result.filtered_hits] == [
            1.0,
            0.944,
            0.889,
        ]
        assert all(hit.score > 0.8 for hit in clause_result.filtered_hits)
        assert all(hit.vector_score > 0.0 for hit in clause_result.filtered_hits)
        assert all(
            hit.retrieval_mode == RETRIEVAL_MODE_HYBRID
            for hit in clause_result.filtered_hits
        )
    assert result.to_log_payload()["retrieval_mode"] == RETRIEVAL_MODE_HYBRID


@pytest.mark.parametrize(
    ("failure_kind", "expected_warning"),
    [
        ("config", "Missing embedding API key"),
        ("embedding", "embedding failed"),
        ("healthcheck", "qdrant healthcheck failed"),
        ("search", "qdrant search failed"),
    ],
)
def test_hybrid_retrieval_falls_back_to_bm25_when_vector_layer_fails(
    tmp_path: Path,
    monkeypatch,
    failure_kind: str,
    expected_warning: str,
) -> None:
    clear_bad_case_runtime_cache()
    _write_v2_bad_case(tmp_path, "case.md", "TW_COMMENT_FALLBACK", "心率小数精度")
    runtime_index = load_bad_case_runtime_index(tmp_path)
    full_chunk_index = next(
        index
        for index, chunk in enumerate(runtime_index.chunks)
        if chunk.field == "full"
    )

    def fake_score(query: str) -> list[BM25Hit]:
        return [BM25Hit(index=full_chunk_index, score=10.0)]

    def config_loader() -> RetrievalConfig:
        if failure_kind == "config":
            raise RuntimeError("Missing embedding API key. Set EMBEDDING_API_KEY.")
        return _fake_retrieval_config()

    monkeypatch.setattr(runtime_index.bm25_index, "score", fake_score)
    embedder = _FakeEmbeddingClient(
        fail_on_embed=failure_kind == "embedding"
    )
    store = _FakeQdrantStore(
        vector_hits=[VectorHit(index=full_chunk_index, score=1.0, payload={})],
        fail_on_healthcheck=failure_kind == "healthcheck",
        fail_on_search=failure_kind == "search",
    )

    result = retrieve_bad_case_hits(
        "一、技术需求\n1、心率指标应支持精确小数显示。",
        directory=tmp_path,
        config_loader=config_loader,
        embedding_client_factory=lambda config: embedder,
        qdrant_store_factory=lambda config: store,
    )

    assert result.retrieval_mode == RETRIEVAL_MODE_BM25_ONLY
    assert len(result.filtered_hits) == 1
    assert result.filtered_hits[0].vector_score == 0.0
    assert result.filtered_hits[0].retrieval_mode == RETRIEVAL_MODE_BM25_ONLY
    assert any(expected_warning in warning for warning in result.warnings)
    assert any("falling back to bm25_only" in warning for warning in result.warnings)
    assert result.to_log_payload()["retrieval_mode"] == RETRIEVAL_MODE_BM25_ONLY


def test_bad_case_prompt_context_dedupes_keeps_highest_score_and_sorts() -> None:
    first_clause = _make_query_clause(
        "clause_001",
        "clause text for first hit must not enter prompt context",
    )
    second_clause = _make_query_clause(
        "clause_002",
        "clause text for second hit must not enter prompt context",
    )
    low_score_duplicate = _make_prompt_context_hit(
        "TW_CONTEXT_A",
        0.84,
        "A lower score risk",
    )
    high_score_duplicate = _make_prompt_context_hit(
        "TW_CONTEXT_A",
        0.96,
        "A higher score risk",
    )
    highest_score = _make_prompt_context_hit(
        "TW_CONTEXT_B",
        0.98,
        "B highest score risk",
    )
    tied_score = _make_prompt_context_hit(
        "TW_CONTEXT_C",
        0.96,
        "C tied score risk",
    )
    result = _build_prompt_context_result(
        [
            (first_clause, [low_score_duplicate, highest_score]),
            (second_clause, [tied_score, high_score_duplicate]),
        ]
    )

    selected_hits = select_injected_bad_case_hits(result)
    prompt_context = build_bad_case_prompt_context(result)

    assert [(hit.case_id, hit.score) for hit in selected_hits] == [
        ("TW_CONTEXT_B", 0.98),
        ("TW_CONTEXT_A", 0.96),
        ("TW_CONTEXT_C", 0.96),
    ]
    assert [entry["risk_pattern"] for entry in prompt_context] == [
        "B highest score risk",
        "A higher score risk",
        "C tied score risk",
    ]
    assert all(
        set(entry) == set(BAD_CASE_PROMPT_CONTEXT_FIELDS)
        for entry in prompt_context
    )
    serialized_context = repr(prompt_context)
    assert "TW_CONTEXT_" not in serialized_context
    assert "0.98" not in serialized_context
    assert "clause text for" not in serialized_context
    assert "chunk_id" not in serialized_context


def test_bad_case_prompt_context_limits_to_twelve_and_tie_sorts_by_case_id() -> None:
    clause = _make_query_clause("clause_001", "matched clause body stays internal")
    hits = [
        _make_prompt_context_hit(
            f"TW_CONTEXT_{index:02d}",
            0.91,
            f"risk pattern {index:02d}",
        )
        for index in reversed(range(DEFAULT_BAD_CASE_PROMPT_CONTEXT_LIMIT + 2))
    ]
    result = _build_prompt_context_result([(clause, hits)])

    selected_hits = select_injected_bad_case_hits(result)
    prompt_context = build_bad_case_prompt_context(result)

    assert len(selected_hits) == DEFAULT_BAD_CASE_PROMPT_CONTEXT_LIMIT
    assert len(prompt_context) == DEFAULT_BAD_CASE_PROMPT_CONTEXT_LIMIT
    assert [hit.case_id for hit in selected_hits] == [
        f"TW_CONTEXT_{index:02d}"
        for index in range(DEFAULT_BAD_CASE_PROMPT_CONTEXT_LIMIT)
    ]
    assert [entry["risk_pattern"] for entry in prompt_context] == [
        f"risk pattern {index:02d}"
        for index in range(DEFAULT_BAD_CASE_PROMPT_CONTEXT_LIMIT)
    ]


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


def _make_query_clause(clause_id: str, text: str) -> QueryClause:
    return QueryClause(
        clause_id=clause_id,
        package="第1包：测试包",
        section="二、技术需求",
        title=f"{clause_id} title",
        text=text,
    )


def _make_prompt_context_hit(
    case_id: str,
    score: float,
    risk_pattern: str,
) -> BadCaseRetrievalHit:
    return BadCaseRetrievalHit(
        rank=1,
        chunk=BadCaseChunk(
            chunk_id=f"{case_id}:full",
            case_id=case_id,
            title=risk_pattern,
            field="full",
            text=f"full bad case text for {case_id}",
            metadata={
                "case_id": case_id,
                "risk_type": "参数指纹",
                "risk_pattern": risk_pattern,
                "recommended_comment_policy": "建议提示：确认该要求是否必要。",
                "applicability_boundary": "有明确标准依据时可保留。",
                "anchor_policy": "锚点取完整分句。",
                "debug_score": str(score),
            },
        ),
        score=score,
        bm25_score=score,
        vector_score=0.0,
        retrieval_mode=RETRIEVAL_MODE_BM25_ONLY,
    )


def _build_prompt_context_result(
    clause_hits: list[tuple[QueryClause, list[BadCaseRetrievalHit]]],
) -> BadCaseRetrievalResult:
    clauses = [clause for clause, _hits in clause_hits]
    return BadCaseRetrievalResult(
        split_result=ClauseSplitResult(
            clauses=clauses,
            clause_split_mode=CLAUSE_SPLIT_MODE_CLAUSE_ONLY,
        ),
        clause_results=[
            ClauseRetrievalResult(
                clause=clause,
                pre_filter_hits=hits,
                filtered_hits=hits,
            )
            for clause, hits in clause_hits
        ],
        retrieval_mode=RETRIEVAL_MODE_BM25_ONLY,
        warnings=[],
        failure_summary=None,
    )


class _FakeEmbeddingClient:
    def __init__(self, *, fail_on_embed: bool = False) -> None:
        self.fail_on_embed = fail_on_embed
        self.queries: list[str] = []

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        if self.fail_on_embed:
            raise RuntimeError("embedding failed")
        return [0.1, 0.2]


class _FakeQdrantStore:
    def __init__(
        self,
        *,
        vector_hits: list[VectorHit],
        fail_on_healthcheck: bool = False,
        fail_on_search: bool = False,
    ) -> None:
        self.vector_hits = vector_hits
        self.fail_on_healthcheck = fail_on_healthcheck
        self.fail_on_search = fail_on_search
        self.healthcheck_count = 0
        self.query_vectors: list[list[float]] = []

    def healthcheck(self) -> None:
        self.healthcheck_count += 1
        if self.fail_on_healthcheck:
            raise RuntimeError("qdrant healthcheck failed")

    def search(self, *, query_vector, limit: int = 50) -> list[VectorHit]:
        self.query_vectors.append(list(query_vector))
        if self.fail_on_search:
            raise RuntimeError("qdrant search failed")
        return self.vector_hits[:limit]


def _fake_retrieval_config() -> RetrievalConfig:
    return RetrievalConfig(
        qdrant_url="http://qdrant.test",
        qdrant_api_key=None,
        collection_name="comment_bad_cases_test",
        embedding_base_url="http://embedding.test/v1",
        embedding_api_key="placeholder",
        embedding_model="test-embedding-model",
        embedding_dimensions=None,
    )
