from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from backend.retrieval.bad_case_loader import (
    DEFAULT_BAD_CASE_DIR,
    BadCaseChunk,
    BadCaseDirectoryLoadResult,
    load_bad_case_directory,
)
from backend.retrieval.bm25 import BM25Index


_DirectorySignature = tuple[tuple[str, int, int], ...]

CLAUSE_SPLIT_MODE_CLAUSE_ONLY = "clause_only"
CLAUSE_SPLIT_MODE_FALLBACK_FULL_TEXT = "fallback_full_text"

_PACKAGE_HEADING_RE = re.compile(r"^第\d+包：.*$")
_SECTION_HEADING_RE = re.compile(r"^[一二三四五六七八九十]+、.*$")
_NUMERIC_CLAUSE_RE = re.compile(r"^\d+、.*$")


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
