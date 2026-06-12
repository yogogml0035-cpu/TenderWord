from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from openai import BadRequestError

import backend.retrieval.embeddings as embeddings_module
from backend.retrieval.embeddings import EmbeddingClient


def test_embed_query_retries_with_shorter_input_on_parameter_invalid(monkeypatch) -> None:
    fake_embeddings = _FakeEmbeddingsEndpoint(threshold=500, code=20015)

    monkeypatch.setattr(
        embeddings_module,
        "OpenAI",
        lambda **_kwargs: SimpleNamespace(embeddings=fake_embeddings),
    )

    client = EmbeddingClient(
        api_key="test-key",
        base_url="http://embedding.test/v1",
        model="test-model",
    )

    vector = client.embed_query("参数要求" * 150)

    assert fake_embeddings.calls == [600, 480]
    assert vector == [480.0, 1.0]


def test_embed_query_propagates_other_bad_request_errors(monkeypatch) -> None:
    fake_embeddings = _FakeEmbeddingsEndpoint(threshold=500, code=12345)

    monkeypatch.setattr(
        embeddings_module,
        "OpenAI",
        lambda **_kwargs: SimpleNamespace(embeddings=fake_embeddings),
    )

    client = EmbeddingClient(
        api_key="test-key",
        base_url="http://embedding.test/v1",
        model="test-model",
    )

    with pytest.raises(BadRequestError):
        client.embed_query("参数要求" * 150)

    assert fake_embeddings.calls == [600]


class _FakeEmbeddingsEndpoint:
    def __init__(self, *, threshold: int, code: int) -> None:
        self.threshold = threshold
        self.code = code
        self.calls: list[int] = []

    def create(self, **kwargs):
        text = str((kwargs.get("input") or [""])[0] or "")
        self.calls.append(len(text))
        if len(text) > self.threshold:
            raise _make_bad_request_error(self.code)
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=[float(len(text)), 1.0])]
        )


def _make_bad_request_error(code: int) -> BadRequestError:
    request = httpx.Request("POST", "https://embedding.test/v1/embeddings")
    response = httpx.Response(
        400,
        request=request,
        json={
            "code": code,
            "message": "The parameter is invalid. Please check again.",
            "data": None,
        },
    )
    return BadRequestError("bad request", response=response, body=response.json())
