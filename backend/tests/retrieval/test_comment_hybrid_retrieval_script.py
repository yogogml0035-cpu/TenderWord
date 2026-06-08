from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from backend.retrieval.bad_case_loader import BadCaseChunk, DEFAULT_BAD_CASE_DIR
from backend.retrieval.comment_bad_case_runtime import (
    CLAUSE_SPLIT_MODE_CLAUSE_ONLY,
    RETRIEVAL_MODE_BM25_ONLY,
    BadCaseRetrievalHit,
    BadCaseRetrievalResult,
    ClauseRetrievalResult,
    ClauseSplitResult,
    QueryClause,
)


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "test_comment_hybrid_retrieval.py"
)


def _load_script_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "test_comment_hybrid_retrieval_script_under_test",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_defaults_to_formal_bad_case_dir_and_prints_clause_only(
    monkeypatch,
    capsys,
) -> None:
    script = _load_script_module()
    calls: dict[str, object] = {}

    def fake_retrieve_bad_case_hits_bm25_only(
        polished_text: str,
        *,
        directory: Path,
        top_k: int,
        score_threshold: float,
    ) -> BadCaseRetrievalResult:
        calls["polished_text"] = polished_text
        calls["directory"] = directory
        calls["top_k"] = top_k
        calls["score_threshold"] = score_threshold
        return _build_fake_retrieval_result()

    monkeypatch.setattr(
        script,
        "retrieve_bad_case_hits_bm25_only",
        fake_retrieve_bad_case_hits_bm25_only,
    )

    exit_code = script.main(["--bm25-only", "--top-k", "3", "--clause-limit", "1"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert calls["directory"] == DEFAULT_BAD_CASE_DIR
    assert calls["top_k"] == 3
    assert calls["score_threshold"] == 0.8
    assert "backend/retrieval/bad_cases" in output.replace("\\", "/")
    assert "Clause split mode: clause_only" in output
    assert "Query mode: clause_only" in output
    assert "case_id=TW_COMMENT_BC2_SCRIPT" in output


def test_script_no_longer_keeps_experimental_core_logic() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "backend/test_doc" not in source
    assert "comments_bad_case_knowledge_essence_v2" not in source
    assert "---BEGIN_BAD_CASE---" not in source
    assert "recreate_collection" not in source
    assert "upsert_chunks" not in source


def _build_fake_retrieval_result() -> BadCaseRetrievalResult:
    clause = QueryClause(
        clause_id="clause_001",
        package="第1包：测试设备",
        section="一、技术需求",
        title="1、设备参数",
        text="1、设备参数应明确可验收。",
    )
    chunk = BadCaseChunk(
        chunk_id="TW_COMMENT_BC2_SCRIPT:risk_pattern",
        case_id="TW_COMMENT_BC2_SCRIPT",
        title="参数边界不清",
        field="risk_pattern",
        text="risk_pattern: 参数边界不清",
        metadata={
            "risk_type": "参数边界",
            "risk_pattern": "参数边界不清",
            "recommended_comment_policy": "提示补充验收口径。",
            "applicability_boundary": "适用于技术参数。",
            "anchor_policy": "锚定完整参数条款。",
        },
    )
    hit = BadCaseRetrievalHit(
        rank=1,
        chunk=chunk,
        score=0.91,
        bm25_score=3.4,
        vector_score=0.0,
        retrieval_mode=RETRIEVAL_MODE_BM25_ONLY,
    )
    return BadCaseRetrievalResult(
        split_result=ClauseSplitResult(
            clauses=[clause],
            clause_split_mode=CLAUSE_SPLIT_MODE_CLAUSE_ONLY,
        ),
        clause_results=[
            ClauseRetrievalResult(
                clause=clause,
                pre_filter_hits=[hit],
                filtered_hits=[hit],
            )
        ],
        retrieval_mode=RETRIEVAL_MODE_BM25_ONLY,
        warnings=[],
        failure_summary=None,
        source_files=[
            {
                "file_name": "comment_bad_cases.md",
                "path": str(DEFAULT_BAD_CASE_DIR / "comment_bad_cases.md"),
                "case_count": 1,
                "chunk_count": 2,
            }
        ],
        load_summary={
            "successful_file_count": 1,
            "failed_file_count": 0,
            "failed_files": [],
        },
    )
