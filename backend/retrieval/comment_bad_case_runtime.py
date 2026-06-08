from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock
from typing import Protocol

from backend.retrieval.bad_case_loader import (
    DEFAULT_BAD_CASE_DIR,
    BadCaseChunk,
    BadCaseDirectoryLoadResult,
    load_bad_case_directory,
)
from backend.retrieval.bm25 import BM25Index
from backend.retrieval.config import RetrievalConfig, load_retrieval_config
from backend.retrieval.hybrid import hybrid_search


_DirectorySignature = tuple[tuple[str, int, int], ...]

CLAUSE_SPLIT_MODE_CLAUSE_ONLY = "clause_only"
CLAUSE_SPLIT_MODE_FALLBACK_FULL_TEXT = "fallback_full_text"
RETRIEVAL_MODE_BM25_ONLY = "bm25_only"
RETRIEVAL_MODE_HYBRID = "hybrid"
DEFAULT_BM25_ONLY_TOP_K = 3
DEFAULT_BM25_ONLY_SCORE_THRESHOLD = 0.8
DEFAULT_HYBRID_VECTOR_LIMIT = 50

_PACKAGE_HEADING_RE = re.compile(r"^第\d+包：.*$")
_SECTION_HEADING_RE = re.compile(r"^[一二三四五六七八九十]+、.*$")
_NUMERIC_CLAUSE_RE = re.compile(r"^\d+、.*$")


class _EmbeddingClient(Protocol):
    def embed_query(self, text: str) -> list[float]:
        ...


class _QdrantStore(Protocol):
    def healthcheck(self) -> None:
        ...

    def search(self, *, query_vector: Sequence[float], limit: int = 50):
        ...


_ConfigLoader = Callable[[], RetrievalConfig]
_EmbeddingClientFactory = Callable[[RetrievalConfig], _EmbeddingClient]
_QdrantStoreFactory = Callable[[RetrievalConfig], _QdrantStore]


@dataclass(frozen=True)
class QueryClause:
    clause_id: str
    package: str
    section: str
    title: str
    text: str

    @property
    def query_text(self) -> str:
        return self.text


@dataclass(frozen=True)
class ClauseSplitResult:
    clauses: list[QueryClause]
    clause_split_mode: str

    def to_log_payload(self) -> dict[str, object]:
        return {
            "clause_split_mode": self.clause_split_mode,
            "clause_count": len(self.clauses),
            "clauses": [
                {
                    "clause_id": clause.clause_id,
                    "package": clause.package,
                    "section": clause.section,
                    "title": clause.title,
                    "text": clause.text,
                    "query_text": clause.query_text,
                }
                for clause in self.clauses
            ],
        }


@dataclass(frozen=True)
class BadCaseRetrievalHit:
    rank: int
    chunk: BadCaseChunk
    score: float
    bm25_score: float
    vector_score: float
    retrieval_mode: str

    @property
    def case_id(self) -> str:
        return self.chunk.case_id

    def to_log_payload(self) -> dict[str, object]:
        return {
            "rank": self.rank,
            "case_id": self.chunk.case_id,
            "chunk_id": self.chunk.chunk_id,
            "field": self.chunk.field,
            "score": self.score,
            "bm25_score": self.bm25_score,
            "vector_score": self.vector_score,
            "retrieval_mode": self.retrieval_mode,
            "risk_type": self.chunk.metadata.get("risk_type", ""),
            "risk_pattern": self.chunk.metadata.get("risk_pattern", ""),
        }


@dataclass(frozen=True)
class ClauseRetrievalResult:
    clause: QueryClause
    pre_filter_hits: list[BadCaseRetrievalHit]
    filtered_hits: list[BadCaseRetrievalHit]

    def to_log_payload(self) -> dict[str, object]:
        return {
            "clause": {
                "clause_id": self.clause.clause_id,
                "package": self.clause.package,
                "section": self.clause.section,
                "title": self.clause.title,
                "text": self.clause.text,
                "query_text": self.clause.query_text,
            },
            "pre_filter_hits": [
                hit.to_log_payload() for hit in self.pre_filter_hits
            ],
            "filtered_hits": [hit.to_log_payload() for hit in self.filtered_hits],
        }


@dataclass(frozen=True)
class BadCaseRetrievalResult:
    split_result: ClauseSplitResult
    clause_results: list[ClauseRetrievalResult]
    retrieval_mode: str
    warnings: list[str]
    failure_summary: dict[str, object] | None

    @property
    def filtered_hits(self) -> list[BadCaseRetrievalHit]:
        return [
            hit
            for clause_result in self.clause_results
            for hit in clause_result.filtered_hits
        ]

    def to_log_payload(self) -> dict[str, object]:
        return {
            "clause_split_summary": self.split_result.to_log_payload(),
            "retrieval_mode": self.retrieval_mode,
            "warnings": list(self.warnings),
            "failure_summary": self.failure_summary,
            "clauses": [
                clause_result.to_log_payload()
                for clause_result in self.clause_results
            ],
        }


@dataclass(frozen=True)
class BadCaseRuntimeIndex:
    load_result: BadCaseDirectoryLoadResult
    bm25_index: BM25Index

    @property
    def chunks(self) -> list[BadCaseChunk]:
        return self.load_result.chunks


@dataclass(frozen=True)
class _CachedRuntimeIndex:
    signature: _DirectorySignature
    runtime_index: BadCaseRuntimeIndex


_CACHE_LOCK = RLock()
_RUNTIME_INDEX_CACHE: dict[Path, _CachedRuntimeIndex] = {}


def load_bad_case_runtime_index(
    directory: str | Path | None = None,
) -> BadCaseRuntimeIndex:
    """Load and cache bad-case chunks plus their BM25 index for one directory.

    The cache is process-local only. It is invalidated whenever the scanned
    markdown file set changes, or any markdown file's mtime or size changes.
    """

    source_dir = Path(directory) if directory is not None else DEFAULT_BAD_CASE_DIR
    cache_key = source_dir.resolve()
    signature = _build_directory_signature(cache_key)

    with _CACHE_LOCK:
        cached = _RUNTIME_INDEX_CACHE.get(cache_key)
        if cached and cached.signature == signature:
            return cached.runtime_index

        load_result = load_bad_case_directory(cache_key)
        runtime_index = BadCaseRuntimeIndex(
            load_result=load_result,
            bm25_index=BM25Index([chunk.text for chunk in load_result.chunks]),
        )
        _RUNTIME_INDEX_CACHE[cache_key] = _CachedRuntimeIndex(
            signature=signature,
            runtime_index=runtime_index,
        )
        return runtime_index


def get_bad_case_runtime_index(
    directory: str | Path | None = None,
) -> BadCaseRuntimeIndex:
    return load_bad_case_runtime_index(directory)


def split_polished_text_into_clauses(polished_text: str) -> ClauseSplitResult:
    """Split polished tender text into clause-only retrieval queries.

    This intentionally mirrors the diagnostic script's first-pass rules:
    package headings, Chinese section headings, and numeric "、" clauses only.
    """

    package = ""
    section = ""
    current_title = ""
    current_lines: list[str] = []
    clauses: list[QueryClause] = []
    clause_count = 0

    def flush_clause() -> None:
        nonlocal current_title, current_lines, clause_count
        if not current_title or not current_lines:
            current_title = ""
            current_lines = []
            return
        clause_count += 1
        clause_text = "\n".join(current_lines).strip()
        clauses.append(
            QueryClause(
                clause_id=f"clause_{clause_count:03d}",
                package=package,
                section=section,
                title=current_title,
                text=clause_text,
            )
        )
        current_title = ""
        current_lines = []

    for raw_line in polished_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _PACKAGE_HEADING_RE.match(line):
            flush_clause()
            package = line
            section = ""
            continue
        if _SECTION_HEADING_RE.match(line):
            flush_clause()
            section = line
            continue
        if _NUMERIC_CLAUSE_RE.match(line):
            flush_clause()
            current_title = line
            current_lines = [line]
            continue
        if current_lines:
            current_lines.append(line)

    flush_clause()
    if clauses:
        return ClauseSplitResult(
            clauses=clauses,
            clause_split_mode=CLAUSE_SPLIT_MODE_CLAUSE_ONLY,
        )

    fallback_text = polished_text.strip()
    fallback_clauses = (
        [
            QueryClause(
                clause_id="clause_001",
                package="",
                section="",
                title=CLAUSE_SPLIT_MODE_FALLBACK_FULL_TEXT,
                text=fallback_text,
            )
        ]
        if fallback_text
        else []
    )
    return ClauseSplitResult(
        clauses=fallback_clauses,
        clause_split_mode=CLAUSE_SPLIT_MODE_FALLBACK_FULL_TEXT,
    )


def build_clause_only_query(clause: QueryClause) -> str:
    return clause.query_text


def retrieve_bad_case_hits_bm25_only(
    polished_text: str,
    *,
    directory: str | Path | None = None,
    top_k: int = DEFAULT_BM25_ONLY_TOP_K,
    score_threshold: float = DEFAULT_BM25_ONLY_SCORE_THRESHOLD,
) -> BadCaseRetrievalResult:
    runtime_index = load_bad_case_runtime_index(directory)
    split_result = split_polished_text_into_clauses(polished_text)
    load_payload = runtime_index.load_result.to_log_payload()

    clause_results = [
        _retrieve_clause_hits_bm25_only(
            clause=clause,
            runtime_index=runtime_index,
            top_k=max(0, top_k),
            score_threshold=score_threshold,
        )
        for clause in split_result.clauses
    ]

    return BadCaseRetrievalResult(
        split_result=split_result,
        clause_results=clause_results,
        retrieval_mode=RETRIEVAL_MODE_BM25_ONLY,
        warnings=list(runtime_index.load_result.warnings),
        failure_summary=load_payload["failure_summary"],
    )


def retrieve_bad_case_hits(
    polished_text: str,
    *,
    directory: str | Path | None = None,
    top_k: int = DEFAULT_BM25_ONLY_TOP_K,
    score_threshold: float = DEFAULT_BM25_ONLY_SCORE_THRESHOLD,
    config_loader: _ConfigLoader = load_retrieval_config,
    embedding_client_factory: _EmbeddingClientFactory | None = None,
    qdrant_store_factory: _QdrantStoreFactory | None = None,
) -> BadCaseRetrievalResult:
    runtime_index = load_bad_case_runtime_index(directory)
    if not runtime_index.chunks:
        return retrieve_bad_case_hits_bm25_only(
            polished_text,
            directory=directory,
            top_k=top_k,
            score_threshold=score_threshold,
        )

    try:
        config = config_loader()
        embedder = (
            embedding_client_factory or _create_embedding_client
        )(config)
        store = (qdrant_store_factory or _create_qdrant_store)(config)
        store.healthcheck()

        split_result = split_polished_text_into_clauses(polished_text)
        clause_results = [
            _retrieve_clause_hits_hybrid(
                clause=clause,
                runtime_index=runtime_index,
                embedder=embedder,
                store=store,
                top_k=max(0, top_k),
                score_threshold=score_threshold,
            )
            for clause in split_result.clauses
        ]
    except Exception as exc:
        return _fallback_to_bm25_only(
            polished_text=polished_text,
            directory=directory,
            top_k=top_k,
            score_threshold=score_threshold,
            warning=_format_hybrid_warning(exc),
        )

    load_payload = runtime_index.load_result.to_log_payload()
    return BadCaseRetrievalResult(
        split_result=split_result,
        clause_results=clause_results,
        retrieval_mode=RETRIEVAL_MODE_HYBRID,
        warnings=list(runtime_index.load_result.warnings),
        failure_summary=load_payload["failure_summary"],
    )


def clear_bad_case_runtime_cache() -> None:
    with _CACHE_LOCK:
        _RUNTIME_INDEX_CACHE.clear()


def _build_directory_signature(directory: Path) -> _DirectorySignature:
    if not directory.exists():
        return ((str(directory), -1, -1),)

    directory_stat = directory.stat()
    if not directory.is_dir():
        return ((str(directory), directory_stat.st_mtime_ns, directory_stat.st_size),)

    markdown_files = sorted(directory.glob("*.md"), key=lambda item: item.name)
    if not markdown_files:
        return ((str(directory), directory_stat.st_mtime_ns, 0),)

    signature_parts: list[tuple[str, int, int]] = []
    for file_path in markdown_files:
        file_stat = file_path.stat()
        signature_parts.append(
            (str(file_path), file_stat.st_mtime_ns, file_stat.st_size)
        )
    return tuple(signature_parts)


def _retrieve_clause_hits_bm25_only(
    *,
    clause: QueryClause,
    runtime_index: BadCaseRuntimeIndex,
    top_k: int,
    score_threshold: float,
) -> ClauseRetrievalResult:
    raw_hits = runtime_index.bm25_index.score(build_clause_only_query(clause))
    raw_scores = {hit.index: hit.score for hit in raw_hits}
    normalized_scores = _normalize_scores(raw_scores)

    pre_filter_hits: list[BadCaseRetrievalHit] = []
    for rank, hit in enumerate(raw_hits, start=1):
        if hit.index >= len(runtime_index.chunks):
            continue
        pre_filter_hits.append(
            BadCaseRetrievalHit(
                rank=rank,
                chunk=runtime_index.chunks[hit.index],
                score=normalized_scores.get(hit.index, 0.0),
                bm25_score=hit.score,
                vector_score=0.0,
                retrieval_mode=RETRIEVAL_MODE_BM25_ONLY,
            )
        )

    filtered_hits = [
        hit for hit in pre_filter_hits if hit.score > score_threshold
    ][:top_k]

    return ClauseRetrievalResult(
        clause=clause,
        pre_filter_hits=pre_filter_hits,
        filtered_hits=_rerank_hits(filtered_hits),
    )


def _retrieve_clause_hits_hybrid(
    *,
    clause: QueryClause,
    runtime_index: BadCaseRuntimeIndex,
    embedder: _EmbeddingClient,
    store: _QdrantStore,
    top_k: int,
    score_threshold: float,
) -> ClauseRetrievalResult:
    query = build_clause_only_query(clause)
    query_vector = embedder.embed_query(query)
    hybrid_hits = hybrid_search(
        query=query,
        chunks=runtime_index.chunks,
        bm25_index=runtime_index.bm25_index,
        query_vector=query_vector,
        store=store,
        top_k=max(len(runtime_index.chunks), top_k),
        vector_limit=DEFAULT_HYBRID_VECTOR_LIMIT,
    )

    pre_filter_hits = [
        BadCaseRetrievalHit(
            rank=hit.rank,
            chunk=hit.chunk,
            score=hit.hybrid_score,
            bm25_score=hit.bm25_score,
            vector_score=hit.vector_score,
            retrieval_mode=RETRIEVAL_MODE_HYBRID,
        )
        for hit in hybrid_hits
    ]
    filtered_hits = [
        hit for hit in pre_filter_hits if hit.score > score_threshold
    ][:top_k]

    return ClauseRetrievalResult(
        clause=clause,
        pre_filter_hits=pre_filter_hits,
        filtered_hits=_rerank_hits(filtered_hits),
    )


def _normalize_scores(scores: dict[int, float]) -> dict[int, float]:
    if not scores:
        return {}
    values = list(scores.values())
    low = min(values)
    high = max(values)
    if high <= low:
        return {key: 1.0 for key in scores}
    return {key: (value - low) / (high - low) for key, value in scores.items()}


def _rerank_hits(hits: list[BadCaseRetrievalHit]) -> list[BadCaseRetrievalHit]:
    return [replace(hit, rank=rank) for rank, hit in enumerate(hits, start=1)]


def _fallback_to_bm25_only(
    *,
    polished_text: str,
    directory: str | Path | None,
    top_k: int,
    score_threshold: float,
    warning: str,
) -> BadCaseRetrievalResult:
    result = retrieve_bad_case_hits_bm25_only(
        polished_text,
        directory=directory,
        top_k=top_k,
        score_threshold=score_threshold,
    )
    return replace(result, warnings=[*result.warnings, warning])


def _format_hybrid_warning(exc: Exception) -> str:
    message = str(exc).replace("\n", " ").strip()
    if len(message) > 300:
        message = f"{message[:300]}..."
    if not message:
        message = exc.__class__.__name__
    return f"hybrid retrieval unavailable; falling back to bm25_only: {message}"


def _create_embedding_client(config: RetrievalConfig) -> _EmbeddingClient:
    from backend.retrieval.embeddings import EmbeddingClient

    return EmbeddingClient(
        api_key=config.embedding_api_key,
        base_url=config.embedding_base_url,
        model=config.embedding_model,
        dimensions=config.embedding_dimensions,
    )


def _create_qdrant_store(config: RetrievalConfig) -> _QdrantStore:
    from backend.retrieval.qdrant_store import QdrantBadCaseStore

    return QdrantBadCaseStore(
        url=config.qdrant_url,
        collection_name=config.collection_name,
        api_key=config.qdrant_api_key,
    )
