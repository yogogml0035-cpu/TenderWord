from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.retrieval.bad_case_loader import DEFAULT_BAD_CASE_DIR  # noqa: E402
from backend.retrieval.comment_bad_case_runtime import (  # noqa: E402
    BAD_CASE_PROMPT_CONTEXT_FIELDS,
    RETRIEVAL_MODE_BM25_ONLY,
    BadCaseRetrievalHit,
    BadCaseRetrievalResult,
    retrieve_bad_case_hits,
    retrieve_bad_case_hits_bm25_only,
    split_polished_text_into_clauses,
)
from backend.retrieval.config import load_retrieval_config  # noqa: E402


SAMPLE_POLISHED_TEXT = """
第1包：团体心率变异检测仪
一、项目概述
1、设备名称及数量：团体心率变异检测仪 壹套
2、交付日期：接到医院通知后的一周内交付
3、付款方式：验收合格后2个月内支付剩余100%货款
二、技术需求
1、★设备采用无线信号采集终端
2、设备内置充电式锂电池，符合安全规定，电池容量≥1000mAh。
3、★无线信号采集终端支持双手握持检测、直连心电导联线等检测方式,方便临床快速检测。
三、售后服务及其他要求
1、投标方必须为产品制造商，或授权的销售代理商，并提供制造商授权函原件。
2、原厂免费保修不少于五年，终身免费提供软件升级维护。
3、★免费开放所提供检测设备的数字化接口，并承担接入医院信息系统所需的所有接口费用。
""".strip()


def configure_console_output() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(errors="replace")
        except Exception:
            pass


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run comment bad-case retrieval diagnostics through the formal "
            "runtime used by generate_comments and comment_agent."
        )
    )
    parser.add_argument(
        "--input-file",
        type=Path,
        default=None,
        help="Polished tender text file to query. Defaults to an inline sample.",
    )
    parser.add_argument(
        "--bad-case-dir",
        type=Path,
        default=DEFAULT_BAD_CASE_DIR,
        help="Bad-case directory. Defaults to backend/retrieval/bad_cases.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Maximum filtered hits to keep per clause.",
    )
    parser.add_argument(
        "--clause-limit",
        "--query-count",
        dest="clause_limit",
        type=int,
        default=20,
        help="Maximum number of clause_only queries to run and print.",
    )
    parser.add_argument(
        "--score-threshold",
        type=float,
        default=0.8,
        help="Minimum score for filtered hits.",
    )
    parser.add_argument("--collection", default=None, help="Qdrant collection name.")
    parser.add_argument("--qdrant-url", default=None, help="Qdrant base URL.")
    parser.add_argument(
        "--bm25-only",
        action="store_true",
        help="Force the formal BM25-only runtime path.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    configure_console_output()
    args = parse_args(argv)

    polished_text = _read_polished_text(args.input_file)
    effective_top_k = max(1, int(args.top_k))
    effective_clause_limit = max(1, int(args.clause_limit))
    limited_text = _limit_polished_text_to_clause_count(
        polished_text,
        clause_limit=effective_clause_limit,
    )

    if args.bm25_only:
        result = retrieve_bad_case_hits_bm25_only(
            limited_text,
            directory=args.bad_case_dir,
            top_k=effective_top_k,
            score_threshold=args.score_threshold,
        )
    else:
        result = retrieve_bad_case_hits(
            limited_text,
            directory=args.bad_case_dir,
            top_k=effective_top_k,
            score_threshold=args.score_threshold,
            config_loader=lambda: load_retrieval_config(
                collection_name=args.collection,
                qdrant_url=args.qdrant_url,
            ),
        )

    _print_retrieval_result(
        result,
        bad_case_dir=args.bad_case_dir,
        top_k=effective_top_k,
        score_threshold=args.score_threshold,
    )
    return 0


def _read_polished_text(input_file: Path | None) -> str:
    if input_file is None:
        return SAMPLE_POLISHED_TEXT
    return input_file.read_text(encoding="utf-8")


def _limit_polished_text_to_clause_count(
    polished_text: str,
    *,
    clause_limit: int,
) -> str:
    split_result = split_polished_text_into_clauses(polished_text)
    if len(split_result.clauses) <= clause_limit:
        return polished_text

    lines: list[str] = []
    current_package = ""
    current_section = ""
    for clause in split_result.clauses[:clause_limit]:
        if clause.package and clause.package != current_package:
            lines.append(clause.package)
            current_package = clause.package
            current_section = ""
        if clause.section and clause.section != current_section:
            lines.append(clause.section)
            current_section = clause.section
        lines.append(clause.text)
    return "\n".join(lines)


def _print_retrieval_result(
    result: BadCaseRetrievalResult,
    *,
    bad_case_dir: Path,
    top_k: int,
    score_threshold: float,
) -> None:
    payload = result.to_log_payload()

    print(f"Bad case directory: {bad_case_dir}")
    print(f"Retrieval mode: {result.retrieval_mode}")
    print(f"Clause split mode: {result.split_result.clause_split_mode}")
    print(f"Query clauses: {len(result.clause_results)}")
    print(f"Top K: {top_k}")
    print(f"Score threshold: {score_threshold:.2f}")

    load_summary = payload.get("load_summary") or {}
    if isinstance(load_summary, dict):
        print(
            "Loaded files: "
            f"{load_summary.get('successful_file_count', 0)} succeeded, "
            f"{load_summary.get('failed_file_count', 0)} failed"
        )

    source_files = payload.get("source_files") or []
    if source_files:
        print("Source files:")
        for source_file in source_files:
            if not isinstance(source_file, dict):
                continue
            print(
                "  "
                f"{source_file.get('file_name', '')} "
                f"cases={source_file.get('case_count', 0)} "
                f"chunks={source_file.get('chunk_count', 0)}"
            )

    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"  - {warning}")

    failure_summary = payload.get("failure_summary")
    if failure_summary:
        print(f"Failure summary: {failure_summary}")

    for clause_result in result.clause_results:
        clause = clause_result.clause
        print("\n" + "=" * 100)
        print(f"{clause.clause_id} | Query mode: clause_only")
        if clause.package:
            print(f"Package: {clause.package}")
        if clause.section:
            print(f"Section: {clause.section}")
        print(f"Title: {clause.title}")
        print(f"Query text: {_preview(clause.query_text, limit=360)}")
        print(f"Pre-filter hits: {len(clause_result.pre_filter_hits)}")
        _print_hits(
            clause_result.filtered_hits,
            retrieval_mode=result.retrieval_mode,
            score_threshold=score_threshold,
        )

    injected_bad_cases = payload.get("injected_bad_cases") or []
    print("\n" + "=" * 100)
    print(f"Injected bad cases: {len(injected_bad_cases)}")
    for item in injected_bad_cases:
        if not isinstance(item, dict):
            continue
        summary = " | ".join(
            str(item.get(field, "") or "")
            for field in BAD_CASE_PROMPT_CONTEXT_FIELDS[:3]
            if item.get(field)
        )
        print(
            "  "
            f"#{item.get('injection_rank')} "
            f"case_id={item.get('case_id')} "
            f"score={float(item.get('score', 0.0)):.4f} "
            f"{summary}"
        )


def _print_hits(
    hits: list[BadCaseRetrievalHit],
    *,
    retrieval_mode: str,
    score_threshold: float,
) -> None:
    if not hits:
        print(f"Filtered hits: none (score <= {score_threshold:.2f})")
        return

    label = "BM25" if retrieval_mode == RETRIEVAL_MODE_BM25_ONLY else "Hybrid"
    print(f"Filtered {label} hits:")
    for hit in hits:
        print(
            f"  #{hit.rank} score={hit.score:.4f} "
            f"bm25={hit.bm25_score:.4f} vector={hit.vector_score:.4f} "
            f"id={hit.case_id} field={hit.chunk.field}"
        )
        print(
            f"     type={hit.chunk.metadata.get('risk_type', '')} "
            f"pattern={_preview(hit.chunk.metadata.get('risk_pattern', ''), limit=120)}"
        )
        print(f"     {_preview(hit.chunk.text, limit=220)}")


def _preview(text: str, limit: int = 220) -> str:
    compact = " ".join(line.strip() for line in text.splitlines() if line.strip())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


if __name__ == "__main__":
    raise SystemExit(main())
