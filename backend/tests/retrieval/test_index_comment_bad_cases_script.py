from __future__ import annotations

from pathlib import Path

from backend.retrieval.config import RetrievalConfig
from backend.scripts import index_comment_bad_cases as script


def test_parse_args_defaults_to_main_file_and_local_qdrant() -> None:
    args = script.parse_args([])

    assert args.source == script.DEFAULT_COMMENT_BAD_CASE_FILE
    assert args.qdrant_url == "http://127.0.0.1:6333"
    assert args.collection is None
    assert args.recreate is False


def test_index_bad_case_source_ensures_collection_and_upserts_chunks(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "comment_bad_cases.md"
    source.write_text(_sample_bad_case_text(), encoding="utf-8")
    calls: dict[str, object] = {}

    def fake_load_retrieval_config(
        *,
        collection_name: str | None = None,
        qdrant_url: str | None = None,
    ) -> RetrievalConfig:
        calls["config_args"] = {
            "collection_name": collection_name,
            "qdrant_url": qdrant_url,
        }
        return RetrievalConfig(
            qdrant_url=qdrant_url or "http://127.0.0.1:6333",
            qdrant_api_key=None,
            collection_name=collection_name or "comment_bad_cases_test",
            embedding_base_url="http://embedding.test/v1",
            embedding_api_key="placeholder",
            embedding_model="test-embedding-model",
            embedding_dimensions=None,
        )

    class FakeEmbeddingClient:
        def __init__(self, **kwargs: object) -> None:
            calls["embedding_kwargs"] = kwargs

        def embed_texts(self, texts) -> list[list[float]]:
            calls["embedded_texts"] = list(texts)
            return [[0.1, 0.2, 0.3] for _ in texts]

    class FakeQdrantBadCaseStore:
        def __init__(self, **kwargs: object) -> None:
            calls["store_kwargs"] = kwargs

        def ensure_collection(self, *, vector_size: int) -> None:
            calls["ensure_collection"] = vector_size

        def recreate_collection(self, *, vector_size: int) -> None:
            calls["recreate_collection"] = vector_size

        def upsert_chunks(self, *, chunks, vectors) -> None:
            calls["upsert_chunk_ids"] = [chunk.chunk_id for chunk in chunks]
            calls["upsert_vectors"] = list(vectors)

    monkeypatch.setattr(script, "load_retrieval_config", fake_load_retrieval_config)
    monkeypatch.setattr(script, "EmbeddingClient", FakeEmbeddingClient)
    monkeypatch.setattr(script, "QdrantBadCaseStore", FakeQdrantBadCaseStore)

    summary = script.index_bad_case_source(
        source=source,
        qdrant_url="http://127.0.0.1:6333",
        collection_name="custom_collection",
    )

    assert summary.case_count == 1
    assert summary.chunk_count == len(calls["upsert_chunk_ids"])
    assert summary.vector_size == 3
    assert summary.collection_name == "custom_collection"
    assert summary.recreated is False
    assert calls["config_args"] == {
        "collection_name": "custom_collection",
        "qdrant_url": "http://127.0.0.1:6333",
    }
    assert calls["store_kwargs"] == {
        "url": "http://127.0.0.1:6333",
        "collection_name": "custom_collection",
        "api_key": None,
    }
    assert calls["ensure_collection"] == 3
    assert "recreate_collection" not in calls
    assert len(calls["embedded_texts"]) == summary.chunk_count
    assert len(calls["upsert_vectors"]) == summary.chunk_count


def test_index_bad_case_source_can_recreate_collection(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "comment_bad_cases.md"
    source.write_text(_sample_bad_case_text(), encoding="utf-8")
    calls: dict[str, object] = {}

    monkeypatch.setattr(
        script,
        "load_retrieval_config",
        lambda **_kwargs: RetrievalConfig(
            qdrant_url="http://127.0.0.1:6333",
            qdrant_api_key=None,
            collection_name="comment_bad_cases_test",
            embedding_base_url="http://embedding.test/v1",
            embedding_api_key="placeholder",
            embedding_model="test-embedding-model",
            embedding_dimensions=None,
        ),
    )

    class FakeEmbeddingClient:
        def __init__(self, **_kwargs: object) -> None:
            return None

        def embed_texts(self, texts) -> list[list[float]]:
            return [[0.1, 0.2] for _ in texts]

    class FakeQdrantBadCaseStore:
        def __init__(self, **_kwargs: object) -> None:
            return None

        def ensure_collection(self, *, vector_size: int) -> None:
            calls["ensure_collection"] = vector_size

        def recreate_collection(self, *, vector_size: int) -> None:
            calls["recreate_collection"] = vector_size

        def upsert_chunks(self, *, chunks, vectors) -> None:
            calls["upsert_count"] = len(chunks)
            calls["vector_count"] = len(vectors)

    monkeypatch.setattr(script, "EmbeddingClient", FakeEmbeddingClient)
    monkeypatch.setattr(script, "QdrantBadCaseStore", FakeQdrantBadCaseStore)

    summary = script.index_bad_case_source(source=source, recreate=True)

    assert summary.recreated is True
    assert calls["recreate_collection"] == 2
    assert "ensure_collection" not in calls
    assert calls["upsert_count"] == summary.chunk_count
    assert calls["vector_count"] == summary.chunk_count


def _sample_bad_case_text() -> str:
    return """
---BEGIN_BAD_CASE---
bad_case_id: TW_COMMENT_TEST_001
risk_layer: general_tender
risk_type: 参数指纹
risk_pattern: 唯一性参数组合
trigger_signals: 同时限定多个非必要参数
keywords_for_retrieval: 参数 指标 唯一
typical_source_pattern: ★设备参数须同时满足 A、B、C。
bad_case_core: 多个非必要参数组合可能形成排他性限制。
recommended_comment_policy: 建议提示参数组合必要性。
applicability_boundary: 仅适用于非核心指标组合。
anchor_policy: 锚定具体参数组合条款。
---END_BAD_CASE---
""".strip()
