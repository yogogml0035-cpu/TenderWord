from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from backend.retrieval.bad_case_loader import BadCaseChunk
from backend.retrieval.bm25 import BM25Index
from backend.retrieval.qdrant_store import QdrantBadCaseStore


@dataclass(frozen=True)
class HybridHit:
    rank: int
    chunk: BadCaseChunk
    hybrid_score: float
    bm25_score: float
    vector_score: float


def _normalize(scores: dict[int, float]) -> dict[int, float]:
    if not scores:
        return {}
    values = list(scores.values())
    low = min(values)
    high = max(values)
    if high <= low:
        return {key: 1.0 for key in scores}
    return {key: (value - low) / (high - low) for key, value in scores.items()}


def hybrid_search(
    *,
    query: str,
    chunks: Sequence[BadCaseChunk],
    bm25_index: BM25Index,
    query_vector: Sequence[float],
    store: QdrantBadCaseStore,
    top_k: int = 10,
    vector_limit: int = 50,
    bm25_weight: float = 0.6,
    vector_weight: float = 0.4,
) -> list[HybridHit]:
    bm25_hits = bm25_index.score(query)
    vector_hits = store.search(query_vector=query_vector, limit=vector_limit)

    raw_bm25 = {hit.index: hit.score for hit in bm25_hits}
    raw_vector = {hit.index: hit.score for hit in vector_hits}
    normalized_bm25 = _normalize(raw_bm25)
    normalized_vector = _normalize(raw_vector)
    candidate_indexes = set(raw_bm25) | set(raw_vector)

    ranked = []
    for index in candidate_indexes:
        hybrid_score = (
            bm25_weight * normalized_bm25.get(index, 0.0)
            + vector_weight * normalized_vector.get(index, 0.0)
        )
        ranked.append(
            HybridHit(
                rank=0,
                chunk=chunks[index],
                hybrid_score=hybrid_score,
                bm25_score=raw_bm25.get(index, 0.0),
                vector_score=raw_vector.get(index, 0.0),
            )
        )

    ranked.sort(key=lambda item: item.hybrid_score, reverse=True)
    return [
        HybridHit(
            rank=rank,
            chunk=hit.chunk,
            hybrid_score=hit.hybrid_score,
            bm25_score=hit.bm25_score,
            vector_score=hit.vector_score,
        )
        for rank, hit in enumerate(ranked[:top_k], start=1)
    ]
