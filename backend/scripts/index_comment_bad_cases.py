from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.retrieval.bad_case_loader import (  # noqa: E402
    DEFAULT_COMMENT_BAD_CASE_FILE,
    build_bad_case_chunks,
    load_bad_case_directory,
    load_bad_cases,
)
from backend.retrieval.config import RetrievalConfig, load_retrieval_config  # noqa: E402
from backend.retrieval.embeddings import EmbeddingClient  # noqa: E402
from backend.retrieval.qdrant_store import QdrantBadCaseStore  # noqa: E402


DEFAULT_QDRANT_URL = "http://127.0.0.1:6333"


@dataclass(frozen=True)
class IndexSummary:
    source_path: Path
    case_count: int
    chunk_count: int
    vector_size: int
    qdrant_url: str
    collection_name: str
    recreated: bool


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Index TenderWord comment bad cases into Qdrant."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_COMMENT_BAD_CASE_FILE,
        help=(
            "Bad-case source file or directory. Defaults to "
            "backend/retrieval/bad_cases/comment_bad_cases.md."
        ),
    )
    parser.add_argument(
        "--qdrant-url",
        default=DEFAULT_QDRANT_URL,
        help=f"Qdrant base URL. Defaults to {DEFAULT_QDRANT_URL}.",
    )
    parser.add_argument(
        "--collection",
        default=None,
        help=(
            "Qdrant collection name. Defaults to COMMENT_BAD_CASE_COLLECTION "
            "or tenderword_comment_bad_cases_demo."
        ),
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop and recreate the target collection before upserting points.",
    )
    return parser.parse_args(argv)


def index_bad_case_source(
    *,
    source: Path = DEFAULT_COMMENT_BAD_CASE_FILE,
    qdrant_url: str = DEFAULT_QDRANT_URL,
    collection_name: str | None = None,
    recreate: bool = False,
) -> IndexSummary:
    source_path = Path(source)
    if not source_path.exists():
        raise FileNotFoundError(f"bad case source not found: {source_path}")

    cases, chunks = _load_source(source_path)
    if not cases:
        raise RuntimeError(f"no bad cases parsed from source: {source_path}")
    if not chunks:
        raise RuntimeError(f"no bad case chunks built from source: {source_path}")

    config = load_retrieval_config(
        collection_name=collection_name,
        qdrant_url=qdrant_url,
    )
    embedder = _create_embedding_client(config)
    vectors = embedder.embed_texts([chunk.text for chunk in chunks])
    if not vectors or not vectors[0]:
        raise RuntimeError("embedding provider returned no vectors")

    vector_size = len(vectors[0])
    store = QdrantBadCaseStore(
        url=config.qdrant_url,
        collection_name=config.collection_name,
        api_key=config.qdrant_api_key,
    )
    if recreate:
        store.recreate_collection(vector_size=vector_size)
    else:
        store.ensure_collection(vector_size=vector_size)
    store.upsert_chunks(chunks=chunks, vectors=vectors)

    return IndexSummary(
        source_path=source_path,
        case_count=len(cases),
        chunk_count=len(chunks),
        vector_size=vector_size,
        qdrant_url=config.qdrant_url,
        collection_name=config.collection_name,
        recreated=recreate,
    )


def _load_source(source_path: Path):
    if source_path.is_dir():
        load_result = load_bad_case_directory(source_path)
        return load_result.cases, load_result.chunks
    cases = load_bad_cases(source_path)
    return cases, build_bad_case_chunks(cases)


def _create_embedding_client(config: RetrievalConfig) -> EmbeddingClient:
    return EmbeddingClient(
        api_key=config.embedding_api_key,
        base_url=config.embedding_base_url,
        model=config.embedding_model,
        dimensions=config.embedding_dimensions,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    summary = index_bad_case_source(
        source=args.source,
        qdrant_url=args.qdrant_url,
        collection_name=args.collection,
        recreate=args.recreate,
    )
    action = "recreated and indexed" if summary.recreated else "indexed"
    print(
        f"Bad cases {action}: source={summary.source_path} "
        f"cases={summary.case_count} chunks={summary.chunk_count} "
        f"vector_size={summary.vector_size} qdrant={summary.qdrant_url} "
        f"collection={summary.collection_name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
