from __future__ import annotations

from backend.retrieval.bad_case_loader import BadCaseChunk
from backend.retrieval.qdrant_store import QdrantBadCaseStore


def test_qdrant_store_disables_system_proxy_for_all_clients(monkeypatch) -> None:
    client_kwargs: list[dict[str, object]] = []

    class FakeResponse:
        def __init__(
            self,
            status_code: int = 200,
            payload: dict[str, object] | None = None,
        ) -> None:
            self.status_code = status_code
            self._payload = payload or {}

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise AssertionError(f"unexpected status {self.status_code}")

        def json(self) -> dict[str, object]:
            return self._payload

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            client_kwargs.append(kwargs)

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def get(self, url: str) -> FakeResponse:
            return FakeResponse()

        def delete(self, url: str) -> FakeResponse:
            return FakeResponse()

        def put(self, url: str, **kwargs: object) -> FakeResponse:
            return FakeResponse()

        def post(self, url: str, **kwargs: object) -> FakeResponse:
            return FakeResponse(
                payload={
                    "result": [
                        {
                            "score": 0.7,
                            "payload": {"chunk_index": 0},
                        }
                    ]
                }
            )

    monkeypatch.setattr("backend.retrieval.qdrant_store.httpx.Client", FakeClient)

    store = QdrantBadCaseStore(
        url="http://127.0.0.1:6333",
        collection_name="bad_cases",
        api_key="secret",
        timeout=2.5,
    )
    chunk = BadCaseChunk(
        chunk_id="chunk-1",
        case_id="case-1",
        title="title",
        field="field",
        text="text",
        metadata={},
    )

    store.healthcheck()
    store.recreate_collection(vector_size=1024)
    store.ensure_collection(vector_size=1024)
    store.upsert_chunks(chunks=[chunk], vectors=[[0.1]])
    hits = store.search(query_vector=[0.1], limit=1)

    assert hits[0].index == 0
    assert client_kwargs
    assert all(kwargs["trust_env"] is False for kwargs in client_kwargs)
    assert all(kwargs["timeout"] == 2.5 for kwargs in client_kwargs)
    assert all(kwargs["headers"] == {"api-key": "secret"} for kwargs in client_kwargs)
