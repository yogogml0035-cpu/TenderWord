from __future__ import annotations

from dataclasses import dataclass
import uuid
from typing import Any, Sequence

import httpx

from backend.retrieval.bad_case_loader import BadCaseChunk


QDRANT_NAMESPACE = uuid.UUID("2f7d7b5e-7e42-4f6c-9a2a-d23718811111")


@dataclass(frozen=True)
class VectorHit:
    index: int
    score: float
    payload: dict[str, Any]


class QdrantBadCaseStore:
    def __init__(
        self,
        *,
        url: str,
        collection_name: str,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.url = url.rstrip("/")
        self.collection_name = collection_name
        self.headers = {"api-key": api_key} if api_key else {}
        self.timeout = timeout

    def _client(self) -> httpx.Client:
        return httpx.Client(
            timeout=self.timeout,
            headers=self.headers,
            trust_env=False,
        )

    def healthcheck(self) -> None:
        with self._client() as client:
            response = client.get(f"{self.url}/")
            response.raise_for_status()

    def recreate_collection(self, *, vector_size: int) -> None:
        with self._client() as client:
            client.delete(f"{self.url}/collections/{self.collection_name}")
            response = client.put(
                f"{self.url}/collections/{self.collection_name}",
                json={"vectors": {"size": vector_size, "distance": "Cosine"}},
            )
            response.raise_for_status()

    def ensure_collection(self, *, vector_size: int) -> None:
        with self._client() as client:
            response = client.get(f"{self.url}/collections/{self.collection_name}")
            if response.status_code == 200:
                return
            if response.status_code != 404:
                response.raise_for_status()
            response = client.put(
                f"{self.url}/collections/{self.collection_name}",
                json={"vectors": {"size": vector_size, "distance": "Cosine"}},
            )
            response.raise_for_status()

    def upsert_chunks(
        self,
        *,
        chunks: Sequence[BadCaseChunk],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")

        points = []
        for index, (chunk, vector) in enumerate(zip(chunks, vectors)):
            payload = {
                **chunk.metadata,
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "chunk_index": index,
            }
            points.append(
                {
                    "id": str(uuid.uuid5(QDRANT_NAMESPACE, chunk.chunk_id)),
                    "vector": list(vector),
                    "payload": payload,
                }
            )

        with self._client() as client:
            for start in range(0, len(points), 64):
                response = client.put(
                    f"{self.url}/collections/{self.collection_name}/points",
                    params={"wait": "true"},
                    json={"points": points[start : start + 64]},
                )
                response.raise_for_status()

    def search(self, *, query_vector: Sequence[float], limit: int = 50) -> list[VectorHit]:
        with self._client() as client:
            response = client.post(
                f"{self.url}/collections/{self.collection_name}/points/search",
                json={
                    "vector": list(query_vector),
                    "limit": limit,
                    "with_payload": True,
                },
            )
            response.raise_for_status()
        result = response.json().get("result", [])
        hits: list[VectorHit] = []
        for item in result:
            payload = item.get("payload") or {}
            index = int(payload.get("chunk_index", -1))
            if index >= 0:
                hits.append(
                    VectorHit(
                        index=index,
                        score=float(item.get("score", 0.0)),
                        payload=payload,
                    )
                )
        return hits
