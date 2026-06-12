from __future__ import annotations

from collections.abc import Sequence
from typing import Optional

from openai import BadRequestError, OpenAI


_EMBEDDING_RETRY_MIN_CHARS = 128
_EMBEDDING_RETRY_SHRINK_FACTOR = 0.8
_EMBEDDING_PARAMETER_INVALID_CODE = 20015


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
        return [self._embed_single_text(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_single_text(text)

    def _embed_single_text(self, text: str) -> list[float]:
        candidate = str(text or "")
        last_error: BadRequestError | None = None

        while True:
            try:
                response = self._create_embeddings([candidate])
                return list(response.data[0].embedding)
            except BadRequestError as exc:
                last_error = exc
                if not self._should_retry_with_shorter_input(exc, candidate):
                    raise
                next_candidate = self._shrink_embedding_text(candidate)
                if next_candidate == candidate:
                    break
                candidate = next_candidate

        if last_error is not None:
            raise last_error
        raise RuntimeError("embedding retry loop exhausted")

    def _create_embeddings(self, texts: list[str]):
        kwargs = {"model": self.model, "input": texts}
        if self.dimensions:
            kwargs["dimensions"] = self.dimensions
        try:
            return self.client.embeddings.create(**kwargs)
        except BadRequestError as exc:
            if "dimensions" not in kwargs:
                raise
            kwargs.pop("dimensions")
            return self.client.embeddings.create(**kwargs)

    def _should_retry_with_shorter_input(
        self,
        exc: BadRequestError,
        _text: str,
    ) -> bool:
        if getattr(exc, "status_code", None) != 400:
            return False
        body = getattr(exc, "body", None)
        if isinstance(body, dict) and body.get("code") == _EMBEDDING_PARAMETER_INVALID_CODE:
            return True
        message = str(exc).lower()
        return "parameter is invalid" in message and "20015" in message

    def _shrink_embedding_text(self, text: str) -> str:
        candidate = str(text or "")
        if len(candidate) <= 1:
            return candidate
        next_length = int(len(candidate) * _EMBEDDING_RETRY_SHRINK_FACTOR)
        next_length = max(_EMBEDDING_RETRY_MIN_CHARS, next_length)
        next_length = min(len(candidate) - 1, next_length)
        return candidate[:next_length]
