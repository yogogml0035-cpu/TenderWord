from __future__ import annotations

from collections.abc import Sequence
from typing import Optional

from openai import BadRequestError, OpenAI


class EmbeddingClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        dimensions: Optional[int] = None,
        batch_size: int = 10,
    ) -> None:
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = list(texts[start : start + self.batch_size])
            response = self._create_embeddings(batch)
            vectors.extend([list(item.embedding) for item in response.data])
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def _create_embeddings(self, texts: list[str]):
        kwargs = {"model": self.model, "input": texts}
        if self.dimensions:
            kwargs["dimensions"] = self.dimensions
        try:
            return self.client.embeddings.create(**kwargs)
        except BadRequestError:
            if "dimensions" not in kwargs:
                raise
            kwargs.pop("dimensions")
            return self.client.embeddings.create(**kwargs)
