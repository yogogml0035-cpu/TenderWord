from __future__ import annotations

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
